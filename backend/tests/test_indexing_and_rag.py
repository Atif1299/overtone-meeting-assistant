from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from indexer import pipeline
from orchestrator.rag_retriever import search_presentation
from services import storage as storage_mod


FAKE_PAGES = [
    {
        "page_number": 1,
        "title": "VoiceNav Architecture Overview",
        "section_label": "Architecture",
        "description": "Integration testing and webhook verification architecture.",
        "key_topics": ["integration testing", "webhook", "architecture"],
        "entities": ["VoiceNav"],
        "content_text": "VoiceNav architecture overview. Integration testing checklist and webhook verification.",
        "searchable_content": "VoiceNav architecture overview. Integration testing checklist and webhook verification.",
        "table_data": None,
        "chart_description": None,
        "diagram_description": None,
        "content_type": "content",
        "has_table": False,
        "has_chart": False,
        "has_diagram": False,
    }
]


def _disabled_blob():
    class FakeBlob:
        def __init__(self, _s):
            pass
        @property
        def enabled(self):
            return False
    return FakeBlob


def test_indexer_builds_local_pages_and_rag_hits(monkeypatch) -> None:
    uploaded = storage_mod.save_upload(
        "deck.pdf",
        b"%PDF-1.4 VoiceNav architecture overview. Integration testing checklist and webhook verification.",
    )

    monkeypatch.setattr(pipeline, "_run_vision_pipeline", AsyncMock(return_value=FAKE_PAGES))
    monkeypatch.setattr(pipeline, "_upload_to_search", AsyncMock(return_value=1))
    monkeypatch.setattr(pipeline, "_save_manifest", MagicMock())
    monkeypatch.setattr(pipeline, "AzureBlobStorageClient", _disabled_blob())

    asyncio.run(pipeline.run_index_job(uploaded.presentation_id))
    presentation = storage_mod.get_presentation(uploaded.presentation_id)
    assert presentation is not None
    assert presentation.status == "ready"
    assert presentation.total_pages and presentation.total_pages >= 1

    hits = asyncio.run(search_presentation("integration testing webhook", uploaded.presentation_id))
    assert len(hits) >= 1
    assert "searchable_content" in hits[0]
