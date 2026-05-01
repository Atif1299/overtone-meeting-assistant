from __future__ import annotations

from api.realtime_relay import _session_update_payload
from config import get_settings


def test_session_update_payload_uses_vad_settings() -> None:
    settings = get_settings()
    previous = (
        settings.openai_realtime_vad_threshold,
        settings.openai_realtime_vad_silence_ms,
        settings.openai_realtime_vad_prefix_padding_ms,
        settings.openai_realtime_interrupt_response,
    )
    settings.openai_realtime_vad_threshold = 0.9
    settings.openai_realtime_vad_silence_ms = 1200
    settings.openai_realtime_vad_prefix_padding_ms = 500
    settings.openai_realtime_interrupt_response = False
    try:
        payload = _session_update_payload(
            presentation_id="demo",
            system_prompt="You are VoiceNav.",
        )
    finally:
        (
            settings.openai_realtime_vad_threshold,
            settings.openai_realtime_vad_silence_ms,
            settings.openai_realtime_vad_prefix_padding_ms,
            settings.openai_realtime_interrupt_response,
        ) = previous

    turn_detection = payload["session"]["turn_detection"]
    assert turn_detection["type"] == "server_vad"
    assert turn_detection["threshold"] == 0.9
    assert turn_detection["silence_duration_ms"] == 1200
    assert turn_detection["prefix_padding_ms"] == 500
    assert turn_detection["interrupt_response"] is False


def test_session_update_payload_clamps_bad_vad_values() -> None:
    settings = get_settings()
    previous = (
        settings.openai_realtime_vad_threshold,
        settings.openai_realtime_vad_silence_ms,
        settings.openai_realtime_vad_prefix_padding_ms,
    )
    settings.openai_realtime_vad_threshold = 4.2
    settings.openai_realtime_vad_silence_ms = -10
    settings.openai_realtime_vad_prefix_padding_ms = -1
    try:
        payload = _session_update_payload(
            presentation_id="demo",
            system_prompt="You are VoiceNav.",
        )
    finally:
        (
            settings.openai_realtime_vad_threshold,
            settings.openai_realtime_vad_silence_ms,
            settings.openai_realtime_vad_prefix_padding_ms,
        ) = previous

    turn_detection = payload["session"]["turn_detection"]
    assert turn_detection["threshold"] == 1.0
    assert turn_detection["silence_duration_ms"] == 300
    assert turn_detection["prefix_padding_ms"] == 0
