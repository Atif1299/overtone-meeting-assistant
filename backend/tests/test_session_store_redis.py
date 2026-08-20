from __future__ import annotations

from datetime import datetime, timezone

from models.bot_session import AgentMode, BotSession, BotSessionState
from services.session_store import session_from_redis_dict, session_to_redis_dict


def test_session_store_redis_roundtrip_helpers() -> None:
    now = datetime.now(timezone.utc)
    sess = BotSession(
        session_id="sess-redis-1",
        customer_id="cust-1",
        bot_id="bot-1",
        recall_bot_id="recall-1",
        presentation_id="pres-1",
        bot_name="Overtone",
        meeting_url="https://meet.google.com/abc-defg-hij",
        agent_mode=AgentMode.REALTIME,
        agent_name="default",
        agent_version=2,
        state=BotSessionState.IN_CALL,
        last_status_code="in_call_recording",
        last_status_message="ok",
        last_transcript_snippet="hello",
        created_at=now,
        updated_at=now,
        expires_at=None,
        extra={"relay_profile": "voicenav", "muted": False},
        pdf_url="https://example.com/a.pdf",
        metadata_url="https://example.com/a.json",
    )

    payload = session_to_redis_dict(sess)
    assert payload["session_id"] == "sess-redis-1"
    assert payload["bot_id"] == "bot-1"
    assert payload["recall_bot_id"] == "recall-1"
    assert payload["agent_mode"] == "realtime"
    assert payload["state"] == "in_call"
    assert payload["extra"]["relay_profile"] == "voicenav"
    assert isinstance(payload["created_at"], str)

    restored = session_from_redis_dict(payload)
    assert restored is not None
    assert restored.session_id == sess.session_id
    assert restored.bot_id == sess.bot_id
    assert restored.recall_bot_id == sess.recall_bot_id
    assert restored.presentation_id == sess.presentation_id
    assert restored.agent_mode == "realtime"
    assert restored.state == "in_call"
    assert restored.extra["relay_profile"] == "voicenav"
    assert restored.pdf_url == sess.pdf_url


def test_session_from_redis_dict_rejects_empty() -> None:
    assert session_from_redis_dict(None) is None
    assert session_from_redis_dict({}) is None
    assert session_from_redis_dict({"bot_id": "x"}) is None
