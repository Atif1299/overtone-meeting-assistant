"""Azure AI Search client — search queries only.

Index creation and document upload are handled by indexer/search_indexer.py.
This client is used at query time by orchestrator/rag_retriever.py.
"""

from __future__ import annotations

from typing import Any

import httpx

from config import Settings

API_VERSION = "2023-11-01"


class AzureSearchClient:
    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.azure_search_endpoint.rstrip("/")
        self._index_name = settings.azure_search_index_name.strip()
        self._api_key = settings.azure_search_key.strip()

    @property
    def enabled(self) -> bool:
        return bool(self._endpoint and self._index_name and self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _index_url(self) -> str:
        return f"{self._endpoint}/indexes/{self._index_name}"

    async def filtered_search(
        self,
        *,
        query: str,
        document_id: str,
        filter: str | None = None,
        top: int = 5,
    ) -> list[dict[str, Any]]:
        """Keyword-only search fallback (used when embeddings are unavailable)."""
        if not self.enabled:
            return []

        escaped_id = document_id.replace("'", "''")
        
        # Combine base document_id filter with any extra filter provided
        base_filter = f"document_id eq '{escaped_id}'"
        final_filter = f"({base_filter}) and ({filter})" if filter else base_filter

        payload = {
            "search": query or "*",
            "filter": final_filter,
            "top": top,
            "queryType": "simple",
            "searchMode": "any",
            "select": (
                "id,document_id,page_id,page_number,chunk_number,"
                "title,section_label,description,content_text,"
                "searchable_content,table_data,chart_description,"
                "diagram_description,key_topics,entities,"
                "content_type,has_table,has_chart,has_diagram,image_url,"
                "questions_answered,full_metadata_json"
            ),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._index_url()}/docs/search?api-version={API_VERSION}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("value", [])

    async def filtered_search_v2(
        self,
        *,
        query: str,
        document_id: str,
        query_vector: list[float],
        filter: str | None = None,
        top: int = 5,
    ) -> list[dict[str, Any]]:
        """Hybrid search: keyword + vector (no semantic reranker — too slow for live voice)."""
        if not self.enabled:
            return []

        from indexer.search_indexer import INDEX_NAME, AZURE_API_VERSION

        index_url = f"{self._endpoint}/indexes/{INDEX_NAME}"
        escaped_id = document_id.replace("'", "''")
        
        # Combine base document_id filter with any extra filter provided
        base_filter = f"document_id eq '{escaped_id}'"
        final_filter = f"({base_filter}) and ({filter})" if filter else base_filter

        payload: dict[str, Any] = {
            "search": query or "*",
            "filter": final_filter,
            "top": top,
            "queryType": "simple",
            "select": (
                "id,document_id,page_id,page_number,chunk_number,"
                "title,section_label,description,content_text,"
                "searchable_content,table_data,chart_description,"
                "diagram_description,key_topics,entities,"
                "content_type,has_table,has_chart,has_diagram,image_url,"
                "questions_answered,full_metadata_json"
            ),
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_vector,
                    "k": top * 2,
                    "fields": "content_vector,title_vector,questions_vector",
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{index_url}/docs/search?api-version={AZURE_API_VERSION}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("value", [])
