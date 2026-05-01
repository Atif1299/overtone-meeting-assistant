from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from pydantic import BaseModel

from api.auth import require_customer_key
from models.bot_session import AgentMode, BotSessionState
from services.session_store import store

router = APIRouter(prefix="/api", tags=["sessions"], dependencies=[Depends(require_customer_key)])


class SessionStatusResponse(BaseModel):
    session_id: str
    presentation_id: str
    bot_id: Optional[str]
    bot_name: str
    meeting_url: str
    agent_mode: AgentMode
    agent_name: str
    agent_version: int | None = None
    state: BotSessionState
    last_status_code: Optional[str]
    last_status_message: Optional[str]
    last_transcript_snippet: Optional[str]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    relay_status: Optional[str] = None
    relay_profile: Optional[str] = None
    relay_connected_at: Optional[datetime] = None
    relay_last_event_at: Optional[datetime] = None
    relay_last_error: Optional[str] = None
    first_audio_latency_ms: Optional[float] = None
    tool_calls: int = 0
    tool_failures: int = 0
    fallback_active: bool = False


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session(session_id: str) -> SessionStatusResponse:
    s = await store.get_by_session_id(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    state_val = s.state if s.state is not None else BotSessionState.UNKNOWN.value
    return SessionStatusResponse(
        session_id=s.session_id,
        presentation_id=s.presentation_id,
        bot_id=s.bot_id,
        bot_name=s.bot_name,
        meeting_url=s.meeting_url,
        agent_mode=s.agent_mode,
        agent_name=s.agent_name,
        agent_version=s.agent_version,
        state=state_val,
        last_status_code=s.last_status_code,
        last_status_message=s.last_status_message,
        last_transcript_snippet=s.last_transcript_snippet,
        created_at=s.created_at,
        updated_at=s.updated_at,
        expires_at=s.expires_at,
        relay_status=s.extra.get("relay_status"),
        relay_profile=s.extra.get("relay_profile"),
        relay_connected_at=s.extra.get("relay_connected_at"),
        relay_last_event_at=s.extra.get("relay_last_event_at"),
        relay_last_error=s.extra.get("relay_last_error"),
        first_audio_latency_ms=s.extra.get("first_audio_latency_ms"),
        tool_calls=int(s.extra.get("tool_calls", 0) or 0),
        tool_failures=int(s.extra.get("tool_failures", 0) or 0),
        fallback_active=bool(s.extra.get("fallback_active", s.agent_mode == AgentMode.WEBHOOK)),
    )
