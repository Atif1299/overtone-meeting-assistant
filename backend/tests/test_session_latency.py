from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.domain.session_store import LiveSession, store
from app.main import create_app


def test_session_get_exposes_first_audio_latency():
    sid = "lat-test-session"
    store.create(
        LiveSession(
            session_id=sid,
            presentation_id="p1",
            bot_name="Test",
            meeting_url="https://meet.example.com/abc",
            extra={"current_page": 1},
        )
    )
    store.merge_extra(
        sid,
        first_audio_latency_ms=1234,
        latency_breakdown={"endpointing_ms": 300, "embed_ms": 180, "tool_ms": 400, "first_audio_ms": 1234},
    )
    key = get_settings().admin_api_key or "dev-admin-key"
    with TestClient(create_app()) as client:
        r = client.get(f"/api/v1/sessions/{sid}", headers={"X-API-Key": key})
    assert r.status_code == 200
    body = r.json()
    assert body["first_audio_latency_ms"] == 1234
    assert body["latency_breakdown"]["embed_ms"] == 180
