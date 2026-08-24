from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.config import effective_realtime_provider, get_settings
from app.db import SessionLocal
from app.domain import agents as agent_store
from app.domain.session_store import store
from app.realtime.gemini_live import (
    decode_browser_pcm_b64,
    encode_pcm_b64,
    new_event_id,
    new_item_id,
    new_response_id,
    openai_tools_to_gemini,
    parse_tool_args,
    presenter_audio_delta_event,
    presenter_transcript_delta_event,
    presenter_turn_end_events,
    presenter_turn_start_events,
    resample_pcm16_mono,
)
from app.realtime.tools import REALTIME_TOOLS, tools
from app.realtime.ws_hub import hub

logger = logging.getLogger("overtone.v2.realtime")
router = APIRouter()


@router.websocket("/ws/presentation/{session_id}")
async def presentation_ws(websocket: WebSocket, session_id: str):
    await hub.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(session_id, websocket)


@router.websocket("/ws/realtime/{session_id}")
async def realtime_ws(websocket: WebSocket, session_id: str):
    sess = store.get(session_id)
    if not sess:
        await websocket.close(code=4404)
        return
    await websocket.accept(subprotocol="realtime")
    provider = effective_realtime_provider()
    runtime = RelayRuntime(websocket, sess.session_id, provider)
    try:
        await runtime.run()
    except WebSocketDisconnect:
        logger.info("browser disconnected session_id=%s", session_id)
    except Exception:
        logger.exception("realtime failed session_id=%s", session_id)
    finally:
        await runtime.close()


class RelayRuntime:
    def __init__(self, browser_ws: WebSocket, session_id: str, provider: str):
        self._browser_ws = browser_ws
        self._session_id = session_id
        self._provider = provider
        self._gemini_session = None
        self._closed = False

    def _session(self):
        return store.get(self._session_id)

    def _muted(self) -> bool:
        sess = self._session()
        return bool(sess and (sess.extra or {}).get("muted"))

    async def _send_browser(self, payload: dict) -> None:
        if self._closed:
            return
        await self._browser_ws.send_text(json.dumps(payload))

    async def _set_state(self, **fields) -> None:
        store.merge_extra(self._session_id, **fields)

    async def run(self) -> None:
        if self._provider == "gemini":
            await self._run_gemini()
        else:
            await self._run_openai()

    async def close(self) -> None:
        self._closed = True

    def _instructions(self) -> str:
        db = SessionLocal()
        try:
            sess = self._session()
            name = (sess.agent_name if sess else "default") or "default"
            return agent_store.instructions_for(db, name)
        finally:
            db.close()

    async def _run_openai(self) -> None:
        settings = get_settings()
        url = f"wss://api.openai.com/v1/realtime?model={settings.openai_realtime_model}"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        async with websockets.connect(url, additional_headers=headers, max_size=8_000_000) as oai:
            await oai.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "instructions": self._instructions(),
                            "voice": settings.openai_realtime_voice,
                            "tools": REALTIME_TOOLS,
                            "modalities": ["text", "audio"],
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": settings.openai_realtime_vad_threshold,
                                "prefix_padding_ms": settings.openai_realtime_vad_prefix_padding_ms,
                                "silence_duration_ms": settings.openai_realtime_vad_silence_ms,
                            },
                        },
                    }
                )
            )
            await self._send_browser({"type": "session.created", "event_id": new_event_id()})
            await self._inject_greeting_openai(oai)
            await asyncio.gather(
                self._pump_browser_to_openai(oai),
                self._pump_openai_to_browser(oai),
            )

    async def _inject_greeting_openai(self, oai) -> None:
        sess = self._session()
        if sess and (sess.extra or {}).get("session_greeting_sent"):
            return
        await oai.send(
            json.dumps(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Greet briefly and say you are ready to present from the deck.",
                            }
                        ],
                    },
                }
            )
        )
        await oai.send(json.dumps({"type": "response.create"}))
        await self._set_state(session_greeting_sent=True)

    async def _pump_browser_to_openai(self, oai) -> None:
        while not self._closed:
            incoming = await self._browser_ws.receive()
            if incoming.get("type") == "websocket.disconnect":
                break
            text = incoming.get("text")
            if not text:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                continue
            et = event.get("type")
            if et in {"input_audio_buffer.append", "input_audio_buffer.commit"} and self._muted():
                continue
            if et == "response.create" or et.startswith("conversation.item"):
                # block client-side tool execution; tools are server-side
                pass
            await oai.send(text)

    async def _pump_openai_to_browser(self, oai) -> None:
        async for raw in oai:
            if self._closed:
                break
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "response.output_item.done":
                item = event.get("item") or {}
                if item.get("type") == "function_call":
                    await self._handle_openai_tool(oai, item)
                    continue
            if self._muted() and event.get("type", "").startswith("response.audio"):
                continue
            await self._send_browser(event)

    async def _handle_openai_tool(self, oai, item: dict) -> None:
        name = item.get("name") or ""
        call_id = item.get("call_id") or item.get("id") or ""
        if self._muted() and name not in {"mute_self", "unmute_self"}:
            result = {"ok": False, "reason": "muted"}
        else:
            result = await tools.execute(self._session_id, name, item.get("arguments"))
        await oai.send(
            json.dumps(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result),
                    },
                }
            )
        )
        await oai.send(json.dumps({"type": "response.create"}))

    async def _run_gemini(self) -> None:
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.gemini_live_voice)
                )
            ),
            tools=[types.Tool(function_declarations=openai_tools_to_gemini(REALTIME_TOOLS))],
            system_instruction=self._instructions(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        async with client.aio.live.connect(model=settings.gemini_live_model, config=config) as session:
            self._gemini_session = session
            await self._send_browser({"type": "session.created", "event_id": new_event_id()})
            await self._send_browser({"type": "session.updated", "event_id": new_event_id()})
            recv_task = asyncio.create_task(self._pump_gemini_to_browser())
            await asyncio.sleep(0)
            await self._inject_greeting_gemini(session)
            try:
                await self._pump_browser_to_gemini(session)
            finally:
                recv_task.cancel()
                try:
                    await recv_task
                except asyncio.CancelledError:
                    pass

    async def _inject_greeting_gemini(self, session) -> None:
        sess = self._session()
        if sess and (sess.extra or {}).get("session_greeting_sent"):
            return
        text = "Greet briefly and say you are ready to present from the deck."
        try:
            await session.send_realtime_input(text=text)
        except Exception:
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]},
                turn_complete=True,
            )
        await self._set_state(session_greeting_sent=True)

    async def _pump_browser_to_gemini(self, session) -> None:
        while not self._closed:
            incoming = await self._browser_ws.receive()
            if incoming.get("type") == "websocket.disconnect":
                break
            text = incoming.get("text")
            if not text:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                continue
            et = event.get("type")
            if et == "input_audio_buffer.append":
                if self._muted():
                    continue
                pcm24 = decode_browser_pcm_b64(event.get("audio") or "")
                pcm16 = resample_pcm16_mono(pcm24, 24000, 16000)
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm16, mime_type="audio/pcm;rate=16000")
                )
            elif et == "input_audio_buffer.commit":
                continue

    async def _pump_gemini_to_browser(self) -> None:
        """Forward Gemini Live audio to presenter.

        google-genai Live ``receive()`` completes after each model turn — keep
        calling it so the bot stays listening. On barge-in, emit
        ``input_audio_buffer.speech_started`` so the presenter interrupts playback
        (same contract as V1 / OpenAI Realtime client).
        """
        assert self._gemini_session is not None
        while not self._closed:
            try:
                response_id: str | None = None
                item_id: str | None = None
                turn_started = False

                async def ensure_turn() -> tuple[str, str]:
                    nonlocal response_id, item_id, turn_started
                    if turn_started and response_id and item_id:
                        return response_id, item_id
                    response_id = new_response_id()
                    item_id = new_item_id()
                    turn_started = True
                    for ev in presenter_turn_start_events(response_id=response_id, item_id=item_id):
                        await self._send_browser(ev)
                    return response_id, item_id

                async for chunk in self._gemini_session.receive():
                    if self._closed:
                        return
                    if getattr(chunk, "tool_call", None):
                        await self._handle_gemini_tools(chunk.tool_call)
                        continue
                    sc = getattr(chunk, "server_content", None)
                    if not sc:
                        continue

                    if getattr(sc, "interrupted", False):
                        speech_item = new_item_id()
                        await self._send_browser(
                            {
                                "event_id": new_event_id(),
                                "type": "input_audio_buffer.speech_started",
                                "item_id": speech_item,
                                "audio_start_ms": 0,
                            }
                        )
                        await self._send_browser(
                            {"type": "response.cancelled", "event_id": new_event_id()}
                        )
                        turn_started = False
                        response_id = None
                        item_id = None
                        continue

                    model_turn = getattr(sc, "model_turn", None)
                    if model_turn and getattr(model_turn, "parts", None):
                        for part in model_turn.parts:
                            inline = getattr(part, "inline_data", None)
                            if inline and getattr(inline, "data", None):
                                if self._muted():
                                    continue
                                pcm = inline.data
                                if isinstance(pcm, str):
                                    pcm = decode_browser_pcm_b64(pcm)
                                pcm24 = resample_pcm16_mono(pcm, 24000, 24000)
                                rid, iid = await ensure_turn()
                                await self._send_browser(
                                    presenter_audio_delta_event(
                                        item_id=iid,
                                        pcm_b64=encode_pcm_b64(pcm24),
                                    )
                                )
                            text = getattr(part, "text", None)
                            if text:
                                rid, iid = await ensure_turn()
                                await self._send_browser(
                                    presenter_transcript_delta_event(item_id=iid, text=text)
                                )

                    out_tx = getattr(sc, "output_transcription", None)
                    if out_tx is not None:
                        text = getattr(out_tx, "text", None) or str(out_tx)
                        if text and not self._muted():
                            rid, iid = await ensure_turn()
                            await self._send_browser(
                                presenter_transcript_delta_event(item_id=iid, text=text)
                            )

                    if getattr(sc, "turn_complete", False):
                        if turn_started and response_id and item_id:
                            for ev in presenter_turn_end_events(
                                response_id=response_id, item_id=item_id
                            ):
                                await self._send_browser(ev)
                        turn_started = False
                        response_id = None
                        item_id = None

                    if getattr(chunk, "go_away", None):
                        logger.warning("gemini go_away session_id=%s", self._session_id)
                        return

                logger.info(
                    "gemini receive() ended after turn; continuing listen loop session_id=%s",
                    self._session_id,
                )
            except Exception:
                if self._closed:
                    return
                logger.exception("gemini receive error; retrying listen loop")
                await asyncio.sleep(0.2)

    async def _handle_gemini_tools(self, tool_call: Any) -> None:
        assert self._gemini_session is not None
        responses = []
        for fc in getattr(tool_call, "function_calls", None) or []:
            name = getattr(fc, "name", "") or ""
            args = parse_tool_args(getattr(fc, "args", None))
            if self._muted() and name not in {"mute_self", "unmute_self"}:
                result = {"ok": False, "reason": "muted"}
            else:
                result = await tools.execute(self._session_id, name, args)
            responses.append(
                types.FunctionResponse(id=getattr(fc, "id", None), name=name, response=result)
            )
        await self._gemini_session.send_tool_response(function_responses=responses)
