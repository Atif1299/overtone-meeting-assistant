from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.db.models import Subscription
from app.domain.usage import usage_snapshot
from app.http.auth import WorkspaceContext, get_workspace_context

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutIn(BaseModel):
    plan: str  # starter | pro


class CheckoutOut(BaseModel):
    url: str


class PortalOut(BaseModel):
    url: str


class UsageOut(BaseModel):
    plan: str
    period_month: str
    launches: dict
    uploads: dict


def _stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _price_for_plan(plan: str) -> str:
    settings = get_settings()
    if plan == "starter":
        if not settings.stripe_price_starter:
            raise HTTPException(status_code=503, detail="Stripe starter price not configured")
        return settings.stripe_price_starter
    if plan == "pro":
        if not settings.stripe_price_pro:
            raise HTTPException(status_code=503, detail="Stripe pro price not configured")
        return settings.stripe_price_pro
    raise HTTPException(status_code=400, detail="Invalid plan")


def _get_or_create_subscription(db: Session, workspace_id: str) -> Subscription:
    sub = (
        db.query(Subscription)
        .filter(Subscription.workspace_id == workspace_id)
        .order_by(Subscription.updated_at.desc())
        .first()
    )
    if sub:
        return sub
    sub = Subscription(workspace_id=workspace_id, plan="free", status="active")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/usage", response_model=UsageOut)
def billing_usage(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if ctx.is_operator:
        return UsageOut(
            plan="operator",
            period_month=datetime.now(timezone.utc).strftime("%Y-%m"),
            launches={"used": 0, "limit": 9999},
            uploads={"used": 0, "limit": 9999},
        )
    snap = usage_snapshot(db, ctx.workspace_id)
    return UsageOut(**snap)


@router.post("/checkout", response_model=CheckoutOut)
def create_checkout(
    body: CheckoutIn,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if ctx.is_operator:
        raise HTTPException(status_code=400, detail="Operator accounts do not need billing")
    settings = get_settings()
    st = _stripe()
    sub = _get_or_create_subscription(db, ctx.workspace_id)
    price_id = _price_for_plan(body.plan)

    customer_id = sub.stripe_customer_id
    if not customer_id:
        customer = st.Customer.create(
            email=ctx.email or None,
            metadata={"workspace_id": ctx.workspace_id, "user_id": ctx.user_id or ""},
        )
        customer_id = customer["id"]
        sub.stripe_customer_id = customer_id
        db.commit()

    session = st.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.dashboard_url.rstrip('/')}/app/billing?checkout=success",
        cancel_url=f"{settings.dashboard_url.rstrip('/')}/app/billing?checkout=cancel",
        metadata={"workspace_id": ctx.workspace_id, "plan": body.plan},
        subscription_data={"metadata": {"workspace_id": ctx.workspace_id, "plan": body.plan}},
    )
    return CheckoutOut(url=session["url"])


@router.post("/portal", response_model=PortalOut)
def customer_portal(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if ctx.is_operator:
        raise HTTPException(status_code=400, detail="Operator accounts do not need billing")
    settings = get_settings()
    st = _stripe()
    sub = _get_or_create_subscription(db, ctx.workspace_id)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer — subscribe first")
    portal = st.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.dashboard_url.rstrip('/')}/app/billing",
    )
    return PortalOut(url=portal["url"])


def _plan_from_stripe_subscription(stripe_sub: dict) -> str:
    meta = stripe_sub.get("metadata") or {}
    plan = meta.get("plan")
    if plan in ("starter", "pro", "free"):
        return plan
    items = stripe_sub.get("items", {}).get("data") or []
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        settings = get_settings()
        if price_id == settings.stripe_price_pro:
            return "pro"
        if price_id == settings.stripe_price_starter:
            return "starter"
    return "free"


def handle_stripe_webhook(db: Session, event: dict) -> None:
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        workspace_id = (data.get("metadata") or {}).get("workspace_id")
        plan = (data.get("metadata") or {}).get("plan", "starter")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        if workspace_id:
            sub = _get_or_create_subscription(db, workspace_id)
            sub.plan = plan
            sub.status = "active"
            sub.stripe_customer_id = customer_id
            sub.stripe_subscription_id = subscription_id
            db.commit()
        return

    if event_type in ("customer.subscription.updated", "customer.subscription.created"):
        workspace_id = (data.get("metadata") or {}).get("workspace_id")
        if not workspace_id:
            customer_id = data.get("customer")
            sub = (
                db.query(Subscription)
                .filter(Subscription.stripe_customer_id == customer_id)
                .first()
            )
            if sub:
                workspace_id = sub.workspace_id
        if workspace_id:
            sub = _get_or_create_subscription(db, workspace_id)
            sub.plan = _plan_from_stripe_subscription(data)
            sub.status = data.get("status", "active")
            sub.stripe_subscription_id = data.get("id")
            sub.stripe_customer_id = data.get("customer")
            if data.get("current_period_start"):
                sub.current_period_start = datetime.fromtimestamp(
                    data["current_period_start"], tz=timezone.utc
                )
            if data.get("current_period_end"):
                sub.current_period_end = datetime.fromtimestamp(
                    data["current_period_end"], tz=timezone.utc
                )
            db.commit()
        return

    if event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_customer_id == customer_id)
            .first()
        )
        if sub:
            sub.plan = "free"
            sub.status = "canceled"
            sub.stripe_subscription_id = None
            db.commit()
