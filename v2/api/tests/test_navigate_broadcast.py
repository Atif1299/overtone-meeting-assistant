from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.session_store import LiveSession, store
from app.realtime.tools import tools


def _make_session(presentation_id: str = "nav-test-pres") -> str:
    sid = f"nav-{uuid.uuid4().hex[:8]}"
    store.create(
        LiveSession(
            session_id=sid,
            presentation_id=presentation_id,
            bot_name="Test",
            meeting_url="https://meet.example.com/abc",
            agent_name="default",
            agent_version=1,
            customer_id=None,
            bot_id="bot-1",
            recall_bot_id=None,
            state="in_call",
            extra={"current_page": 1},
        )
    )
    return sid


@pytest.mark.asyncio
async def test_navigate_broadcasts_target_page():
    session_id = _make_session()
    broadcast = AsyncMock()
    page_payload = {
        "ok": True,
        "page_number": 4,
        "slide_title": "Slide 4",
        "slide_content": "content",
        "instruction": "Answer only from slide_content.",
    }

    with (
        patch("app.realtime.tools.hub.broadcast", broadcast),
        patch.object(tools, "_page_payload", AsyncMock(return_value=page_payload)),
        patch(
            "app.realtime.tools.PresentationStore.load_index_pages",
            return_value=[{"page_number": i} for i in range(1, 11)],
        ),
    ):
        result = await tools.execute(session_id, "navigate_to_slide", {"page_number": 4})

    assert result["target_page"] == 4
    broadcast.assert_awaited_once()
    payload = broadcast.await_args.args[1]
    assert payload["type"] == "navigate"
    assert payload["target_page"] == 4
    assert payload["page_number"] == 4


@pytest.mark.asyncio
async def test_search_broadcasts_target_page():
    session_id = _make_session()
    broadcast = AsyncMock()
    hit = {
        "page_number": 3,
        "title": "Slide 3",
        "searchable_content": "orchestrating agentic AI",
        "score": 0.9,
    }

    with (
        patch("app.realtime.tools.hub.broadcast", broadcast),
        patch("app.realtime.tools.hybrid_search", AsyncMock(return_value=[hit])),
    ):
        result = await tools.execute(
            session_id,
            "search_and_answer",
            {"user_question": "What is VisionsCraft?", "search_query": "VisionsCraft"},
        )

    assert result["target_page"] == 3
    broadcast.assert_awaited_once()
    payload = broadcast.await_args.args[1]
    assert payload["type"] == "navigate"
    assert payload["target_page"] == 3
