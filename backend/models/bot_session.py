from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Column, String, DateTime, Text, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base

from database import Base


class BotSessionState(str, Enum):
    CREATED = "created"
    JOINING = "joining"
    IN_WAITING_ROOM = "in_waiting_room"
    IN_CALL = "in_call"
    RECORDING = "recording"
    CALL_ENDED = "call_ended"
    DONE = "done"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class AgentMode(str, Enum):
    REALTIME = "realtime"
    WEBHOOK = "webhook"


def _utcnow():
    return datetime.now(timezone.utc)


class BotSession(Base):
    __tablename__ = "bot_sessions"

    session_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=True)
    bot_id = Column(String, nullable=True)
    presentation_id = Column(String, nullable=True)
    bot_name = Column(String)
    meeting_url = Column(String)
    agent_mode = Column(String, default=AgentMode.REALTIME.value)
    agent_name = Column(String, default="default")
    agent_version = Column(Integer, nullable=True)
    state = Column(String, default=BotSessionState.CREATED.value)
    last_status_code = Column(String, nullable=True)
    last_status_message = Column(String, nullable=True)
    last_transcript_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    expires_at = Column(DateTime, nullable=True)
    extra = Column(JSON, default=dict)

    # Additional fields for customer API
    pdf_url = Column(String, nullable=True)
    metadata_url = Column(String, nullable=True)
    recall_bot_id = Column(String, nullable=True)  # Recall.ai's bot ID (set after launch)
