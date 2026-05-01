from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from config import Settings, get_settings
from services.event_dedupe import event_deduper, extract_event_id
from services.recall_verify import verify_recall_signature
from services.session_store import store

router = APIRouter(prefix="/api/webhook/recall", tags=["webhooks"])
logger = logging.getLogger(__name__)

# ── Intent detection patterns ──────────────────────────────────────────
_UNMUTE_PATTERNS = re.compile(
    r"\b(unmute|un-mute|come back|speak now|wake up|you can speak|start speaking|resume)\b",
    re.IGNORECASE,
)
_MUTE_PATTERNS = re.compile(
    r"\b(mute yourself|go on mute|be quiet|stop talking|shut up|mute|shhh|go silent)\b",
    re.IGNORECASE,
)


def _detect_mute_intent(text: str) -> str | None:
    """Return 'unmute', 'mute', or None based on the chat message text."""
    if _UNMUTE_PATTERNS.search(text):
        return "unmute"
    if _MUTE_PATTERNS.search(text):
        return "mute"
    return None


def _parse_chat_message(body: dict[str, Any]) -> tuple[str | None, str, str | None]:
    """Extract bot_id, message text, and sender name from a chat webhook payload.

    Actual Recall payload structure for participant_events.chat_message:
    {
      "event": "participant_events.chat_message",
      "data": {
        "data": {
          "action": "chat_message",
          "participant": {"id": 100, "name": "Rahul Choudhary", ...},
          "data": {"text": "hi", "to": "everyone"},
          ...
        },
        "bot": {"id": "777f906e-...", "metadata": {}},
        ...
      }
    }
    """
    data = body.get("data")
    if not isinstance(data, dict):
        return None, "", None

    # bot_id lives at data.bot.id
    bot_id = None
    bot_obj = data.get("bot")
    if isinstance(bot_obj, dict):
        bot_id = str(bot_obj["id"]) if bot_obj.get("id") else None

    # The inner event data is at data.data
    inner = data.get("data")
    if not isinstance(inner, dict):
        return bot_id, "", None

    # Sender is at data.data.participant.name
    sender = None
    if isinstance(inner.get("participant"), dict):
        sender = inner["participant"].get("name")

    # Text is at data.data.data.text
    text = ""
    msg_data = inner.get("data")
    if isinstance(msg_data, dict):
        text = str(msg_data.get("text") or "").strip()
    if not text:
        text = str(inner.get("text") or inner.get("message") or "").strip()

    return bot_id, text, sender


@router.post("/chat")
async def recall_chat_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """
    Incoming chat message from a meeting participant.
    Configure this URL in the Create Bot `realtime_endpoints` with
    event type `participant_events.chat_message`.

    This handler also detects mute/unmute intent from chat messages,
    because a muted bot cannot hear voice commands — chat is the only
    way to unmute it.
    """
    raw = await request.body()
    hdrs = {k: v for k, v in request.headers.items()}

    # Verify signature
    if settings.recall_webhook_secret and not settings.recall_skip_webhook_verify:
        if not verify_recall_signature(settings.recall_webhook_secret, hdrs, raw):
            logger.warning("Chat webhook signature verification failed")
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

    # Dedupe
    event_id = extract_event_id(hdrs, body)
    if await event_deduper.is_duplicate(event_id):
        logger.info("Duplicate chat webhook ignored (event_id=%s)", event_id)
        return {"status": "ignored", "reason": "duplicate event"}

    bot_id, text, sender = _parse_chat_message(body)
    logger.info(
        "Chat webhook received bot_id=%s sender=%s text=%r",
        bot_id, sender, text[:120] if text else "",
    )

    if not bot_id:
        logger.warning("Chat webhook missing bot_id: %s", body)
        raise HTTPException(400, "Missing bot id")

    if not text:
        return {"status": "ignored", "reason": "empty text"}

    # Look up session
    sess = await store.get_by_bot_id(bot_id)
    if not sess:
        logger.warning("Chat webhook: no session for bot_id=%s", bot_id)
        return {"status": "ignored", "reason": "session not found"}

    # ── Mute / Unmute via chat ──────────────────────────────────────────
    intent = _detect_mute_intent(text)
    if intent == "unmute":
        sess.extra = {**sess.extra, "muted": False}
        logger.info("🔊 UNMUTE via chat message — session_id=%s sender=%s", sess.session_id, sender)

        # Broadcast unmute event so the frontend can update UI
        from orchestrator.ws_manager import ws_manager
        await ws_manager.broadcast_json(
            sess.session_id,
            {"type": "bot_unmuted", "trigger": "chat", "sender": sender or "Unknown"},
        )

        # Inject a prompt into the OpenAI session so the bot knows it was unmuted
        # and can greet the participants via voice (voice_reply=True).
        from orchestrator import relay_registry
        await relay_registry.inject_chat_message(
            sess.session_id,
            sender or "Unknown",
            f"[UNMUTE COMMAND] {text}. You have just been unmuted via chat. Say a brief greeting like 'I'm back! What can I help with?'",
            voice_reply=True,
        )
        await ws_manager.broadcast_json(
            sess.session_id,
            {
                "type": "chat_message",
                "sender": sender or "Unknown",
                "text": text,
                "direction": "incoming",
                "action": "unmute",
            },
        )
        return {"status": "ok", "action": "unmuted"}

    if intent == "mute":
        sess.extra = {**sess.extra, "muted": True}
        logger.info("🔇 MUTE via chat message — session_id=%s sender=%s", sess.session_id, sender)

        from orchestrator.ws_manager import ws_manager
        await ws_manager.broadcast_json(
            sess.session_id,
            {"type": "bot_muted", "trigger": "chat", "sender": sender or "Unknown"},
        )
        await ws_manager.broadcast_json(
            sess.session_id,
            {
                "type": "chat_message",
                "sender": sender or "Unknown",
                "text": text,
                "direction": "incoming",
                "action": "mute",
            },
        )
        return {"status": "ok", "action": "muted"}

    # ── Regular chat message (no mute intent) ───────────────────────────
    from orchestrator.ws_manager import ws_manager
    from orchestrator import relay_registry

    # Inject into OpenAI so the bot can respond to it
    await relay_registry.inject_chat_message(
        sess.session_id,
        sender or "Unknown",
        text,
    )

    # Also broadcast to frontend for UI display
    await ws_manager.broadcast_json(
        sess.session_id,
        {
            "type": "chat_message",
            "sender": sender or "Unknown",
            "text": text,
            "direction": "incoming",
        },
    )

    logger.info(
        "Chat message broadcasted session_id=%s sender=%s",
        sess.session_id, sender,
    )
    return {"status": "ok"}
