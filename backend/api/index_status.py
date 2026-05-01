from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_customer_key
from config import Settings, get_settings
from services.index_jobs import dispatch_index_job
from services import storage as storage_mod

router = APIRouter(prefix="/api", tags=["deprecated"], dependencies=[Depends(require_customer_key)])


class IndexStatusResponse(BaseModel):
    presentation_id: str
    status: str
    indexed_pages: int
    total_pages: Optional[int] = None
    index_error: Optional[str] = None
    document_id: Optional[str] = None
    azure_indexed_chunks: Optional[int] = None
    metadata_provider: Optional[str] = None
    metadata_model: Optional[str] = None
    pages: Optional[List[dict]] = None


@router.get("/index-status/{presentation_id}", response_model=IndexStatusResponse, deprecated=True)
async def index_status(presentation_id: str) -> IndexStatusResponse:
    p = storage_mod.get_presentation(presentation_id)
    if not p:
        raise HTTPException(404, "Presentation not found")
    meta = storage_mod.get_presentation_meta(presentation_id) or {}
    return IndexStatusResponse(
        presentation_id=p.presentation_id,
        status=p.status,
        indexed_pages=p.indexed_pages,
        total_pages=p.total_pages,
        index_error=meta.get("index_error"),
        document_id=meta.get("document_id"),
        azure_indexed_chunks=meta.get("azure_indexed_chunks"),
        metadata_provider=meta.get("metadata_provider"),
        metadata_model=meta.get("metadata_model"),
        pages=storage_mod.load_index_pages(presentation_id) if p.status == "ready" else None,
    )


@router.post("/index-status/{presentation_id}/run", response_model=IndexStatusResponse, deprecated=True)
async def run_indexing(
    presentation_id: str,
    settings: Settings = Depends(get_settings),
) -> IndexStatusResponse:
    p = storage_mod.get_presentation(presentation_id)
    if not p:
        raise HTTPException(404, "Presentation not found")
    dispatch_index_job(presentation_id)
    return await index_status(presentation_id)
