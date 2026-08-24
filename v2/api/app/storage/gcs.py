from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass
class UploadResult:
    blob_name: str
    url: str


class GcsClient:
    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._bucket = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.gcs_bucket)

    def _bucket_obj(self):
        if not self.enabled:
            return None
        if self._bucket is None:
            from google.cloud import storage

            self._client = storage.Client()
            self._bucket = self._client.bucket(self.settings.gcs_bucket)
        return self._bucket

    def blob_url(self, blob_name: str) -> str:
        return f"https://storage.googleapis.com/{self.settings.gcs_bucket}/{blob_name}"

    def upload_bytes(
        self, blob_name: str, payload: bytes, content_type: str = "application/octet-stream"
    ) -> UploadResult | None:
        bucket = self._bucket_obj()
        if not bucket:
            return None
        blob = bucket.blob(blob_name)
        blob.upload_from_string(payload, content_type=content_type)
        return UploadResult(blob_name=blob_name, url=self.blob_url(blob_name))

    def download_bytes(self, blob_name: str) -> bytes | None:
        bucket = self._bucket_obj()
        if not bucket:
            return None
        blob = bucket.blob(blob_name)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under prefix. Returns number deleted."""
        bucket = self._bucket_obj()
        if not bucket:
            return 0
        cleaned = prefix.strip("/")
        if cleaned and not cleaned.endswith("/"):
            cleaned = f"{cleaned}/"
        deleted = 0
        for blob in bucket.list_blobs(prefix=cleaned):
            blob.delete()
            deleted += 1
        return deleted
