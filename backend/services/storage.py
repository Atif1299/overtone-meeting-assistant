"""Presentation storage with local and DynamoDB-backed metadata support."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from config import get_settings
from models.presentation import PresentationSummary
from services.aws_clients import get_dynamodb_resource
from services.blob_storage import AzureBlobStorageClient

_DEFAULT_PRESENTATIONS_ROOT = Path(__file__).resolve().parent.parent / "presentations"
_PRESENTATIONS_ROOT = Path(
    os.getenv("PRESENTATIONS_ROOT", str(_DEFAULT_PRESENTATIONS_ROOT))
).expanduser()
_META: dict[str, dict] = {}
_DISK_SCAN_DONE: bool = False  # True after first full scan — prevents re-scanning on every call


def presentations_root() -> Path:
    _PRESENTATIONS_ROOT.mkdir(parents=True, exist_ok=True)
    return _PRESENTATIONS_ROOT


def _settings():
    return get_settings()


def _cloud_meta_enabled() -> bool:
    settings = _settings()
    return settings.storage_backend == "dynamodb" and bool(settings.aws_dynamodb_presentations_table)


def _derived_index_blob_name(presentation_id: str) -> str:
    return f"{presentation_id}/derived/index.json"


def _derived_chunks_blob_name(presentation_id: str) -> str:
    return f"{presentation_id}/derived/chunks.json"


def _blob_client() -> AzureBlobStorageClient:
    return AzureBlobStorageClient(_settings())


def _ddb_table():
    settings = _settings()
    return get_dynamodb_resource(settings).Table(settings.aws_dynamodb_presentations_table)


def _normalize_meta(loaded: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(loaded)
    for key in (
        "indexed_pages",
        "azure_indexed_chunks",
        "upload_received_bytes",
        "upload_next_chunk_index",
        "upload_total_chunks",
    ):
        if key in normalized and normalized[key] is not None:
            try:
                normalized[key] = int(normalized[key])
            except Exception:
                pass
    return normalized


def register_presentation(
    presentation_id: str,
    filename: str,
    *,
    status: str = "ready",
    total_pages: int = 1,
    indexed_pages: int = 1,
) -> PresentationSummary:
    meta = {
        "filename": filename,
        "status": status,
        "total_pages": total_pages,
        "indexed_pages": indexed_pages,
        "index_error": None,
        "document_id": presentation_id,
        "azure_indexed_chunks": 0,
        "metadata_provider": None,
        "metadata_model": None,
    }
    _put_meta(presentation_id, meta)
    return _summary_from_meta(presentation_id, meta)


def save_upload(filename: str, data: bytes) -> PresentationSummary:
    safe_name = Path(filename).name
    presentation_id = str(uuid.uuid4())
    meta = {
        "filename": safe_name,
        "status": "uploaded",
        "total_pages": None,
        "indexed_pages": 0,
        "index_error": None,
        "document_id": presentation_id,
        "azure_indexed_chunks": 0,
        "metadata_provider": None,
        "metadata_model": None,
    }

    if _cloud_meta_enabled():
        blob = _blob_client()
        if blob.enabled:
            source_blob_name = f"{presentation_id}/source/{safe_name}"
            uploaded = blob.upload_bytes_sync(
                blob_name=source_blob_name,
                payload=data,
                content_type="application/octet-stream",
            )
            if uploaded:
                meta["source_blob_name"] = uploaded.blob_name
                meta["source_blob_url"] = uploaded.blob_url
        _put_meta(presentation_id, meta)
        return _summary_from_meta(presentation_id, meta)

    presentations_root()
    dest_dir = _PRESENTATIONS_ROOT / presentation_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / safe_name).write_bytes(data)
    (dest_dir / "index.json").write_text("[]")
    (dest_dir / "chunks.json").write_text("[]")
    _put_meta(presentation_id, meta)
    return _summary_from_meta(presentation_id, meta)


def create_upload_slot(filename: str) -> PresentationSummary:
    safe_name = Path(filename).name
    presentation_id = str(uuid.uuid4())
    meta = {
        "filename": safe_name,
        "status": "uploading",
        "total_pages": None,
        "indexed_pages": 0,
        "index_error": None,
        "document_id": presentation_id,
        "azure_indexed_chunks": 0,
        "metadata_provider": None,
        "metadata_model": None,
        "upload_received_bytes": 0,
        "upload_next_chunk_index": 0,
        "upload_total_chunks": None,
    }
    presentations_root()
    dest_dir = _PRESENTATIONS_ROOT / presentation_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "index.json").write_text("[]")
    (dest_dir / "chunks.json").write_text("[]")
    _put_meta(presentation_id, meta)
    return _summary_from_meta(presentation_id, meta)


def list_presentations() -> list[PresentationSummary]:
    if _cloud_meta_enabled():
        out: list[PresentationSummary] = []
        table = _ddb_table()
        cursor: dict[str, Any] | None = None
        while True:
            kwargs = {"ExclusiveStartKey": cursor} if cursor else {}
            response = table.scan(**kwargs)
            for item in response.get("Items", []):
                pid = str(item.get("presentation_id") or "")
                if not pid:
                    continue
                meta = _normalize_meta(item)
                _META[pid] = meta
                out.append(_summary_from_meta(pid, meta))
            cursor = response.get("LastEvaluatedKey")
            if not cursor:
                break
        return out

    global _DISK_SCAN_DONE

    # On first call after server start, scan disk to recover presentations from
    # previous sessions. Uses setdefault so in-memory (newer) state wins over disk.
    if not _DISK_SCAN_DONE and _PRESENTATIONS_ROOT.exists():
        _DISK_SCAN_DONE = True
        for p in _PRESENTATIONS_ROOT.iterdir():
            if p.is_dir() and (p / "meta.json").is_file():
                try:
                    m = _load_meta_local(p.name)
                    if not m:
                        continue
                    _META.setdefault(p.name, m)
                except (json.JSONDecodeError, KeyError):
                    continue

    out: list[PresentationSummary] = []
    for pid, m in _META.items():
        out.append(_summary_from_meta(pid, m))
    return out


def get_presentation(presentation_id: str) -> PresentationSummary | None:
    if presentation_id in _META:
        m = _META[presentation_id]
        return _summary_from_meta(presentation_id, m)
    m = _load_meta(presentation_id)
    if m:
        _META[presentation_id] = m
        return _summary_from_meta(presentation_id, m)
    return None


def get_presentation_meta(presentation_id: str) -> dict[str, Any] | None:
    meta = _META.get(presentation_id)
    if meta:
        return dict(meta)
    loaded = _load_meta(presentation_id)
    if loaded:
        _META[presentation_id] = loaded
        return dict(loaded)
    return None


def update_presentation_meta(presentation_id: str, **updates: Any) -> PresentationSummary | None:
    base = get_presentation_meta(presentation_id)
    if not base:
        return None
    base.update(updates)
    _put_meta(presentation_id, base)
    return get_presentation(presentation_id)


def presentation_dir(presentation_id: str) -> Path | None:
    d = _PRESENTATIONS_ROOT / presentation_id
    return d if d.is_dir() else None


def source_file_path(presentation_id: str) -> Path | None:
    meta = get_presentation_meta(presentation_id)
    if not meta:
        return None
    d = presentation_dir(presentation_id)
    if not d:
        return None
    filename = meta.get("filename")
    if not filename:
        return None
    path = d / str(filename)
    if path.is_file():
        return path
    if _cloud_meta_enabled():
        return None
    return None


def upload_temp_file_path(presentation_id: str) -> Path | None:
    d = presentation_dir(presentation_id)
    if not d:
        return None
    return d / "upload.tmp"


def save_index_pages(presentation_id: str, pages: list[dict[str, Any]]) -> None:
    if _cloud_meta_enabled():
        blob = _blob_client()
        payload = json.dumps(pages).encode("utf-8")
        if blob.enabled:
            blob.upload_bytes_sync(
                blob_name=_derived_index_blob_name(presentation_id),
                payload=payload,
                content_type="application/json",
            )
            return
    d = presentation_dir(presentation_id)
    if not d:
        return
    (d / "index.json").write_text(json.dumps(pages))


def save_chunk_rows(presentation_id: str, chunks: list[dict[str, Any]]) -> None:
    if _cloud_meta_enabled():
        blob = _blob_client()
        payload = json.dumps(chunks).encode("utf-8")
        if blob.enabled:
            blob.upload_bytes_sync(
                blob_name=_derived_chunks_blob_name(presentation_id),
                payload=payload,
                content_type="application/json",
            )
            return
    d = presentation_dir(presentation_id)
    if not d:
        return
    (d / "chunks.json").write_text(json.dumps(chunks))


def load_index_pages(presentation_id: str) -> list[dict[str, Any]]:
    if _cloud_meta_enabled():
        blob = _blob_client()
        if blob.enabled:
            payload = blob.download_bytes_sync(blob_name=_derived_index_blob_name(presentation_id))
            if not payload:
                return []
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception:
                return []
            return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    d = presentation_dir(presentation_id)
    if not d:
        return []
    index_file = d / "index.json"
    if not index_file.is_file():
        return []
    try:
        data = json.loads(index_file.read_text())
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def load_chunk_rows(presentation_id: str) -> list[dict[str, Any]]:
    if _cloud_meta_enabled():
        blob = _blob_client()
        if blob.enabled:
            payload = blob.download_bytes_sync(blob_name=_derived_chunks_blob_name(presentation_id))
            if not payload:
                return []
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception:
                return []
            return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    d = presentation_dir(presentation_id)
    if not d:
        return []
    chunk_file = d / "chunks.json"
    if not chunk_file.is_file():
        return []
    try:
        data = json.loads(chunk_file.read_text())
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def load_provided_metadata(presentation_id: str) -> dict[str, Any] | None:
    """Load the user-provided metadata JSON if it exists."""
    d = presentation_dir(presentation_id)
    if not d:
        return None
    provided_file = d / "provided_metadata.json"
    if not provided_file.is_file():
        return None
    try:
        data = json.loads(provided_file.read_text())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def slide_image_path(presentation_id: str, page_number: int) -> Path | None:
    d = presentation_dir(presentation_id)
    if not d:
        return None
    candidates = [
        d / "pages" / f"page_{page_number}.png",  # Vision pipeline output
        d / f"page_{page_number}.png",
        d / f"slide_{page_number}.png",
        d / f"{page_number}.png",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _meta_path(presentation_id: str) -> Path:
    return presentations_root() / presentation_id / "meta.json"


def _write_meta_local(presentation_id: str, meta: dict[str, Any]) -> None:
    path = _meta_path(presentation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta))


def _load_meta_local(presentation_id: str) -> dict[str, Any] | None:
    path = _meta_path(presentation_id)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _put_meta(presentation_id: str, meta: dict[str, Any]) -> None:
    normalized = _normalize_meta(meta)
    _META[presentation_id] = dict(normalized)
    if _cloud_meta_enabled():
        table = _ddb_table()
        item = {"presentation_id": presentation_id, **normalized}
        table.put_item(Item=item)
    else:
        _write_meta_local(presentation_id, normalized)


def _load_meta(presentation_id: str) -> dict[str, Any] | None:
    if _cloud_meta_enabled():
        table = _ddb_table()
        response = table.get_item(Key={"presentation_id": presentation_id})
        item = response.get("Item")
        if not item:
            return None
        return _normalize_meta(item)
    return _load_meta_local(presentation_id)


def append_upload_chunk(presentation_id: str, chunk_index: int, data: bytes) -> None:
    """Append a chunk of bytes to the in-progress upload temp file."""
    temp_path = upload_temp_file_path(presentation_id)
    if not temp_path:
        return
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    if chunk_index == 0 and temp_path.exists():
        temp_path.unlink()
    with temp_path.open("ab") as fh:
        fh.write(data)


def assemble_upload_chunks(presentation_id: str) -> bytes | None:
    """Read and return the assembled temp file bytes, or None if not present."""
    temp_path = upload_temp_file_path(presentation_id)
    if not temp_path or not temp_path.is_file() or temp_path.stat().st_size == 0:
        return None
    return temp_path.read_bytes()


def save_assembled_upload(presentation_id: str, filename: str, data: bytes) -> None:
    """Write the assembled bytes as the canonical source file and clean up temp."""
    dest_dir = presentation_dir(presentation_id)
    if not dest_dir:
        return
    final_path = dest_dir / Path(filename).name
    final_path.write_bytes(data)
    temp_path = upload_temp_file_path(presentation_id)
    if temp_path and temp_path.exists():
        temp_path.unlink()
    update_presentation_meta(presentation_id, status="uploaded", filename=Path(filename).name)


def _summary_from_meta(presentation_id: str, meta: dict[str, Any]) -> PresentationSummary:
    return PresentationSummary(
        presentation_id=presentation_id,
        filename=str(meta.get("filename") or "unknown"),
        status=str(meta.get("status") or "unknown"),
        total_pages=meta.get("total_pages"),
        indexed_pages=int(meta.get("indexed_pages", 0) or 0),
        document_id=meta.get("document_id"),
        azure_indexed_chunks=meta.get("azure_indexed_chunks"),
        metadata_provider=meta.get("metadata_provider"),
        metadata_model=meta.get("metadata_model"),
        index_error=meta.get("index_error"),
    )
