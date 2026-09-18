from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
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
    transaction_id: str | None = None


class PaddleConfigOut(BaseModel):
    client_token: str
    environment: str


class PortalOut(BaseModel):
    url: str


class UsageOut(BaseModel):
    plan: str
    period_month: str
    launches: dict
    uploads: dict


def paddle_environment(api_base: str) -> str:
    return "sandbox" if "sandbox" in (api_base or "").lower() else "live"


def _paddle_configured() -> None:
    settings = get_settings()
    if not settings.paddle_api_key:
        raise HTTPException(status_code=503, detail="Paddle not configured")


def _price_for_plan(plan: str) -> str:
    settings = get_settings()
    if plan == "starter":
        if not settings.paddle_price_starter:
            raise HTTPException(status_code=503, detail="Paddle starter price not configured")
        return settings.paddle_price_starter
    if plan == "pro":
        if not settings.paddle_price_pro:
            raise HTTPException(status_code=503, detail="Paddle pro price not configured")
        return settings.paddle_price_pro
    raise HTTPException(status_code=400, detail="Invalid plan")


def _paddle_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.paddle_api_key}",
        "Content-Type": "application/json",
        "Paddle-Version": "1",
    }


def _paddle_post(path: str, payload: dict | None = None) -> dict:
    _paddle_configured()
    settings = get_settings()
    url = f"{settings.paddle_api_base.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=_paddle_headers(), json=payload or {})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Paddle request failed") from exc
    if response.status_code >= 400:
        detail = "Paddle request failed"
        try:
            body = response.json()
            err = body.get("error") or {}
            if isinstance(err, dict) and err.get("detail"):
                detail = str(err["detail"])
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=502, detail=detail)
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Paddle request failed") from exc


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


def verify_paddle_signature(raw_body: bytes | str, signature_header: str, secret: str) -> bool:
    if not signature_header or not secret:
        return False
    ts = ""
    signatures: list[str] = []
    for part in signature_header.split(";"):
        piece = part.strip()
        if piece.startswith("ts="):
            ts = piece[3:]
        elif piece.startswith("h1="):
            signatures.append(piece[3:])
    if not ts or not signatures:
        return False
    body_text = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else raw_body
    signed = f"{ts}:{body_text}"
    expected = hmac.new(secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(sig, expected) for sig in signatures if len(sig) == len(expected))


def _price_ids_from_items(items: list) -> list[str]:
    ids: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        price_id = item.get("price_id")
        price = item.get("price")
        if not price_id and isinstance(price, dict):
            price_id = price.get("id")
        if price_id:
            ids.append(str(price_id))
    return ids


def plan_from_paddle_payload(data: dict, *, starter_price: str, pro_price: str) -> str:
    for price_id in _price_ids_from_items(data.get("items") or []):
        if pro_price and price_id == pro_price:
            return "pro"
        if starter_price and price_id == starter_price:
            return "starter"
    custom = data.get("custom_data") or {}
    if isinstance(custom, dict):
        plan = custom.get("plan")
        if plan in ("starter", "pro", "free"):
            return plan
    return "free"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _workspace_id_from_data(db: Session, data: dict) -> str | None:
    custom = data.get("custom_data") or {}
    if isinstance(custom, dict) and custom.get("workspace_id"):
        return str(custom["workspace_id"])
    subscription_id = data.get("subscription_id") or (
        data.get("id") if str(data.get("id") or "").startswith("sub_") else None
    )
    if subscription_id:
        sub = (
            db.query(Subscription)
            .filter(Subscription.paddle_subscription_id == subscription_id)
            .first()
        )
        if sub:
            return sub.workspace_id
    customer_id = data.get("customer_id")
    if customer_id:
        sub = (
            db.query(Subscription)
            .filter(Subscription.paddle_customer_id == customer_id)
            .first()
        )
        if sub:
            return sub.workspace_id
    return None


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
    if body.plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Invalid plan")
    sub = _get_or_create_subscription(db, ctx.workspace_id)
    current = (sub.plan or "free").lower()
    if current == body.plan:
        raise HTTPException(status_code=400, detail=f"Already on {body.plan}")
    if current == "pro" and body.plan == "starter":
        raise HTTPException(status_code=400, detail="Use Manage subscription to change plan")
    price_id = _price_for_plan(body.plan)
    payload: dict = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "custom_data": {"workspace_id": ctx.workspace_id, "plan": body.plan},
        "collection_mode": "automatic",
    }
    if sub.paddle_customer_id:
        payload["customer_id"] = sub.paddle_customer_id
    elif ctx.email:
        payload["customer"] = {"email": ctx.email}
    result = _paddle_post("/transactions", payload)
    data = result.get("data") or {}
    checkout = data.get("checkout") or {}
    url = checkout.get("url")
    if not url:
        raise HTTPException(status_code=502, detail="Paddle checkout URL missing")
    return CheckoutOut(url=url, transaction_id=data.get("id"))


@router.get("/paddle-config", response_model=PaddleConfigOut)
def paddle_config(ctx: WorkspaceContext = Depends(get_workspace_context)):
    settings = get_settings()
    if not settings.paddle_client_token:
        raise HTTPException(status_code=503, detail="Paddle client token not configured")
    return PaddleConfigOut(
        client_token=settings.paddle_client_token,
        environment=paddle_environment(settings.paddle_api_base),
    )


@router.post("/portal", response_model=PortalOut)
def customer_portal(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    if ctx.is_operator:
        raise HTTPException(status_code=400, detail="Operator accounts do not need billing")
    sub = _get_or_create_subscription(db, ctx.workspace_id)
    if not sub.paddle_customer_id:
        raise HTTPException(status_code=400, detail="No Paddle customer — subscribe first")
    path = f"/customers/{sub.paddle_customer_id}/portal-sessions"
    body: dict = {}
    if sub.paddle_subscription_id:
        body["subscription_ids"] = [sub.paddle_subscription_id]
    result = _paddle_post(path, body)
    data = result.get("data") or {}
    urls = data.get("urls") or {}
    general = urls.get("general") or {}
    url = general.get("overview")
    if not url:
        raise HTTPException(status_code=502, detail="Paddle portal URL missing")
    return PortalOut(url=url)


def handle_paddle_webhook(db: Session, event: dict) -> None:
    event_type = event.get("event_type") or ""
    data = event.get("data") or {}
    if not isinstance(data, dict):
        return
    settings = get_settings()

    if event_type == "transaction.completed":
        workspace_id = _workspace_id_from_data(db, data)
        if not workspace_id:
            return
        sub = _get_or_create_subscription(db, workspace_id)
        sub.plan = plan_from_paddle_payload(
            data,
            starter_price=settings.paddle_price_starter,
            pro_price=settings.paddle_price_pro,
        )
        sub.status = "active"
        if data.get("customer_id"):
            sub.paddle_customer_id = data["customer_id"]
        if data.get("subscription_id"):
            sub.paddle_subscription_id = data["subscription_id"]
        db.commit()
        return

    if event_type in (
        "subscription.created",
        "subscription.updated",
        "subscription.past_due",
        "subscription.canceled",
    ):
        workspace_id = _workspace_id_from_data(db, data)
        if not workspace_id:
            return
        sub = _get_or_create_subscription(db, workspace_id)
        status = data.get("status") or (
            "canceled" if event_type == "subscription.canceled" else "active"
        )
        if event_type == "subscription.canceled" or status == "canceled":
            sub.plan = "free"
            sub.status = "canceled"
            sub.paddle_subscription_id = None
        else:
            sub.plan = plan_from_paddle_payload(
                data,
                starter_price=settings.paddle_price_starter,
                pro_price=settings.paddle_price_pro,
            )
            sub.status = status
            if data.get("id"):
                sub.paddle_subscription_id = data["id"]
        if data.get("customer_id"):
            sub.paddle_customer_id = data["customer_id"]
        period = data.get("current_billing_period") or {}
        if isinstance(period, dict):
            start = _parse_dt(period.get("starts_at"))
            end = _parse_dt(period.get("ends_at"))
            if start:
                sub.current_period_start = start
            if end:
                sub.current_period_end = end
        db.commit()
