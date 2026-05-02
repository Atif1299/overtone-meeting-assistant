from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api import (
    agents,
    customer_api,
    index_status,
    launch_bot,
    presentations,
    realtime_relay,
    sessions,
    tts,
    webhook_bot_status,
    webhook_chat,
    webhook_recall,
    admin_api,
    auth_admin,
)
from config import get_settings
from database import create_tables, get_db
from sqlalchemy.orm import Session
from models.bot_session import BotSession
from orchestrator.engine import configure_queue, queue_depth, transcript_worker_loop
from orchestrator.ws_manager import ws_manager
from services.event_dedupe import event_deduper
from services.agent_store import agent_store
from services import storage as storage_mod
from services.session_store import store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None


def _parse_cors_origins(raw: str) -> list[str]:
    origins = [entry.strip() for entry in raw.split(",") if entry.strip()]
    if origins:
        return origins
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ]


async def _session_cleanup_loop(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        removed = await store.prune_expired()
        if removed:
            logger.info("Pruned %s expired session(s)", removed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _cleanup_task
    settings = get_settings()
    create_tables()  # Create database tables
    store.set_ttl_seconds(settings.session_ttl_seconds)
    store.configure_redis(settings.redis_url, settings.redis_key_prefix)
    await store.load_from_redis()
    agent_store.configure(settings.agents_db_path)
    agent_store.initialize()
    event_deduper.set_ttl_seconds(settings.webhook_dedupe_ttl_seconds)
    await configure_queue(settings.redis_url, settings.redis_key_prefix)
    storage_mod.register_presentation(
        "demo",
        "demo-deck.pdf",
        status="ready",
        total_pages=20,
        indexed_pages=20,
    )
    _worker_task = asyncio.create_task(transcript_worker_loop())
    if settings.session_cleanup_interval_seconds > 0:
        _cleanup_task = asyncio.create_task(
            _session_cleanup_loop(settings.session_cleanup_interval_seconds)
        )
    logger.info(
        "Overtone backend started; Recall base URL=%s",
        settings.recall_api_base_url,
    )
    yield
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Overtone API", lifespan=lifespan)

settings = get_settings()
cors_origins = _parse_cors_origins(settings.cors_allowed_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=(
        r"https://.*\.(vercel\.app|trycloudflare\.com|railway\.app|ngrok-free\.app)"
        # Regional Cloud Run: https://SERVICE-PROJECT.REGION.run.app (not only *.a.run.app)
        r"|https://.+\.run\.app$"
    ),
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(customer_api.router)
app.include_router(admin_api.router)
app.include_router(auth_admin.router)
app.include_router(presentations.router)
app.include_router(index_status.router)
app.include_router(launch_bot.router)
app.include_router(sessions.router)
app.include_router(webhook_recall.router)
app.include_router(webhook_bot_status.router)
app.include_router(webhook_chat.router)
app.include_router(tts.router)
app.include_router(realtime_relay.router)

if os.getenv("VOICENAV_DEV") == "1":
    from api import dev as dev_routes

    app.include_router(dev_routes.router)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "active_sessions": await store.active_count(),
        "transcript_queue_depth": queue_depth(),
        "webhook_dedupe_cache": await event_deduper.seen_count(),
    }


@app.websocket("/ws/presentation/{session_id}")
async def presentation_ws(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)) -> None:
    sess = await store.get_by_session_id(session_id)
    if not sess:
        # Fall back to DB — session exists there even after a server restart
        db_sess = db.query(BotSession).filter(BotSession.session_id == session_id).first()
        if not db_sess:
            await websocket.accept()
            await websocket.close(code=4404)
            return
        sess = db_sess
    await ws_manager.connect(session_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "status",
                "status": "listening",
                "presentation_id": sess.presentation_id,
            }
        )
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            if msg.get("type") == "ready":
                continue
            if msg.get("type") == "state":
                continue
    finally:
        ws_manager.disconnect(session_id, websocket)


def run() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("VOICENAV_DEV") == "1"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    run()
