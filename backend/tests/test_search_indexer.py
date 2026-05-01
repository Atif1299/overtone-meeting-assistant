from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from indexer.search_indexer import _build_chunk_document, prepare_documents


SAMPLE_META = {
    "page_number": 3,
    "title": "Pricing Tiers",
    "section_label": "Pricing",
    "description": "Three pricing tiers: Starter, Growth, Enterprise.",
    "key_topics": ["pricing", "tiers", "enterprise"],
    "entities": ["Starter", "Growth", "Enterprise"],
    "content_text": "Starter $99/mo, Growth $299/mo, Enterprise custom.",
    "searchable_content": "Pricing Tiers. Starter $99/mo, Growth $299/mo, Enterprise custom pricing.",
    "table_data": "| Tier | Price |\n| --- | --- |\n| Starter | $99/mo |",
    "chart_description": None,
    "diagram_description": None,
    "content_type": "data",
    "has_table": True,
    "has_chart": False,
    "has_diagram": False,
}


def test_build_chunk_document_ids():
    doc = _build_chunk_document(
        metadata=SAMPLE_META,
        presentation_id="abc-123",
        content_vector=[0.1] * 3072,
        title_vector=[0.2] * 3072,
    )

    assert doc["id"] == "abc-123_p3_c1"
    assert doc["document_id"] == "abc-123"
    assert doc["page_id"] == "abc-123_p3"
    assert doc["page_number"] == 3
    assert doc["chunk_number"] == 1


def test_build_chunk_document_fields():
    doc = _build_chunk_document(
        metadata=SAMPLE_META,
        presentation_id="abc-123",
        content_vector=[0.1] * 3072,
        title_vector=[0.2] * 3072,
    )

    assert doc["title"] == "Pricing Tiers"
    assert doc["section_label"] == "Pricing"
    assert doc["has_table"] is True
    assert doc["has_chart"] is False
    assert doc["content_type"] == "data"
    assert len(doc["content_vector"]) == 3072


def test_prepare_documents_calls_embedding_per_page():
    """prepare_documents generates 2 embeddings per page (content + title)."""
    call_count = {"n": 0}

    async def fake_embed(text):
        call_count["n"] += 1
        return [0.0] * 3072

    result = asyncio.run(
        prepare_documents(
            page_metadata_list=[SAMPLE_META],
            presentation_id="abc-123",
            generate_embedding=fake_embed,
        )
    )

    assert len(result) == 1
    assert call_count["n"] == 2  # content + title embeddings


def test_prepare_documents_correct_id_for_multiple_pages():
    pages = [
        {**SAMPLE_META, "page_number": 1, "title": "Cover"},
        {**SAMPLE_META, "page_number": 2, "title": "Intro"},
    ]

    async def fake_embed(text):
        return [0.0] * 3072

    docs = asyncio.run(
        prepare_documents(
            page_metadata_list=pages,
            presentation_id="pres-xyz",
            generate_embedding=fake_embed,
        )
    )

    ids = [d["id"] for d in docs]
    assert "pres-xyz_p1_c1" in ids
    assert "pres-xyz_p2_c1" in ids
