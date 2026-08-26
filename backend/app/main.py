from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal, create_tables
from app.domain import agents as agent_store
from app.http import agents, auth_routes, billing, customers, me, presentations, sessions, webhooks
from app.http.auth import require_admin_key
from app.realtime import relay
from fastapi import Depends

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("overtone.v2")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        agent_store.ensure_default_agent(db)
    finally:
        db.close()
    logger.info("Overtone V2 API ready")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Overtone V2", version="2.0.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
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
