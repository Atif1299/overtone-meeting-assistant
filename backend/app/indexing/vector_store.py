from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

from sqlalchemy import text

from app.config import get_settings
from app.db import engine, is_postgres


def ensure_chunks_table() -> None:
    if not is_postgres():
        return
    # Keep extension bootstrap separate so a permission warning cannot
    # roll back table creation (vector usually already exists on this DB).
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS v2_presentation_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_id TEXT,
                    page_number INT,
                    chunk_number INT DEFAULT 1,
                    title TEXT,
                    section_label TEXT,
                    description TEXT,
                    content TEXT,
                    searchable_content TEXT,
                    image_url TEXT,
                    full_metadata_json TEXT,
                    content_vector vector(3072),
                    title_vector vector(3072)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS v2_chunks_document_id_idx "
                "ON v2_presentation_chunks (document_id)"
            )
        )
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS v2_chunks_content_hnsw "
                    "ON v2_presentation_chunks USING hnsw (content_vector vector_cosine_ops)"
                )
            )
    except Exception:
        pass


def ensure_chunks_table_safe() -> None:
    """Best-effort bootstrap used at startup; never crash the API."""
    try:
        ensure_chunks_table()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("overtone.v2.db").exception("ensure_chunks_table failed: %s", exc)


def delete_document_chunks(document_id: str) -> None:
    if not is_postgres():
        return
    ensure_chunks_table()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM v2_presentation_chunks WHERE document_id = :d"),
            {"d": document_id},
        )


async def upsert_pages(
    presentation_id: str,
    pages: list[dict],
    generate_embedding: Callable[[str], Awaitable[list[float] | None]],
) -> int:
    if not is_postgres():
        return 0
    ensure_chunks_table()
    delete_document_chunks(presentation_id)
    count = 0
    with engine.begin() as conn:
        for page in pages:
            n = int(page.get("page_number") or 0)
            searchable = page.get("searchable_content") or _searchable(page)
            emb = await generate_embedding(searchable or " ")
            title_emb = await generate_embedding(f"{page.get('title') or ''} — {page.get('section_label') or ''}")
            chunk_id = f"{presentation_id}_p{n}_c1"
            page_id = f"{presentation_id}_p{n}"
            vec = _vec_literal(emb)
            tvec = _vec_literal(title_emb)
            conn.execute(
                text(
                    """
                    INSERT INTO v2_presentation_chunks (
                        id, document_id, page_id, page_number, chunk_number,
                        title, section_label, description, content, searchable_content,
                        image_url, full_metadata_json, content_vector, title_vector
                    ) VALUES (
                        :id, :document_id, :page_id, :page_number, 1,
                        :title, :section_label, :description, :content, :searchable_content,
                        :image_url, :full_metadata_json,
                        CAST(:content_vector AS vector), CAST(:title_vector AS vector)
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        searchable_content = EXCLUDED.searchable_content,
                        content = EXCLUDED.content,
                        content_vector = EXCLUDED.content_vector,
                        title_vector = EXCLUDED.title_vector,
                        full_metadata_json = EXCLUDED.full_metadata_json
                    """
                ),
                {
                    "id": chunk_id,
                    "document_id": presentation_id,
                    "page_id": page_id,
                    "page_number": n,
                    "title": page.get("title") or "",
                    "section_label": page.get("section_label") or "",
                    "description": page.get("description") or "",
                    "content": page.get("content") or "",
                    "searchable_content": searchable,
                    "image_url": f"/api/v1/presentations/{presentation_id}/pages/{n}/image",
                    "full_metadata_json": json.dumps(page),
                    "content_vector": vec,
                    "title_vector": tvec,
                },
            )
            count += 1
    return count


async def hybrid_search(
    presentation_id: str,
    query: str,
    generate_embedding: Callable[[str], Awaitable[list[float] | None]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """pgvector hybrid search, or local keyword fallback."""
    if is_postgres():
        emb = await generate_embedding(query)
        if emb:
            vec = _vec_literal(emb)
            with engine.begin() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT page_number, title, searchable_content, content, full_metadata_json,
                               GREATEST(
                                 1 - (content_vector <=> CAST(:q AS vector)),
                                 1 - (title_vector <=> CAST(:q AS vector))
                               ) AS score
                        FROM v2_presentation_chunks
                        WHERE document_id = :d
                        ORDER BY score DESC
                        LIMIT :k
                        """
                    ),
                    {"q": vec, "d": presentation_id, "k": top_k},
                ).mappings().all()
            return [dict(r) for r in rows]

    # local keyword fallback from caller-provided index is handled in tools
    return []


def _searchable(page: dict) -> str:
    parts = [
        page.get("title") or "",
        page.get("description") or "",
        page.get("content") or "",
        page.get("speaker_notes") or "",
        "\n".join(page.get("data_points") or []),
    ]
    return "\n".join(p for p in parts if p).strip()


def _vec_literal(emb: list[float] | None) -> str:
    if not emb:
        # zero vector placeholder
        return "[" + ",".join(["0"] * 3072) + "]"
    return "[" + ",".join(str(float(x)) for x in emb) + "]"
