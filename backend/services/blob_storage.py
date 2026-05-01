from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from config import Settings


@dataclass
class BlobUploadResult:
    blob_name: str
    blob_url: str


class AzureBlobStorageClient:
    def __init__(self, settings: Settings) -> None:
        self._account_url = settings.azure_blob_account_url.rstrip("/")
        self._account_key = settings.azure_blob_account_key.strip()
        self._container_name = settings.azure_blob_container_name.strip() or "presentations"
        self._service_client: BlobServiceClient | None = None
        self._container_ready = False

    @property
    def enabled(self) -> bool:
        return bool(self._account_url and self._account_key and self._container_name)

    def blob_url(self, blob_name: str) -> str:
        normalized = blob_name.lstrip("/")
        return f"{self._account_url}/{self._container_name}/{normalized}"

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

    def generate_upload_sas_url(self, *, blob_name: str, ttl_minutes: int = 30) -> str | None:
        if not self.enabled:
            return None
        self._ensure_container_sync()
        account_name = self._account_url.rstrip("/").split("/")[-1].split(".")[0]
        expiry = datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
        sas = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=blob_name.lstrip("/"),
            account_key=self._account_key,
            permission=BlobSasPermissions(read=True, create=True, write=True),
            expiry=expiry,
            content_type="application/octet-stream",
        )
        return f"{self.blob_url(blob_name)}?{sas}"

    def _upload_bytes_sync(
        self, blob_name: str, payload: bytes, content_type: str
    ) -> BlobUploadResult | None:
        self._ensure_container_sync()
        client = self._blob_client(blob_name)
        client.upload_blob(
            payload,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return BlobUploadResult(blob_name=blob_name, blob_url=self.blob_url(blob_name))

    def _download_bytes_sync(self, blob_name: str) -> bytes | None:
        self._ensure_container_sync()
        client = self._blob_client(blob_name)
        try:
            return client.download_blob().readall()
        except ResourceNotFoundError:
            return None

    def _blob_exists_sync(self, blob_name: str) -> bool:
        self._ensure_container_sync()
        client = self._blob_client(blob_name)
        try:
            return bool(client.exists())
        except ResourceNotFoundError:
            return False

    def _ensure_container_sync(self) -> None:
        if not self.enabled or self._container_ready:
            return
        service = self._blob_service_client()
        try:
            service.create_container(name=self._container_name)
        except ResourceExistsError:
            pass
        self._container_ready = True

    def _blob_service_client(self) -> BlobServiceClient:
        if self._service_client is None:
            self._service_client = BlobServiceClient(
                account_url=self._account_url,
                credential=self._account_key,
            )
        return self._service_client

    def _blob_client(self, blob_name: str):
        service = self._blob_service_client()
        return service.get_blob_client(
            container=self._container_name,
            blob=blob_name.lstrip("/"),
        )
