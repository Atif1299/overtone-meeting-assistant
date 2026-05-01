from __future__ import annotations

import asyncio

from config import get_settings
from orchestrator import rag_retriever
from services import storage as storage_mod


def _with_local_retrieval():
    settings = get_settings()
    previous = (
        settings.azure_search_endpoint,
        settings.azure_search_key,
        settings.azure_search_index_name,
    )
    settings.azure_search_endpoint = ""
    settings.azure_search_key = ""
    settings.azure_search_index_name = ""
    return settings, previous


def _restore_azure_settings(previous: tuple[str, str, str]) -> None:
    settings = get_settings()
    settings.azure_search_endpoint = previous[0]
    settings.azure_search_key = previous[1]
    settings.azure_search_index_name = previous[2]


def test_rag_search_ignores_empty_extraction_pages() -> None:
    uploaded = storage_mod.save_upload("deck.pdf", b"%PDF-1.4 fake content")
    storage_mod.save_chunk_rows(
        uploaded.presentation_id,
        [
            {
                "page_number": 1,
                "chunk_number": 1,
                "title": "Page 1",
                "content_text": "No text extracted for page 1.",
                "chunk_kind": "section",
                "parent_chunk_id": "p1",
                "parent_content_text": "No text extracted for page 1.",
            },
            {
                "page_number": 2,
                "chunk_number": 1,
                "title": "Latency",
                "content_text": "The first audio latency metric is 240 milliseconds.",
                "chunk_kind": "section",
                "parent_chunk_id": "p2",
                "parent_content_text": "The first audio latency metric is 240 milliseconds.",
            },
        ],
    )
    storage_mod.update_presentation_meta(
        uploaded.presentation_id,
        status="ready",
        total_pages=2,
        indexed_pages=2,
        pages_without_text=1,
    )

    settings, previous = _with_local_retrieval()
    try:
        hits = asyncio.run(
            rag_retriever.search_presentation(
                "what is the latency metric",
                uploaded.presentation_id,
                settings,
            )
        )
    finally:
        _restore_azure_settings(previous)

    assert hits
    assert hits[0]["page_number"] == 2
    assert "latency metric" in hits[0]["searchable_content"].lower()
    assert all(
        "no text extracted for page" not in str(hit.get("searchable_content", "")).lower()
        for hit in hits
    )


def test_rag_returns_empty_when_only_non_extractable_pages_exist() -> None:
    uploaded = storage_mod.save_upload("deck.pdf", b"%PDF-1.4 fake content")
    storage_mod.save_chunk_rows(
        uploaded.presentation_id,
        [
            {
                "page_number": 1,
                "chunk_number": 1,
                "title": "Page 1",
                "content_text": "No text extracted for page 1.",
                "chunk_kind": "section",
                "parent_chunk_id": "p1",
                "parent_content_text": "No text extracted for page 1.",
            },
            {
                "page_number": 2,
                "chunk_number": 1,
                "title": "Page 2",
                "content_text": "No text extracted for page 2.",
                "chunk_kind": "section",
                "parent_chunk_id": "p2",
                "parent_content_text": "No text extracted for page 2.",
            },
        ],
    )
    storage_mod.update_presentation_meta(
        uploaded.presentation_id,
        status="ready",
        total_pages=2,
        indexed_pages=2,
        pages_without_text=2,
    )

    settings, previous = _with_local_retrieval()
    try:
        hits = asyncio.run(
            rag_retriever.search_presentation(
                "what is the latency metric",
                uploaded.presentation_id,
                settings,
            )
        )
    finally:
        _restore_azure_settings(previous)

    assert hits == []


def test_rag_dedupes_child_hits_by_parent_chunk() -> None:
    uploaded = storage_mod.save_upload("deck.pdf", b"%PDF-1.4 fake content")
    storage_mod.save_chunk_rows(
        uploaded.presentation_id,
        [
            {
                "page_number": 3,
                "chunk_number": 1,
                "title": "Benchmark",
                "section_heading": "Latency",
                "content_text": "Latency baseline is 180ms.",
                "chunk_kind": "section",
                "parent_chunk_id": "parent-3",
                "parent_content_text": "Slide 3 discusses latency baseline and jitter controls.",
            },
            {
                "page_number": 3,
                "chunk_number": 2,
                "title": "Benchmark",
                "section_heading": "Jitter",
                "content_text": "Adaptive jitter keeps packet loss under 1%.",
                "chunk_kind": "section",
                "parent_chunk_id": "parent-3",
                "parent_content_text": "Slide 3 discusses latency baseline and jitter controls.",
            },
            {
                "page_number": 4,
                "chunk_number": 1,
                "title": "Cost",
                "section_heading": "Revenue",
                "content_text": "Annual revenue upside is $847M.",
                "chunk_kind": "section",
                "parent_chunk_id": "parent-4",
                "parent_content_text": "Slide 4 covers business impact and upside.",
            },
        ],
    )

    settings, previous = _with_local_retrieval()
    try:
        hits = asyncio.run(
            rag_retriever.search_presentation(
                "latency jitter",
                uploaded.presentation_id,
                settings,
            )
        )
    finally:
        _restore_azure_settings(previous)

    assert hits
    assert hits[0]["page_number"] == 3
    assert hits[0]["parent_chunk_id"] == "parent-3"
    assert "slide 3 discusses latency baseline" in hits[0]["parent_content_text"].lower()
    assert len([hit for hit in hits if hit["parent_chunk_id"] == "parent-3"]) == 1
