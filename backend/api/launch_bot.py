from __future__ import annotations

import uuid
from typing import Literal
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from api.auth import require_customer_key
from config import Settings, get_settings
from indexer.pipeline import run_index_job
from models.bot_session import AgentMode
from services.agent_store import DEFAULT_AGENT_NAME, agent_store
from services.recall_client import RecallClient
from services.session_store import store

router = APIRouter(prefix="/api", tags=["deprecated"], dependencies=[Depends(require_customer_key)])


class LaunchBotRequest(BaseModel):
    bot_name: str = Field(..., min_length=1, max_length=120)
    meeting_url: HttpUrl
    presentation_id: str | None = None
    agent_mode: AgentMode | None = None
    agent_name: str | None = None
    output_media_url_override: HttpUrl | None = None
    relay_profile: Literal["voicenav", "demo"] | None = None
    auto_present_pages: int | None = Field(None, ge=0, le=200)


class LaunchBotResponse(BaseModel):
    session_id: str
    bot_id: str
    presentation_id: str
    agent_mode: AgentMode
    agent_name: str
    agent_version: int | None = None
    relay_profile: Literal["voicenav", "demo"]
    output_media_url: str
    realtime_relay_url: str | None = None
    transcript_webhook_enabled: bool
    message: str = "Bot creation requested"


def _recall_client(settings: Settings) -> RecallClient:
    return RecallClient(settings)


def _public_ws_base(backend_url: str) -> str:
    if backend_url.startswith("https://"):
        return "wss://" + backend_url[len("https://") :]
    if backend_url.startswith("http://"):
        return "ws://" + backend_url[len("http://") :]
    return backend_url


def _resolve_agent_mode(body: LaunchBotRequest, settings: Settings) -> AgentMode:
    if body.agent_mode:
        return body.agent_mode
    return AgentMode(settings.voice_agent_mode)


def _resolve_relay_profile(body: LaunchBotRequest) -> Literal["voicenav", "demo"]:
    if body.relay_profile:
        return body.relay_profile
    if body.output_media_url_override:
        return "demo"
    return "voicenav"


def _resolve_agent_name(body: LaunchBotRequest) -> str:
    value = (body.agent_name or DEFAULT_AGENT_NAME).strip()
    if not value:
        return DEFAULT_AGENT_NAME
    return value


def _resolve_presentation_id(body: LaunchBotRequest, agent_presentation_id: str | None) -> str:
    if body.presentation_id and body.presentation_id.strip():
        return body.presentation_id.strip()
    if agent_presentation_id and str(agent_presentation_id).strip():
        return str(agent_presentation_id).strip()
    raise HTTPException(
        status_code=400,
        detail=(
            "presentation_id is required. Select a presentation at launch or attach a "
            "default presentation to the active agent version."
        ),
    )


def _set_query_param_if_missing(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if key in existing:
        return url
    existing[key] = value
    query = urlencode(existing)
    return urlunparse(parsed._replace(query=query))


@router.post("/launch-bot", response_model=LaunchBotResponse, deprecated=True)
async def launch_bot(
    body: LaunchBotRequest,
    settings: Settings = Depends(get_settings),
) -> LaunchBotResponse:
    if not settings.recall_api_key:
        raise HTTPException(503, "RECALL_API_KEY is not configured")

    from services import storage as storage_mod

    selected_agent_name = _resolve_agent_name(body)
    active_agent = agent_store.get_active_version(selected_agent_name)
    if not active_agent:
        raise HTTPException(
            status_code=404,
            detail=f"No active version found for agent '{selected_agent_name}'. "
            "Create/activate a version from the Agents page.",
        )
    resolved_presentation_id = _resolve_presentation_id(body, active_agent.presentation_id)
    pres = storage_mod.get_presentation(resolved_presentation_id)
    if not pres:
        raise HTTPException(404, f"Unknown presentation_id: {resolved_presentation_id}")
    if pres.status != "ready":
        await run_index_job(resolved_presentation_id)
        pres = storage_mod.get_presentation(resolved_presentation_id)
        if not pres or pres.status != "ready":
            raise HTTPException(409, "Presentation is not indexed and ready for launch")

    session_id = str(uuid.uuid4())
    fe = settings.frontend_url.rstrip("/")
    be = settings.backend_url.rstrip("/")
    agent_mode = _resolve_agent_mode(body, settings)
    relay_profile = _resolve_relay_profile(body)
    q_session = quote(session_id, safe="")
    q_pres = quote(resolved_presentation_id, safe="")
    q_mode = quote(agent_mode.value, safe="")
    output_url = f"{fe}/?session={q_session}&presentation={q_pres}&mode={q_mode}"
    if body.output_media_url_override:
        output_url = str(body.output_media_url_override).strip()
    relay_wss: str | None = None
    if agent_mode == AgentMode.REALTIME:
        relay_wss = f"{_public_ws_base(be)}/ws/realtime/{q_session}"
        if body.output_media_url_override:
            output_url = _set_query_param_if_missing(output_url, "wss", relay_wss)
        else:
            output_url = f"{output_url}&wss={quote(relay_wss, safe='')}"

    webhook_url = f"{be}/api/webhook/recall/transcript"

    client = _recall_client(settings)
    payload = client.build_create_bot_payload(
        meeting_url=str(body.meeting_url),
        bot_name=body.bot_name,
        output_media_page_url=output_url,
        transcript_webhook_url=webhook_url,
        enable_transcript_webhook=agent_mode == AgentMode.WEBHOOK,
    )

    try:
        created = await client.create_bot(payload)
    except Exception as e:
        raise HTTPException(502, f"Recall.ai Create Bot failed: {e}") from e

    bot_id = created.get("id") or created.get("bot_id")
    if not bot_id:
        raise HTTPException(502, f"Unexpected Recall response: {created!r}")

    await store.create_session(
        presentation_id=resolved_presentation_id,
        bot_name=body.bot_name,
        meeting_url=str(body.meeting_url),
        agent_mode=agent_mode,
        agent_name=active_agent.agent_name,
        agent_version=active_agent.version_number,
        bot_id=str(bot_id),
        session_id=session_id,
        extra={
            "relay_status": "idle" if agent_mode == AgentMode.REALTIME else "disabled",
            "fallback_active": agent_mode == AgentMode.WEBHOOK,
            "realtime_errors": 0,
            "relay_profile": relay_profile,
            "agent_system_prompt": active_agent.system_prompt,
            "agent_presentation_id": active_agent.presentation_id,
            "auto_present_pages": body.auto_present_pages or 0,
        },
    )

    return LaunchBotResponse(
        session_id=session_id,
        bot_id=str(bot_id),
        presentation_id=resolved_presentation_id,
        agent_mode=agent_mode,
        agent_name=active_agent.agent_name,
        agent_version=active_agent.version_number,
        relay_profile=relay_profile,
        output_media_url=output_url,
        realtime_relay_url=relay_wss,
        transcript_webhook_enabled=agent_mode == AgentMode.WEBHOOK,
    )
