from __future__ import annotations

from app.config import CANONICAL_CORS_ORIGINS, Settings, cors_origin_list
from app.main import create_app
from fastapi.testclient import TestClient


def test_cors_origin_list_includes_live_dashboard_when_env_is_localhost_only():
    settings = Settings(
        cors_allowed_origins="http://127.0.0.1:5176,http://localhost:5176",
        dashboard_url="http://127.0.0.1:5176",
        frontend_url="http://127.0.0.1:5175",
        marketing_url="http://127.0.0.1:5177",
    )
    origins = cors_origin_list(settings)
    assert "https://deckvoice-v2-dashboard-4idrhaffca-uc.a.run.app" in origins
    assert "https://deckvoice-v2-dashboard-95044197271.us-central1.run.app" in origins
    for origin in CANONICAL_CORS_ORIGINS:
        assert origin in origins


def test_preflight_allows_live_dashboard_origin():
    with TestClient(create_app()) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://deckvoice-v2-dashboard-4idrhaffca-uc.a.run.app",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://deckvoice-v2-dashboard-4idrhaffca-uc.a.run.app"
        )
