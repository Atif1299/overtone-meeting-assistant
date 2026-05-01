"""Local testing helpers. Enable with VOICENAV_DEV=1 only."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_admin_key
from services.session_store import store

router = APIRouter(prefix="/api", tags=["dev"])


def _check() -> None:
    if os.getenv("VOICENAV_DEV") != "1":
        raise HTTPException(404, "Not found")


class SeedResponse(BaseModel):
    session_id: str
    bot_id: str
    presentation_id: str


@router.post("/dev/seed-session", response_model=SeedResponse)
async def seed_session(_: None = Depends(require_admin_key)) -> SeedResponse:
    _check()
    fake_bot = "00000000-0000-4000-8000-000000000001"
    sid = str(uuid.uuid4())
    await store.create_session(
        presentation_id="demo",
        bot_name="Dev Bot",
        meeting_url="https://example.com/meeting",
        bot_id=fake_bot,
        session_id=sid,
    )
    return SeedResponse(
        session_id=sid,
        bot_id=fake_bot,
        presentation_id="demo",
    )
