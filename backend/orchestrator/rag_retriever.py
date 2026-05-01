from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from config import Settings, get_settings
from services.azure_search import AzureSearchClient
from services import storage as storage_mod
from services import brief_utils
from services import embeddings

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "of", "on", "or", "that",
    "the", "this", "to", "was", "what", "which", "who", "why",
    "with", "you", "your",
}

EMPTY_TEXT_MARKER = "no text extracted for page"





async def search_presentation(
    query: str,
    presentation_id: str,
    settings: Settings | None = None,
) -> list[dict]:
    t_search_start = time.monotonic()
    settings = settings or get_settings()
    terms = _tokenize(query)
    azure = AzureSearchClient(settings)

    if azure.enabled:
        try:
            query_vector = await embeddings.generate_embedding(query, settings)
            t_azure_start = time.monotonic()
            if query_vector:
                azure_hits = await azure.filtered_search_v2(
                    query=query,
                    document_id=presentation_id,
                    query_vector=query_vector,
                    filter="content_type eq 'content'",
                    top=5,
                )
            else:
                # Fall back to keyword-only if embeddings unavailable
                azure_hits = await azure.filtered_search(
                    query=query,
                    document_id=presentation_id,
                    filter="content_type eq 'content'",
                    top=12,
                )
            azure_ms = (time.monotonic() - t_azure_start) * 1000
            normalized_hits = _rank_hits(azure_hits, terms=terms, query=query)
            logger.info(
                "⏱ RAG azure_ms=%.1f raw_hits=%d ranked_hits=%d total_rag_ms=%.1f",
                azure_ms, len(azure_hits), len(normalized_hits),
                (time.monotonic() - t_search_start) * 1000,
            )
            if normalized_hits:
                return normalized_hits
        except Exception:
            logger.warning(
                "⏱ RAG azure FAILED after_ms=%.1f", (time.monotonic() - t_search_start) * 1000
            )

    # Local keyword fallback
    chunk_rows = storage_mod.load_chunk_rows(presentation_id)
    if not chunk_rows:
        pages = storage_mod.load_index_pages(presentation_id)
        chunk_rows = _chunks_from_pages(pages)
    if not chunk_rows:
        return []

    results = _rank_hits(chunk_rows, terms=terms, query=query)
    logger.info(
        "⏱ RAG local_fallback hits=%d total_rag_ms=%.1f",
        len(results), (time.monotonic() - t_search_start) * 1000,
    )
    return results


async def get_total_pages(presentation_id: str) -> int:
    p = storage_mod.get_presentation(presentation_id)
    if p and p.total_pages:
        return p.total_pages
    pages = storage_mod.load_index_pages(presentation_id)
    if pages:
        return len(pages)
    return 20


def _rank_hits(rows: list[dict[str, Any]], *, terms: list[str], query: str) -> list[dict]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        content = _clean_text(str(row.get("content_text") or row.get("searchable_content") or ""))
        parent = _clean_text(str(row.get("parent_content_text") or ""))
        if not content:
            continue
        if _is_empty_extraction(content):
            continue
        azure_score = float(row.get("@search.score") or row.get("@search.reranker_score") or 0.0)
        # If Azure already ranked this hit (via vector/hybrid search), trust it — don't
        # filter by keyword overlap. Keyword filter only applies to local fallback results.
        if azure_score == 0.0 and terms and not _has_term_overlap(content=content, parent=parent, terms=terms):
            continue
        score = _score_text(content=content, parent=parent, terms=terms, query=query)
        score += azure_score

        # --- Layer 1: Title and section label boost ---
        # Slides whose title or section matches query terms are almost certainly
        # the right target (e.g. "pricing" → slide titled "Pricing").
        title = (row.get("title") or "").lower()
        section = (row.get("section_label") or "").lower()
        for term in terms:
            if term in title:
                score += 4.0   # strong signal — title is the slide's identity
            if term in section:
                # If it's a BRIEFING hit (page_number=0), section_label is the JSON key.
                # A keyword match here is extremely high intent.
                boost = 10.0 if row.get("page_number") == 0 else 2.0
                score += boost

                # NEW: Hierarchy Boost for Briefings
                # Favor top-level summaries (fewer ' > ' separators)
                if row.get("page_number") == 0:
                    levels = section.count(" > ")
                    # Level 0 (global) gets +5.0, Level 1 gets +3.0, Level 2+ gets 0.0
                    h_boost = max(0, 5.0 - (levels * 2.0))
                    score += h_boost

        if score <= 0:
            continue
        scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    seen_parents: set[str] = set()
    results: list[dict[str, Any]] = []
    for score, hit in scored:
        parent_chunk_id = str(
            hit.get("parent_chunk_id")
            or hit.get("page_id")
            or f"page_{int(hit.get('page_number') or 1)}"
        )
        if parent_chunk_id in seen_parents:
            continue
        seen_parents.add(parent_chunk_id)
        raw_pn = hit.get("page_number")
        page_number = int(raw_pn) if raw_pn is not None else 1
        content = _clean_text(str(hit.get("content_text") or hit.get("searchable_content") or ""))
        parent_content = _clean_text(str(hit.get("parent_content_text") or ""))
        results.append(
            {
                "page_number": page_number,
                "title": hit.get("title") or f"Page {page_number}",
                "searchable_content": content,
                "parent_content_text": parent_content,
                # Enriched fields from vision index
                "section_label": hit.get("section_label"),
                "content_type": hit.get("content_type"),
                "has_table": hit.get("has_table", False),
                "has_chart": hit.get("has_chart", False),
                "has_diagram": hit.get("has_diagram", False),
                "page_id": hit.get("page_id") or hit.get("parent_chunk_id"),
                "document_id": hit.get("document_id"),
                "chunk_level": hit.get("chunk_level") or "child",
                "chunk_kind": hit.get("chunk_kind") or "section",
                "section_heading": hit.get("section_heading"),
                "score": score,
                "parent_chunk_id": parent_chunk_id,
                "full_metadata_json": hit.get("full_metadata_json"),
            }
        )
        if len(results) >= 5:
            break

    return results


def _chunks_from_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in pages:
        page_number = int(page.get("page_number") or 1)
        parent_content = _clean_text(str(page.get("searchable_content") or page.get("content_text") or ""))
        if not parent_content:
            continue
        sections = page.get("sections")
        if isinstance(sections, list) and sections:
            chunk_number = 0
            for section in sections:
                if not isinstance(section, dict):
                    continue
                section_content = _clean_text(str(section.get("content") or ""))
                if not section_content:
                    continue
                chunk_number += 1
                rows.append(
                    {
                        "page_number": page_number,
                        "chunk_number": chunk_number,
                        "title": page.get("title") or f"Page {page_number}",
                        "chunk_level": "child",
                        "content_text": section_content,
                        "chunk_kind": "section",
                        "section_heading": section.get("heading"),
                        "parent_chunk_id": f"page_{page_number}",
                        "parent_content_text": parent_content,
                        "section_label": page.get("section_label"),
                        "content_type": page.get("content_type"),
                        "has_table": page.get("has_table", False),
                        "has_chart": page.get("has_chart", False),
                        "has_diagram": page.get("has_diagram", False),
                        "full_metadata_json": page.get("full_metadata_json"),
                    }
                )
            continue
        rows.append(
            {
                "page_number": page_number,
                "chunk_number": 1,
                "title": page.get("title") or f"Page {page_number}",
                "chunk_level": "child",
                "content_text": parent_content,
                "chunk_kind": "paragraph",
                "section_heading": None,
                "parent_chunk_id": f"page_{page_number}",
                "parent_content_text": parent_content,
                "section_label": page.get("section_label"),
                "content_type": page.get("content_type"),
                "has_table": page.get("has_table", False),
                "has_chart": page.get("has_chart", False),
                "has_diagram": page.get("has_diagram", False),
                "full_metadata_json": page.get("full_metadata_json"),
            }
        )
    return rows


def _tokenize(value: str) -> list[str]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(t) > 2]
    return [t for t in tokens if t not in STOPWORDS]


def _is_empty_extraction(content: str) -> bool:
    return EMPTY_TEXT_MARKER in (content or "").lower()


def _has_term_overlap(*, content: str, parent: str, terms: list[str]) -> bool:
    if not terms:
        return True
    normalized = f"{content} {parent}".lower()
    return any(term in normalized for term in terms)


def _score_text(*, content: str, parent: str, terms: list[str], query: str) -> float:
    normalized = content.lower()
    parent_normalized = parent.lower()
    score = 0.0
    for term in terms:
        child_occurrences = normalized.count(term)
        parent_occurrences = parent_normalized.count(term)
        if child_occurrences:
            score += min(child_occurrences, 6) * 1.5
        elif parent_occurrences:
            score += min(parent_occurrences, 4) * 0.8
    if query and query.lower() in normalized:
        score += 5.0
    return score


import json

async def search_meeting_briefs(
    query: str,
    brief_file_paths: list[str],
    settings: Settings | None = None,
    presentation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search across uploaded meeting brief JSON files using Azure if possible, else local."""
    if not brief_file_paths:
        return []

    settings = settings or get_settings()
    azure = AzureSearchClient(settings)
    
    if azure.enabled and presentation_id:
        try:
            query_vector = await embeddings.generate_embedding(query, settings)
            t_azure_start = time.monotonic()
            logger.info("RAG Searching briefs query=%r pid=%s filter=%r", query, presentation_id, f"content_type eq 'brief'")
            # Hybrid search with filter for content_type='brief'
            azure_hits = await azure.filtered_search_v2(
                query=query,
                document_id=presentation_id,
                query_vector=query_vector,
                filter=f"content_type eq 'brief'",
                top=10,
            )
            if azure_hits:
                logger.info(
                    "⏱ RAG brief_azure success ms=%.1f hits=%d top_raw_score=%.4f", 
                    (time.monotonic() - t_azure_start)*1000, 
                    len(azure_hits),
                    azure_hits[0].get("@search.score", 0.0)
                )
                
                # Apply custom ranking and boost logic (same as slides)
                terms = _tokenize(query)
                ranked = _rank_hits(azure_hits, terms=terms, query=query)
                
                return [
                    {
                        "section": hit.get("section_label") or "Brief",
                        "content_text": hit.get("searchable_content") or "",
                        "score": hit.get("score") or 0.0,
                        "type": "brief"
                    } for hit in ranked
                ]
        except Exception as e:
            logger.warning("⏱ RAG brief_azure FAILED, falling back to local: %s", e)

    # Local fallback
    t0 = time.monotonic()
    sections = brief_utils.load_and_dedupe_brief_sections(brief_file_paths)
    chunks = brief_utils.convert_sections_to_chunks(sections)
    
    terms = _tokenize(query)
    results = _rank_brief_hits(chunks, terms=terms, query=query)
    
    logger.info(
        "⏱ RAG search_briefs_local ms=%.1f query=%r hits=%d",
        (time.monotonic() - t0) * 1000, query[:60], len(results)
    )
    return results


def _rank_brief_hits(chunks: list[dict[str, Any]], terms: list[str], query: str) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        content = chunk["content_text"]
        score = _score_text(content=content, parent="", terms=terms, query=query)
        
        # Boost if the section name itself matches query terms
        section_name = chunk["section"].lower()
        for term in terms:
            if term in section_name:
                score += 3.0
        
        if score > 0:
            scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, chunk in scored[:5]:
        results.append({
            "section": chunk["section"],
            "content_text": chunk["content_text"],
            "score": score,
            "type": "brief"
        })
    return results


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
