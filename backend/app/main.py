from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CLOUD_RUN_CORS_ORIGIN_REGEX, cors_origin_list, get_settings
from app.db import SessionLocal, create_tables
from app.domain import agents as agent_store
from app.http import agents, auth_routes, billing, customers, me, presentations, sessions, webhooks
from app.http.auth import require_admin_key
from app.realtime import relay
from fastapi import Depends

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deckvoice.v2")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        agent_store.ensure_default_agent(db)
    finally:
        db.close()
    logger.info("DeckVoice API ready")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="DeckVoice", version="2.0.0", lifespan=lifespan)
    origins = cors_origin_list(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=CLOUD_RUN_CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_routes.router)
    app.include_router(me.router)
    app.include_router(billing.router)
    app.include_router(presentations.router)
    app.include_router(agents.router)
    app.include_router(sessions.router)
    app.include_router(customers.router)
    app.include_router(webhooks.router)
    app.include_router(relay.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "v2"}

    @app.post("/admin/bootstrap-db")
    def bootstrap_db(_: None = Depends(require_admin_key)):
        from app.indexing.vector_store import ensure_chunks_table

        try:
            ensure_chunks_table()
            return {"ok": True, "chunks_table": "v2_presentation_chunks"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    return app


app = create_app()
