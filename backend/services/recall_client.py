from __future__ import annotations

from typing import Any
import json

import httpx

from config import Settings


class RecallClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        base = settings.recall_api_base_url.rstrip("/")
        self._base = base
        self._headers = {
            "Authorization": f"Token {settings.recall_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, headers=self._headers, timeout=60.0)

    def build_create_bot_payload(
        self,
        *,
        meeting_url: str,
        bot_name: str,
        output_media_page_url: str,
        transcript_webhook_url: str,
        chat_webhook_url: str | None = None,
        enable_transcript_webhook: bool = True,
        join_at: str | None = None,
    ) -> dict[str, Any]:
        """Build the Recall.ai Create Bot request payload."""
        payload: dict[str, Any] = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "output_media": {
                "camera": {
                    "kind": "webpage",
                    "config": {"url": output_media_page_url},
                }
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
        if join_at:
            payload["join_at"] = join_at

        if enable_transcript_webhook:
            # bot.status_change belongs at the top-level realtime_endpoints;
            # recording_config.realtime_endpoints only accepts transcript events.
            payload["realtime_endpoints"] = [
                {
                    "type": "webhook",
                    "url": transcript_webhook_url,
                    "events": ["bot.status_change"],
                }
            ]
            payload["recording_config"]["realtime_endpoints"] = [
                {
                    "type": "webhook",
                    "url": transcript_webhook_url,
                    "events": ["transcript.data", "transcript.partial_data"],
                }
            ]

        # Subscribe to incoming chat messages (must be in recording_config.realtime_endpoints
        # alongside transcript events — this is where in-call participant events live)
        if chat_webhook_url:
            chat_endpoint = {
                "type": "webhook",
                "url": chat_webhook_url,
                "events": ["participant_events.chat_message"],
            }
            if "realtime_endpoints" not in payload["recording_config"]:
                payload["recording_config"]["realtime_endpoints"] = []
            payload["recording_config"]["realtime_endpoints"].append(chat_endpoint)

        return payload

    async def create_bot(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as client:
            try:
                # Log truncated payload for debugging
                try:
                    payload_preview = json.dumps(payload)[:2000]
                except Exception:
                    payload_preview = str(payload)[:2000]
                print(f"[recall_client] create_bot payload_preview={payload_preview!r}")

                r = await client.post("/bot/", json=payload)
                # If non-success, print full response details for debugging
                if r.status_code >= 400:
                    print(f"[recall_client] create_bot response status={r.status_code}")
                    try:
                        headers = dict(r.headers)
                    except Exception:
                        headers = str(r.headers)
                    print(f"[recall_client] response headers={headers!r}")
                    print(f"[recall_client] response body={r.text!r}")
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                # Attempt to surface the response body when available
                resp = getattr(e, "response", None)
                if resp is not None:
                    print(f"[recall_client] HTTPStatusError status={resp.status_code} body={resp.text!r}")
                else:
                    print(f"[recall_client] HTTPStatusError: {e}")
                raise
            except Exception as e:
                print(f"[recall_client] create_bot unexpected error: {e}")
                raise

    async def get_bot(self, bot_id: str) -> dict[str, Any]:
        async with self._client() as client:
            try:
                r = await client.get(f"/bot/{bot_id}/")
                if r.status_code >= 400:
                    print(f"[recall_client] get_bot bot_id={bot_id!r} status={r.status_code} body={r.text!r}")
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                resp = getattr(e, "response", None)
                if resp is not None:
                    print(f"[recall_client] get_bot HTTPStatusError status={resp.status_code} body={resp.text!r}")
                else:
                    print(f"[recall_client] get_bot HTTPStatusError: {e}")
                raise

    async def delete_output_media_camera(self, bot_id: str) -> None:
        async with self._client() as client:
            r = await client.request(
                "DELETE",
                f"/bot/{bot_id}/output_media/",
                json={"camera": True},
            )
            if r.status_code not in (200, 204):
                r.raise_for_status()

    async def delete_bot(self, bot_id: str) -> dict[str, Any]:
        """Permanently delete a bot instance from Recall.ai."""
        async with self._client() as client:
            r = await client.delete(f"/bot/{bot_id}/")
            if r.status_code in (200, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
            return {}

    async def leave_call(self, bot_id: str) -> dict[str, Any]:
        """Instruct the bot to leave the current call gracefully."""
        async with self._client() as client:
            r = await client.post(f"/bot/{bot_id}/leave_call/")
            if r.status_code in (200, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
            return {}

    async def mute_bot(self, bot_id: str) -> dict[str, Any]:
        """Mute the bot's audio output in the meeting."""
        async with self._client() as client:
            r = await client.post(
                f"/bot/{bot_id}/output_audio/",
                json={"kind": "silence"},
            )
            if r.status_code in (200, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
            return {}

    async def unmute_bot(self, bot_id: str) -> dict[str, Any]:
        """Restore the bot's audio output in the meeting."""
        async with self._client() as client:
            r = await client.delete(f"/bot/{bot_id}/output_audio/")
            if r.status_code in (200, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
            return {}

    async def send_chat_message(
        self,
        bot_id: str,
        message: str,
        *,
        to: str = "everyone",
        pin: bool = False,
    ) -> dict[str, Any]:
        """Send a chat message into the meeting via Recall.ai.

        POST /bot/{id}/send_chat_message/
        Body: {"message": str, "to": str, "pin": bool}
        """
        async with self._client() as client:
            r = await client.post(
                f"/bot/{bot_id}/send_chat_message/",
                json={"message": message, "to": to, "pin": pin},
            )
            if r.status_code in (200, 201, 204):
                try:
                    return r.json()
                except Exception:
                    return {"ok": True}
            r.raise_for_status()
            return {}
