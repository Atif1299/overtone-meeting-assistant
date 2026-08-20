from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from indexer.metadata_enricher import extract_all_pages, extract_slide_metadata


SAMPLE_METADATA = {
    "page_number": 1,
    "title": "Architecture Overview",
    "section_label": "Architecture",
    "description": "Describes the three-tier microservice layout.",
    "key_topics": ["microservices", "API gateway", "data layer"],
    "entities": ["Redis", "Postgres", "FastAPI"],
    "content_text": "The system consists of three tiers: API gateway, service layer, and data layer.",
    "table_data": None,
    "chart_description": None,
    "diagram_description": "Three boxes connected by arrows: API gateway → service layer → data layer.",
    "image_description": None,
    "content_type": "diagram",
    "has_table": False,
    "has_chart": False,
    "has_diagram": True,
    "searchable_content": "Architecture Overview. The system consists of three tiers: API gateway, service layer, and data layer. Components: Redis, Postgres, FastAPI.",
}


def _openai_response(payload: dict) -> MagicMock:
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return fake_response


def test_extract_slide_metadata_parses_json(tmp_path):
    """extract_slide_metadata sends image + prompt to OpenAI Vision and parses JSON."""
    img = tmp_path / "page_1.png"
    img.write_bytes(b"fake png bytes")

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_openai_response(SAMPLE_METADATA))

    result = asyncio.run(
        extract_slide_metadata(
            image_path=str(img),
            page_number=1,
            total_pages=5,
            filename="deck.pdf",
            client=fake_client,
        )
    )

    assert result["title"] == "Architecture Overview"
    assert result["section_label"] == "Architecture"
    assert result["has_diagram"] is True
    assert result["has_table"] is False
    fake_client.chat.completions.create.assert_awaited_once()


def test_extract_slide_metadata_passes_image_as_base64(tmp_path):
    """The image data is base64-encoded as a data URL in the message content."""
    import base64

    img_bytes = b"fake png content"
    img = tmp_path / "page_1.png"
    img.write_bytes(img_bytes)

    captured = {}

    async def capture_create(**kwargs):
        captured["kwargs"] = kwargs
        return _openai_response(SAMPLE_METADATA)

    fake_client = MagicMock()
    fake_client.chat.completions.create = capture_create

    asyncio.run(
        extract_slide_metadata(
            image_path=str(img),
            page_number=1,
            total_pages=5,
            filename="deck.pdf",
            client=fake_client,
        )
    )

    content = captured["kwargs"]["messages"][0]["content"]
    image_block = next(b for b in content if b.get("type") == "image_url")
    expected_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
    assert image_block["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"


def test_extract_all_pages_returns_ordered_results(tmp_path):
    """extract_all_pages returns one metadata dict per page, in page order."""
    pages = []
    for i in range(1, 4):
        p = tmp_path / f"page_{i}.png"
        p.write_bytes(b"fake")
        pages.append(str(p))

    call_order = []

    async def fake_extract(image_path, page_number, total_pages, filename, client, model=None):
        call_order.append(page_number)
        return {**SAMPLE_METADATA, "page_number": page_number, "title": f"Page {page_number}"}

    with patch("indexer.metadata_enricher.extract_slide_metadata", side_effect=fake_extract):
        results = asyncio.run(
            extract_all_pages(
                page_images=pages,
                filename="deck.pdf",
                client=MagicMock(),
                concurrency=3,
            )
        )

    assert len(results) == 3
    assert results[0]["page_number"] == 1
    assert results[1]["page_number"] == 2
    assert results[2]["page_number"] == 3


def test_extract_all_pages_respects_concurrency_limit(tmp_path):
    """No more than `concurrency` Vision calls run simultaneously."""
    import asyncio as aio

    pages = [str(tmp_path / f"p{i}.png") for i in range(6)]
    for p in pages:
        Path(p).write_bytes(b"x")

    active = {"count": 0, "max": 0}

    async def fake_extract(image_path, page_number, total_pages, filename, client, model=None):
        active["count"] += 1
        active["max"] = max(active["max"], active["count"])
        await aio.sleep(0.01)
        active["count"] -= 1
        return {**SAMPLE_METADATA, "page_number": page_number}

    with patch("indexer.metadata_enricher.extract_slide_metadata", side_effect=fake_extract):
        asyncio.run(
            extract_all_pages(
                page_images=pages,
                filename="deck.pdf",
                client=MagicMock(),
                concurrency=2,
            )
        )

    assert active["max"] <= 2
