from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["auth"])


class AdminAuthIn(BaseModel):
    api_key: str = ""
    admin_api_key: str = ""


@router.post("/auth/admin")
def auth_admin(body: AdminAuthIn):
    settings = get_settings()
    provided = body.api_key or body.admin_api_key
    if settings.admin_api_key and provided != settings.admin_api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid admin key")
    return {"ok": True, "role": "admin"}
