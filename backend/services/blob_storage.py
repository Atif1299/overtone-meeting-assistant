from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from config import Settings


@dataclass
class BlobUploadResult:
    blob_name: str
    blob_url: str


class GcsStorageClient:
    def __init__(self, settings: Settings) -> None:
        self._bucket_name = (settings.gcs_bucket or "").strip()
        self._client = None
        self._bucket = None

    @property
    def enabled(self) -> bool:
        return bool(self._bucket_name)

    def blob_url(self, blob_name: str) -> str:
        normalized = blob_name.lstrip("/")
        return f"https://storage.googleapis.com/{self._bucket_name}/{normalized}"

    async def upload_bytes(
        self, *, blob_name: str, payload: bytes, content_type: str
    ) -> BlobUploadResult | None:
        if not self.enabled or not payload:
            return None
        return await asyncio.to_thread(
            self._upload_bytes_sync,
            blob_name,
            payload,
            content_type,
        )

    def upload_bytes_sync(
        self, *, blob_name: str, payload: bytes, content_type: str
    ) -> BlobUploadResult | None:
        if not self.enabled or not payload:
            return None
        return self._upload_bytes_sync(blob_name, payload, content_type)

    async def download_bytes(self, *, blob_name: str) -> bytes | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(self._download_bytes_sync, blob_name)

    def download_bytes_sync(self, *, blob_name: str) -> bytes | None:
        if not self.enabled:
            return None
        return self._download_bytes_sync(blob_name)

    async def blob_exists(self, *, blob_name: str) -> bool:
        if not self.enabled:
            return False
        return await asyncio.to_thread(self._blob_exists_sync, blob_name)

    def blob_exists_sync(self, *, blob_name: str) -> bool:
        if not self.enabled:
            return False
        return self._blob_exists_sync(blob_name)

    def list_blob_names(self, prefix: str = "") -> list[str]:
        if not self.enabled:
            return []
        bucket = self._gcs_client().bucket(self._bucket_name)
        return [blob.name for blob in bucket.list_blobs(prefix=prefix)]

    def generate_upload_sas_url(self, *, blob_name: str, ttl_minutes: int = 30) -> str | None:
        if not self.enabled:
            return None
        blob = self._blob(blob_name)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=max(1, ttl_minutes)),
            method="PUT",
        )

    def _upload_bytes_sync(
        self, blob_name: str, payload: bytes, content_type: str
    ) -> BlobUploadResult | None:
        blob = self._blob(blob_name)
        blob.upload_from_string(payload, content_type=content_type)
        return BlobUploadResult(blob_name=blob_name, blob_url=self.blob_url(blob_name))

    def _download_bytes_sync(self, blob_name: str) -> bytes | None:
        blob = self._blob(blob_name)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    def _blob_exists_sync(self, blob_name: str) -> bool:
        return bool(self._blob(blob_name).exists())

    def _gcs_client(self):
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client

    def _blob(self, blob_name: str):
        if self._bucket is None:
            self._bucket = self._gcs_client().bucket(self._bucket_name)
        return self._bucket.blob(blob_name.lstrip("/"))


AzureBlobStorageClient = GcsStorageClient
