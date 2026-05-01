from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from config import get_settings
from indexer import pipeline
from services import storage as storage_mod


SAMPLE_VISION_META = [
    {
        "page_number": 1,
        "title": "Overtone Demo",
        "section_label": "Cover",
        "description": "Cover slide.",
        "key_topics": ["voice", "AI"],
        "entities": ["Overtone"],
        "content_text": "Overtone — Voice AI Platform",
        "searchable_content": "Overtone — Voice AI Platform. Cover slide.",
        "table_data": None,
        "chart_description": None,
        "diagram_description": None,
        "content_type": "title_slide",
        "has_table": False,
        "has_chart": False,
        "has_diagram": False,
    },
    {
        "page_number": 2,
        "title": "Architecture",
        "section_label": "Architecture",
        "description": "System architecture.",
        "key_topics": ["microservices"],
        "entities": ["FastAPI", "Redis"],
        "content_text": "Three-tier microservice architecture with FastAPI and Redis.",
        "searchable_content": "Architecture. Three-tier microservice architecture with FastAPI and Redis.",
        "table_data": None,
        "chart_description": None,
        "diagram_description": "Three boxes: API → Service → DB",
        "content_type": "diagram",
        "has_table": False,
        "has_chart": False,
        "has_diagram": True,
    },
]


def _make_fake_blob_storage(enabled=False):
    class FakeBlob:
        def __init__(self, _s):
            pass
        @property
        def enabled(self):
            return enabled
        async def upload_bytes(self, *, blob_name, payload, content_type):
            return type("R", (), {"blob_name": blob_name, "blob_url": f"https://blob/{blob_name}"})()
    return FakeBlob


def test_vision_pipeline_runs_end_to_end(monkeypatch, tmp_path):
    """Full pipeline: convert → vision → index → manifest → status=ready."""
    uploaded = storage_mod.save_upload("demo.pdf", b"%PDF-1.4 fake")

    monkeypatch.setattr(
        pipeline,
        "_run_vision_pipeline",
        AsyncMock(return_value=SAMPLE_VISION_META),
    )
    monkeypatch.setattr(
        pipeline,
        "_upload_to_search",
        AsyncMock(return_value=2),
    )
    monkeypatch.setattr(
        pipeline,
        "_save_manifest",
        MagicMock(),
    )
    monkeypatch.setattr(pipeline, "AzureBlobStorageClient", _make_fake_blob_storage(enabled=False))

    asyncio.run(pipeline.run_index_job(uploaded.presentation_id))

    summary = storage_mod.get_presentation(uploaded.presentation_id)
    assert summary is not None
    assert summary.status == "ready"
    assert summary.total_pages == 2
    assert summary.indexed_pages == 2


def test_vision_pipeline_marks_failed_on_conversion_error(monkeypatch):
    """If converter raises, status is set to failed with error message."""
    uploaded = storage_mod.save_upload("bad.pdf", b"not a pdf")

    monkeypatch.setattr(
        pipeline,
        "_run_vision_pipeline",
        AsyncMock(side_effect=RuntimeError("pdftoppm failed")),
    )
    monkeypatch.setattr(pipeline, "AzureBlobStorageClient", _make_fake_blob_storage(enabled=False))

    asyncio.run(pipeline.run_index_job(uploaded.presentation_id))

    summary = storage_mod.get_presentation(uploaded.presentation_id)
    assert summary.status == "failed"
    assert "pdftoppm failed" in (summary.index_error or "")


def test_vision_pipeline_saves_local_pages_for_rag_fallback(monkeypatch):
    """Vision metadata is saved to local storage so keyword RAG fallback works."""
    uploaded = storage_mod.save_upload("demo.pdf", b"%PDF-1.4 fake")

    monkeypatch.setattr(
        pipeline,
        "_run_vision_pipeline",
        AsyncMock(return_value=SAMPLE_VISION_META),
    )
    monkeypatch.setattr(pipeline, "_upload_to_search", AsyncMock(return_value=2))
    monkeypatch.setattr(pipeline, "_save_manifest", MagicMock())
    monkeypatch.setattr(pipeline, "AzureBlobStorageClient", _make_fake_blob_storage(enabled=False))

    asyncio.run(pipeline.run_index_job(uploaded.presentation_id))

    pages = storage_mod.load_index_pages(uploaded.presentation_id)
    assert len(pages) == 2
    assert pages[0]["title"] == "Overtone Demo"
    assert pages[1]["searchable_content"].startswith("Architecture")

    chunks = storage_mod.load_chunk_rows(uploaded.presentation_id)
    assert len(chunks) == 2
    assert chunks[0]["page_number"] == 1
