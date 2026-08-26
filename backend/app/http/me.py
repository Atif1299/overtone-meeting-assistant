from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.domain.usage import usage_snapshot
from app.domain.workspaces import bootstrap_user_workspace
from app.http.auth import WorkspaceContext, get_workspace_context
from app.http.billing import handle_stripe_webhook

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
            email="operator@overtone.local",
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


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    handle_stripe_webhook(db, event)
    return {"ok": True}
