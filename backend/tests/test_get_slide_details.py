from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.realtime_tools import RealtimeToolExecutor


def test_get_slide_details_uses_vision_content_text_fields() -> None:
    executor = RealtimeToolExecutor(settings=MagicMock())
    vision_page = {
        "page_number": 8,
        "title": "Roadmap",
        "content_text": "Q3 launch timeline and milestones.",
        "searchable_content": "Roadmap Q3 launch timeline and milestones.",
        "description": "Roadmap overview",
    }

    async def _run() -> dict:
        with (
            patch("orchestrator.realtime_tools._get_session", new=AsyncMock(return_value=MagicMock(presentation_id="deck-1"))),
            patch("services.storage.load_provided_metadata", return_value={"pages": [vision_page], "account_name": "Acme"}),
            patch("services.storage.load_index_pages", return_value=[]),
        ):
            return await executor._get_slide_details(session_id="s1", args={"page_number": 8})

    result = asyncio.run(_run())
    assert result["ok"] is True
    assert "Q3 launch" in result["slide_content"]
    assert result["title"] == "Roadmap"


def test_get_slide_details_falls_back_to_index_pages() -> None:
    executor = RealtimeToolExecutor(settings=MagicMock())
    index_page = {
        "page_number": 4,
        "title": "Pricing",
        "searchable_content": "Enterprise plan is $99 per seat.",
    }

    async def _run() -> dict:
        with (
            patch("orchestrator.realtime_tools._get_session", new=AsyncMock(return_value=MagicMock(presentation_id="deck-2"))),
            patch("services.storage.load_provided_metadata", return_value={}),
            patch("services.storage.load_index_pages", return_value=[index_page]),
        ):
            return await executor._get_slide_details(session_id="s1", args={"page_number": 4})

    result = asyncio.run(_run())
    assert result["ok"] is True
    assert "Enterprise plan" in result["slide_content"]


def test_openai_tools_to_gemini_and_resample() -> None:
    from services.gemini_live import (
        openai_tools_to_gemini,
        presenter_audio_delta_event,
        presenter_turn_start_events,
        resample_pcm16_mono,
    )

    tools = [
        {
            "type": "function",
            "name": "navigate_to_slide",
            "description": "Go to a slide",
            "parameters": {"type": "object", "properties": {"page_number": {"type": "integer"}}},
        }
    ]
    decls = openai_tools_to_gemini(tools)
    assert decls[0]["name"] == "navigate_to_slide"
    assert "parameters" in decls[0]

    pcm24 = b"\x00\x01" * 24
    out = resample_pcm16_mono(pcm24, 24000, 16000)
    assert len(out) % 2 == 0
    assert 0 < len(out) <= len(pcm24)

    start = presenter_turn_start_events(response_id="resp_1", item_id="item_1")
    assert start[0]["type"] == "response.created"
    assert start[0]["event_id"]
    assert start[1]["type"] == "conversation.item.created"
    audio = presenter_audio_delta_event(item_id="item_1", pcm_b64="AAAA")
    assert audio["type"] == "response.audio.delta"
    assert audio["item_id"] == "item_1"
    assert audio["event_id"]


def test_effective_realtime_provider_prefers_gemini_when_key_set() -> None:
    from config import Settings, effective_realtime_provider

    s = Settings(realtime_provider="auto", gemini_api_key="g-key", openai_api_key="o-key")
    assert effective_realtime_provider(s) == "gemini"
    s2 = Settings(realtime_provider="auto", gemini_api_key="", openai_api_key="o-key")
    assert effective_realtime_provider(s2) == "openai"
    s3 = Settings(realtime_provider="openai", gemini_api_key="g-key")
    assert effective_realtime_provider(s3) == "openai"
