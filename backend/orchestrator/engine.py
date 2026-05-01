from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from orchestrator import llm_reasoner
from orchestrator import rag_retriever
from orchestrator import tts_client
from orchestrator.ws_manager import ws_manager
from models.bot_session import AgentMode
from services.session_store import store

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - handled at runtime
    redis_async = None

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[dict[str, Any]] | None = None
_redis_client: Any | None = None
_redis_queue_key = "voicenav:queue:transcripts"


def _ensure_queue() -> asyncio.Queue[dict[str, Any]]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


def _encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


async def configure_queue(redis_url: str, redis_prefix: str = "voicenav") -> None:
    """
    Queue bootstrap. If Redis is configured and reachable:
    - queue items are mirrored into Redis for durability
    - pending Redis items are rehydrated into memory at startup
    """
    global _redis_client, _redis_queue_key, _queue
    _queue = asyncio.Queue()
    _redis_queue_key = f"{redis_prefix}:queue:transcripts"
    _redis_client = None

    if not redis_url:
        return
    if redis_async is None:
        logger.warning("REDIS_URL is set but redis package is unavailable; transcript queue is in-memory")
        return

    try:
        client = redis_async.from_url(redis_url, decode_responses=True)
        await client.ping()
        _redis_client = client
        raw_items = await client.lrange(_redis_queue_key, 0, -1)
        for raw in raw_items:
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    await _queue.put(payload)
            except json.JSONDecodeError:
                continue
        if raw_items:
            logger.info("Recovered %s queued transcript event(s) from Redis", len(raw_items))
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning("Redis queue unavailable (%s); using in-memory queue", exc)
        _redis_client = None


async def clear_queue() -> None:
    queue = _ensure_queue()
    while not queue.empty():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break
    if _redis_client:
        await _redis_client.delete(_redis_queue_key)


async def _persist_payload(payload: dict[str, Any]) -> None:
    if not _redis_client:
        return
    try:
        await _redis_client.rpush(_redis_queue_key, _encode_payload(payload))
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning("Failed to persist transcript queue payload to Redis: %s", exc)


async def _ack_payload(payload: dict[str, Any]) -> None:
    if not _redis_client:
        return
    try:
        await _redis_client.lrem(_redis_queue_key, 1, _encode_payload(payload))
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning("Failed to ack transcript payload in Redis: %s", exc)


async def transcript_worker_loop() -> None:
    queue = _ensure_queue()
    while True:
        payload = await queue.get()
        bot_id = str(payload.get("bot_id", ""))
        text = str(payload.get("text", ""))
        speaker = payload.get("speaker")
        try:
            await _process_final(bot_id, text, speaker)
        except Exception:
            logger.exception("transcript worker failed bot_id=%s", bot_id)
        finally:
            await _ack_payload(payload)
            queue.task_done()


async def enqueue_transcript(
    bot_id: str,
    text: str,
    *,
    is_partial: bool,
    speaker: str | None = None,
) -> None:
    """Partials: UI only. Finals: queued for LLM (non-blocking webhook)."""
    sess = await store.get_by_bot_id(bot_id)
    if not sess:
        logger.warning("No session for bot_id=%s", bot_id)
        return
    if sess.agent_mode == AgentMode.REALTIME:
        # Realtime relay is the single authority for voice actions in realtime mode.
        return

    await ws_manager.broadcast_json(
        sess.session_id,
        {
            "type": "transcript",
            "text": text,
            "speaker": speaker,
            "is_partial": is_partial,
        },
    )

    if is_partial:
        return

    logger.info(
        "Queued final transcript bot_id=%s speaker=%s text=%s",
        bot_id,
        speaker or "unknown",
        text[:160],
    )
    await store.set_transcript_snippet(bot_id, text)
    payload = {"bot_id": bot_id, "text": text, "speaker": speaker}
    await _persist_payload(payload)
    await _ensure_queue().put(payload)


async def _process_final(bot_id: str, text: str, speaker: str | None) -> None:
    sess = await store.get_by_bot_id(bot_id)
    if not sess:
        return
    if sess.agent_mode == AgentMode.REALTIME:
        return

    await ws_manager.broadcast_json(
        sess.session_id, {"type": "status", "status": "processing"}
    )

    loop = asyncio.get_running_loop()
    start = loop.time()
    decision = await llm_reasoner.decide(
        text,
        sess.presentation_id,
        agent_system_prompt=str(sess.extra.get("agent_system_prompt") or ""),
    )
    duration_ms = (loop.time() - start) * 1000.0
    logger.info(
        "Processed transcript bot_id=%s ignore=%s navigate_to=%s answer=%s duration_ms=%.1f",
        bot_id,
        decision.ignore,
        decision.navigate_to,
        bool(decision.answer_text),
        duration_ms,
    )

    if decision.ignore:
        await ws_manager.broadcast_json(
            sess.session_id, {"type": "status", "status": "listening"}
        )
        return

    audio_url = None
    if decision.answer_text:
        audio_url = await tts_client.synthesize_url(decision.answer_text)
        logger.info(
            "TTS result bot_id=%s audio_generated=%s",
            bot_id,
            bool(audio_url),
        )

    total = await rag_retriever.get_total_pages(sess.presentation_id)
    target = decision.navigate_to
    if target is not None:
        target = max(1, min(target, total))

    page_metadata = decision.page_metadata or {}

    if target is not None and decision.answer_text:
        await ws_manager.broadcast_json(
            sess.session_id,
            {
                "type": "navigate_and_answer",
                "target_page": target,
                "answer_text": decision.answer_text,
                "audio_url": audio_url,
                "source_pages": [target],
                "page_metadata": page_metadata,
            },
        )
    elif target is not None:
        await ws_manager.broadcast_json(
            sess.session_id,
            {
                "type": "navigate",
                "target_page": target,
                "page_metadata": page_metadata,
            },
        )
    elif decision.answer_text:
        await ws_manager.broadcast_json(
            sess.session_id,
            {
                "type": "answer",
                "answer_text": decision.answer_text,
                "audio_url": audio_url,
                "source_pages": [],
                "page_metadata": page_metadata,
            },
        )

    await ws_manager.broadcast_json(
        sess.session_id, {"type": "status", "status": "listening"}
    )


def queue_depth() -> int:
    return _ensure_queue().qsize()
