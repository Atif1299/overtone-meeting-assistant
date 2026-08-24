from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.db.models import Presentation
from app.indexing.vector_store import delete_document_chunks
from app.storage.gcs import GcsClient


def presentations_root() -> Path:
    root = Path(get_settings().presentations_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def presentation_dir(presentation_id: str) -> Path:
    d = presentations_root() / presentation_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "pages").mkdir(exist_ok=True)
    return d


def gcs_key(*parts: str) -> str:
    prefix = get_settings().gcs_prefix.strip("/")
    return "/".join([prefix, "presentations", *[p.strip("/") for p in parts if p]])


@dataclass
class PresentationMeta:
    presentation_id: str
    filename: str
    status: str
    total_pages: int | None = None
    indexed_pages: int = 0
    indexed_chunks: int | None = None
    metadata_provider: str | None = None
    metadata_model: str | None = None
    index_error: str | None = None
    customer_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "presentation_id": self.presentation_id,
            "filename": self.filename,
            "status": self.status,
            "total_pages": self.total_pages,
            "indexed_pages": self.indexed_pages,
            "indexed_chunks": self.indexed_chunks,
            "metadata_provider": self.metadata_provider,
            "metadata_model": self.metadata_model,
            "index_error": self.index_error,
            "customer_id": self.customer_id,
        }


class PresentationStore:
    def __init__(self, db: DbSession):
        self.db = db
        self.gcs = GcsClient()

    def create(self, presentation_id: str, filename: str, customer_id: str | None = None) -> PresentationMeta:
        row = Presentation(
            presentation_id=presentation_id,
            filename=filename,
            status="uploaded",
            customer_id=customer_id,
        )
        self.db.merge(row)
        self.db.commit()
        meta = PresentationMeta(
            presentation_id=presentation_id,
            filename=filename,
            status="uploaded",
            customer_id=customer_id,
        )
        self._write_meta_file(meta)
        return meta

    def get(self, presentation_id: str) -> PresentationMeta | None:
        row = self.db.get(Presentation, presentation_id)
        if not row:
            return None
        return PresentationMeta(
            presentation_id=row.presentation_id,
            filename=row.filename,
            status=row.status,
            total_pages=row.total_pages,
            indexed_pages=row.indexed_pages or 0,
            indexed_chunks=row.indexed_chunks,
            metadata_provider=row.metadata_provider,
            metadata_model=row.metadata_model,
            index_error=row.index_error,
            customer_id=row.customer_id,
        )

    def list_all(self, customer_id: str | None = None) -> list[PresentationMeta]:
        q = self.db.query(Presentation).order_by(Presentation.created_at.desc())
        if customer_id and customer_id != "operator":
            q = q.filter(Presentation.customer_id == customer_id)
        return [
            PresentationMeta(
                presentation_id=r.presentation_id,
                filename=r.filename,
                status=r.status,
                total_pages=r.total_pages,
                indexed_pages=r.indexed_pages or 0,
                indexed_chunks=r.indexed_chunks,
                metadata_provider=r.metadata_provider,
                metadata_model=r.metadata_model,
                index_error=r.index_error,
                customer_id=r.customer_id,
            )
            for r in q.all()
        ]

    def update(self, presentation_id: str, **fields) -> PresentationMeta | None:
        row = self.db.get(Presentation, presentation_id)
        if not row:
            return None
        for k, v in fields.items():
            if hasattr(row, k):
                setattr(row, k, v)
        self.db.commit()
        meta = self.get(presentation_id)
        if meta:
            self._write_meta_file(meta)
        return meta

    def delete(self, presentation_id: str) -> bool:
        """Remove presentation row, pgvector chunks, local files, and GCS objects."""
        row = self.db.get(Presentation, presentation_id)
        if not row:
            return False

        try:
            delete_document_chunks(presentation_id)
        except Exception:
            pass

        self.db.delete(row)
        self.db.commit()

        local = presentations_root() / presentation_id
        if local.exists():
            shutil.rmtree(local, ignore_errors=True)

        try:
            self.gcs.delete_prefix(gcs_key(presentation_id))
        except Exception:
            pass

        return True

    def save_source_bytes(self, presentation_id: str, filename: str, data: bytes) -> Path:
        d = presentation_dir(presentation_id)
        path = d / filename
        path.write_bytes(data)
        self.gcs.upload_bytes(gcs_key(presentation_id, "source", filename), data)
        return path

    def source_path(self, presentation_id: str) -> Path | None:
        meta = self.get(presentation_id)
        if not meta:
            return None
        d = presentation_dir(presentation_id)
        local = d / meta.filename
        if local.exists():
            return local
        data = self.gcs.download_bytes(gcs_key(presentation_id, "source", meta.filename))
        if data:
            local.write_bytes(data)
            return local
        # any file in dir except known folders
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in {".pdf", ".pptx", ".ppt"}:
                return p
        return None

    def save_page_image(self, presentation_id: str, page_number: int, png_path: Path) -> None:
        dest = presentation_dir(presentation_id) / "pages" / f"page_{page_number}.png"
        if png_path.resolve() != dest.resolve():
            dest.write_bytes(png_path.read_bytes())
        self.gcs.upload_bytes(
            gcs_key(presentation_id, "images", f"page_{page_number}.png"),
            dest.read_bytes(),
            content_type="image/png",
        )

    def page_image_path(self, presentation_id: str, page_number: int) -> Path | None:
        local = presentation_dir(presentation_id) / "pages" / f"page_{page_number}.png"
        if local.exists():
            return local
        data = self.gcs.download_bytes(gcs_key(presentation_id, "images", f"page_{page_number}.png"))
        if data:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
            return local
        return None

    def save_index(self, presentation_id: str, pages: list[dict], chunks: list[dict]) -> None:
        d = presentation_dir(presentation_id)
        (d / "index.json").write_text(json.dumps(pages), encoding="utf-8")
        (d / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
        self.gcs.upload_bytes(
            gcs_key(presentation_id, "derived", "index.json"),
            json.dumps(pages).encode(),
            content_type="application/json",
        )
        self.gcs.upload_bytes(
            gcs_key(presentation_id, "derived", "chunks.json"),
            json.dumps(chunks).encode(),
            content_type="application/json",
        )

    def load_index_pages(self, presentation_id: str) -> list[dict]:
        path = presentation_dir(presentation_id) / "index.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.gcs.download_bytes(gcs_key(presentation_id, "derived", "index.json"))
        if data:
            return json.loads(data.decode("utf-8"))
        return []

    def _write_meta_file(self, meta: PresentationMeta) -> None:
        path = presentation_dir(meta.presentation_id) / "meta.json"
        path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")
        self.gcs.upload_bytes(
            gcs_key(meta.presentation_id, "derived", "meta.json"),
            json.dumps(meta.to_dict()).encode(),
            content_type="application/json",
        )
