from __future__ import annotations

import os
from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from api.auth import require_customer_key
from config import Settings, get_settings
from models.api_key import ApiKey
from models.presentation import PresentationSummary
from services.blob_storage import AzureBlobStorageClient
from services.index_jobs import dispatch_index_job
from services import storage as storage_mod

router = APIRouter(prefix="/api/v1/presentations", tags=["presentations"])

ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".pptx"}


def _should_auto_dispatch() -> bool:
    return os.getenv("VERCEL") != "1"


def _validate_filename(filename: str) -> str:
    safe_name = Path(filename or "upload").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(400, "Only .pdf and .pptx uploads are supported")
    return safe_name


def _trigger_index(presentation_id: str, *, trigger: str) -> None:
    storage_mod.update_presentation_meta(presentation_id, status="indexing", index_error=None)
    dispatch_index_job(presentation_id)


class PresentationPageResponse(BaseModel):
    presentation_id: str
    page_number: int
    title: str
    content_text: str
    document_id: str | None = None
    image_blob_name: str | None = None
    image_blob_url: str | None = None
    image_available: bool = False


@router.get("", response_model=list[PresentationSummary])
async def list_presentations(_: ApiKey = Depends(require_customer_key)) -> list[PresentationSummary]:
    return storage_mod.list_presentations()


@router.post("", response_model=PresentationSummary)
async def upload_file(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    _: ApiKey = Depends(require_customer_key),
) -> PresentationSummary:
    safe_name = _validate_filename(file.filename or "upload.pdf")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes // 1_048_576} MB limit")
    uploaded = storage_mod.save_upload(safe_name, data)
    if _should_auto_dispatch():
        _trigger_index(uploaded.presentation_id, trigger="upload")
    return uploaded


class DirectUploadInitResponse(BaseModel):
    upload_url: str
    presentation: PresentationSummary


@router.post("/direct/init", response_model=DirectUploadInitResponse)
async def upload_direct_init(
    filename: str = Form(...),
    total_size: int = Form(0),
    settings: Settings = Depends(get_settings),
    _: ApiKey = Depends(require_customer_key),
) -> DirectUploadInitResponse:
    safe_name = _validate_filename(filename)
    if total_size > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes // 1_048_576} MB limit")
    blob_storage = AzureBlobStorageClient(settings)
    if not blob_storage.enabled:
        raise HTTPException(503, "Direct upload requires Azure Blob Storage to be configured")
    slot = storage_mod.create_upload_slot(safe_name)
    blob_name = f"{slot.presentation_id}/source/{safe_name}"
    sas_url = blob_storage.generate_upload_sas_url(
        blob_name=blob_name,
        ttl_minutes=settings.azure_blob_upload_sas_ttl_minutes,
    )
    if not sas_url:
        raise HTTPException(500, "Failed to generate upload URL")
    storage_mod.update_presentation_meta(
        slot.presentation_id,
        source_blob_name=blob_name,
        status="uploaded",
    )
    return DirectUploadInitResponse(upload_url=sas_url, presentation=slot)


class DirectUploadCompleteRequest(BaseModel):
    presentation_id: str


@router.post("/direct/complete", response_model=PresentationSummary)
async def upload_direct_complete(
    body: DirectUploadCompleteRequest,
    settings: Settings = Depends(get_settings),
    _: ApiKey = Depends(require_customer_key),
) -> PresentationSummary:
    meta = storage_mod.get_presentation_meta(body.presentation_id)
    if not meta:
        raise HTTPException(404, "Presentation not found")
    if _should_auto_dispatch():
        _trigger_index(body.presentation_id, trigger="direct_upload")
    return storage_mod.get_presentation(body.presentation_id) or PresentationSummary(
        presentation_id=body.presentation_id,
        filename=str(meta.get("filename", "")),
        status="indexing",
    )


@router.post("/init")
async def upload_init(
    filename: str = Form(...),
    total_size: int = Form(0),
    total_chunks: int = Form(1),
    settings: Settings = Depends(get_settings),
    _: ApiKey = Depends(require_customer_key),
) -> dict:
    safe_name = _validate_filename(filename)
    if total_size > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes // 1_048_576} MB limit")
    slot = storage_mod.create_upload_slot(safe_name)
    storage_mod.update_presentation_meta(slot.presentation_id, total_chunks=total_chunks)
    return {"presentation_id": slot.presentation_id, "filename": safe_name}


@router.post("/{presentation_id}/chunk")
async def upload_chunk(
    presentation_id: str,
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    _: ApiKey = Depends(require_customer_key),
) -> dict:
    data = await chunk.read()
    storage_mod.append_upload_chunk(presentation_id, chunk_index, data)
    return {"ok": True, "chunk_index": chunk_index}


@router.post("/{presentation_id}/complete", response_model=PresentationSummary)
async def upload_complete(
    presentation_id: str,
    settings: Settings = Depends(get_settings),
    _: ApiKey = Depends(require_customer_key),
) -> PresentationSummary:
    data = storage_mod.assemble_upload_chunks(presentation_id)
    if data is None:
        raise HTTPException(404, "No upload chunks found for this presentation")
    meta = storage_mod.get_presentation_meta(presentation_id) or {}
    filename = str(meta.get("filename") or "upload.bin")
    storage_mod.save_assembled_upload(presentation_id, filename, data)
    if _should_auto_dispatch():
        _trigger_index(presentation_id, trigger="chunked_upload")
    return storage_mod.get_presentation(presentation_id) or PresentationSummary(
        presentation_id=presentation_id,
        filename=filename,
        status="indexing",
    )


@router.get("/{presentation_id}", response_model=PresentationSummary)
async def get_presentation(
    presentation_id: str
) -> PresentationSummary:
    p = storage_mod.get_presentation(presentation_id)
    if not p:
        raise HTTPException(404, "Presentation not found")
    return p


@router.post("/{presentation_id}/reindex", response_model=PresentationSummary)
async def reindex_presentation(
    presentation_id: str,
    _: ApiKey = Depends(require_customer_key),
) -> PresentationSummary:
    """Re-trigger indexing for an existing presentation."""
    p = storage_mod.get_presentation(presentation_id)
    if not p:
        raise HTTPException(404, "Presentation not found")
    _trigger_index(presentation_id, trigger="reindex")
    return storage_mod.get_presentation(presentation_id) or PresentationSummary(
        presentation_id=presentation_id,
        filename=p.filename,
        status="indexing",
    )


@router.get(
    "/{presentation_id}/page/{page_number}",
    response_model=PresentationPageResponse,
)
async def get_presentation_page(
    presentation_id: str, page_number: int
) -> PresentationPageResponse:
    pages = storage_mod.load_index_pages(presentation_id)
    match = next((row for row in pages if int(row.get("page_number") or 0) == page_number), None)
    document_id = None
    presentation_meta = storage_mod.get_presentation_meta(presentation_id) or {}
    if presentation_meta:
        document_id = str(presentation_meta.get("document_id") or "") or None
    if match:
        image_blob_name = str(match.get("image_blob_name") or "") or None
        image_blob_url = str(match.get("image_blob_url") or "") or None
        image_available = bool(
            image_blob_name
            or image_blob_url
            or storage_mod.slide_image_path(presentation_id, page_number)
        )
        return PresentationPageResponse(
            presentation_id=presentation_id,
            page_number=page_number,
            title=str(match.get("title") or f"Slide {page_number}"),
            content_text=str(match.get("searchable_content") or match.get("content_text") or ""),
            document_id=document_id,
            image_blob_name=image_blob_name,
            image_blob_url=image_blob_url,
            image_available=image_available,
        )
    return PresentationPageResponse(
        presentation_id=presentation_id,
        page_number=page_number,
        title=f"Slide {page_number}",
        content_text="No preview image found yet for this page.",
        document_id=document_id,
    )


@router.get("/{presentation_id}/page/{page_number}/image")
async def get_slide_image(
    presentation_id: str, page_number: int
) -> Response:
    page = await get_presentation_page(presentation_id, page_number)
    if page.image_blob_name:
        blob_storage = AzureBlobStorageClient(get_settings())
        if blob_storage.enabled:
            payload = await blob_storage.download_bytes(blob_name=page.image_blob_name)
            if payload:
                return Response(content=payload, media_type="image/png")

    path = storage_mod.slide_image_path(presentation_id, page_number)
    if path and path.is_file():
        return FileResponse(path, media_type="image/png")

    snippet = " ".join(page.content_text.split())[:220] or "No content extracted for this page yet."
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720' viewBox='0 0 1280 720'>"
        "<defs>"
        "<linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#0b1628'/>"
        "<stop offset='100%' stop-color='#111f35'/>"
        "</linearGradient>"
        "</defs>"
        "<rect width='1280' height='720' fill='url(#bg)'/>"
        "<rect x='86' y='90' width='1108' height='540' rx='28' fill='#0f1c31' stroke='#2a4164' stroke-width='2'/>"
        "<text x='130' y='170' fill='#9ac7ff' font-size='28' font-family='Avenir Next,Segoe UI,sans-serif'>"
        f"{escape(page.title)}"
        "</text>"
        "<text x='130' y='230' fill='#d8e7ff' font-size='18' font-family='Avenir Next,Segoe UI,sans-serif'>"
        f"{escape(snippet)}"
        "</text>"
        "<text x='130' y='588' fill='#7fa6d8' font-size='16' font-family='Avenir Next,Segoe UI,sans-serif'>"
        "Slide image is unavailable, showing extracted text preview."
        "</text>"
        "</svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")
