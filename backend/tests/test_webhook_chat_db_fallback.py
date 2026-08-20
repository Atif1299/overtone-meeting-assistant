from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from database import SessionLocal
from models.bot_session import AgentMode, BotSession, BotSessionState
from services.session_store import store


def test_webhook_chat_db_fallback(client: TestClient) -> None:
    """Memory miss → SQL by recall_bot_id → chat mute path finds the session."""
    session_id = "sid-chat-db-fallback"
    recall_bot_id = "recall-bot-chat-db-1"

    db = SessionLocal()
    try:
        db.merge(
            BotSession(
                session_id=session_id,
                bot_id=recall_bot_id,
                recall_bot_id=recall_bot_id,
                presentation_id="demo",
                bot_name="Overtone",
                meeting_url="https://meet.google.com/abc-defg-hij",
                agent_mode=AgentMode.REALTIME.value,
                agent_name="default",
                state=BotSessionState.IN_CALL.value,
                extra={"muted": False},
            )
        )
        db.commit()
    finally:
        db.close()

    # Ensure in-memory store does not already know this bot.
    asyncio.run(store.clear())

    response = client.post(
        "/api/webhook/recall/chat",
        json={
            "event": "participant_events.chat_message",
            "data": {
                "bot": {"id": recall_bot_id},
                "data": {
                    "action": "chat_message",
                    "participant": {"id": 1, "name": "Host"},
                    "data": {"text": "mute", "to": "everyone"},
                },
            },
        },
        headers={"svix-id": "chat-db-fallback-1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    sess = asyncio.run(store.get_by_bot_id(recall_bot_id))
    assert sess is not None
    assert sess.session_id == session_id
    assert (sess.extra or {}).get("muted") is True
