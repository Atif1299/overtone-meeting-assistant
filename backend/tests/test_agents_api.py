from __future__ import annotations

from fastapi.testclient import TestClient


def test_agents_default_seed_exists(client: TestClient) -> None:
    response = client.get("/api/agents")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(agent["agent_name"] == "default" for agent in payload)


def test_agents_create_and_activate_versions(client: TestClient) -> None:
    upload = client.post(
        "/api/upload",
        files={"file": ("deck.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert upload.status_code == 200
    presentation_id = upload.json()["presentation_id"]

    create_v1 = client.post(
        "/api/agents/support/versions",
        json={
            "system_prompt": "You are support agent v1.",
            "presentation_id": presentation_id,
            "activate": True,
        },
    )
    assert create_v1.status_code == 200
    assert create_v1.json()["version_number"] == 1
    assert create_v1.json()["is_active"] is True
    assert create_v1.json()["presentation_id"] == presentation_id

    create_v2 = client.post(
        "/api/agents/support/versions",
        json={"system_prompt": "You are support agent v2.", "activate": False},
    )
    assert create_v2.status_code == 200
    assert create_v2.json()["version_number"] == 2
    assert create_v2.json()["is_active"] is False

    versions_before = client.get("/api/agents/support/versions")
    assert versions_before.status_code == 200
    payload_before = versions_before.json()
    assert payload_before[0]["version_number"] == 2
    assert payload_before[1]["version_number"] == 1
    assert payload_before[1]["is_active"] is True
    assert payload_before[1]["presentation_id"] == presentation_id

    activate_v2 = client.post("/api/agents/support/activate", json={"version_number": 2})
    assert activate_v2.status_code == 200
    assert activate_v2.json()["version_number"] == 2
    assert activate_v2.json()["is_active"] is True

    versions_after = client.get("/api/agents/support/versions")
    assert versions_after.status_code == 200
    payload_after = versions_after.json()
    assert payload_after[0]["version_number"] == 2
    assert payload_after[0]["is_active"] is True
    assert payload_after[1]["version_number"] == 1
    assert payload_after[1]["is_active"] is False


def test_agents_reject_unknown_presentation(client: TestClient) -> None:
    response = client.post(
        "/api/agents/research/versions",
        json={
            "system_prompt": "You answer from docs only.",
            "presentation_id": "missing-presentation-id",
            "activate": True,
        },
    )
    assert response.status_code == 404
    assert "not found" in response.text.lower()
