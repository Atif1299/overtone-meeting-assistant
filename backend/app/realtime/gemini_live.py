"""Helpers for Gemini Live + Vision (no OpenRouter pipeline)."""

from __future__ import annotations

import array
import base64
import json
import uuid
from typing import Any


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def new_item_id() -> str:
    return f"item_{uuid.uuid4().hex}"


def new_response_id() -> str:
    return f"resp_{uuid.uuid4().hex}"


def resample_pcm16_mono(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear-resample little-endian int16 mono PCM."""
    if src_rate == dst_rate or not pcm:
        return pcm
    if len(pcm) % 2:
        pcm = pcm[:-1]
    samples = array.array("h")
    samples.frombytes(pcm)
    if not samples:
        return b""
    ratio = float(src_rate) / float(dst_rate)
    out_len = max(1, int(len(samples) / ratio))
    out = array.array("h")
    last = len(samples) - 1
    for i in range(out_len):
        src_idx = i * ratio
        i0 = int(src_idx)
        i1 = min(i0 + 1, last)
        frac = src_idx - i0
        val = int(samples[i0] * (1.0 - frac) + samples[i1] * frac)
        if val > 32767:
            val = 32767
        elif val < -32768:
            val = -32768
        out.append(val)
    return out.tobytes()


def openai_tools_to_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI Realtime function tool defs to Gemini function_declarations."""
    decls: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "").strip()
        if not name:
            continue
        decl: dict[str, Any] = {
            "name": name,
            "description": str(tool.get("description") or ""),
        }
        params = tool.get("parameters")
        if isinstance(params, dict):
            decl["parameters"] = params
        decls.append(decl)
    return decls


def decode_browser_pcm_b64(audio_b64: str) -> bytes:
    return base64.b64decode(audio_b64)


def encode_pcm_b64(pcm: bytes) -> str:
    return base64.b64encode(pcm).decode("ascii")


def parse_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


def presenter_turn_start_events(*, response_id: str, item_id: str) -> list[dict[str, Any]]:
    """Emit the OpenAI-beta event chain @openai/realtime-api-beta needs before audio."""
    return [
        {
            "event_id": new_event_id(),
            "type": "response.created",
            "response": {"id": response_id, "output": []},
        },
        {
            "event_id": new_event_id(),
            "type": "conversation.item.created",
            "item": {
                "id": item_id,
                "object": "realtime.item",
                "type": "message",
                "status": "in_progress",
                "role": "assistant",
                "content": [],
            },
        },
        {
            "event_id": new_event_id(),
            "type": "response.output_item.added",
            "response_id": response_id,
            "output_index": 0,
            "item": {
                "id": item_id,
                "object": "realtime.item",
                "type": "message",
                "status": "in_progress",
                "role": "assistant",
                "content": [],
            },
        },
        {
            "event_id": new_event_id(),
            "type": "response.content_part.added",
            "response_id": response_id,
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "audio", "transcript": ""},
        },
    ]


def presenter_audio_delta_event(*, item_id: str, pcm_b64: str) -> dict[str, Any]:
    return {
        "event_id": new_event_id(),
        "type": "response.audio.delta",
        "item_id": item_id,
        "content_index": 0,
        "delta": pcm_b64,
    }


def presenter_transcript_delta_event(*, item_id: str, text: str) -> dict[str, Any]:
    # Client listens for response.audio_transcript.delta (underscore), not dotted.
    return {
        "event_id": new_event_id(),
        "type": "response.audio_transcript.delta",
        "item_id": item_id,
        "content_index": 0,
        "delta": text,
    }


def presenter_turn_end_events(*, response_id: str, item_id: str) -> list[dict[str, Any]]:
    return [
        {
            "event_id": new_event_id(),
            "type": "response.output_item.done",
            "response_id": response_id,
            "output_index": 0,
            "item": {
                "id": item_id,
                "object": "realtime.item",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "audio", "transcript": ""}],
            },
        },
        {
            "event_id": new_event_id(),
            "type": "response.done",
            "response": {"id": response_id, "status": "completed", "output": [item_id]},
        },
    ]
