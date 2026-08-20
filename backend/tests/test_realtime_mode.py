from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from models.bot_session import AgentMode
from orchestrator.realtime_tools import RealtimeToolExecutor
from services.session_store import store


@pytest.fixture
def recall_settings():
    from config import get_settings

    settings = get_settings()
    old_values = {
        "recall_api_key": settings.recall_api_key,
        "frontend_url": settings.frontend_url,
        "backend_url": settings.backend_url,
        "voice_agent_mode": settings.voice_agent_mode,
    }
    settings.recall_api_key = "test-recall-key"
    settings.frontend_url = "https://frontend.example.com"
    settings.backend_url = "https://backend.example.com"
    settings.voice_agent_mode = "realtime"
    try:
        yield settings
    finally:
        settings.recall_api_key = old_values["recall_api_key"]
        settings.frontend_url = old_values["frontend_url"]
        settings.backend_url = old_values["backend_url"]
        settings.voice_agent_mode = old_values["voice_agent_mode"]


def test_launch_bot_realtime_mode_includes_relay_and_disables_transcript_webhook(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, recall_settings
) -> None:
    captured_payloads: list[dict] = []

    async def _fake_create_bot(self, payload: dict) -> dict:
        captured_payloads.append(payload)
        return {"id": "bot-realtime-123"}

    monkeypatch.setattr("services.recall_client.RecallClient.create_bot", _fake_create_bot)

    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "VoiceNav Presenter",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/example",
            "presentation_id": "demo",
            "agent_mode": "realtime",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_mode"] == "realtime"
    assert payload["relay_profile"] == "voicenav"
    assert payload["transcript_webhook_enabled"] is False
    assert payload["realtime_relay_url"].startswith("wss://backend.example.com/ws/realtime/")
    assert "mode=realtime" in payload["output_media_url"]
    assert "wss=" in payload["output_media_url"]

    assert captured_payloads
    recording_config = captured_payloads[0]["recording_config"]
    endpoints = recording_config.get("realtime_endpoints") or []
    # Realtime mode skips transcript webhooks but always attaches chat webhook.
    assert endpoints
    assert all(
        "transcript.data" not in (ep.get("events") or [])
        and "transcript.partial_data" not in (ep.get("events") or [])
        for ep in endpoints
    )
    assert any(
        "participant_events.chat_message" in (ep.get("events") or []) for ep in endpoints
    )


def test_launch_bot_uses_agent_default_presentation_when_missing_in_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, recall_settings
) -> None:
    monkeypatch.setattr("api.presentations.dispatch_index_job", lambda _presentation_id: True)
    upload = client.post(
        "/api/v1/presentations",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert upload.status_code == 200
    presentation_id = upload.json()["presentation_id"]
    from services import storage as storage_mod

    storage_mod.update_presentation_meta(
        presentation_id, status="ready", indexed_pages=1, total_pages=1
    )

    agent_version = client.post(
        "/api/agents/default/versions",
        json={
            "system_prompt": "You are the default deck-aware agent.",
            "presentation_id": presentation_id,
            "activate": True,
        },
    )
    assert agent_version.status_code == 200

    captured_payloads: list[dict] = []

    async def _fake_create_bot(self, payload: dict) -> dict:
        captured_payloads.append(payload)
        return {"id": "bot-default-deck-123"}

    monkeypatch.setattr("services.recall_client.RecallClient.create_bot", _fake_create_bot)

    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "VoiceNav Presenter",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/example",
            "agent_name": "default",
            "agent_mode": "realtime",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["presentation_id"] == presentation_id
    assert f"presentation={presentation_id}" in payload["output_media_url"]
    assert captured_payloads


def test_launch_bot_webhook_mode_enables_transcript_webhook_and_omits_relay(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, recall_settings
) -> None:
    captured_payloads: list[dict] = []

    async def _fake_create_bot(self, payload: dict) -> dict:
        captured_payloads.append(payload)
        return {"id": "bot-webhook-123"}

    monkeypatch.setattr("services.recall_client.RecallClient.create_bot", _fake_create_bot)

    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "VoiceNav Presenter",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/example",
            "presentation_id": "demo",
            "agent_mode": "webhook",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_mode"] == "webhook"
    assert payload["relay_profile"] == "voicenav"
    assert payload["transcript_webhook_enabled"] is True
    assert payload["realtime_relay_url"] is None
    assert "mode=webhook" in payload["output_media_url"]
    assert "wss=" not in payload["output_media_url"]

    assert captured_payloads
    recording_config = captured_payloads[0]["recording_config"]
    assert "realtime_endpoints" in recording_config


def test_launch_bot_output_override_uses_demo_profile_and_injects_wss(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, recall_settings
) -> None:
    captured_payloads: list[dict] = []

    async def _fake_create_bot(self, payload: dict) -> dict:
        captured_payloads.append(payload)
        return {"id": "bot-demo-123"}

    monkeypatch.setattr("services.recall_client.RecallClient.create_bot", _fake_create_bot)

    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "VoiceNav Presenter",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/example",
            "presentation_id": "demo",
            "agent_mode": "realtime",
            "output_media_url_override": "https://recallai-demo.netlify.app",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["relay_profile"] == "demo"
    assert payload["output_media_url"].startswith("https://recallai-demo.netlify.app")
    assert "wss=" in payload["output_media_url"]
    assert "session=" not in payload["output_media_url"]

    assert captured_payloads
    assert captured_payloads[0]["output_media"]["camera"]["config"]["url"] == payload["output_media_url"]


def test_launch_bot_sets_recall_bot_id_and_chat_webhook(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, recall_settings
) -> None:
    monkeypatch.setattr("api.presentations.dispatch_index_job", lambda _presentation_id: True)
    upload = client.post(
        "/api/v1/presentations",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert upload.status_code == 200
    presentation_id = upload.json()["presentation_id"]
    from services import storage as storage_mod

    storage_mod.update_presentation_meta(
        presentation_id, status="ready", indexed_pages=1, total_pages=1
    )

    captured_payloads: list[dict] = []

    async def _fake_create_bot(self, payload: dict) -> dict:
        captured_payloads.append(payload)
        return {"id": "bot-chat-parity-123"}

    monkeypatch.setattr("services.recall_client.RecallClient.create_bot", _fake_create_bot)

    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "Overtone Agent",
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "presentation_id": presentation_id,
            "agent_mode": "realtime",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_id"] == "bot-chat-parity-123"
    assert body["session_id"]

    assert captured_payloads
    rec_endpoints = captured_payloads[0]["recording_config"]["realtime_endpoints"]
    chat_urls = [
        ep["url"]
        for ep in rec_endpoints
        if "participant_events.chat_message" in (ep.get("events") or [])
    ]
    assert chat_urls
    assert chat_urls[0].endswith("/api/webhook/recall/chat")

    sess = asyncio.run(store.get_by_session_id(body["session_id"]))
    assert sess is not None
    assert sess.bot_id == "bot-chat-parity-123"
    assert sess.recall_bot_id == "bot-chat-parity-123"

    from database import SessionLocal
    from models.bot_session import BotSession as BotSessionModel

    db = SessionLocal()
    try:
        row = (
            db.query(BotSessionModel)
            .filter(BotSessionModel.session_id == body["session_id"])
            .one_or_none()
        )
        assert row is not None
        assert row.bot_id == "bot-chat-parity-123"
        assert row.recall_bot_id == "bot-chat-parity-123"
        assert row.presentation_id == presentation_id
    finally:
        db.close()


def test_realtime_relay_rejects_non_realtime_sessions(client: TestClient) -> None:
    asyncio.run(
        store.create_session(
            presentation_id="demo",
            bot_name="VoiceNav Presenter",
            meeting_url="https://teams.microsoft.com/l/meetup-join/example",
            agent_mode=AgentMode.WEBHOOK,
            bot_id="bot-webhook-1",
            session_id="sid-webhook-1",
        )
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/realtime/sid-webhook-1") as websocket:
            websocket.receive_text()
    assert exc.value.code == 4409


def test_realtime_mode_webhook_is_isolated(client: TestClient) -> None:
    asyncio.run(
        store.create_session(
            presentation_id="demo",
            bot_name="VoiceNav Presenter",
            meeting_url="https://teams.microsoft.com/l/meetup-join/example",
            agent_mode=AgentMode.REALTIME,
            bot_id="bot-realtime-1",
            session_id="sid-realtime-1",
        )
    )

    payload = {
        "event": "transcript.final",
        "data": {"bot": {"id": "bot-realtime-1"}, "data": {"text": "go to slide 3"}},
    }
    response = client.post("/api/webhook/recall/transcript", json=payload, headers={"svix-id": "evt-2"})
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_realtime_tool_executor_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(
        store.create_session(
            presentation_id="demo",
            bot_name="VoiceNav Presenter",
            meeting_url="https://teams.microsoft.com/l/meetup-join/example",
            agent_mode=AgentMode.REALTIME,
            bot_id="bot-tools-1",
            session_id="sid-tools-1",
        )
    )

    async def _fake_total_pages(presentation_id: str) -> int:
        assert presentation_id == "demo"
        return 20

    async def _fake_search(query: str, presentation_id: str, settings) -> list[dict]:
        assert presentation_id == "demo"
        return [
            {
                "page_number": 5,
                "title": "Architecture",
                "searchable_content": "VoiceNav routes realtime tool calls through backend relay.",
                "score": 1.0,
            }
        ]

    monkeypatch.setattr("orchestrator.rag_retriever.get_total_pages", _fake_total_pages)
    monkeypatch.setattr("orchestrator.rag_retriever.search_presentation", _fake_search)

    executor = RealtimeToolExecutor()
    nav_result = asyncio.run(
        executor.execute(
            session_id="sid-tools-1",
            tool_name="navigate_to_slide",
            raw_arguments='{"page_number": 7}',
        )
    )
    assert nav_result["ok"] is True
    assert nav_result["page_number"] == 7

    answer_result = asyncio.run(
        executor.execute(
            session_id="sid-tools-1",
            tool_name="search_and_answer",
            raw_arguments='{"user_question": "How does this work?"}',
        )
    )
    assert answer_result["ok"] is True
    assert "slide_content" in answer_result
    assert "instruction" in answer_result
    assert "target_page" in answer_result
