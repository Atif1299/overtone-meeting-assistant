from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.security.presenter_token import sign_presenter_token


class RecallClient:
    def __init__(self):
        self.settings = get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.settings.recall_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def build_output_media_url(self, *, session_id: str, presentation_id: str) -> str:
        base = self.settings.frontend_url.rstrip("/")
        wss_base = self.settings.backend_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
        token = sign_presenter_token(session_id=session_id, presentation_id=presentation_id)
        qs = urlencode(
            {
                "session": session_id,
                "presentation": presentation_id,
                "wss": f"{wss_base}/ws/realtime/{session_id}",
                "token": token,
            }
        )
        return f"{base}/?{qs}"

    def build_create_bot_payload(
        self,
        *,
        meeting_url: str,
        bot_name: str,
        output_media_page_url: str,
        chat_webhook_url: str | None = None,
        status_webhook_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "output_media": {
                "camera": {"kind": "webpage", "config": {"url": output_media_page_url}}
            },
            "recording_config": {
                "transcript": {
                    "provider": {"recallai_streaming": {}},
                    "diarization": {"use_separate_streams_when_available": True},
                },
            },
            "variant": {
                "microsoft_teams": "web_4_core",
                "zoom": "web_4_core",
                "google_meet": "web_4_core",
            },
        }
        realtime_endpoints: list[dict] = []
        if chat_webhook_url:
            realtime_endpoints.append(
                {
                    "type": "webhook",
                    "url": chat_webhook_url,
                    "events": ["participant_events.chat_message"],
                }
            )
        if realtime_endpoints:
            payload["recording_config"]["realtime_endpoints"] = realtime_endpoints
        if status_webhook_url:
            payload["realtime_endpoints"] = [
                {
                    "type": "webhook",
                    "url": status_webhook_url,
                    "events": ["bot.status_change"],
                }
            ]
        return payload

    async def create_bot(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.settings.recall_api_base_url.rstrip('/')}/bot/",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def leave_call(self, bot_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.settings.recall_api_base_url.rstrip('/')}/bot/{bot_id}/leave_call/",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return {"ok": False, "status": resp.status_code}
            return resp.json() if resp.content else {"ok": True}

    async def mute_bot(self, bot_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.settings.recall_api_base_url.rstrip('/')}/bot/{bot_id}/output_audio/",
                headers=self._headers(),
                json={"kind": "silence"},
            )
            return resp.json() if resp.content else {"ok": True}

    async def unmute_bot(self, bot_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{self.settings.recall_api_base_url.rstrip('/')}/bot/{bot_id}/output_audio/",
                headers=self._headers(),
            )
            return resp.json() if resp.content else {"ok": True}

    async def send_chat_message(self, bot_id: str, message: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.settings.recall_api_base_url.rstrip('/')}/bot/{bot_id}/send_chat_message/",
                headers=self._headers(),
                json={"message": message, "to": "everyone", "pin": False},
            )
            return resp.json() if resp.content else {"ok": True}
