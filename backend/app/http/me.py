from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.domain.usage import usage_snapshot
from app.domain.workspaces import bootstrap_user_workspace
from app.http.auth import WorkspaceContext, get_workspace_context
from app.http.billing import handle_paddle_webhook, verify_paddle_signature
from app.http.paddle_ips import fetch_paddle_ipv4_cidrs, ip_in_cidrs, source_ip_from_request

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    workspace_id: str
    workspace_name: str
    plan: str
    usage: dict


class BootstrapOut(BaseModel):
    ok: bool
    workspace_id: str


@router.get("/api/v1/me", response_model=MeOut)
def get_me(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if ctx.is_operator:
        return MeOut(
            user_id="operator",
            email="operator@deckvoice.local",
            full_name="Operator",
            workspace_id="operator",
            workspace_name="Operator",
            plan="operator",
            usage={
                "plan": "operator",
                "period_month": "",
                "launches": {"used": 0, "limit": 9999},
                "uploads": {"used": 0, "limit": 9999},
            },
        )
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user, workspace = bootstrap_user_workspace(
        db,
        user_id=ctx.user_id,
        email=ctx.email,
    )
    snap = usage_snapshot(db, workspace.id)
    return MeOut(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        plan=snap["plan"],
        usage=snap,
    )


@router.post("/api/v1/auth/bootstrap", response_model=BootstrapOut)
def auth_bootstrap(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    _, workspace = bootstrap_user_workspace(
        db,
        user_id=ctx.user_id,
        email=ctx.email,
    )
    return BootstrapOut(ok=True, workspace_id=workspace.id)


@router.post("/webhooks/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.paddle_webhook_secret:
        raise HTTPException(status_code=503, detail="Paddle webhook not configured")
    source_ip = source_ip_from_request(request.headers.get("x-forwarded-for"))
    if source_ip:
        cidrs = fetch_paddle_ipv4_cidrs()
        if cidrs and not ip_in_cidrs(source_ip, cidrs):
            raise HTTPException(status_code=403, detail="Paddle webhook source not allowlisted")
    payload = await request.body()
    sig = request.headers.get("paddle-signature", "")
    if not verify_paddle_signature(payload, sig, settings.paddle_webhook_secret):
        raise HTTPException(status_code=400, detail="Invalid Paddle signature")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    handle_paddle_webhook(db, event)
    return {"ok": True}
