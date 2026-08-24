from __future__ import annotations

import logging

from app.config import effective_indexer_provider, get_settings
from app.db import SessionLocal
from app.indexing.converter import convert_to_page_images
from app.indexing.embeddings import generate_embedding
from app.indexing.vector_store import upsert_pages
from app.indexing.vision import extract_all_pages, is_stub_page
from app.storage import PresentationStore

logger = logging.getLogger("overtone.v2.indexing")


def _normalize_page(raw: dict) -> dict | None:
    n = raw.get("page_number")
    if n is None:
        return None
    searchable = raw.get("searchable_content")
    if not searchable:
        parts = [
            raw.get("title") or "",
            raw.get("description") or "",
            raw.get("content") or "",
            raw.get("speaker_notes") or "",
            "\n".join(raw.get("data_points") or []),
        ]
        searchable = "\n".join(p for p in parts if p).strip()
    out = dict(raw)
    out["page_number"] = int(n)
    out["searchable_content"] = searchable
    out.setdefault("section_label", raw.get("tag") or "Content")
    return out


async def run_index_job(presentation_id: str) -> None:
    db = SessionLocal()
    store = PresentationStore(db)
    try:
        meta = store.get(presentation_id)
        if not meta:
            return
        source = store.source_path(presentation_id)
        if not source:
            store.update(presentation_id, status="failed", index_error="Missing source file")
            return

        store.update(presentation_id, status="indexing", index_error=None)
        page_images = await convert_to_page_images(source, presentation_id)
        for i, path in enumerate(page_images, start=1):
            store.save_page_image(presentation_id, i, path)

        if not page_images:
            store.update(presentation_id, status="failed", index_error="No page images produced")
            return

        provider = effective_indexer_provider()
        settings = get_settings()
        if provider == "openai" and not settings.openai_api_key:
            store.update(presentation_id, status="failed", index_error="OPENAI_API_KEY required for indexing")
            return
        if provider == "gemini" and not settings.gemini_api_key:
            store.update(presentation_id, status="failed", index_error="GEMINI_API_KEY required for indexing")
            return

        raw_pages = await extract_all_pages(
            page_images=page_images, filename=meta.filename, provider=provider
        )
        pages = [p for p in (_normalize_page(r) for r in raw_pages) if p]
        stub_count = sum(1 for p in pages if is_stub_page(p))
        if pages and stub_count / len(pages) > 0.5:
            store.update(
                presentation_id,
                status="failed",
                index_error=f"Index quality gate failed: {stub_count}/{len(pages)} stub pages",
                total_pages=len(pages),
                indexed_pages=0,
            )
            return

        chunks = [
            {
                "id": f"{presentation_id}_p{p['page_number']}_c1",
                "page_number": p["page_number"],
                "searchable_content": p["searchable_content"],
                "title": p.get("title"),
            }
            for p in pages
        ]
        store.save_index(presentation_id, pages, chunks)

        indexed = 0
        try:
            indexed = await upsert_pages(presentation_id, pages, generate_embedding)
        except Exception as exc:  # noqa: BLE001
            logger.exception("pgvector upsert failed; continuing with local index: %s", exc)

        store.update(
            presentation_id,
            status="ready",
            total_pages=len(pages),
            indexed_pages=len(pages),
            indexed_chunks=indexed or len(pages),
            metadata_provider=provider,
            metadata_model=(
                settings.gemini_vision_model if provider == "gemini" else settings.indexer_llm_model
            ),
            index_error=None if indexed else "pgvector upsert skipped/failed; local keyword index active",
        )
        logger.info("indexed %s pages=%s chunks=%s", presentation_id, len(pages), indexed)
    except Exception as exc:  # noqa: BLE001
        logger.exception("index failed %s", presentation_id)
        store.update(presentation_id, status="failed", index_error=str(exc))
    finally:
        db.close()
