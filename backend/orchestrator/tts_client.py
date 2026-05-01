from __future__ import annotations

import httpx
import logging

from config import Settings, get_settings
from services import audio_store

logger = logging.getLogger(__name__)


async def synthesize_url(text: str, settings: Settings | None = None) -> str | None:
    """Return a playable audio URL for the Presentation page, or None if TTS unavailable."""
    settings = settings or get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {"text": text, "model_id": "eleven_turbo_v2_5"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body, headers=headers)
        if r.status_code != 200:
            logger.warning(
                "ElevenLabs synthesis failed status=%s body=%s",
                r.status_code,
                (r.text or "")[:200],
            )
            return None
    clip_id = audio_store.save_mp3(r.content)
    base = settings.backend_url.rstrip("/")
    return f"{base}/api/tts/{clip_id}.mp3"
