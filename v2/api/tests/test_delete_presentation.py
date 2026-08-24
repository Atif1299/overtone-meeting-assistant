from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import create_app
from app.storage import PresentationStore


def test_delete_presentation_removes_row():
    with TestClient(create_app()) as client:
        from app.config import get_settings

        key = get_settings().admin_api_key or "dev-admin-key"
        headers = {"X-API-Key": key}

        db = SessionLocal()
        try:
            store = PresentationStore(db)
            store.create("del-test-pres", "delete-me.pdf")
        finally:
            db.close()

        listed = client.get("/api/v1/presentations", headers=headers)
        assert listed.status_code == 200
        assert any(p["presentation_id"] == "del-test-pres" for p in listed.json())

        deleted = client.delete("/api/v1/presentations/del-test-pres", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["ok"] is True

        missing = client.get("/api/v1/presentations/del-test-pres", headers=headers)
        assert missing.status_code == 404

        listed2 = client.get("/api/v1/presentations", headers=headers)
        assert listed2.status_code == 200
        assert not any(p["presentation_id"] == "del-test-pres" for p in listed2.json())
