from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.db.models import ApiKey
from app.domain.workspaces import bootstrap_user_workspace, get_user_workspace
from app.http.supabase_auth import decode_supabase_jwt


@dataclass
class WorkspaceContext:
    workspace_id: str
    user_id: str | None = None
    email: str = ""
    is_operator: bool = False


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _extract_key(request: Request) -> str:
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""
    if not key:
        key = _extract_bearer(request)
    return key


def require_admin_key(request: Request) -> None:
    settings = get_settings()
    if settings.open_demo_access or not settings.admin_api_key:
        return
    if _extract_key(request) != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


def require_api_key(request: Request, db: Session = Depends(get_db)) -> ApiKey:
    """Legacy API-key auth — kept for admin tooling and backward compatibility."""
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


def get_workspace_context(request: Request, db: Session = Depends(get_db)) -> WorkspaceContext:
    settings = get_settings()
    token = _extract_bearer(request)

    if token and (
        settings.supabase_jwt_secret
        or (settings.supabase_url and settings.supabase_anon_key)
    ):
        try:
            identity = decode_supabase_jwt(token)
        except HTTPException:
            raise
        user, workspace = bootstrap_user_workspace(
            db,
            user_id=identity["user_id"],
            email=identity["email"],
            full_name=identity.get("full_name"),
        )
        return WorkspaceContext(
            workspace_id=workspace.id,
            user_id=user.id,
            email=user.email,
        )

    api_key = require_api_key(request, db)
    if api_key.customer_id == "operator":
        return WorkspaceContext(workspace_id="operator", is_operator=True)
    return WorkspaceContext(workspace_id=api_key.customer_id, is_operator=False)


def assert_session_access(ctx: WorkspaceContext, session_customer_id: str | None) -> None:
    if ctx.is_operator:
        return
    if session_customer_id and session_customer_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Session not found")


def assert_presentation_access(ctx: WorkspaceContext, presentation_customer_id: str | None) -> None:
    if ctx.is_operator:
        return
    if presentation_customer_id and presentation_customer_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Not found")
