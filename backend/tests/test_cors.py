from __future__ import annotations


def test_cors_allows_vercel_preview_origins(client) -> None:
    origin = "https://overtone-dashboard-preview-123.vercel.app"
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origin(client) -> None:
    response = client.get("/health", headers={"Origin": "https://untrusted.example.com"})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None
