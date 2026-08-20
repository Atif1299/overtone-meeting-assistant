"""pgvector search client — query-time RAG on Cloud SQL.

Index creation and document upload are handled by indexer/search_indexer.py.
This client is used at query time by orchestrator/rag_retriever.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import text

from config import Settings

logger = logging.getLogger(__name__)

_CONTENT_TYPE_RE = re.compile(r"content_type\s+eq\s+'([^']+)'", re.IGNORECASE)


def _is_postgres(settings: Settings) -> bool:
    return "postgres" in (settings.database_url or "").lower()


def _parse_content_type(filter: str | None) -> str | None:
    if not filter:
        return None
    match = _CONTENT_TYPE_RE.search(filter)
    return match.group(1) if match else None


def _row_to_hit(row: Any) -> dict[str, Any]:
    mapping = dict(row._mapping)
    score = mapping.pop("score", 0.0)
    mapping["@search.score"] = float(score or 0.0)
    for key in ("key_topics", "entities", "questions_answered"):
        raw = mapping.get(key)
        if isinstance(raw, str):
            try:
                mapping[key] = json.loads(raw)
            except json.JSONDecodeError:
                mapping[key] = []
    return mapping


class AzureSearchClient:
    """Presentation chunk search backed by pgvector when DATABASE_URL is Postgres."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return _is_postgres(self._settings)

    async def filtered_search(
        self,
        *,
        query: str,
        document_id: str,
        filter: str | None = None,
        top: int = 5,
    ) -> list[dict[str, Any]]:
        """Keyword search fallback (used when embeddings are unavailable)."""
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._query_sync,
            query,
            document_id,
            None,
            _parse_content_type(filter),
            top,
        )

    async def filtered_search_v2(
        self,
        *,
        query: str,
        document_id: str,
        query_vector: list[float],
        filter: str | None = None,
        top: int = 5,
    ) -> list[dict[str, Any]]:
        """Hybrid search: cosine similarity plus optional keyword match."""
        if not self.enabled:
            return []
        return await asyncio.to_thread(
            self._query_sync,
            query,
            document_id,
            query_vector,
            _parse_content_type(filter),
            top,
        )

    def _query_sync(
        self,
        query: str,
        document_id: str,
        query_vector: list[float] | None,
        content_type: str | None,
        top: int,
    ) -> list[dict[str, Any]]:
        from database import SessionLocal

        where = ["document_id = :document_id"]
        params: dict[str, Any] = {"document_id": document_id, "top": top}
        if content_type:
            where.append("content_type = :content_type")
            params["content_type"] = content_type

        pattern = f"%{(query or '').strip()}%"
        if query_vector:
            vec = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
            params["qvec"] = vec
            score_sql = """
                GREATEST(
                    1 - (content_vector <=> CAST(:qvec AS vector)),
                    1 - (title_vector <=> CAST(:qvec AS vector)),
                    COALESCE(1 - (questions_vector <=> CAST(:qvec AS vector)), 0)
                )
            """
            if (query or "").strip():
                params["pattern"] = pattern
                score_sql = f"""
                    ({score_sql})
                    + CASE WHEN (
                        searchable_content ILIKE :pattern
                        OR title ILIKE :pattern
                        OR content_text ILIKE :pattern
                    ) THEN 0.15 ELSE 0 END
                """
        else:
            params["pattern"] = pattern
            score_sql = """
                CASE WHEN (
                    searchable_content ILIKE :pattern
                    OR title ILIKE :pattern
                    OR content_text ILIKE :pattern
                    OR COALESCE(entities, '') ILIKE :pattern
                ) THEN 1.0 ELSE 0.1 END
            """

        sql = text(
            f"""
            SELECT
                id, document_id, page_id, page_number, chunk_number,
                title, section_label, description, content_text,
                parent_content_text, searchable_content, table_data,
                chart_description, diagram_description, key_topics, entities,
                content_type, has_table, has_chart, has_diagram, image_url,
                questions_answered, full_metadata_json,
                ({score_sql}) AS score
            FROM presentation_chunks
            WHERE {' AND '.join(where)}
            ORDER BY score DESC
            LIMIT :top
            """
        )
        db = SessionLocal()
        try:
            rows = db.execute(sql, params).fetchall()
            return [_row_to_hit(row) for row in rows]
        except Exception:
            logger.exception("pgvector search failed")
            raise
        finally:
            db.close()
