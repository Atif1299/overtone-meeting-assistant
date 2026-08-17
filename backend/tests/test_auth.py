from __future__ import annotations

from fastapi.testclient import TestClient


def test_customer_routes_open_when_admin_key_unset(client: TestClient) -> None:
    response = client.get("/api/v1/presentations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_admin_key_acts_as_operator_on_customer_routes(client: TestClient) -> None:
    from config import get_settings

    settings = get_settings()
    old = settings.admin_api_key
    settings.admin_api_key = "operator-secret"
    try:
        blocked = client.get("/api/v1/presentations")
        assert blocked.status_code == 401

        allowed = client.get(
            "/api/v1/presentations",
            headers={"X-API-Key": "operator-secret"},
        )
        assert allowed.status_code == 200
        assert isinstance(allowed.json(), list)

        bearer = client.get(
            "/api/agents",
            headers={"Authorization": "Bearer operator-secret"},
        )
        assert bearer.status_code == 200
    finally:
        settings.admin_api_key = old


def test_unknown_key_is_rejected_when_admin_configured(client: TestClient) -> None:
    from config import get_settings

    settings = get_settings()
    old = settings.admin_api_key
    settings.admin_api_key = "operator-secret"
    try:
        response = client.get(
            "/api/v1/presentations",
            headers={"X-API-Key": "not-the-admin-key"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.text
    finally:
        settings.admin_api_key = old
