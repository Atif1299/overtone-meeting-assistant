from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import connect as ws_connect

from agents.runtime import compose_realtime_instructions
from config import get_settings
from models.bot_session import AgentMode, BotSession
from orchestrator.realtime_tools import REALTIME_TOOLS, RealtimeToolExecutor
from orchestrator.ws_manager import ws_manager
from orchestrator import relay_registry
from services.filler_audio import get_random_filler_b64
from services.session_store import store
from database import get_db
from sqlalchemy.orm import Session

router = APIRouter(tags=["realtime-relay"])
logger = logging.getLogger(__name__)


def _openai_realtime_url() -> str:
    settings = get_settings()
    model = quote(settings.openai_realtime_model, safe="")
    return f"wss://api.openai.com/v1/realtime?model={model}"


def _session_update_payload(*, presentation_id: str, system_prompt: str, current_page: int = 1, auto_present_pages: int = 0, last_retrieval_context: str = "") -> dict:
    settings = get_settings()
    instructions = compose_realtime_instructions(
        system_prompt=system_prompt,
        presentation_id=presentation_id,
        current_page=current_page,
        auto_present_pages=auto_present_pages,
        last_retrieval_context=last_retrieval_context,
    )
    vad_threshold = min(max(float(settings.openai_realtime_vad_threshold), 0.0), 1.0)
    silence_ms = max(int(settings.openai_realtime_vad_silence_ms), 300)
    prefix_padding_ms = max(int(settings.openai_realtime_vad_prefix_padding_ms), 0)
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "voice": settings.openai_realtime_voice,
            "turn_detection": {
                "type": "server_vad",
                "threshold": vad_threshold,
                "silence_duration_ms": silence_ms,
                "prefix_padding_ms": prefix_padding_ms,
                "create_response": True,
                "interrupt_response": settings.openai_realtime_interrupt_response,
            },
            "instructions": instructions,
            "tools": REALTIME_TOOLS,
            "tool_choice": "auto",
        },
    }


@router.websocket("/ws/realtime/{session_id}")
async def realtime_relay(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)) -> None:
    sess = await store.get_by_session_id(session_id)
    if not sess:
        # Fall back to DB — session exists there even after a server restart
        db_sess = db.query(BotSession).filter(BotSession.session_id == session_id).first()
        if not db_sess:
            await websocket.accept(subprotocol="realtime")
            await websocket.close(code=4404)
            return
        sess = db_sess
        # Register into the in-memory store so that tool calls (navigate_to_slide,
        # search_and_answer, etc.) can find this session via store.get_by_session_id.
        # Without this, every tool call after a server restart raises "Session not found".
        await store.register_session(sess)
    if sess.agent_mode != AgentMode.REALTIME:
        await websocket.accept(subprotocol="realtime")
        await websocket.close(code=4409, reason="Session is not configured for realtime mode")
        return

    settings = get_settings()
    if not settings.openai_api_key:
        await websocket.accept(subprotocol="realtime")
        await websocket.close(code=1011, reason="OPENAI_API_KEY is not configured")
        return

    await websocket.accept(subprotocol="realtime")
    relay = _RealtimeRelayRuntime(
        browser_ws=websocket,
        session=sess,
    )
    await relay.run()


class _RealtimeRelayRuntime:
    def __init__(self, *, browser_ws: WebSocket, session: BotSession) -> None:
        self._browser_ws = browser_ws
        self._session = session
        self._settings = get_settings()
        self._tool_executor = RealtimeToolExecutor(self._settings)
        self._openai_ws = None
        self._connected_monotonic: float | None = None
        self._first_audio_recorded = False
        self._tool_calls = int(session.extra.get("tool_calls", 0) or 0)
        self._tool_failures = int(session.extra.get("tool_failures", 0) or 0)
        self._relay_profile = str(session.extra.get("relay_profile") or "voicenav")
        # Auto-present: server drives navigation, not the model
        self._auto_present_limit = int(session.extra.get("auto_present_pages") or 0)
        self._auto_present_page = 0  # 0 = haven't started yet
        self._model_has_narrated = False  # True after model's first speech completes
        self._current_page = 1
        # Chat-reply state: tracks text-only responses triggered by incoming chat messages
        self._chat_reply_sender: str | None = None
        self._chat_reply_buffer: list[str] = []
        self._in_chat_response: bool = False

    async def run(self) -> None:
        uri = _openai_realtime_url()
        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "realtime=v1",
        }
        await self._set_state(relay_status="connecting", fallback_active=False)

        try:
            if self._relay_profile == "demo":
                await self._run_demo_passthrough(uri, headers)
                return
            async with ws_connect(
                uri,
                extra_headers=headers,
                subprotocols=["realtime"],
                ping_interval=20,
                ping_timeout=20,
                max_size=None,
            ) as openai_ws:
                self._openai_ws = openai_ws
                self._connected_monotonic = time.monotonic()
                relay_registry.register(self._session.session_id, openai_ws, self)
                logger.info("Realtime relay connected session_id=%s", self._session.session_id)
                await self._set_state(
                    relay_status="connected",
                    relay_connected_at=_now_utc_iso(),
                    relay_last_error=None,
                )

                initial = await openai_ws.recv()
                await self._set_state(relay_last_event_at=_now_utc_iso())
                await self._browser_ws.send_text(initial)
                agent_prompt = str(
                    self._session.extra.get("agent_system_prompt")
                    or "You are Overtone, a live voice assistant."
                )
                auto_present_pages = int(
                    self._session.extra.get("auto_present_pages") or 0
                )
                last_context = str(self._session.extra.get("last_retrieval_context", ""))
                await openai_ws.send(
                    json.dumps(
                        _session_update_payload(
                            presentation_id=self._session.presentation_id,
                            system_prompt=agent_prompt,
                            current_page=self._current_page,
                            auto_present_pages=auto_present_pages,
                            last_retrieval_context=last_context,
                        )
                    )
                )

                # Wait for session.updated before injecting anything.
                # OpenAI must finish applying our session config (VAD, tools, voice)
                # before we can safely inject conversation items — otherwise the
                # item arrives before VAD/tools are wired up and OpenAI drops it.
                async with asyncio.timeout(5):
                    while True:
                        msg = await openai_ws.recv()
                        await self._set_state(relay_last_event_at=_now_utc_iso())
                        await self._browser_ws.send_text(msg)
                        evt = json.loads(msg)
                        if evt.get("type") == "session.updated":
                            logger.info("session.updated received — ready to inject greeting")
                            break

                # If auto-present is on, inject slide 1 content immediately
                # so the model narrates it right away instead of monologuing an intro.
                if self._auto_present_limit > 0:
                    self._auto_present_page = 1
                    await ws_manager.broadcast_json(
                        self._session.session_id,
                        {"type": "navigate", "target_page": 1},
                    )
                    slide_content = ""
                    slide_title = ""
                    try:
                        from services import storage as storage_mod
                        pages = storage_mod.load_index_pages(self._session.presentation_id)
                        for page in (pages or []):
                            if int(page.get("page_number", 0)) == 1:
                                slide_content = str(
                                    page.get("searchable_content") or page.get("content_text") or ""
                                ).strip()[:1500]
                                slide_title = str(page.get("title") or "")
                                break
                    except Exception:
                        pass
                    
                    if slide_content:
                        await openai_ws.send(
                            json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{
                                        "type": "input_text",
                                        "text": (
                                            f"SESSION START. Slide 1 context (for your reference only — do NOT narrate yet):\n"
                                            f"Title: {slide_title}\n{slide_content}\n\n"
                                            "Greet the participants warmly, use the slide context to tease what this presentation is about "
                                            "in one compelling sentence, then ask if they're ready to begin."
                                        ),
                                    }],
                                },
                            })
                        )
                    else:
                        await openai_ws.send(
                            json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "SESSION START. Greet the participants warmly and ask if they're ready to begin the presentation."}],
                                },
                            })
                        )

                    # Force the model to respond instantly with its greeting
                    await openai_ws.send(json.dumps({"type": "response.create"}))
                    logger.info("Auto-present: injected greeting trigger at session start")

                else:
                    # Q&A mode — bot should speak first when it joins the room.
                    # Inject a session-start trigger so the model greets participants
                    # immediately rather than sitting silent until someone speaks.
                    await openai_ws.send(
                        json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "SESSION_START"}],
                            },
                        })
                    )
                    await openai_ws.send(json.dumps({"type": "response.create"}))
                    logger.info("Q&A mode: injected greeting trigger at session start")

                browser_task = asyncio.create_task(self._pump_browser_to_openai())
                openai_task = asyncio.create_task(self._pump_openai_to_browser())
                done, pending = await asyncio.wait(
                    [browser_task, openai_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    err = task.exception()
                    if err:
                        raise err
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
        except ConnectionClosed:
            logger.info("Realtime relay closed session_id=%s", self._session.session_id)
        except WebSocketDisconnect:
            logger.info("Browser disconnected session_id=%s", self._session.session_id)
        except Exception as exc:
            logger.exception("Realtime relay failed session_id=%s", self._session.session_id)
            await self._increment_error(str(exc))
        finally:
            relay_registry.unregister(self._session.session_id)
            await self._set_state(relay_status="disconnected")

    async def _run_demo_passthrough(self, uri: str, headers: dict[str, str]) -> None:
        logger.info("Realtime relay using demo profile session_id=%s", self._session.session_id)
        async with ws_connect(
            uri,
            extra_headers=headers,
            subprotocols=["realtime"],
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        ) as openai_ws:
            self._openai_ws = openai_ws
            self._connected_monotonic = time.monotonic()
            logger.info("Realtime demo relay connected session_id=%s", self._session.session_id)
            await self._set_state(
                relay_status="connected",
                relay_connected_at=_now_utc_iso(),
                relay_last_error=None,
            )

            initial = await openai_ws.recv()
            await self._set_state(relay_last_event_at=_now_utc_iso())
            await self._browser_ws.send_text(initial)

            async def browser_to_openai() -> None:
                while True:
                    try:
                        message = await self._browser_ws.receive_text()
                    except WebSocketDisconnect:
                        return
                    await openai_ws.send(message)

            async def openai_to_browser() -> None:
                while True:
                    message = await openai_ws.recv()
                    payload = _safe_json(message)
                    if payload and str(payload.get("type") or "") == "response.audio.delta":
                        await self._record_first_audio_latency()
                    await self._set_state(relay_last_event_at=_now_utc_iso())
                    await self._browser_ws.send_text(message)

            tasks = [
                asyncio.create_task(browser_to_openai()),
                asyncio.create_task(openai_to_browser()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    async def _pump_browser_to_openai(self) -> None:
        assert self._openai_ws is not None
        msg_count = 0
        while True:
            message = await self._browser_ws.receive_text()
            msg_count += 1
            maybe_event = _safe_json(message)
            event_type = maybe_event.get("type", "unknown") if maybe_event else "non-json"
            logger.debug(
                "Browser→OpenAI msg#%d session_id=%s type=%s",
                msg_count, self._session.session_id, event_type,
            )
            if maybe_event and maybe_event.get("type") == "session.update":
                # The backend owns session config (tools/instructions). Ignore client overrides.
                logger.info(
                    "Ignored browser session.update session_id=%s (backend owns config)",
                    self._session.session_id,
                )
                continue
            # Audio always flows to OpenAI even while muted so the model can hear
            # voice commands (e.g. 'unmute'). The output-side response.audio.delta
            # drop in _pump_openai_to_browser keeps the bot silent while muted.
            await self._openai_ws.send(message)

    async def _pump_openai_to_browser(self) -> None:
        import websockets
        assert self._openai_ws is not None
        try:
            while True:
                message = await self._openai_ws.recv()
                payload = _safe_json(message)
                should_forward = True
                if payload:
                    should_forward = await self._handle_openai_event(payload)
                if should_forward:
                    try:
                        await self._browser_ws.send_text(message)
                    except (websockets.exceptions.ConnectionClosed, RuntimeError, Exception) as e:
                        logger.warning("Browser WebSocket send failed (stale connection): %s", e)
                        break # Stop pumping if browser is gone
        except websockets.exceptions.ConnectionClosed:
            logger.info("OpenAI WebSocket closed in _pump_openai_to_browser")
        except Exception as e:
            logger.error("Unexpected error in _pump_openai_to_browser: %s", e)

    async def _handle_openai_event(self, payload: dict) -> bool:
        await self._set_state(relay_last_event_at=_now_utc_iso())
        event_type = str(payload.get("type") or "")

        if event_type == "input_audio_buffer.speech_started":
            # Auto-present: advance slide when user speaks (only when not muted)
            if (not self._session.extra.get("muted")
                    and self._auto_present_limit > 0
                    and self._auto_present_page < self._auto_present_limit
                    and self._model_has_narrated):
                await self._auto_advance_on_speech()

        if event_type == "response.audio.delta":
            await self._record_first_audio_latency()
            # Drop audio while muted OR during a text-only chat response
            if self._session.extra.get("muted") or self._in_chat_response:
                return False
            return True

        # Drop audio transcript and text deltas while muted so nothing leaks to
        # the browser TTS path (e.g. model saying "Silence." as a text reply).
        if event_type in {
            "response.audio.transcript.delta",
            "response.audio.transcript.done",
        }:
            if self._session.extra.get("muted"):
                return False

        # ── Text-only chat response: capture delta, send as Recall chat on done ────
        if event_type == "response.text.delta":
            if self._session.extra.get("muted") and not self._in_chat_response:
                return False  # swallow stray text responses while muted
            if self._in_chat_response:
                self._chat_reply_buffer.append(str(payload.get("delta") or ""))
            return True  # forward to browser for UI

        if event_type == "response.done" and self._in_chat_response:
            full_text = "".join(self._chat_reply_buffer).strip()
            # Fallback: extract from response.output if buffer empty (edge case)
            if not full_text:
                response_obj = payload.get("response") or {}
                for out_item in response_obj.get("output", []):
                    if isinstance(out_item, dict) and out_item.get("type") == "message":
                        for content in out_item.get("content", []):
                            if isinstance(content, dict) and content.get("type") == "text":
                                full_text += content.get("text", "")
            # Reset chat-reply state
            self._in_chat_response = False
            self._chat_reply_buffer = []
            reply_sender = self._chat_reply_sender or "Unknown"
            self._chat_reply_sender = None
            # Re-enable VAD now that the text-only response is done
            asyncio.ensure_future(self._push_session_update())
            # Send the text back into the meeting chat
            if full_text:
                recall_bot_id = getattr(self._session, "recall_bot_id", None)
                if recall_bot_id:
                    try:
                        from services.recall_client import RecallClient
                        client = RecallClient(self._settings)
                        await client.send_chat_message(recall_bot_id, full_text)
                        logger.info(
                            "Chat reply sent to meeting session_id=%s sender=%s: %r",
                            self._session.session_id, reply_sender, full_text[:80],
                        )
                        await ws_manager.broadcast_json(
                            self._session.session_id,
                            {
                                "type": "chat_message",
                                "sender": "Bot",
                                "text": full_text,
                                "direction": "outgoing",
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to send chat reply session_id=%s: %s",
                            self._session.session_id, exc,
                        )
                else:
                    logger.warning(
                        "No recall_bot_id — cannot send chat reply session_id=%s",
                        self._session.session_id,
                    )
            if not self._model_has_narrated:
                self._model_has_narrated = True
            return True  # still forward response.done to browser
        # ────────────────────────────────────────────────────────────────────────────
        if event_type == "error":
            err_obj = payload.get("error")
            if isinstance(err_obj, dict):
                message = str(err_obj.get("message") or "OpenAI realtime error")
            else:
                message = "OpenAI realtime error"
            await self._increment_error(message)
            return True
        if event_type == "conversation.item.created":
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                # Browser RealtimeClient auto-runs tools when it sees function_call completion.
                # Keep tool execution server-side only to prevent duplicate/conflicting calls.
                return False
        if event_type == "response.output_item.added":
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                return False
        if event_type == "response.output_item.done":
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                await self._handle_function_call(item)
                return False
        if event_type in {
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
        }:
            return False
        if event_type == "response.done":
            # Mark that the model has spoken — enables auto-advance on next user speech
            if not self._model_has_narrated:
                self._model_has_narrated = True
            # Strip function_call items from response.output before forwarding.
            # If the browser's RealtimeClient sees them it will try to auto-execute
            # the tool client-side, creating a duplicate response.
            response = payload.get("response")
            if isinstance(response, dict):
                output = response.get("output")
                if isinstance(output, list) and any(
                    isinstance(item, dict) and item.get("type") == "function_call"
                    for item in output
                ):
                    cleaned = [
                        item for item in output
                        if not (isinstance(item, dict) and item.get("type") == "function_call")
                    ]
                    response["output"] = cleaned
                    await self._browser_ws.send_text(json.dumps(payload))
                    return False
        return True

    async def handle_incoming_chat(self, sender: str, text: str) -> bool:
        """Inject a meeting chat message into OpenAI and reply text-only back to the meeting.

        The relay requests a text-only response (modalities=["text"]) so OpenAI does NOT
        produce audio. The response.text.delta events are captured in
        _chat_reply_buffer and, on response.done, the assembled text is sent back to
        the meeting via Recall's send_chat_message API.
        """
        if self._openai_ws is None:
            return False
        # Guard against concurrent chat requests (queue at most one at a time)
        if self._in_chat_response:
            logger.warning(
                "handle_incoming_chat: previous chat response still in flight, queuing sender=%s",
                sender,
            )
        self._in_chat_response = True
        self._chat_reply_sender = sender
        self._chat_reply_buffer = []
        try:
            # Disable VAD so OpenAI cannot auto-fire a voice response from
            # incoming audio while we wait for the text-only reply.
            await self._openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {"turn_detection": None},
            }))
            # Cancel any in-flight audio response and flush the audio buffer.
            await self._openai_ws.send(json.dumps({"type": "response.cancel"}))
            await self._openai_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
            await self._openai_ws.send(
                json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{
                            "type": "input_text",
                            "text": f"[MEETING CHAT from {sender}]: {text}",
                        }],
                    },
                })
            )
            await self._openai_ws.send(
                json.dumps({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text"],
                        "instructions": (
                            "A meeting participant sent you a text chat message. "
                            "Reply concisely (1-3 sentences). "
                            "Do NOT speak; your response will be delivered as a text chat message."
                        ),
                    },
                })
            )
            logger.info(
                "handle_incoming_chat: text-only request sent session_id=%s sender=%s",
                self._session.session_id, sender,
            )
            return True
        except Exception as exc:
            self._in_chat_response = False
            self._chat_reply_buffer = []
            self._chat_reply_sender = None
            logger.error("handle_incoming_chat failed session_id=%s: %s", self._session.session_id, exc)
            return False

    async def _handle_function_call(self, item: dict) -> None:
        assert self._openai_ws is not None
        t_call_start = time.monotonic()
        call_id = str(item.get("call_id") or "")
        tool_name = str(item.get("name") or "")
        arguments = item.get("arguments")
        self._tool_calls += 1
        logger.info(
            "⏱ [1] TOOL_CALL_RECEIVED session_id=%s tool=%s call_id=%s",
            self._session.session_id, tool_name, call_id,
        )

        # While muted, block ALL tool execution except unmute_self / mute_self.
        # Audio still reaches OpenAI so the model can detect the unmute command,
        # but we must suppress every other action here server-side — the prompt
        # alone is insufficient to prevent the model from calling tools.
        _MUTE_ALLOWED_TOOLS = {"unmute_self", "mute_self"}
        if self._session.extra.get("muted") and tool_name not in _MUTE_ALLOWED_TOOLS:
            logger.info(
                "MUTED: blocked tool=%s call_id=%s session_id=%s",
                tool_name, call_id, self._session.session_id,
            )
            # Return a no-op result so OpenAI doesn't hang waiting for a function output.
            # Do NOT fire response.create — that would cause the model to generate a
            # text reply (e.g. "Silence.") which would get spoken.
            await self._openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({"ok": False, "reason": "muted"}),
                },
            }))
            return

        # --- Filler audio: plays INSTANTLY via presentation WebSocket ---
        # Bypasses OpenAI entirely. Pre-recorded mp3 sent as base64 to the
        # browser, which decodes and plays it through the page audio context.
        # Recall captures it → meeting participants hear it immediately.
        if tool_name == "search_and_answer":
            filler_b64 = get_random_filler_b64()
            if filler_b64:
                await ws_manager.broadcast_json(
                    self._session.session_id,
                    {"type": "play_filler", "audio_b64": filler_b64},
                )
                logger.info(
                    "⏱ [1.5] FILLER_AUDIO_SENT session_id=%s",
                    self._session.session_id,
                )

        # Broadcast tool start to the frontend for UI loading states
        await ws_manager.broadcast_json(
            self._session.session_id,
            {"type": "tool_start", "call_id": call_id, "tool_name": tool_name},
        )

        # Execute the tool (RAG search runs while filler plays)
        output: dict
        try:
            output = await self._tool_executor.execute(
                session_id=self._session.session_id,
                tool_name=tool_name,
                raw_arguments=arguments,
            )
        except Exception as exc:
            self._tool_failures += 1
            output = {"ok": False, "error": str(exc), "tool_name": tool_name}
            await self._increment_error(str(exc))
            logger.warning(
                "Realtime tool failed session_id=%s tool=%s error=%s",
                self._session.session_id, tool_name, exc,
            )
        finally:
            # Broadcast tool completion to the frontend (unless it's a long-running async job)
            if output.get("action") != "async_job_started":
                await ws_manager.broadcast_json(
                    self._session.session_id,
                    {"type": "tool_done", "call_id": call_id, "tool_name": tool_name},
                )

        t_exec_ms = (time.monotonic() - t_call_start) * 1000
        logger.info(
            "⏱ [2] TOOL_EXEC_DONE session_id=%s tool=%s exec_ms=%.1f",
            self._session.session_id, tool_name, t_exec_ms,
        )

        # Send tool result to OpenAI → it generates TTS for the real answer
        await self._set_state(tool_calls=self._tool_calls, tool_failures=self._tool_failures)
        await self._openai_ws.send(
            json.dumps(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(output),
                    },
                }
            )
        )
        await self._openai_ws.send(json.dumps({"type": "response.create"}))
        logger.info(
            "⏱ [3] TOOL_RESULT_SENT_TO_OPENAI session_id=%s tool=%s total_tool_ms=%.1f "
            "(OpenAI TTS now generating)",
            self._session.session_id, tool_name, (time.monotonic() - t_call_start) * 1000,
        )

        if output.get("action") == "async_job_started":
            query = output.get("query", "unknown")
            asyncio.create_task(self._simulate_external_job(query, call_id))

        # Update current page if navigation happened
        new_page = output.get("page_number")
        if new_page and int(new_page) != self._current_page:
            self._current_page = int(new_page)
            await self._push_session_update()

    async def _push_session_update(self) -> None:
        """Push a session.update to OpenAI with the latest instructions and page context."""
        if self._openai_ws is None:
            return
        agent_prompt = str(
            self._session.extra.get("agent_system_prompt")
            or "You are Overtone, a live voice assistant."
        )
        auto_present_pages = int(
            self._session.extra.get("auto_present_pages") or 0
        )
        last_context = str(self._session.extra.get("last_retrieval_context", ""))
        await self._openai_ws.send(
            json.dumps(
                _session_update_payload(
                    presentation_id=self._session.presentation_id,
                    system_prompt=agent_prompt,
                    current_page=self._current_page,
                    auto_present_pages=auto_present_pages,
                    last_retrieval_context=last_context,
                )
            )
        )
        logger.info("Pushed session.update for page %d context", self._current_page)

    async def _simulate_external_job(self, query: str, call_id: str) -> None:
        """Simulate a long-running external job.
        Wait 30s, then simply 'return' the query as the data.
        """
        print(f"🔧 [BACKGROUND JOB] Starting processing for: {query} | Session: {self._session.session_id}")
        logger.info("🔧 [BACKGROUND JOB] Starting processing for: %s | Session: %s", query, self._session.session_id)
        
        from orchestrator import account_brief_retriever
        
        # Run deep search
        search_data = await account_brief_retriever.search_account_brief(query)
        
        # Save to session for context retention
        self._session.extra["last_retrieval_context"] = search_data
        await store.register_session(self._session)
        await self._push_session_update()
        
        if self._openai_ws is None:
            return

        try:
            
            print(f"DEBUG: Processing complete. Result: {search_data}")
            logger.info("✅ [BACKGROUND JOB] Processing complete. Injecting into session_id=%s", self._session.session_id)
            
            # Ask the participant for permission before sharing the data.
            # The model will only walk through the results if they confirm.
            injection_text = (
                f"NOTIFICATION: The external search for '{query}' has completed. "
                "Do NOT share the data yet. First, tell the participant the results are in and ask: "
                "'I've got the results for that — would you like me to walk you through them?' "
                "Wait for their response. Only if they say yes, share and explain the following data: "
                f"{search_data}"
            )
            
            print("DEBUG: Sending conversation.item.create (role: user) to OpenAI")
            await self._openai_ws.send(
                json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user", 
                        "content": [{
                            "type": "input_text", 
                            "text": injection_text
                        }],
                    },
                })
            )
            
            # Force the model to read out the result
            print("DEBUG: Triggering response.create")
            await self._openai_ws.send(json.dumps({"type": "response.create"}))

            # FINALLY broadcast tool_done so the toast disappears
            await ws_manager.broadcast_json(
                self._session.session_id,
                {"type": "tool_done", "call_id": call_id, "tool_name": "fetch_external_data"},
            )

        except Exception as e:
            print(f"❌ DEBUG: Background job error: {e}")
            logger.error("❌ [BACKGROUND JOB] Failed for session_id=%s: %s", self._session.session_id, e)
            try:
                await self._openai_ws.send(
                    json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{
                                "type": "input_text", 
                                "text": f"[SYSTEM ERROR: The processing for '{query}' failed. Inform the user.]"
                            }],
                        },
                    })
                )
                await self._openai_ws.send(json.dumps({"type": "response.create"}))
            except Exception:
                pass

    async def _auto_advance_on_speech(self) -> None:
        """Advance to the next slide when the user starts speaking during auto-present.

        The slide navigates and its content is injected into the conversation
        so the model's next response (after handling the user's speech) has the
        new slide context available. The model narrates the new slide naturally
        as part of its response.
        """
        if self._openai_ws is None:
            return

        next_page = self._auto_present_page + 1
        self._auto_present_page = next_page
        self._current_page = next_page
        
        await self._push_session_update()

        logger.info(
            "⏱ AUTO_ADVANCE_ON_SPEECH session_id=%s page=%d/%d",
            self._session.session_id, next_page, self._auto_present_limit,
        )

        # Navigate the frontend to the next slide
        await ws_manager.broadcast_json(
            self._session.session_id,
            {"type": "navigate", "target_page": next_page},
        )

        # Load slide content so the model has context for its response
        slide_content = ""
        slide_title = ""
        try:
            from services import storage as storage_mod
            pages = storage_mod.load_index_pages(self._session.presentation_id)
            for page in (pages or []):
                if int(page.get("page_number", 0)) == next_page:
                    slide_content = str(
                        page.get("searchable_content") or page.get("content_text") or ""
                    ).strip()[:1500]
                    slide_title = str(page.get("title") or "")
                    break
        except Exception:
            pass

        # Inject slide content into conversation context
        prompt = (
            f"[Slide advanced to: '{slide_title}']\n"
            f"slide_content: {slide_content}\n\n"
            f"After responding to the user, narrate this new slide in 2-3 sentences "
            f"using ONLY the slide_content above. Do NOT mention slide numbers."
        )
        if next_page >= self._auto_present_limit:
            prompt += (
                "\n\nThis is the LAST slide. After narrating it:\n"
                "1. Ask: 'That covers everything. Do you have any questions, or is "
                "there anything you'd like to go deeper on?'\n"
                "2. Answer any questions the audience has using search_and_answer.\n"
                "3. When they say no / that's all / we're good / nothing else — say a "
                "brief thank-you ('Great, I'll leave you to it — thanks for your time.') "
                "and immediately call leave_call."
            )

        await self._openai_ws.send(
            json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            })
        )

    async def _record_first_audio_latency(self) -> None:
        if self._connected_monotonic is None:
            return
        latency_ms = (time.monotonic() - self._connected_monotonic) * 1000.0
        if not self._first_audio_recorded:
            self._first_audio_recorded = True
            logger.info(
                "⏱ [4] FIRST_AUDIO_CHUNK session_id=%s latency_from_connect_ms=%.1f",
                self._session.session_id, latency_ms,
            )
            await self._set_state(first_audio_latency_ms=round(latency_ms, 1))

    async def _increment_error(self, message: str) -> None:
        current = int(self._session.extra.get("realtime_errors", 0) or 0) + 1
        self._session.extra["realtime_errors"] = current
        await self._set_state(
            relay_last_error=message[:400],
            realtime_errors=current,
        )

    async def _set_state(self, **fields: object) -> None:
        await store.merge_extra(self._session.session_id, **fields)
        self._session = await store.get_by_session_id(self._session.session_id) or self._session


def _safe_json(message: str) -> dict | None:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
