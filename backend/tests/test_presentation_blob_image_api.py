from __future__ import annotations

from fastapi.testclient import TestClient

from api import presentations as presentations_api
from services import storage as storage_mod


def test_slide_image_endpoint_reads_from_blob_when_available(
    client: TestClient, monkeypatch
) -> None:
    uploaded = storage_mod.save_upload("deck.pdf", b"%PDF-1.4 fake content")
    storage_mod.save_index_pages(
        uploaded.presentation_id,
        [
            {
                "page_number": 1,
                "title": "Page 1",
                "content_text": "Blob-backed preview page",
                "searchable_content": "Blob-backed preview page",
                "image_blob_name": f"{uploaded.presentation_id}/pages/page_1.png",
                "image_blob_url": "https://blob.example/page_1.png",
            }
        ],
    )

    class FakeBlobStorageClient:
        def __init__(self, _settings) -> None:
            pass

        @property
        def enabled(self) -> bool:
            return True

        async def download_bytes(self, *, blob_name: str):
            assert blob_name.endswith("/page_1.png")
            return b"\x89PNG\r\n\x1a\nfake"

    monkeypatch.setattr(
        presentations_api,
        "AzureBlobStorageClient",
        FakeBlobStorageClient,
    )

    response = client.get(f"/api/presentations/{uploaded.presentation_id}/page/1/image")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")
