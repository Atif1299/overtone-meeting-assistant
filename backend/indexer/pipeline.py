"""Presentation indexing orchestrator — provided metadata + Claude Vision fallback pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from indexer import converter as converter_mod
from indexer import manifest as manifest_mod
from indexer import metadata_enricher as metadata_enricher_mod
from indexer import search_indexer as search_indexer_mod
from services.azure_search import AzureSearchClient
from services.blob_storage import AzureBlobStorageClient
from services import storage as storage_mod
from config import get_settings, Settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def run_index_job(presentation_id: str) -> None:
    """
    Full indexing pipeline:
      1. Get source file (local or download from blob)
      2. Convert to per-page PNGs (LibreOffice + pdftoppm)
      3a. Use provided_metadata.json if present and valid
      3b. Fallback: Claude Vision extraction per page + document metadata generation
      4. Upload to Azure AI Search (vectors + keyword)
      5. Save manifest.json
      6. Update presentation status
    """
    settings = get_settings()
    presentation_meta = storage_mod.get_presentation_meta(presentation_id) or {}

    source = storage_mod.source_file_path(presentation_id)
    if not source:
        source = await _download_source_blob(presentation_id, presentation_meta, settings)
    if not source:
        storage_mod.update_presentation_meta(
            presentation_id,
            status="failed",
            index_error="Missing presentation source file",
            indexed_pages=0,
            total_pages=0,
        )
        return

    storage_mod.update_presentation_meta(
        presentation_id,
        status="indexing",
        index_error=None,
        indexed_pages=0,
    )

    # Upload source to blob (best-effort)
    blob_storage = AzureBlobStorageClient(settings)
    if blob_storage.enabled:
        try:
            source_bytes = await asyncio.to_thread(source.read_bytes)
            source_blob_name = f"{presentation_id}/source/{source.name}"
            source_blob = await blob_storage.upload_bytes(
                blob_name=source_blob_name,
                payload=source_bytes,
                content_type=_guess_content_type(source),
            )
            if source_blob:
                storage_mod.update_presentation_meta(
                    presentation_id,
                    source_blob_name=source_blob.blob_name,
                    source_blob_url=source_blob.blob_url,
                )
        except Exception:
            pass

    # 1. Convert to images for the UI
    try:
        conversion = await converter_mod.convert_to_page_images(str(source), presentation_id)
        page_images = conversion["page_images"]  # list[str] of file paths

        # Best effort upload to blob for frontend display
        blob_urls = {}
        if blob_storage.enabled:
            for idx, img_path in enumerate(page_images, start=1):
                try:
                    img_bytes = await asyncio.to_thread(Path(img_path).read_bytes)
                    blob_name = f"{presentation_id}/images/page_{idx}.png"
                    blob = await blob_storage.upload_bytes(
                        blob_name=blob_name,
                        payload=img_bytes,
                        content_type="image/png",
                    )
                    if blob:
                        blob_urls[idx] = {"name": blob.blob_name, "url": blob.blob_url}
                except Exception:
                    pass
    except Exception as exc:
        logger.warning(f"Image conversion failed: {exc}")
        blob_urls = {}
        page_images = []

    # 2. Build page metadata: try provided_metadata.json first, fall back to Claude Vision
    user_metadata = storage_mod.load_provided_metadata(presentation_id)
    has_provided = bool(user_metadata and user_metadata.get("pages"))

    if has_provided:
        logger.info("[%s] Using provided metadata (%d pages)", presentation_id, len(user_metadata["pages"]))
        page_metadata_list, metadata_provider, metadata_model = (
            _build_metadata_from_provided(user_metadata, blob_urls),
            "customer",
            "provided",
        )
        if not page_metadata_list:
            storage_mod.update_presentation_meta(
                presentation_id,
                status="failed",
                index_error="No valid pages extracted from provided metadata",
                indexed_pages=0,
                total_pages=0,
            )
            return
    else:
        # Claude Vision fallback
        logger.info("[%s] No provided metadata — falling back to Claude Vision extraction", presentation_id)
        if not page_images:
            storage_mod.update_presentation_meta(
                presentation_id,
                status="failed",
                index_error="No provided metadata and no slide images available for Vision extraction",
                indexed_pages=0,
                total_pages=0,
            )
            return

        if not settings.anthropic_api_key:
            storage_mod.update_presentation_meta(
                presentation_id,
                status="failed",
                index_error="No provided metadata and ANTHROPIC_API_KEY is not configured for Vision fallback",
                indexed_pages=0,
                total_pages=0,
            )
            return

        try:
            page_metadata_list, metadata_provider, metadata_model = await _run_vision_extraction(
                presentation_id=presentation_id,
                page_images=page_images,
                blob_urls=blob_urls,
                source=source,
                settings=settings,
            )
        except Exception as exc:
            logger.exception("[%s] Claude Vision extraction failed: %s", presentation_id, exc)
            storage_mod.update_presentation_meta(
                presentation_id,
                status="failed",
                index_error=f"Claude Vision extraction failed: {exc}",
                indexed_pages=0,
                total_pages=0,
            )
            return

    total_pages = len(page_metadata_list)

    # Save pages + chunks locally for RAG keyword fallback
    _save_local_index(presentation_id, page_metadata_list)

    # Upload to Azure AI Search
    azure_chunks = 0
    azure = AzureSearchClient(settings)
    if azure.enabled:
        try:
            azure_chunks = await _upload_to_search(
                page_metadata_list=page_metadata_list,
                presentation_id=presentation_id,
                settings=settings,
            )
        except Exception as exc:
            _save_local_index(presentation_id, [])  # clear partial state
            storage_mod.update_presentation_meta(
                presentation_id,
                status="failed",
                index_error=f"Azure Search indexing failed: {exc}",
                indexed_pages=total_pages,
                total_pages=total_pages,
            )
            return

    # Save manifest
    _save_manifest(presentation_id, presentation_meta.get("filename", source.name), page_metadata_list)

    # Update presentation status
    storage_mod.update_presentation_meta(
        presentation_id,
        status="ready",
        indexed_pages=total_pages,
        total_pages=total_pages,
        index_error=None,
        document_id=presentation_id,
        azure_indexed_chunks=azure_chunks,
        metadata_provider=metadata_provider,
        metadata_model=metadata_model,
    )

    # NEW: Index meeting briefs if present
    brief_paths = presentation_meta.get("brief_file_paths", [])
    if brief_paths:
        try:
            logger.info("[%s] Indexing %d brief files", presentation_id, len(brief_paths))
            await search_indexer_mod.index_meeting_briefs(
                presentation_id=presentation_id,
                brief_file_paths=brief_paths,
                settings=settings
            )
        except Exception as exc:
            logger.error("[%s] Briefing indexing failed (non-fatal): %s", presentation_id, exc)


def _build_page_metadata_entry(p_data: dict, blob_urls: dict) -> dict | None:
    """Convert a single page dict (from provided or Vision metadata) into pipeline format."""
    page_num = p_data.get("page_number")
    if page_num is None:
        return None

    title = p_data.get("title") or f"Page {page_num}"
    description = p_data.get("description") or ""
    content_text = p_data.get("content") or p_data.get("content_text") or description or ""

    # Build searchable_content if not already present
    searchable_content = p_data.get("searchable_content") or ""
    if not searchable_content:
        data_points = p_data.get("data_points")
        data_points_str = ""
        if isinstance(data_points, dict):
            def _dp_val(v):
                return v.get("value", "") if isinstance(v, dict) else str(v)
            data_points_str = "\n".join(f"{k}: {_dp_val(v)}" for k, v in data_points.items())
        speaker_notes = p_data.get("speaker_notes") or ""
        searchable_content = f"{title}\n{description}\n{content_text}\n{speaker_notes}\n{data_points_str}".strip()

    img_info = blob_urls.get(int(page_num), {})

    return {
        "page_number": int(page_num),
        "title": str(title),
        "section_label": str(p_data.get("section_label") or p_data.get("tag") or "Content"),
        "description": str(description),
        "content_text": str(content_text),
        "searchable_content": str(searchable_content),
        "full_metadata_json": json.dumps(p_data),
        "has_table": bool(p_data.get("has_table") or p_data.get("table_data")),
        "has_chart": bool(p_data.get("has_chart") or p_data.get("visuals")),
        "has_diagram": bool(p_data.get("has_diagram") or p_data.get("diagram_description")),
        "questions_answered": p_data.get("questions_answered") or [],
        "image_blob_name": img_info.get("name"),
        "image_blob_url": img_info.get("url"),
        "content_type": "content",
    }


def _build_metadata_from_provided(user_metadata: dict, blob_urls: dict) -> list[dict]:
    """Convert provided_metadata.json pages into pipeline page_metadata_list."""
    result = []
    for p_data in user_metadata.get("pages", []):
        entry = _build_page_metadata_entry(p_data, blob_urls)
        if entry is not None:
            result.append(entry)
    return result


async def _run_vision_extraction(
    *,
    presentation_id: str,
    page_images: list[str],
    blob_urls: dict,
    source: Path,
    settings: Settings,
) -> tuple[list[dict], str, str]:
    """Run Claude Vision extraction and return (page_metadata_list, provider, model)."""
    import anthropic

    vision_model = settings.indexer_llm_model or settings.anthropic_model or metadata_enricher_mod.CLAUDE_MODEL
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        raw_pages = await metadata_enricher_mod.extract_all_pages(
            page_images=page_images,
            filename=source.name,
            client=client,
            model=vision_model,
        )

        # Generate document-level metadata from extracted pages
        doc_meta = {}
        try:
            doc_meta = await metadata_enricher_mod.extract_document_metadata(
                page_metadatas=raw_pages,
                total_pages=len(raw_pages),
                client=client,
                model=vision_model,
            )
        except Exception as exc:
            logger.warning("[%s] Document metadata generation failed (non-fatal): %s", presentation_id, exc)

        # Save generated metadata as provided_metadata.json so other services can use it
        full_metadata = {
            **doc_meta,
            "total_pages": len(raw_pages),
            "pages": raw_pages,
        }
        try:
            dest_dir = storage_mod.presentations_root() / presentation_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / "provided_metadata.json").write_text(json.dumps(full_metadata, indent=2))
            logger.info("[%s] Saved Vision-generated metadata to provided_metadata.json", presentation_id)
        except Exception as exc:
            logger.warning("[%s] Failed to save Vision metadata to disk: %s", presentation_id, exc)

        page_metadata_list = []
        for p_data in raw_pages:
            entry = _build_page_metadata_entry(p_data, blob_urls)
            if entry is not None:
                page_metadata_list.append(entry)

        return page_metadata_list, "vision", vision_model
    finally:
        await client.close()


async def _upload_to_search(
    *,
    page_metadata_list: list[dict[str, Any]],
    presentation_id: str,
    settings: Settings,
) -> int:
    """Generate embeddings and upload to Azure AI Search."""
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_embedding(text: str) -> list[float]:
        resp = await openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=text or " ",
        )
        return resp.data[0].embedding

    try:
        await search_indexer_mod.ensure_index_exists(
            settings.azure_search_endpoint,
            settings.azure_search_key,
        )
        await search_indexer_mod.delete_document_chunks(
            presentation_id,
            settings.azure_search_endpoint,
            settings.azure_search_key,
        )
        docs = await search_indexer_mod.prepare_documents(
            page_metadata_list=page_metadata_list,
            presentation_id=presentation_id,
            generate_embedding=generate_embedding,
        )
        return await search_indexer_mod.upload_documents(
            docs,
            settings.azure_search_endpoint,
            settings.azure_search_key,
        )
    finally:
        await openai_client.close()


def _save_local_index(
    presentation_id: str,
    page_metadata_list: list[dict[str, Any]],
) -> None:
    """Persist pages + chunk rows locally for the keyword RAG fallback."""
    enriched_pages = []
    chunk_rows = []

    for meta in page_metadata_list:
        page_num = int(meta.get("page_number") or 1)
        searchable_content = str(meta.get("searchable_content") or meta.get("content_text") or "")
        enriched_pages.append({
            "page_number": page_num,
            "title": meta.get("title", f"Page {page_num}"),
            "searchable_content": searchable_content,
            "content_text": meta.get("content_text", ""),
            "description": meta.get("description", ""),
            "section_label": meta.get("section_label", "Content"),
            "content_type": meta.get("content_type", "content"),
            "has_table": meta.get("has_table", False),
            "has_chart": meta.get("has_chart", False),
            "has_diagram": meta.get("has_diagram", False),
            "full_metadata_json": meta.get("full_metadata_json", ""),
            "document_id": presentation_id,
        })
        chunk_rows.append({
            "page_number": page_num,
            "chunk_number": 1,
            "title": meta.get("title", f"Page {page_num}"),
            "content_text": searchable_content,
            "full_metadata_json": meta.get("full_metadata_json", ""),
            "chunk_kind": "section",
            "chunk_level": "child",
            "parent_chunk_id": f"{presentation_id}_p{page_num}",
            "parent_content_text": searchable_content,
            "section_heading": meta.get("section_label"),
            "document_id": presentation_id,
        })

    storage_mod.save_index_pages(presentation_id, enriched_pages)
    storage_mod.save_chunk_rows(presentation_id, chunk_rows)


def _save_manifest(
    presentation_id: str,
    filename: str,
    page_metadata_list: list[dict[str, Any]],
) -> None:
    manifest = manifest_mod.build_manifest(presentation_id, filename, page_metadata_list)
    manifest_mod.save_manifest(presentation_id, manifest)


async def _download_source_blob(
    presentation_id: str,
    presentation_meta: dict[str, Any],
    settings: Settings,
) -> Path | None:
    """Download source file from Azure Blob to a temp file."""
    blob_name = str(presentation_meta.get("source_blob_name") or "").strip()
    filename = str(presentation_meta.get("filename") or "source.bin").strip() or "source.bin"
    if not blob_name:
        filename_only = Path(filename).name
        if filename_only:
            blob_name = f"{presentation_id}/source/{filename_only}"
    if not blob_name:
        return None
    blob_storage = AzureBlobStorageClient(settings)
    if not blob_storage.enabled:
        return None
    try:
        data = await blob_storage.download_bytes(blob_name=blob_name)
        if not data:
            return None
        tmp = Path(tempfile.mkdtemp()) / Path(filename).name
        tmp.write_bytes(data)
        return tmp
    except Exception as exc:
        logger.warning("Failed to download source blob %s: %s", blob_name, exc)
        return None


def _guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
    }.get(ext, "application/octet-stream")
