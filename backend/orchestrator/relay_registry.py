"""Global registry of active OpenAI Realtime WebSocket connections.

The relay registers its OpenAI WS when connected, keyed by session_id.
Other parts of the system (e.g., the chat webhook) can look up the
connection and inject messages directly into the OpenAI conversation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# session_id → (openai_ws, relay_runtime)
_registry: dict[str, tuple[Any, Any]] = {}


def register(session_id: str, openai_ws: Any, relay: Any = None) -> None:
    _registry[session_id] = (openai_ws, relay)
    logger.info("Relay registry: registered session_id=%s", session_id)


def unregister(session_id: str) -> None:
    _registry.pop(session_id, None)
    logger.info("Relay registry: unregistered session_id=%s", session_id)


def get(session_id: str) -> Any | None:
    entry = _registry.get(session_id)
    return entry[0] if entry else None


async def inject_chat_message(
    session_id: str,
    sender: str,
    text: str,
    *,
    voice_reply: bool = False,
) -> bool:
    """Inject an incoming chat message into the OpenAI Realtime session.

    When *voice_reply* is False (default) the bot responds via meeting chat text
    (text-only OpenAI response captured and sent back via Recall send_chat_message).
    When *voice_reply* is True the bot speaks its reply aloud (used for unmute greetings).

    Returns True if successfully injected, False if no active connection.
    """
    entry = _registry.get(session_id)
    if entry is None:
        logger.warning(
            "Relay registry: no active connection for session_id=%s, cannot inject chat",
            session_id,
        )
        return False

    openai_ws, relay = entry

    # Route through the relay runtime so it can capture the text response and
    # send it back as a meeting chat message.
    if relay is not None and not voice_reply:
        return await relay.handle_incoming_chat(sender, text)

    # --- Voice reply (unmute greeting) or legacy fallback ---
    try:
        await openai_ws.send(
            json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": (
                            f"[MEETING CHAT from {sender}]: {text}\n\n"
                            "Respond to this naturally and briefly via speech."
                        ),
                    }],
                },
            })
        )
        await openai_ws.send(json.dumps({"type": "response.create"}))
        logger.info(
            "Relay registry: injected voice chat message into OpenAI session_id=%s sender=%s",
            session_id, sender,
        )
        return True
    except Exception as exc:
        logger.error(
            "Relay registry: failed to inject chat session_id=%s: %s",
            session_id, exc,
        )
        return False
