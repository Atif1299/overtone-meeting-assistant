from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_open_demo_access_allows_unauthenticated_list(monkeypatch):
    monkeypatch.setenv("OPEN_DEMO_ACCESS", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            r = client.get("/api/v1/presentations")
            assert r.status_code == 200
            assert isinstance(r.json(), list)
    finally:
        get_settings.cache_clear()
