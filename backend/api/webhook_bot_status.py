from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from config import Settings, get_settings
from services.event_dedupe import event_deduper, extract_event_id
from services.recall_verify import verify_recall_signature
from services.session_store import store

router = APIRouter(prefix="/api/webhook/recall", tags=["webhooks"])
logger = logging.getLogger(__name__)


def _parse_bot_status(body: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return bot_id, status_code, message from Recall bot status webhook (Svix)."""
    data = body.get("data")
    if not isinstance(data, dict):
        return None, None, None

    status_obj = data.get("status")
    if isinstance(status_obj, dict) and data.get("bot_id"):
        code = status_obj.get("code")
        msg = status_obj.get("message") or status_obj.get("sub_code")
        return str(data["bot_id"]), str(code) if code else None, str(msg) if msg else None

    inner = data.get("data")
    bot = data.get("bot")
    bot_id = data.get("bot_id")
    if isinstance(bot, dict) and bot.get("id"):
        bot_id = str(bot["id"])
    if isinstance(inner, dict) and inner.get("code"):
        return (
            str(bot_id) if bot_id else None,
            str(inner["code"]),
            str(inner.get("sub_code") or inner.get("message") or "") or None,
        )
    return (str(bot_id) if bot_id else None), None, None


@router.post("/bot-status")
async def recall_bot_status_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """
    Configure this URL in the Recall.ai dashboard (Bot Webhooks / Svix).
    Real-time transcript webhooks are separate (per Create Bot).
    """
    raw = await request.body()
    hdrs = {k: v for k, v in request.headers.items()}

    if settings.recall_webhook_secret and not settings.recall_skip_webhook_verify:
        if not verify_recall_signature(settings.recall_webhook_secret, hdrs, raw):
            logger.warning("Bot status webhook signature verification failed")
            raise HTTPException(401, "Invalid signature")
    elif not settings.recall_skip_webhook_verify and not settings.recall_webhook_secret:
        logger.warning(
            "RECALL_WEBHOOK_SECRET not set; set RECALL_SKIP_WEBHOOK_VERIFY=true for local dev"
        )
        raise HTTPException(503, "Webhook verification not configured")

    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}") from e

    event_id = extract_event_id(hdrs, body)
    if await event_deduper.is_duplicate(event_id):
        logger.info("Duplicate bot-status webhook ignored (event_id=%s)", event_id)
        return {"status": "ignored", "reason": "duplicate event"}

    bot_id, code, message = _parse_bot_status(body)
    event = body.get("event", "")
    logger.info("Bot status webhook event=%s bot_id=%s code=%s", event, bot_id, code)

    if bot_id and code:
        await store.update_bot_status(bot_id, code=code, message=message)

    return {"status": "ok"}
