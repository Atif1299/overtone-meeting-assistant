from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from config import Settings, get_settings
from models.bot_session import AgentMode
from orchestrator.engine import enqueue_transcript
from services.event_dedupe import event_deduper, extract_event_id
from services.recall_verify import verify_recall_signature
from services.session_store import store

router = APIRouter(prefix="/api/webhook/recall", tags=["webhooks"])
logger = logging.getLogger(__name__)


def _normalize_headers(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items()}


def _extract_from_body(body: dict[str, Any]) -> tuple[str | None, str, bool, str | None]:
    """
    Returns: bot_id, text, is_partial, speaker
    """
    event = body.get("event") or body.get("type") or ""
    is_partial = "partial" in str(event).lower()

    data = body.get("data")
    if not isinstance(data, dict):
        data = {}

    bot = data.get("bot")
    if not isinstance(bot, dict):
        bot = body.get("bot") if isinstance(body.get("bot"), dict) else {}
    bot_id = bot.get("id") if bot else None
    if bot_id is not None:
        bot_id = str(bot_id)

    inner = data.get("data")
    if not isinstance(inner, dict):
        inner = data

    speaker = None
    if isinstance(inner.get("participant"), dict):
        speaker = inner["participant"].get("name")
    if not speaker and isinstance(inner.get("speaker"), str):
        speaker = inner.get("speaker")

    words = inner.get("words")
    text = ""
    if isinstance(words, list):
        parts: list[str] = []
        for w in words:
            if isinstance(w, dict):
                t = w.get("text") or w.get("word") or ""
            else:
                t = str(w)
            if t:
                parts.append(t)
        text = " ".join(parts).strip()
    if not text:
        text = (inner.get("text") or inner.get("payload") or "").strip()

    return bot_id, text, is_partial, speaker


@router.post("/transcript")
async def recall_transcript_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    raw = await request.body()
    hdrs = _normalize_headers(request)

    if settings.recall_webhook_secret and not settings.recall_skip_webhook_verify:
        if not verify_recall_signature(settings.recall_webhook_secret, hdrs, raw):
            logger.warning("Transcript webhook signature verification failed")
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
        logger.info("Duplicate transcript webhook ignored (event_id=%s)", event_id)
        return {"status": "ignored", "reason": "duplicate event"}

    bot_id, text, is_partial, speaker = _extract_from_body(body)
    if not bot_id:
        logger.warning("Transcript webhook missing bot id: %s", body)
        raise HTTPException(400, "Missing bot id")

    if not text:
        return {"status": "ignored", "reason": "empty text"}

    sess = await store.get_by_bot_id(bot_id)
    if sess and sess.agent_mode == AgentMode.REALTIME:
        return {"status": "ignored", "reason": "realtime mode handles speech directly"}

    await enqueue_transcript(bot_id, text, is_partial=is_partial, speaker=speaker)
    return {"status": "ok"}
