from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class AdminAuthRequest(BaseModel):
    admin_api_key: str


class AdminAuthResponse(BaseModel):
    ok: bool
    message: str


@router.post("/admin", response_model=AdminAuthResponse)
async def verify_admin(request: AdminAuthRequest) -> AdminAuthResponse:
    """Verify provided admin_api_key against configured ADMIN_API_KEY."""
    settings = get_settings()
    required = (settings.admin_api_key or "").strip()
    if not required:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY not configured")

    if request.admin_api_key != required:
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    return AdminAuthResponse(ok=True, message="Admin API key valid")
