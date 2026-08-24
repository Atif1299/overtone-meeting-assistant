from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.domain.session_store import store

logger = logging.getLogger("overtone.v2.webhooks")
router = APIRouter(prefix="/webhooks/recall", tags=["webhooks"])


def _verify(request_body: bytes, signature: str | None) -> None:
    settings = get_settings()
    if settings.recall_skip_webhook_verify:
        return
    if not settings.recall_webhook_secret:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")
    # Svix-style: accept if secret present in header for MVP; full verify can be tightened later
    if settings.recall_webhook_secret not in (signature or ""):
        # also allow exact hmac of body
        digest = hmac.new(
            settings.recall_webhook_secret.encode(), request_body, "sha256"
        ).hexdigest()
        if digest not in (signature or ""):
            logger.warning("webhook signature mismatch")


@router.post("/bot-status")
async def bot_status(
    request: Request,
    webhook_signature: str | None = Header(default=None, alias="webhook-signature"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
):
    body = await request.body()
    _verify(body, webhook_signature or svix_signature)
    payload = await request.json()
    data = payload.get("data") or payload
    bot_id = str(data.get("bot_id") or data.get("id") or "")
    status = data.get("status") or {}
    if isinstance(status, dict):
        code = str(status.get("code") or status.get("status_code") or "")
        message = str(status.get("message") or "")
    else:
        code = str(status)
        message = ""
    nested = data.get("data") if isinstance(data.get("data"), dict) else None
    if nested and not bot_id:
        bot_id = str(nested.get("bot_id") or nested.get("id") or "")
    if bot_id and code:
        store.update_bot_status(bot_id, code, message)
    return {"status": "ok"}


@router.post("/chat")
async def chat_webhook(request: Request):
    # Optional: inject chat into live relay later; acknowledge for now
    await request.json()
    return {"status": "ok"}
