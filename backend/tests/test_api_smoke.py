from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient


def test_health_exposes_runtime_metrics(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "active_sessions" in payload
    assert "transcript_queue_depth" in payload
    assert "webhook_dedupe_cache" in payload


def test_upload_and_list_presentation(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert response.status_code == 200
    uploaded = response.json()
    assert uploaded["filename"] == "deck.pdf"
    assert uploaded["status"] == "uploaded"

    list_response = client.get("/api/presentations")
    assert list_response.status_code == 200
    assert any(item["presentation_id"] == uploaded["presentation_id"] for item in list_response.json())


def test_upload_dispatches_index_job(client: TestClient, monkeypatch) -> None:
    dispatched: list[str] = []

    def fake_dispatch(presentation_id: str) -> bool:
        dispatched.append(presentation_id)
        return True

    monkeypatch.setattr("api.upload.dispatch_index_job", fake_dispatch)
    response = client.post(
        "/api/upload",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert response.status_code == 200
    uploaded = response.json()
    assert dispatched == [uploaded["presentation_id"]]


def test_chunked_upload_flow(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("api.upload.dispatch_index_job", lambda _presentation_id: True)

    init = client.post(
        "/api/upload/init",
        data={
            "filename": "deck.pdf",
            "total_size": "24",
            "total_chunks": "2",
        },
    )
    assert init.status_code == 200
    presentation_id = init.json()["presentation_id"]

    chunk_a = client.post(
        f"/api/upload/{presentation_id}/chunk",
        data={"chunk_index": "0"},
        files={"chunk": ("part-0.bin", b"%PDF-1.4 ", "application/octet-stream")},
    )
    assert chunk_a.status_code == 200
    assert chunk_a.json()["ok"] is True

    chunk_b = client.post(
        f"/api/upload/{presentation_id}/chunk",
        data={"chunk_index": "1"},
        files={"chunk": ("part-1.bin", b"fake content", "application/octet-stream")},
    )
    assert chunk_b.status_code == 200
    assert chunk_b.json()["ok"] is True

    complete = client.post(f"/api/upload/{presentation_id}/complete")
    assert complete.status_code == 200
    payload = complete.json()
    assert payload["presentation_id"] == presentation_id


def test_run_indexing_endpoint_executes_job(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("api.upload.dispatch_index_job", lambda _presentation_id: True)
    uploaded = client.post(
        "/api/upload",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    ).json()

    executed: list[str] = []

    def fake_dispatch_index_job(presentation_id: str) -> None:
        from services import storage as storage_mod

        executed.append(presentation_id)
        storage_mod.update_presentation_meta(
            presentation_id,
            status="ready",
            indexed_pages=1,
            total_pages=1,
        )

    monkeypatch.setattr("api.index_status.dispatch_index_job", fake_dispatch_index_job)
    response = client.post(f"/api/index-status/{uploaded['presentation_id']}/run", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["presentation_id"] == uploaded["presentation_id"]
    assert payload["status"] == "ready"
    assert executed == [uploaded["presentation_id"]]


def test_admin_api_key_enforced_when_configured(client: TestClient) -> None:
    from config import get_settings

    settings = get_settings()
    old = settings.admin_api_key
    settings.admin_api_key = "phase2-secret"
    try:
        blocked = client.post(
            "/api/upload",
            files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        assert blocked.status_code == 401

        allowed = client.post(
            "/api/upload",
            headers={"X-API-Key": "phase2-secret"},
            files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
        assert allowed.status_code == 200
    finally:
        settings.admin_api_key = old


def test_upload_rejects_unknown_extension(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "supported" in response.text.lower()


def test_session_not_found(client: TestClient) -> None:
    response = client.get("/api/session/not-real")
    assert response.status_code == 404


def test_launch_requires_recall_api_key(client: TestClient) -> None:
    response = client.post(
        "/api/launch-bot",
        json={
            "bot_name": "VoiceNav Presenter",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/example",
            "presentation_id": "demo",
        },
    )
    assert response.status_code == 503
    assert "RECALL_API_KEY" in response.text


def test_transcript_webhook_validates_bot_id(client: TestClient) -> None:
    response = client.post(
        "/api/webhook/recall/transcript",
        json={"event": "transcript.final", "data": {"data": {"text": "hello"}}},
    )
    assert response.status_code == 400
    assert "bot id" in response.text.lower()


def test_transcript_webhook_is_idempotent(client: TestClient) -> None:
    from models.bot_session import AgentMode
    from services.session_store import store

    asyncio.run(
        store.create_session(
            presentation_id="demo",
            bot_name="VoiceNav Presenter",
            meeting_url="https://teams.microsoft.com/l/meetup-join/example",
            agent_mode=AgentMode.WEBHOOK,
            bot_id="bot-123",
            session_id="sid-123",
        )
    )

    payload = {
        "event": "transcript.final",
        "data": {"bot": {"id": "bot-123"}, "data": {"text": "go to slide 3"}},
    }

    first = client.post("/api/webhook/recall/transcript", json=payload, headers={"svix-id": "evt-1"})
    assert first.status_code == 200
    assert first.json()["status"] == "ok"

    second = client.post("/api/webhook/recall/transcript", json=payload, headers={"svix-id": "evt-1"})
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
