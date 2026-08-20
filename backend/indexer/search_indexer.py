"""pgvector index management and vector document upload for the vision pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from services import brief_utils
from services import embeddings

logger = logging.getLogger(__name__)

INDEX_NAME = "overtone"

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS presentation_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page_id TEXT,
    page_number INTEGER,
    chunk_number INTEGER,
    title TEXT,
    section_label TEXT,
    description TEXT,
    content_text TEXT,
    parent_content_text TEXT,
    searchable_content TEXT,
    table_data TEXT,
    chart_description TEXT,
    diagram_description TEXT,
    key_topics TEXT,
    entities TEXT,
    content_type TEXT,
    has_table BOOLEAN,
    has_chart BOOLEAN,
    has_diagram BOOLEAN,
    image_url TEXT,
    questions_answered TEXT,
    full_metadata_json TEXT,
    content_vector vector(3072),
    title_vector vector(3072),
    questions_vector vector(3072)
);

CREATE INDEX IF NOT EXISTS idx_presentation_chunks_document_id
    ON presentation_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_presentation_chunks_content_type
    ON presentation_chunks (content_type);
"""


def _db_session():
    from database import SessionLocal

    return SessionLocal()


def _json_list(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(list(value or []))


def _vec(values: list[float] | None) -> str | None:
    if not values:
        return None
    return "[" + ",".join(str(float(x)) for x in values) + "]"


async def ensure_index_exists(*_args: Any, **_kwargs: Any) -> None:
    """Create the presentation_chunks table and vector extension on Postgres."""
    await asyncio.to_thread(_ensure_index_exists_sync)


def _ensure_index_exists_sync() -> None:
    db = _db_session()
    try:
        for statement in CREATE_TABLE_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                db.execute(text(stmt))
        db.commit()
        try:
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_chunks_content_hnsw "
                    "ON presentation_chunks USING hnsw (content_vector vector_cosine_ops)"
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Skipping HNSW index on content_vector: %s", exc)
        logger.info("pgvector presentation_chunks table is ready")
    finally:
        db.close()


async def delete_document_chunks(document_id: str, *_args: Any, **_kwargs: Any) -> None:
    """Delete all existing chunks for a document_id before re-indexing."""
    await asyncio.to_thread(_delete_document_chunks_sync, document_id)


def _delete_document_chunks_sync(document_id: str) -> None:
    db = _db_session()
    try:
        result = db.execute(
            text("DELETE FROM presentation_chunks WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        db.commit()
        logger.info("Deleted %s existing chunks for document_id=%s", result.rowcount, document_id)
    finally:
        db.close()


def _build_chunk_document(
    *,
    metadata: dict[str, Any],
    presentation_id: str,
    content_vector: list[float],
    title_vector: list[float],
    questions_vector: list[float] | None = None,
) -> dict[str, Any]:
    page_num = int(metadata.get("page_number") or 1)
    chunk_num = 1  # One chunk per page
    page_id = f"{presentation_id}_p{page_num}"
    chunk_id = f"{presentation_id}_p{page_num}_c{chunk_num}"
    searchable_content = str(metadata.get("searchable_content") or metadata.get("content_text") or "")

    doc: dict[str, Any] = {
        "id": chunk_id,
        "document_id": presentation_id,
        "page_id": page_id,
        "page_number": page_num,
        "chunk_number": chunk_num,
        "title": str(metadata.get("title") or f"Page {page_num}"),
        "section_label": str(metadata.get("section_label") or "Content"),
        "description": str(metadata.get("description") or ""),
        "content_text": str(metadata.get("content_text") or ""),
        "parent_content_text": searchable_content,
        "searchable_content": searchable_content,
        "table_data": str(metadata.get("table_data") or "") or None,
        "chart_description": str(metadata.get("chart_description") or "") or None,
        "diagram_description": str(metadata.get("diagram_description") or "") or None,
        "key_topics": list(metadata.get("key_topics") or []),
        "entities": list(metadata.get("entities") or []),
        "content_type": str(metadata.get("content_type") or "content"),
        "has_table": bool(metadata.get("has_table", False)),
        "has_chart": bool(metadata.get("has_chart", False)),
        "has_diagram": bool(metadata.get("has_diagram", False)),
        "image_url": f"/api/slides/{presentation_id}/page_{page_num}.png",
        "questions_answered": list(metadata.get("questions_answered") or []),
        "full_metadata_json": str(metadata.get("full_metadata_json") or ""),
        "content_vector": content_vector,
        "title_vector": title_vector,
    }
    if questions_vector:
        doc["questions_vector"] = questions_vector
    return doc


async def prepare_documents(
    *,
    page_metadata_list: list[dict[str, Any]],
    presentation_id: str,
    generate_embedding: Callable[[str], Awaitable[list[float]]],
) -> list[dict[str, Any]]:
    """Build search documents with embeddings for all pages."""
    docs = []
    for metadata in page_metadata_list:
        searchable_content = str(metadata.get("searchable_content") or metadata.get("content_text") or "")
        title_text = f"{metadata.get('title', '')} — {metadata.get('section_label', '')}"

        questions_list = list(metadata.get("questions_answered") or [])
        questions_text = " ".join(questions_list) if questions_list else ""

        embedding_tasks = [
            generate_embedding(searchable_content),
            generate_embedding(title_text),
        ]
        if questions_text:
            embedding_tasks.append(generate_embedding(questions_text))

        vectors = await asyncio.gather(*embedding_tasks)
        content_vector = vectors[0]
        title_vector = vectors[1]
        questions_vector = vectors[2] if len(vectors) > 2 else None

        doc = _build_chunk_document(
            metadata=metadata,
            presentation_id=presentation_id,
            content_vector=content_vector,
            title_vector=title_vector,
            questions_vector=questions_vector,
        )
        docs.append(doc)
    return docs


UPSERT_SQL = text(
    """
    INSERT INTO presentation_chunks (
        id, document_id, page_id, page_number, chunk_number,
        title, section_label, description, content_text, parent_content_text,
        searchable_content, table_data, chart_description, diagram_description,
        key_topics, entities, content_type, has_table, has_chart, has_diagram,
        image_url, questions_answered, full_metadata_json,
        content_vector, title_vector, questions_vector
    ) VALUES (
        :id, :document_id, :page_id, :page_number, :chunk_number,
        :title, :section_label, :description, :content_text, :parent_content_text,
        :searchable_content, :table_data, :chart_description, :diagram_description,
        :key_topics, :entities, :content_type, :has_table, :has_chart, :has_diagram,
        :image_url, :questions_answered, :full_metadata_json,
        CAST(:content_vector AS vector), CAST(:title_vector AS vector), CAST(:questions_vector AS vector)
    )
    ON CONFLICT (id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        page_id = EXCLUDED.page_id,
        page_number = EXCLUDED.page_number,
        chunk_number = EXCLUDED.chunk_number,
        title = EXCLUDED.title,
        section_label = EXCLUDED.section_label,
        description = EXCLUDED.description,
        content_text = EXCLUDED.content_text,
        parent_content_text = EXCLUDED.parent_content_text,
        searchable_content = EXCLUDED.searchable_content,
        table_data = EXCLUDED.table_data,
        chart_description = EXCLUDED.chart_description,
        diagram_description = EXCLUDED.diagram_description,
        key_topics = EXCLUDED.key_topics,
        entities = EXCLUDED.entities,
        content_type = EXCLUDED.content_type,
        has_table = EXCLUDED.has_table,
        has_chart = EXCLUDED.has_chart,
        has_diagram = EXCLUDED.has_diagram,
        image_url = EXCLUDED.image_url,
        questions_answered = EXCLUDED.questions_answered,
        full_metadata_json = EXCLUDED.full_metadata_json,
        content_vector = EXCLUDED.content_vector,
        title_vector = EXCLUDED.title_vector,
        questions_vector = EXCLUDED.questions_vector
    """
)


def _doc_params(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["id"],
        "document_id": doc["document_id"],
        "page_id": doc.get("page_id"),
        "page_number": doc.get("page_number"),
        "chunk_number": doc.get("chunk_number"),
        "title": doc.get("title"),
        "section_label": doc.get("section_label"),
        "description": doc.get("description"),
        "content_text": doc.get("content_text"),
        "parent_content_text": doc.get("parent_content_text"),
        "searchable_content": doc.get("searchable_content"),
        "table_data": doc.get("table_data"),
        "chart_description": doc.get("chart_description"),
        "diagram_description": doc.get("diagram_description"),
        "key_topics": _json_list(doc.get("key_topics")),
        "entities": _json_list(doc.get("entities")),
        "content_type": doc.get("content_type") or "content",
        "has_table": bool(doc.get("has_table", False)),
        "has_chart": bool(doc.get("has_chart", False)),
        "has_diagram": bool(doc.get("has_diagram", False)),
        "image_url": doc.get("image_url"),
        "questions_answered": _json_list(doc.get("questions_answered")),
        "full_metadata_json": doc.get("full_metadata_json") or "",
        "content_vector": _vec(doc.get("content_vector")),
        "title_vector": _vec(doc.get("title_vector")),
        "questions_vector": _vec(doc.get("questions_vector")),
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def upload_documents(
    docs: list[dict[str, Any]],
    *_args: Any,
    batch_size: int = 100,
    **_kwargs: Any,
) -> int:
    """Batch-upload documents to pgvector. Returns total uploaded count."""
    if not docs:
        return 0
    return await asyncio.to_thread(_upload_documents_sync, docs, batch_size)


def _upload_documents_sync(docs: list[dict[str, Any]], batch_size: int) -> int:
    db = _db_session()
    uploaded = 0
    try:
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            for doc in batch:
                db.execute(UPSERT_SQL, _doc_params(doc))
            db.commit()
            uploaded += len(batch)
            logger.info("Uploaded batch %d-%d (%d docs)", i, i + len(batch), len(batch))
        return uploaded
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def index_meeting_briefs(
    presentation_id: str,
    brief_file_paths: list[str],
    settings: Settings,
) -> int:
    """Parse, chunk, embed and upload meeting briefs to pgvector."""
    if not brief_file_paths:
        return 0

    sections = brief_utils.load_and_dedupe_brief_sections(brief_file_paths)
    chunks = brief_utils.convert_sections_to_chunks(sections)
    if not chunks:
        return 0

    docs = []
    for i, chunk in enumerate(chunks):
        content = chunk["content_text"]
        section = chunk["section"]
        safe_section = "".join(c if c.isalnum() else "_" for c in section)
        chunk_id = f"brief_{presentation_id}_{safe_section}_{i}"

        vectors = await asyncio.gather(
            embeddings.generate_embedding(content, settings),
            embeddings.generate_embedding(section, settings),
        )
        content_vector = vectors[0] or ([0.0] * 3072)
        title_vector = vectors[1] or ([0.0] * 3072)

        docs.append(
            {
                "id": chunk_id,
                "document_id": presentation_id,
                "page_id": f"brief_{section}",
                "page_number": 0,
                "chunk_number": i,
                "title": f"Brief: {section}",
                "section_label": section,
                "content_text": content,
                "searchable_content": content,
                "content_type": "brief",
                "content_vector": content_vector,
                "title_vector": title_vector,
                "description": "",
                "parent_content_text": content,
                "has_table": False,
                "has_chart": False,
                "has_diagram": False,
                "entities": [],
                "key_topics": [],
                "questions_answered": [],
                "full_metadata_json": "{}",
            }
        )

    await ensure_index_exists()
    count = await upload_documents(docs)
    logger.info("Indexed %d brief chunks for presentation_id=%s", count, presentation_id)
    return count
