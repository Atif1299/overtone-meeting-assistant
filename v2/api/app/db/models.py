from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SessionState(str, Enum):
    CREATED = "created"
    JOINING = "joining"
    IN_WAITING_ROOM = "in_waiting_room"
    IN_CALL = "in_call"
    RECORDING = "recording"
    CALL_ENDED = "call_ended"
    DONE = "done"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class Presentation(Base):
    __tablename__ = "v2_presentations"

    presentation_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_pages: Mapped[int] = mapped_column(Integer, default=0)
    indexed_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_model: Mapped[str | None] = mapped_column(String, nullable=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Session(Base):
    __tablename__ = "v2_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    bot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recall_bot_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    presentation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    bot_name: Mapped[str] = mapped_column(String, default="Overtone")
    meeting_url: Mapped[str] = mapped_column(String, default="")
    agent_name: Mapped[str] = mapped_column(String, default="default")
    agent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String, default=SessionState.CREATED.value)
    last_status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_status_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class ApiKey(Base):
    __tablename__ = "v2_api_keys"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AgentVersion(Base):
    __tablename__ = "v2_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
