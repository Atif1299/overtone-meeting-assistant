"""Azure AI Search index management and vector document upload for the vision pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from config import Settings
from services import brief_utils
from services import embeddings

logger = logging.getLogger(__name__)

AZURE_API_VERSION = "2023-11-01"
INDEX_NAME = "overtone"

INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "searchable": False, "filterable": True, "sortable": True, "retrievable": True},
        {"name": "document_id", "type": "Edm.String", "searchable": False, "filterable": True, "sortable": True, "retrievable": True},
        {"name": "page_id", "type": "Edm.String", "searchable": False, "filterable": True, "sortable": True, "retrievable": True},
        {"name": "page_number", "type": "Edm.Int32", "searchable": False, "filterable": True, "sortable": True, "facetable": True, "retrievable": True},
        {"name": "chunk_number", "type": "Edm.Int32", "searchable": False, "filterable": True, "sortable": True, "retrievable": True},
        {"name": "title", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "section_label", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True, "retrievable": True},
        {"name": "description", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "content_text", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "parent_content_text", "type": "Edm.String", "searchable": False, "filterable": False, "retrievable": True},
        {"name": "searchable_content", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "table_data", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "chart_description", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "diagram_description", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "key_topics", "type": "Collection(Edm.String)", "searchable": True, "filterable": True, "retrievable": True},
        {"name": "entities", "type": "Collection(Edm.String)", "searchable": True, "filterable": True, "retrievable": True},
        {"name": "content_type", "type": "Edm.String", "searchable": False, "filterable": True, "facetable": True, "retrievable": True},
        {"name": "has_table", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True},
        {"name": "has_chart", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True},
        {"name": "has_diagram", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True},
        {"name": "image_url", "type": "Edm.String", "searchable": False, "filterable": False, "retrievable": True},
        {"name": "questions_answered", "type": "Collection(Edm.String)", "searchable": True, "filterable": False, "retrievable": True},
        {"name": "full_metadata_json", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True},
        {
            "name": "content_vector",
            "type": "Collection(Edm.Single)",
            "dimensions": 3072,
            "vectorSearchProfile": "overtone-vector-profile",
            "searchable": True,
            "retrievable": False,
        },
        {
            "name": "title_vector",
            "type": "Collection(Edm.Single)",
            "dimensions": 3072,
            "vectorSearchProfile": "overtone-vector-profile",
            "searchable": True,
            "retrievable": False,
        },
        {
            "name": "questions_vector",
            "type": "Collection(Edm.Single)",
            "dimensions": 3072,
            "vectorSearchProfile": "overtone-vector-profile",
            "searchable": True,
            "retrievable": False,
        },
    ],
    "vectorSearch": {
        "algorithms": [
            {
                "name": "overtone-hnsw",
                "kind": "hnsw",
                "hnswParameters": {"m": 4, "efConstruction": 400, "efSearch": 500, "metric": "cosine"},
            }
        ],
        "profiles": [{"name": "overtone-vector-profile", "algorithm": "overtone-hnsw"}],
    },
    "semantic": {
        "configurations": [
            {
                "name": "overtone-semantic-config",
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [
                        {"fieldName": "searchable_content"},
                        {"fieldName": "description"},
                        {"fieldName": "content_text"},
                    ],
                },
            }
        ]
    },
}

REQUIRED_FIELD_NAMES = {f["name"] for f in INDEX_SCHEMA["fields"]}


def _index_url(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}/indexes/{INDEX_NAME}"


def _headers(api_key: str) -> dict[str, str]:
    return {"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}


async def ensure_index_exists(endpoint: str, api_key: str) -> None:
    """Create or recreate the overtone index with the full vision schema."""
    url = _index_url(endpoint)
    hdrs = _headers(api_key)

    async with httpx.AsyncClient(timeout=30.0) as client:
        current = await client.get(f"{url}?api-version={AZURE_API_VERSION}", headers=hdrs)
        if current.status_code == 200:
            existing_fields = {f["name"] for f in current.json().get("fields", [])}
            if REQUIRED_FIELD_NAMES.issubset(existing_fields):
                return  # Schema is compatible — skip recreation
            # Drop and recreate
            drop = await client.delete(f"{url}?api-version={AZURE_API_VERSION}", headers=hdrs)
            if drop.status_code not in (204, 404):
                drop.raise_for_status()
        elif current.status_code != 404:
            current.raise_for_status()

        create = await client.put(
            f"{url}?api-version={AZURE_API_VERSION}&allowIndexDowntime=true",
            headers=hdrs,
            json=INDEX_SCHEMA,
        )
        create.raise_for_status()
        logger.info("Azure Search index '%s' created/recreated", INDEX_NAME)


async def delete_document_chunks(document_id: str, endpoint: str, api_key: str) -> None:
    """Delete all existing chunks for a document_id before re-indexing."""
    escaped = document_id.replace("'", "''")
    url = _index_url(endpoint)
    hdrs = _headers(api_key)

    async with httpx.AsyncClient(timeout=30.0) as client:
        search_resp = await client.post(
            f"{url}/docs/search?api-version={AZURE_API_VERSION}",
            headers=hdrs,
            json={"search": "*", "filter": f"document_id eq '{escaped}'", "select": "id", "top": 1000},
        )
        search_resp.raise_for_status()
        ids = [r["id"] for r in search_resp.json().get("value", []) if r.get("id")]
        if not ids:
            return

        delete_resp = await client.post(
            f"{url}/docs/index?api-version={AZURE_API_VERSION}",
            headers=hdrs,
            json={"value": [{"@search.action": "delete", "id": rid} for rid in ids]},
        )
        delete_resp.raise_for_status()
        logger.info("Deleted %d existing chunks for document_id=%s", len(ids), document_id)


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
    """Build Azure Search documents with embeddings for all pages."""
    docs = []
    for metadata in page_metadata_list:
        searchable_content = str(metadata.get("searchable_content") or metadata.get("content_text") or "")
        title_text = f"{metadata.get('title', '')} — {metadata.get('section_label', '')}"

        # Build questions text for embedding (Layer 3: Q&A pairs)
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def upload_documents(
    docs: list[dict[str, Any]],
    endpoint: str,
    api_key: str,
    batch_size: int = 100,
) -> int:
    """Batch-upload documents to Azure AI Search. Returns total uploaded count."""
    if not docs:
        return 0
    url = _index_url(endpoint)
    hdrs = _headers(api_key)
    uploaded = 0

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            payload = {"value": [{"@search.action": "upload", **doc} for doc in batch]}
            resp = await client.post(
                f"{url}/docs/index?api-version={AZURE_API_VERSION}",
                headers=hdrs,
                json=payload,
            )
            resp.raise_for_status()
            results = resp.json().get("value", [])
            failed = [r for r in results if not r.get("status", False)]
            if failed:
                # Log the first few errors for debugging
                error_details = []
                for r in failed[:3]:
                    error_details.append(f"Key={r.get('key')} Error={r.get('errorMessage')} Code={r.get('statusCode')}")
                
                error_msg = f"Azure Search indexing failed for {len(failed)} document(s). Samples: {'; '.join(error_details)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            uploaded += len(results)
            logger.info("Uploaded batch %d-%d (%d docs)", i, i + len(batch), len(batch))

    return uploaded

async def index_meeting_briefs(
    presentation_id: str,
    brief_file_paths: list[str],
    settings: Settings,
) -> int:
    """Parse, chunk, embed and upload meeting briefs to Azure AI Search."""
    if not brief_file_paths:
        return 0

    # 1. Clean up existing brief chunks for this document
    # (Optional, but good for fresh re-indexing)
    # We use a filter like content_type='brief' AND document_id=presentation_id
    # But delete_document_chunks deletes EVERYTHING for the doc.
    # If we want to keep slides, we should be careful.
    # Since we are likely indexing a new bot or re-indexing, let's just add.
    
    # 2. Parse and chunk
    sections = brief_utils.load_and_dedupe_brief_sections(brief_file_paths)
    chunks = brief_utils.convert_sections_to_chunks(sections)
    if not chunks:
        return 0

    # 3. Preparation
    docs = []
    for i, chunk in enumerate(chunks):
        content = chunk["content_text"]
        section = chunk["section"]
        # Use a unique safe ID
        safe_section = "".join(c if c.isalnum() else "_" for c in section)
        chunk_id = f"brief_{presentation_id}_{safe_section}_{i}"
        
        # Build embeddings in parallel for speed
        vectors = await asyncio.gather(
            embeddings.generate_embedding(content, settings),
            embeddings.generate_embedding(section, settings),
        )
        content_vector = vectors[0] or ([0.0] * 3072)
        title_vector = vectors[1] or ([0.0] * 3072)
        
        doc = {
            "id": chunk_id,
            "document_id": presentation_id,
            "page_id": f"brief_{section}",
            "page_number": 0, # Conventional marker for non-slide content
            "chunk_number": i,
            "title": f"Brief: {section}",
            "section_label": section,
            "content_text": content,
            "searchable_content": content,
            "content_type": "brief",
            "content_vector": content_vector,
            "title_vector": title_vector,
            # Fill missing required fields with defaults to avoid schema errors
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
        docs.append(doc)

    # 4. Upload
    count = await upload_documents(
        docs, 
        settings.azure_search_endpoint, 
        settings.azure_search_key
    )
    logger.info("Indexed %d brief chunks for presentation_id=%s", count, presentation_id)
    return count
