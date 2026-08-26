from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.db.models import SessionState
from app.domain import agents as agent_store
from app.domain.session_store import LiveSession, store
from app.domain.usage import check_quota, increment_usage
from app.http.auth import WorkspaceContext, assert_session_access, get_workspace_context
from app.meetings.recall import RecallClient
from app.storage import PresentationStore

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class LaunchIn(BaseModel):
    meeting_url: str
    presentation_id: str
    bot_name: str = "Overtone"
    agent_name: str = "default"


class LaunchOut(BaseModel):
    session_id: str
    presentation_id: str
    recall_bot_id: str | None = None
    output_media_url: str
    realtime_relay_url: str
    agent_name: str
    agent_version: int | None = None
    state: str
    message: str = "Bot launched"


class SessionOut(BaseModel):
    session_id: str
    presentation_id: str | None
    bot_name: str
    meeting_url: str
    agent_name: str
    agent_version: int | None
    state: str
    recall_bot_id: str | None
    last_status_code: str | None = None
    last_status_message: str | None = None
    extra: dict = Field(default_factory=dict)


@router.post("/launch", response_model=LaunchOut)
async def launch_session(
    body: LaunchIn,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    settings = get_settings()
    if not settings.recall_api_key:
        raise HTTPException(status_code=400, detail="RECALL_API_KEY not configured")

    if not ctx.is_operator:
        check_quota(db, ctx.workspace_id, "launches")

    meta = PresentationStore(db).get(body.presentation_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Presentation not found")
    if not ctx.is_operator:
        assert_session_access(ctx, meta.customer_id)
    if meta.status != "ready":
        raise HTTPException(status_code=400, detail=f"Presentation status is {meta.status}, need ready")

    agent_store.ensure_default_agent(db, ctx.workspace_id if not ctx.is_operator else None)
    active = agent_store.get_active(db, body.agent_name, ctx.workspace_id if not ctx.is_operator else None) or agent_store.get_active(
        db, "default", ctx.workspace_id if not ctx.is_operator else None
    )
    session_id = str(uuid.uuid4())
    bot_id = str(uuid.uuid4())
    tenant_id = None if ctx.is_operator else ctx.workspace_id

    recall = RecallClient()
    output_url = recall.build_output_media_url(session_id=session_id, presentation_id=body.presentation_id)
    wss = settings.backend_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    relay_url = f"{wss}/ws/realtime/{session_id}"
    status_url = f"{settings.backend_url.rstrip('/')}/webhooks/recall/bot-status"
    chat_url = f"{settings.backend_url.rstrip('/')}/webhooks/recall/chat"

    payload = recall.build_create_bot_payload(
        meeting_url=body.meeting_url,
        bot_name=body.bot_name,
        output_media_page_url=output_url,
        chat_webhook_url=chat_url,
        status_webhook_url=status_url,
    )
    try:
        created = await recall.create_bot(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Recall create_bot failed: {exc}") from exc

    recall_bot_id = str(created.get("id") or created.get("bot_id") or "")
    sess = LiveSession(
        session_id=session_id,
        presentation_id=body.presentation_id,
        bot_name=body.bot_name,
        meeting_url=body.meeting_url,
        agent_name=body.agent_name,
        agent_version=active.version if active else 1,
        customer_id=tenant_id,
        bot_id=bot_id,
        recall_bot_id=recall_bot_id,
        state=SessionState.JOINING.value,
        extra={"current_page": 1, "muted": False, "session_greeting_sent": False},
    )
    store.create(sess)

    if not ctx.is_operator:
        increment_usage(db, ctx.workspace_id, "launches")

    return LaunchOut(
        session_id=session_id,
        presentation_id=body.presentation_id,
        recall_bot_id=recall_bot_id,
        output_media_url=output_url,
        realtime_relay_url=relay_url,
        agent_name=body.agent_name,
        agent_version=active.version if active else 1,
        state=sess.state,
    )


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    assert_session_access(ctx, sess.customer_id)
    return SessionOut(
        session_id=sess.session_id,
        presentation_id=sess.presentation_id,
        bot_name=sess.bot_name,
        meeting_url=sess.meeting_url,
        agent_name=sess.agent_name,
        agent_version=sess.agent_version,
        state=sess.state,
        recall_bot_id=sess.recall_bot_id,
        last_status_code=sess.last_status_code,
        last_status_message=sess.last_status_message,
        extra=sess.extra or {},
    )


@router.post("/{session_id}/leave")
async def leave_session(
    session_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    assert_session_access(ctx, sess.customer_id)
    if sess.recall_bot_id:
        await RecallClient().leave_call(sess.recall_bot_id)
    store.update(session_id, state=SessionState.CALL_ENDED.value)
    return {"ok": True}
