from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.db.models import ApiKey
from app.http.auth import require_admin_key, require_api_key
from app.indexing.pipeline import run_index_job
from app.storage import PresentationStore

router = APIRouter(prefix="/api/v1/presentations", tags=["presentations"])


class PresentationOut(BaseModel):
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


@router.get("", response_model=list[PresentationOut])
def list_presentations(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    rows = PresentationStore(db).list_all(api_key.customer_id)
    return [PresentationOut(**r.to_dict()) for r in rows]


@router.post("", response_model=PresentationOut)
async def upload_presentation(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    settings = get_settings()
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    filename = file.filename or "deck.pdf"
    pid = str(uuid.uuid4())
    store = PresentationStore(db)
    customer_id = None if api_key.customer_id == "operator" else api_key.customer_id
    meta = store.create(pid, filename, customer_id=customer_id)
    store.save_source_bytes(pid, filename, data)
    background.add_task(run_index_job, pid)
    return PresentationOut(**meta.to_dict())


@router.get("/{presentation_id}", response_model=PresentationOut)
def get_presentation(
    presentation_id: str,
    db: Session = Depends(get_db),
):
    """Public read — presenter output-media browser has no API key."""
    meta = PresentationStore(db).get(presentation_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Not found")
    return PresentationOut(**meta.to_dict())


@router.post("/{presentation_id}/reindex", response_model=PresentationOut)
def reindex(
    presentation_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    store = PresentationStore(db)
    meta = store.get(presentation_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Not found")
    store.update(presentation_id, status="uploaded", index_error=None)
    background.add_task(run_index_job, presentation_id)
    return PresentationOut(**store.get(presentation_id).to_dict())


@router.delete("/{presentation_id}")
def delete_presentation(
    presentation_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    store = PresentationStore(db)
    meta = store.get(presentation_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Not found")
    if api_key.customer_id and api_key.customer_id != "operator":
        if meta.customer_id and meta.customer_id != api_key.customer_id:
            raise HTTPException(status_code=404, detail="Not found")
    ok = store.delete(presentation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "presentation_id": presentation_id}


@router.get("/{presentation_id}/pages/{page_number}/image")
def page_image(
    presentation_id: str,
    page_number: int,
    db: Session = Depends(get_db),
):
    path = PresentationStore(db).page_image_path(presentation_id, page_number)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(path, media_type="image/png")
