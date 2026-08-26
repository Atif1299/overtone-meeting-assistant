from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.db.models import ApiKey


def _extract_key(request: Request) -> str:
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""
    auth = request.headers.get("Authorization") or ""
    if not key and auth.lower().startswith("bearer "):
        key = auth[7:].strip()
    return key


def require_admin_key(request: Request) -> None:
    settings = get_settings()
    if settings.open_demo_access or not settings.admin_api_key:
        return
    if _extract_key(request) != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


def require_api_key(request: Request, db: Session = Depends(get_db)) -> ApiKey:
    settings = get_settings()
    provided = _extract_key(request)
    if settings.admin_api_key and provided == settings.admin_api_key:
        return ApiKey(key=provided, customer_id="operator", customer_name="Operator", is_active=True)
    if settings.open_demo_access or (not provided and not settings.admin_api_key):
        return ApiKey(key="demo", customer_id="operator", customer_name="Demo", is_active=True)
    row = db.get(ApiKey, provided)
    if not row or not row.is_active:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return row
