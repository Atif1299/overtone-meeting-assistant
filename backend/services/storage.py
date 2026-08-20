"""Presentation storage with SQL catalog, local files, and GCS objects."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from config import get_settings
from models.presentation import PresentationSummary
from models.presentation_record import PresentationRecord
from services.aws_clients import get_dynamodb_resource
from services.blob_storage import AzureBlobStorageClient

logger = logging.getLogger(__name__)

_DEFAULT_PRESENTATIONS_ROOT = Path(__file__).resolve().parent.parent / "presentations"
_PRESENTATIONS_ROOT = Path(
    os.getenv("PRESENTATIONS_ROOT", str(_DEFAULT_PRESENTATIONS_ROOT))
).expanduser()
_META: dict[str, dict] = {}
_DISK_SCAN_DONE: bool = False

_SQL_FIELDS = (
    "filename",
    "status",
    "total_pages",
    "indexed_pages",
    "document_id",
    "azure_indexed_chunks",
    "metadata_provider",
    "metadata_model",
    "index_error",
)


def presentations_root() -> Path:
    _PRESENTATIONS_ROOT.mkdir(parents=True, exist_ok=True)
    return _PRESENTATIONS_ROOT


def _settings():
    return get_settings()


def _cloud_meta_enabled() -> bool:
    settings = _settings()
    return settings.storage_backend == "dynamodb" and bool(settings.aws_dynamodb_presentations_table)


def _gcs_enabled() -> bool:
    return _blob_client().enabled


def _derived_index_blob_name(presentation_id: str) -> str:
    return f"{presentation_id}/derived/index.json"


def _derived_chunks_blob_name(presentation_id: str) -> str:
    return f"{presentation_id}/derived/chunks.json"


def _derived_meta_blob_name(presentation_id: str) -> str:
    return f"{presentation_id}/derived/meta.json"


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
        "total_pages",
    ):
        if key in normalized and normalized[key] is not None:
            try:
                normalized[key] = int(normalized[key])
            except Exception:
                pass
    return normalized


def _ensure_dir(presentation_id: str) -> Path:
    dest_dir = presentations_root() / presentation_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


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

    dest_dir = _ensure_dir(presentation_id)
    (dest_dir / safe_name).write_bytes(data)
    (dest_dir / "index.json").write_text("[]")
    (dest_dir / "chunks.json").write_text("[]")

    if _gcs_enabled():
        blob = _blob_client()
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
    dest_dir = _ensure_dir(presentation_id)
    (dest_dir / "index.json").write_text("[]")
    (dest_dir / "chunks.json").write_text("[]")
    _put_meta(presentation_id, meta)
    return _summary_from_meta(presentation_id, meta)


def _has_source(presentation_id: str, meta: dict[str, Any]) -> bool:
    if str(meta.get("source_blob_name") or "").strip():
        return True
    filename = meta.get("filename")
    if not filename:
        return False
    path = _PRESENTATIONS_ROOT / presentation_id / str(filename)
    return path.is_file()


def list_presentations() -> list[PresentationSummary]:
    rows = _list_sql_rows()
    if rows is not None:
        out: list[PresentationSummary] = []
        for pid, meta in rows:
            if str(meta.get("status") or "") == "uploading" and not _has_source(pid, meta):
                continue
            _META[pid] = meta
            out.append(_summary_from_meta(pid, meta))
        return out

    if _cloud_meta_enabled():
        out = []
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
                if str(meta.get("status") or "") == "uploading" and not _has_source(pid, meta):
                    continue
                _META[pid] = meta
                out.append(_summary_from_meta(pid, meta))
            cursor = response.get("LastEvaluatedKey")
            if not cursor:
                break
        return out

    global _DISK_SCAN_DONE
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

    out = []
    for pid, m in _META.items():
        if str(m.get("status") or "") == "uploading" and not _has_source(pid, m):
            continue
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
    filename = meta.get("filename")
    if not filename:
        return None
    dest_dir = _ensure_dir(presentation_id)
    path = dest_dir / str(filename)
    if path.is_file():
        return path
    blob_name = str(meta.get("source_blob_name") or "").strip()
    if not blob_name:
        blob_name = f"{presentation_id}/source/{Path(str(filename)).name}"
    if not _gcs_enabled():
        return None
    data = _blob_client().download_bytes_sync(blob_name=blob_name)
    if not data:
        return None
    path.write_bytes(data)
    return path


def upload_temp_file_path(presentation_id: str) -> Path | None:
    d = presentation_dir(presentation_id)
    if not d:
        return None
    return d / "upload.tmp"


def save_index_pages(presentation_id: str, pages: list[dict[str, Any]]) -> None:
    payload = json.dumps(pages).encode("utf-8")
    dest_dir = _ensure_dir(presentation_id)
    (dest_dir / "index.json").write_bytes(payload)
    if _gcs_enabled():
        _blob_client().upload_bytes_sync(
            blob_name=_derived_index_blob_name(presentation_id),
            payload=payload,
            content_type="application/json",
        )


def save_chunk_rows(presentation_id: str, chunks: list[dict[str, Any]]) -> None:
    payload = json.dumps(chunks).encode("utf-8")
    dest_dir = _ensure_dir(presentation_id)
    (dest_dir / "chunks.json").write_bytes(payload)
    if _gcs_enabled():
        _blob_client().upload_bytes_sync(
            blob_name=_derived_chunks_blob_name(presentation_id),
            payload=payload,
            content_type="application/json",
        )


def load_index_pages(presentation_id: str) -> list[dict[str, Any]]:
    d = presentation_dir(presentation_id)
    if d:
        index_file = d / "index.json"
        if index_file.is_file():
            try:
                data = json.loads(index_file.read_text())
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
    if _gcs_enabled():
        payload = _blob_client().download_bytes_sync(blob_name=_derived_index_blob_name(presentation_id))
        if payload:
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception:
                return []
            return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    return []


def load_chunk_rows(presentation_id: str) -> list[dict[str, Any]]:
    d = presentation_dir(presentation_id)
    if d:
        chunk_file = d / "chunks.json"
        if chunk_file.is_file():
            try:
                data = json.loads(chunk_file.read_text())
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
    if _gcs_enabled():
        payload = _blob_client().download_bytes_sync(blob_name=_derived_chunks_blob_name(presentation_id))
        if payload:
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception:
                return []
            return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    return []


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
    dest_dir = _ensure_dir(presentation_id)
    candidates = [
        dest_dir / "pages" / f"page_{page_number}.png",
        dest_dir / f"page_{page_number}.png",
        dest_dir / f"slide_{page_number}.png",
        dest_dir / f"{page_number}.png",
    ]
    for p in candidates:
        if p.is_file():
            return p
    if not _gcs_enabled():
        return None
    blob_names = [
        f"{presentation_id}/images/page_{page_number}.png",
        f"{presentation_id}/pages/page_{page_number}.png",
    ]
    local = dest_dir / "pages" / f"page_{page_number}.png"
    local.parent.mkdir(parents=True, exist_ok=True)
    for blob_name in blob_names:
        data = _blob_client().download_bytes_sync(blob_name=blob_name)
        if data:
            local.write_bytes(data)
            return local
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


def _row_to_meta(row: PresentationRecord) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if row.extra_json:
        try:
            parsed = json.loads(row.extra_json)
            if isinstance(parsed, dict):
                extra = parsed
        except json.JSONDecodeError:
            extra = {}
    meta = {
        "filename": row.filename,
        "status": row.status,
        "total_pages": row.total_pages,
        "indexed_pages": int(row.indexed_pages or 0),
        "document_id": row.document_id,
        "azure_indexed_chunks": row.azure_indexed_chunks,
        "metadata_provider": row.metadata_provider,
        "metadata_model": row.metadata_model,
        "index_error": row.index_error,
        **extra,
    }
    return _normalize_meta(meta)


def _list_sql_rows() -> list[tuple[str, dict[str, Any]]] | None:
    try:
        from database import SessionLocal
    except Exception:
        return None
    session = SessionLocal()
    try:
        rows = session.query(PresentationRecord).all()
        return [(str(row.presentation_id), _row_to_meta(row)) for row in rows]
    except Exception as exc:
        logger.warning("SQL catalog list failed: %s", exc)
        return None
    finally:
        session.close()


def _put_sql(presentation_id: str, meta: dict[str, Any]) -> None:
    from database import SessionLocal

    extra = {key: value for key, value in meta.items() if key not in _SQL_FIELDS}
    session = SessionLocal()
    try:
        row = session.get(PresentationRecord, presentation_id)
        if row is None:
            row = PresentationRecord(presentation_id=presentation_id)
            session.add(row)
        row.filename = str(meta.get("filename") or "unknown")
        row.status = str(meta.get("status") or "unknown")
        row.total_pages = meta.get("total_pages")
        row.indexed_pages = int(meta.get("indexed_pages", 0) or 0)
        row.document_id = meta.get("document_id")
        row.azure_indexed_chunks = meta.get("azure_indexed_chunks")
        row.metadata_provider = meta.get("metadata_provider")
        row.metadata_model = meta.get("metadata_model")
        row.index_error = meta.get("index_error")
        row.extra_json = json.dumps(extra)
        session.commit()
    finally:
        session.close()


def _load_sql(presentation_id: str) -> dict[str, Any] | None:
    from database import SessionLocal

    session = SessionLocal()
    try:
        row = session.get(PresentationRecord, presentation_id)
        if row is None:
            return None
        return _row_to_meta(row)
    except Exception as exc:
        logger.warning("SQL catalog load failed: %s", exc)
        return None
    finally:
        session.close()


def _put_meta(presentation_id: str, meta: dict[str, Any]) -> None:
    normalized = _normalize_meta(meta)
    _META[presentation_id] = dict(normalized)
    _put_sql(presentation_id, normalized)
    _write_meta_local(presentation_id, normalized)
    if _gcs_enabled():
        payload = json.dumps(normalized).encode("utf-8")
        try:
            _blob_client().upload_bytes_sync(
                blob_name=_derived_meta_blob_name(presentation_id),
                payload=payload,
                content_type="application/json",
            )
        except Exception as exc:
            logger.warning("GCS meta upload failed for %s: %s", presentation_id, exc)
    if _cloud_meta_enabled():
        table = _ddb_table()
        item = {"presentation_id": presentation_id, **normalized}
        table.put_item(Item=item)


def _load_meta(presentation_id: str) -> dict[str, Any] | None:
    loaded = _load_sql(presentation_id)
    if loaded:
        return loaded
    if _cloud_meta_enabled():
        table = _ddb_table()
        response = table.get_item(Key={"presentation_id": presentation_id})
        item = response.get("Item")
        if item:
            return _normalize_meta(item)
    local = _load_meta_local(presentation_id)
    if local:
        return _normalize_meta(local)
    if _gcs_enabled():
        payload = _blob_client().download_bytes_sync(blob_name=_derived_meta_blob_name(presentation_id))
        if payload:
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception:
                return None
            return _normalize_meta(data) if isinstance(data, dict) else None
    return None


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
    dest_dir = _ensure_dir(presentation_id)
    safe_name = Path(filename).name
    final_path = dest_dir / safe_name
    final_path.write_bytes(data)
    temp_path = upload_temp_file_path(presentation_id)
    if temp_path and temp_path.exists():
        temp_path.unlink()
    updates: dict[str, Any] = {"status": "uploaded", "filename": safe_name}
    if _gcs_enabled():
        uploaded = _blob_client().upload_bytes_sync(
            blob_name=f"{presentation_id}/source/{safe_name}",
            payload=data,
            content_type="application/octet-stream",
        )
        if uploaded:
            updates["source_blob_name"] = uploaded.blob_name
            updates["source_blob_url"] = uploaded.blob_url
    update_presentation_meta(presentation_id, **updates)


def _pgvector_chunk_count(document_id: str) -> int:
    settings = _settings()
    if not settings.database_url or "postgres" not in settings.database_url.lower():
        return 0
    from sqlalchemy import text

    from database import engine

    try:
        with engine.connect() as conn:
            value = conn.execute(
                text("SELECT COUNT(*) FROM presentation_chunks WHERE document_id = :d"),
                {"d": document_id},
            ).scalar()
        return int(value or 0)
    except Exception as exc:
        logger.warning("pgvector chunk count failed for %s: %s", document_id, exc)
        return 0


def recover_catalog_from_gcs() -> int:
    """Upsert missing catalog rows from GCS prefixes. Returns recovered count."""
    if not _gcs_enabled():
        return 0
    try:
        names = _blob_client().list_blob_names()
    except Exception as exc:
        logger.warning("GCS catalog recover list failed: %s", exc)
        return 0

    prefixes: dict[str, list[str]] = {}
    for name in names:
        pid = name.split("/", 1)[0].strip()
        if not pid:
            continue
        prefixes.setdefault(pid, []).append(name)

    recovered = 0
    pending_index: list[str] = []
    for pid, blob_names in prefixes.items():
        existing = _load_sql(pid)
        if existing:
            continue
        source_blobs = [n for n in blob_names if n.startswith(f"{pid}/source/")]
        filename = Path(source_blobs[0]).name if source_blobs else f"{pid}.bin"
        source_blob_name = source_blobs[0] if source_blobs else ""
        chunk_count = _pgvector_chunk_count(pid)
        if chunk_count > 0:
            meta = {
                "filename": filename,
                "status": "ready",
                "total_pages": chunk_count,
                "indexed_pages": chunk_count,
                "index_error": None,
                "document_id": pid,
                "azure_indexed_chunks": chunk_count,
                "metadata_provider": "openai",
                "metadata_model": "gpt-4o",
                "source_blob_name": source_blob_name,
            }
        else:
            meta = {
                "filename": filename,
                "status": "uploaded",
                "total_pages": None,
                "indexed_pages": 0,
                "index_error": None,
                "document_id": pid,
                "azure_indexed_chunks": 0,
                "metadata_provider": None,
                "metadata_model": None,
                "source_blob_name": source_blob_name,
            }
            if source_blob_name:
                pending_index.append(pid)
        _put_meta(pid, meta)
        recovered += 1

    if pending_index:
        from services.index_jobs import dispatch_index_job

        for pid in pending_index:
            try:
                dispatch_index_job(pid)
            except Exception as exc:
                logger.warning("Recover reindex dispatch failed for %s: %s", pid, exc)
    return recovered


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
