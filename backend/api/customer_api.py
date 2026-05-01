import json
import logging
import uuid
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from typing import Annotated, List
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from api.auth import require_customer_key
from config import get_settings
from indexer import search_indexer as indexer_mod
from services import index_jobs as index_jobs_mod
from models.api_key import ApiKey
from database import get_db
from models.bot_session import BotSession, BotSessionState
from models.metadata import PresentationMetadata
from datetime import datetime, timezone
from services.index_jobs import dispatch_index_job
from services import storage as storage_mod
from services.recall_client import RecallClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["customer"], dependencies=[Depends(require_customer_key)])


class CreateBotRequest(BaseModel):
    session_id: str
    meeting_url: str
    bot_name: str = "Customer Bot"
    metadata: str | None = None


class CreateBotResponse(BaseModel):
    bot_id: str
    status: str
    message: str
    output_media_url: str | None = None
    presentation_id: str | None = None


class BotStatusResponse(BaseModel):
    bot_id: str
    session_id: str
    status: str
    pdf_url: str | None
    metadata_url: str | None
    created_at: str
    recall_payload: dict | None = None


class ScheduleBotRequest(BaseModel):
    meeting_url: str
    join_at: str # ISO 8601 datetime string for scheduling
    bot_name: str = "Customer Bot"


class ScheduleBotResponse(BaseModel):
    bot_id: str
    status: str
    message: str
    output_media_url: str | None = None


class ActionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class LaunchBotRequest(BaseModel):
    bot_id: str
    meeting_url: str
    bot_name: str = "Customer Bot"


class LaunchBotResponse(BaseModel):
    session_id: str
    bot_id: str
    presentation_id: str
    agent_mode: str
    agent_name: str
    agent_version: int | None = None
    relay_profile: str
    output_media_url: str
    realtime_relay_url: str | None = None
    transcript_webhook_enabled: bool
    message: str = "Bot launched successfully"



@router.get("/bot", response_model=list[BotStatusResponse])
async def list_bots(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> list[BotStatusResponse]:
    """
    List all bots for the authenticated customer.
    """
    bots = db.query(BotSession).filter(BotSession.customer_id == api_key.customer_id).all()
    
    results = []
    for b in bots:
        results.append(BotStatusResponse(
            bot_id=b.bot_id or "",
            session_id=b.session_id,
            status=b.state,
            pdf_url=b.pdf_url,
            metadata_url=b.metadata_url,
            created_at=b.created_at.isoformat(),
            recall_payload=None,
        ))
    return results

@router.post("/bot", response_model=CreateBotResponse)
async def create_bot(
    session_id: str = Form(...),
    meeting_url: str = Form(...),
    bot_name: str = Form("Customer Bot"),
    presentation_file: UploadFile = File(..., alias="pdf_file"),
    brief_files: UploadFile = File(..., alias="brief_file"),
    metadata: str | None = Form(None),
    settings = Depends(get_settings),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> CreateBotResponse:
    """
    Create a new bot with uploaded PDF and meeting details.
    If metadata is provided it will be used directly (skipping Vision API).
    If omitted, Claude Vision will extract metadata from the PDF slides automatically.
    """
    print(f"[customer_api] create_bot called session_id={session_id!r} meeting_url={meeting_url!r} bot_name={bot_name!r} filename={presentation_file.filename!r} metadata_provided={bool(metadata)!r}")
    
    # Internalize session_id with customer prefix to allow per-user uniqueness
    internal_session_id = f"{api_key.customer_id}:{session_id}"
    
    # Check if session_id already exists for this customer (using internal ID)
    existing = db.query(BotSession).filter(
        BotSession.session_id == internal_session_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Session ID '{session_id}' already exists for your account.")

    # Validate file type
    _allowed_exts = (".pdf", ".ppt", ".pptx")
    if not any(presentation_file.filename.lower().endswith(ext) for ext in _allowed_exts):
        raise HTTPException(400, "Only PDF, PPT, or PPTX files are supported")

    # Read file data
    file_data = await presentation_file.read()

    # Treat an empty string the same as not provided
    metadata_provided = bool(metadata and metadata.strip())

    if metadata_provided:
        # 1. Parse and validate provided metadata structure
        try:
            metadata_dict = json.loads(metadata)
            PresentationMetadata.model_validate(metadata_dict)
        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            logger.error("Strict metadata validation failed: %s", e)
            raise HTTPException(status_code=400, detail=f"Strict metadata validation failed: {str(e)}")

        # 2. Validate page/slide count against metadata BEFORE saving to storage
        from indexer.converter import get_file_page_count_from_bytes
        file_pages = await get_file_page_count_from_bytes(file_data, presentation_file.filename or "")

        meta_pages_list = metadata_dict.get("pages", [])
        meta_pages_count = len(meta_pages_list)
        declared_total = metadata_dict.get("total_pages", meta_pages_count)

        if file_pages > 0 and (declared_total != file_pages or meta_pages_count != file_pages):
            logger.error(
                "Page count mismatch: file has %d pages, metadata declares %d total, and has %d page objects",
                file_pages, declared_total, meta_pages_count
            )
            raise HTTPException(
                status_code=400,
                detail=f"Page count mismatch: file has {file_pages} pages, but metadata has {meta_pages_count} page entries."
            )

    # 3. Save PDF to storage
    original_ext = os.path.splitext(presentation_file.filename or "")[1].lower() or ".pdf"
    safe_name = f"{session_id}{original_ext}"
    uploaded = storage_mod.save_upload(safe_name, file_data)

    # 4. Save metadata to the presentation directory (only when provided)
    if metadata_provided:
        try:
            dest_dir = storage_mod.presentations_root() / uploaded.presentation_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / "provided_metadata.json").write_text(metadata)
            logger.info("Saved provided metadata for %s", uploaded.presentation_id)
        except Exception as e:
            logger.error("Failed to save provided metadata for %s: %s", uploaded.presentation_id, e)
            raise HTTPException(status_code=500, detail="Internal error saving metadata")
    else:
        logger.info("No metadata provided for %s — Claude Vision will extract it during indexing", uploaded.presentation_id)

    # Save briefing files
    brief_paths = []
    # for bf in brief_files:
    bf = brief_files
    if bf.filename:
        bf_data = await bf.read()
        dest_dir = storage_mod.presentations_root() / uploaded.presentation_id / "brief_files"
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_bf_name = f"{uuid.uuid4()}_{bf.filename}"
        bf_path = dest_dir / safe_bf_name
        bf_path.write_bytes(bf_data)
        brief_paths.append(str(bf_path))
        logger.info("Saved brief file: %s", bf_path)

    # Trigger indexing
    storage_mod.update_presentation_meta(
        uploaded.presentation_id, 
        status="indexing", 
        index_error=None,
        brief_file_paths=brief_paths # Store paths for the pipeline
    )
    index_jobs_mod.dispatch_index_job(uploaded.presentation_id)
    bot_id = str(uuid.uuid4())

    from services.agent_store import agent_store
    active_agent = agent_store.get_active_version("default")
    agent_prompt = active_agent.system_prompt if active_agent else "You are Overtone, a live voice assistant."

    bot_session = BotSession(
        session_id=internal_session_id,
        customer_id=api_key.customer_id,
        bot_id=bot_id,
        presentation_id=uploaded.presentation_id,
        bot_name=bot_name,
        meeting_url=meeting_url,
        state=BotSessionState.CREATED.value,
        pdf_url=uploaded.presentation_id,
        metadata_url="",
        extra={
            "agent_system_prompt": agent_prompt,
            "muted": False,
            "auto_present_pages": 1,
            "brief_file_paths": brief_paths,
        }
    )
    db.add(bot_session)
    db.commit()

    # Trigger indexing
    storage_mod.update_presentation_meta(uploaded.presentation_id, status="indexing", index_error=None)
    dispatch_index_job(uploaded.presentation_id)

    fe = settings.frontend_url.rstrip("/")
    be = settings.backend_url.rstrip("/")
    output_media_url = f"{fe}/?session={internal_session_id}&api={be}"

    return CreateBotResponse(
        bot_id=bot_id,
        status="created",
        message="Bot created and indexing started. Call /bot/{bot_id}/schedule to deploy to Recall.",
        output_media_url=output_media_url,
        presentation_id=bot_session.presentation_id,
    )


@router.get("/bot/{bot_id}", response_model=BotStatusResponse)
async def get_bot_status(
    bot_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> BotStatusResponse:
    """
    Get bot status from database.
    """
    print(f"[customer_api] get_bot_status called bot_id={bot_id!r}")
    bot_session = db.query(BotSession).filter(BotSession.bot_id == bot_id, BotSession.customer_id == api_key.customer_id).first()
    if not bot_session:
        raise HTTPException(404, "Bot not found")

    recall_payload = None
    try:
        from services.recall_client import RecallClient

        client = RecallClient(get_settings())
        if bot_session.recall_bot_id:
            recall_payload = await client.get_bot(bot_session.recall_bot_id)
    except Exception:
        recall_payload = None

    return BotStatusResponse(
        bot_id=bot_session.bot_id,
        session_id=bot_session.session_id,
        status=bot_session.state,
        pdf_url=bot_session.pdf_url,
        metadata_url=bot_session.metadata_url,
        created_at=bot_session.created_at.isoformat(),
        recall_payload=recall_payload,
    )


@router.post("/bot/{bot_id}/schedule", response_model=ScheduleBotResponse)
async def schedule_bot(
    bot_id: str,
    request: ScheduleBotRequest,
    settings = Depends(get_settings),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> ScheduleBotResponse:
    """
    Schedule/join meeting with the bot using Recall.ai API.
    """
    print(f"[customer_api] schedule_bot called bot_id={bot_id!r} meeting_url={request.meeting_url!r} bot_name={request.bot_name!r}")
    
    valid_join_at = None
    if request.join_at:
        try:
            dt = datetime.fromisoformat(request.join_at.replace("Z", "+00:00"))
            valid_join_at = dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise HTTPException(400, "join_at must be a valid ISO 8601 UTC datetime string (e.g. 2024-05-10T14:00:00Z)")

    bot_session = db.query(BotSession).filter(BotSession.bot_id == bot_id, BotSession.customer_id == api_key.customer_id).first()
    if not bot_session:
        raise HTTPException(404, "Bot not found")

    # Gate: presentation must be indexed and ready before scheduling
    if bot_session.presentation_id:
        pres = storage_mod.get_presentation(bot_session.presentation_id)
        if not pres:
            raise HTTPException(409, "Presentation not found. The PDF may still be processing.")
        if pres.status != "ready":
            raise HTTPException(
                409,
                f"Presentation is not ready (status={pres.status!r}). "
                "Wait for indexing to complete before scheduling the bot.",
            )

    # Duplicate-schedule guard: reject if ANY bot (same or different) from this customer
    # is already scheduled for the same meeting URL within a 5-minute window.
    if valid_join_at:
        from datetime import datetime
        requested_dt = datetime.fromisoformat(valid_join_at)
        _active_states = [
            BotSessionState.CREATED.value,
            BotSessionState.JOINING.value,
            BotSessionState.IN_WAITING_ROOM.value,
            BotSessionState.IN_CALL.value,
        ]
        # Query ALL sessions for this customer + meeting URL (including current bot)
        candidates = (
            db.query(BotSession)
            .filter(
                BotSession.customer_id == api_key.customer_id,
                BotSession.meeting_url == request.meeting_url,
                BotSession.state.in_(_active_states),
            )
            .all()
        )
        for candidate in candidates:
            existing_join_at = (candidate.extra or {}).get("scheduled_join_at")
            if not existing_join_at:
                continue
            try:
                existing_dt = datetime.fromisoformat(existing_join_at)
                if abs((requested_dt - existing_dt).total_seconds()) < 300:
                    who = "This bot is" if candidate.bot_id == bot_id else f"Bot '{candidate.bot_id}' is"
                    raise HTTPException(
                        409,
                        f"{who} already scheduled for this meeting at {existing_join_at}, "
                        f"which is within 5 minutes of the requested time ({valid_join_at}). "
                        "Choose a different time or meeting URL.",
                    )
            except ValueError:
                pass  # malformed stored value — ignore

    # Update meeting URL and tentative state
    bot_session.meeting_url = request.meeting_url
    bot_session.bot_name = request.bot_name
    bot_session.state = BotSessionState.JOINING.value
    db.commit()

    # Call Recall.ai to create and schedule the bot
    from services.recall_client import RecallClient

    client = RecallClient(settings)

    fe = settings.frontend_url.rstrip("/")
    be = settings.backend_url.rstrip("/")
    output_url = f"{fe}/?session={bot_session.session_id}&presentation={bot_session.presentation_id}&api={be}"
    webhook_url = f"{be}/api/webhook/recall/transcript"
    chat_webhook_url = f"{be}/api/webhook/recall/chat"

    payload = client.build_create_bot_payload(
        meeting_url=str(request.meeting_url),
        bot_name=request.bot_name,
        output_media_page_url=output_url,
        transcript_webhook_url=webhook_url,
        chat_webhook_url=chat_webhook_url,
        enable_transcript_webhook=True,
        join_at=valid_join_at,
    )

    try:
        created = await client.create_bot(payload)
    except Exception as e:
        # mark error state
        bot_session.state = BotSessionState.FATAL.value
        db.commit()
        raise HTTPException(502, f"Recall.ai schedule failed: {e}") from e

    recall_bot_id = created.get("id") or created.get("bot_id")
    if not recall_bot_id:
        bot_session.state = BotSessionState.FATAL.value
        db.commit()
        raise HTTPException(502, f"Unexpected Recall response: {created!r}")

    bot_session.recall_bot_id = str(recall_bot_id)
    bot_session.state = BotSessionState.JOINING.value
    # Persist the scheduled time so duplicate-schedule checks can use it
    extra = dict(bot_session.extra or {})
    if valid_join_at:
        extra["scheduled_join_at"] = valid_join_at
    bot_session.extra = extra
    db.commit()

    return ScheduleBotResponse(
        bot_id=bot_session.bot_id,
        status="scheduled",
        message="Bot scheduled to join meeting",
        output_media_url=output_url,
    )


@router.post("/bot/launch", response_model=LaunchBotResponse)
async def launch_bot(
    request: LaunchBotRequest,
    background_tasks: BackgroundTasks,
    settings = Depends(get_settings),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> LaunchBotResponse:
    """
    Launch an existing bot into a meeting.
    Looks up the bot by bot_id to get its presentation, then creates a fresh
    session for this deployment. A single bot can be launched into multiple
    meetings — each launch gets its own session_id.
    """
    print(f"[customer_api] launch_bot called bot_id={request.bot_id!r} meeting_url={request.meeting_url!r} bot_name={request.bot_name!r}")

    # Look up the bot to get its presentation_id
    bot = db.query(BotSession).filter(
        BotSession.bot_id == request.bot_id,
        BotSession.customer_id == api_key.customer_id,
    ).first()
    if not bot:
        raise HTTPException(404, f"Bot not found: {request.bot_id}")

    presentation_id = bot.presentation_id
    if not presentation_id:
        raise HTTPException(409, "Bot has no presentation attached. Re-create the bot with a PDF upload.")

    # Verify the presentation is indexed and ready
    from services import storage as storage_mod
    pres = storage_mod.get_presentation(presentation_id)
    if not pres:
        raise HTTPException(404, f"Presentation not found: {presentation_id}")
    if pres.status != "ready":
        raise HTTPException(409, f"Presentation is not ready for launch (status={pres.status!r}). Wait for indexing to finish.")

    # Create a fresh BotSession for this specific meeting deployment
    session_id = str(uuid.uuid4())
    session_bot_id = str(uuid.uuid4())
    bot_session = BotSession(
        session_id=session_id,
        customer_id=api_key.customer_id,
        bot_id=session_bot_id,
        presentation_id=presentation_id,
        bot_name=request.bot_name,
        meeting_url=str(request.meeting_url),
        state=BotSessionState.JOINING.value,
        pdf_url=presentation_id,
        metadata_url="",
        extra=bot.extra or {},
    )
    db.add(bot_session)
    db.commit()

    # Call Recall.ai to create and launch the bot
    from services.recall_client import RecallClient
    from models.bot_session import AgentMode

    client = RecallClient(settings)

    fe = settings.frontend_url.rstrip("/")
    be = settings.backend_url.rstrip("/")
    output_url = f"{fe}/?session={session_id}&presentation={presentation_id}&mode=realtime&api={be}"
    webhook_url = f"{be}/api/webhook/recall/transcript"
    chat_webhook_url = f"{be}/api/webhook/recall/chat"

    payload = client.build_create_bot_payload(
        meeting_url=str(request.meeting_url),
        bot_name=request.bot_name,
        output_media_page_url=output_url,
        transcript_webhook_url=webhook_url,
        chat_webhook_url=chat_webhook_url,
        enable_transcript_webhook=False,  # Use realtime mode
    )

    try:
        created = await client.create_bot(payload)
    except Exception as e:
        bot_session.state = BotSessionState.FATAL.value
        db.commit()
        raise HTTPException(502, f"Recall.ai launch failed: {e}") from e

    recall_bot_id = created.get("id") or created.get("bot_id")
    if not recall_bot_id:
        bot_session.state = BotSessionState.FATAL.value
        db.commit()
        raise HTTPException(502, f"Unexpected Recall response: {created!r}")

    # Store Recall's ID separately — do NOT overwrite our internal bot_id
    bot_session.recall_bot_id = str(recall_bot_id)
    db.commit()

    # Create session in memory store for WebSocket connections
    from services.session_store import store
    in_mem_sess = await store.create_session(
        presentation_id=presentation_id,
        bot_name=request.bot_name,
        meeting_url=str(request.meeting_url),
        agent_mode=AgentMode.REALTIME,
        agent_name="default",
        agent_version=1,
        bot_id=str(recall_bot_id),
        session_id=session_id,
        extra={
            "relay_status": "idle",
            "fallback_active": False,
            "realtime_errors": 0,
            "relay_profile": "voicenav",
            "agent_system_prompt": "",
            "agent_presentation_id": presentation_id,
            "auto_present_pages": 0,
            "brief_file_paths": bot.extra.get("brief_file_paths", []) if bot.extra else [],
        },
    )
    # Stamp recall_bot_id on the in-memory session so voice tools (leave/mute) can use it
    in_mem_sess.recall_bot_id = str(recall_bot_id)

    # Pre-warm the deep RAG caches in the background so the first search is instant
    from orchestrator import account_brief_retriever
    background_tasks.add_task(account_brief_retriever.init_caches)

    return LaunchBotResponse(
        session_id=session_id,
        bot_id=session_bot_id,
        presentation_id=presentation_id,
        agent_mode="realtime",
        agent_name="default",
        agent_version=1,
        relay_profile="voicenav",
        output_media_url=output_url,
        realtime_relay_url=f"{be.replace('http', 'ws')}/ws/realtime/{session_id}",
        transcript_webhook_enabled=False,
        message="Bot launched successfully",
    )

@router.post("/bot/leave_call", response_model=ActionResponse)
async def leave_call(
    session_id: str = Form(...),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> ActionResponse:
    """
    Tells the bot associated with session_id to leave the call.
    """
    # Internalize session_id with customer prefix
    internal_session_id = f"{api_key.customer_id}:{session_id}"
    session = db.query(BotSession).filter(BotSession.session_id == internal_session_id).first()
    if not session or not session.recall_bot_id:
        raise HTTPException(404, "Active bot session not found")

    recall = RecallClient(get_settings())
    try:
        success = await recall.leave_call(session.recall_bot_id)
    except Exception as e:
        logger.error("Recall.ai leave_call failed for %s: %s", session.recall_bot_id, e)
        raise HTTPException(502, f"Recall.ai leave_call failed: {e}")

    if not success:
        raise HTTPException(502, "Failed to tell bot to leave call")

    session.state = BotSessionState.CALL_ENDED.value
    db.commit()

    return ActionResponse(
        session_id=session_id,
        status="success",
        message="Bot is leaving the call",
    )


class SendChatRequest(BaseModel):
    message: str
    to: str = "everyone"
    pin: bool = False


class SendChatResponse(BaseModel):
    bot_id: str
    status: str
    message: str


@router.post("/bot/{bot_id}/chat", response_model=SendChatResponse)
async def send_chat_message(
    bot_id: str,
    request: SendChatRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_customer_key),
) -> SendChatResponse:
    """
    Send a chat message into the meeting via Recall.ai.
    The bot must be in a call for this to work.
    """
    bot_session = db.query(BotSession).filter(
        BotSession.bot_id == bot_id,
        BotSession.customer_id == api_key.customer_id,
    ).first()
    if not bot_session:
        raise HTTPException(404, "Bot not found")

    if not bot_session.recall_bot_id:
        raise HTTPException(409, "Bot has not been deployed to Recall yet. Schedule or launch the bot first.")

    recall = RecallClient(get_settings())
    try:
        await recall.send_chat_message(
            bot_session.recall_bot_id,
            request.message,
            to=request.to,
            pin=request.pin,
        )
    except Exception as e:
        logger.error("send_chat_message failed for bot_id=%s: %s", bot_id, e)
        raise HTTPException(502, f"Recall.ai send_chat_message failed: {e}")

    return SendChatResponse(
        bot_id=bot_id,
        status="sent",
        message="Chat message sent successfully",
    )