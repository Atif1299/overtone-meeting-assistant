from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    with TestClient(create_app()) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["version"] == "v2"


def test_admin_auth_and_agents():
    with TestClient(create_app()) as client:
        from app.config import get_settings

        key = get_settings().admin_api_key or "dev-admin-key"
        r = client.post("/auth/admin", json={"admin_api_key": key})
        assert r.status_code == 200
        headers = {"X-API-Key": key}
        r2 = client.get("/api/v1/agents", headers=headers)
        assert r2.status_code == 200
        assert "agents" in r2.json()


def test_presentations_list_empty():
    with TestClient(create_app()) as client:
        from app.config import get_settings

        key = get_settings().admin_api_key or "dev-admin-key"
        r = client.get("/api/v1/presentations", headers={"X-API-Key": key})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
