from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.db import SessionLocal
from app.db.models import Session as SessionRow, SessionState

DURABLE_KEYS = ("session_greeting_sent", "muted", "current_page")


@dataclass
class LiveSession:
    session_id: str
    presentation_id: str
    bot_name: str
    meeting_url: str
    agent_name: str = "default"
    agent_version: int | None = 1
    customer_id: str | None = None
    bot_id: str | None = None
    recall_bot_id: str | None = None
    state: str = SessionState.CREATED.value
    last_status_code: str | None = None
    last_status_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self):
        self._by_id: dict[str, LiveSession] = {}
        self._by_recall: dict[str, str] = {}
        self._redis = None

    def _redis_client(self):
        settings = get_settings()
        if not settings.redis_url:
            return None
        if self._redis is None:
            import redis

            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"{get_settings().redis_key_prefix}:session:{session_id}"

    def create(self, sess: LiveSession) -> LiveSession:
        self.register(sess)
        self._persist_sql(sess)
        self._persist_redis(sess)
        return sess

    def register(self, sess: LiveSession) -> None:
        self._by_id[sess.session_id] = sess
        if sess.recall_bot_id:
            self._by_recall[sess.recall_bot_id] = sess.session_id
        sess.updated_at = time.time()

    def get(self, session_id: str) -> LiveSession | None:
        if session_id in self._by_id:
            return self._by_id[session_id]
        r = self._redis_client()
        if r:
            raw = r.get(self._key(session_id))
            if raw:
                data = json.loads(raw)
                sess = LiveSession(**{k: data[k] for k in LiveSession.__dataclass_fields__ if k in data})
                self.register(sess)
                return sess
        db = SessionLocal()
        try:
            row = db.get(SessionRow, session_id)
            if not row:
                return None
            sess = LiveSession(
                session_id=row.session_id,
                presentation_id=row.presentation_id or "",
                bot_name=row.bot_name or "Overtone",
                meeting_url=row.meeting_url or "",
                agent_name=row.agent_name or "default",
                agent_version=row.agent_version,
                customer_id=row.customer_id,
                bot_id=row.bot_id,
                recall_bot_id=row.recall_bot_id,
                state=row.state,
                last_status_code=row.last_status_code,
                last_status_message=row.last_status_message,
                extra=dict(row.extra or {}),
            )
            self.register(sess)
            return sess
        finally:
            db.close()

    def get_by_recall_bot_id(self, recall_bot_id: str) -> LiveSession | None:
        sid = self._by_recall.get(recall_bot_id)
        if sid:
            return self.get(sid)
        db = SessionLocal()
        try:
            row = (
                db.query(SessionRow)
                .filter(SessionRow.recall_bot_id == recall_bot_id)
                .order_by(SessionRow.created_at.desc())
                .first()
            )
            if not row:
                return None
            return self.get(row.session_id)
        finally:
            db.close()

    def merge_extra(self, session_id: str, **fields) -> LiveSession | None:
        sess = self.get(session_id)
        if not sess:
            return None
        extra = dict(sess.extra or {})
        extra.update(fields)
        sess.extra = extra
        sess.updated_at = time.time()
        self._persist_redis(sess)
        durable = {k: extra[k] for k in DURABLE_KEYS if k in extra}
        if durable:
            self._mirror_sql_extra(session_id, durable)
        return sess

    def update(self, session_id: str, **fields) -> LiveSession | None:
        sess = self.get(session_id)
        if not sess:
            return None
        for k, v in fields.items():
            if hasattr(sess, k) and k != "extra":
                setattr(sess, k, v)
            elif k == "extra" and isinstance(v, dict):
                sess.extra = v
        if sess.recall_bot_id:
            self._by_recall[sess.recall_bot_id] = sess.session_id
        sess.updated_at = time.time()
        self._persist_sql(sess)
        self._persist_redis(sess)
        return sess

    def update_bot_status(self, recall_bot_id: str, code: str, message: str = "") -> None:
        sess = self.get_by_recall_bot_id(recall_bot_id)
        if not sess:
            return
        mapping = {
            "joining_call": SessionState.JOINING.value,
            "in_waiting_room": SessionState.IN_WAITING_ROOM.value,
            "in_call_not_recording": SessionState.IN_CALL.value,
            "in_call_recording": SessionState.RECORDING.value,
            "call_ended": SessionState.CALL_ENDED.value,
            "done": SessionState.DONE.value,
            "fatal": SessionState.FATAL.value,
        }
        self.update(
            sess.session_id,
            state=mapping.get(code, sess.state),
            last_status_code=code,
            last_status_message=message,
        )

    def _persist_sql(self, sess: LiveSession) -> None:
        db = SessionLocal()
        try:
            row = db.get(SessionRow, sess.session_id) or SessionRow(session_id=sess.session_id)
            row.customer_id = sess.customer_id
            row.bot_id = sess.bot_id
            row.recall_bot_id = sess.recall_bot_id
            row.presentation_id = sess.presentation_id
            row.bot_name = sess.bot_name
            row.meeting_url = sess.meeting_url
            row.agent_name = sess.agent_name
            row.agent_version = sess.agent_version
            row.state = sess.state
            row.last_status_code = sess.last_status_code
            row.last_status_message = sess.last_status_message
            row.extra = deepcopy(sess.extra or {})
            row.updated_at = datetime.now(timezone.utc)
            db.merge(row)
            db.commit()
        finally:
            db.close()

    def _mirror_sql_extra(self, session_id: str, durable: dict) -> None:
        db = SessionLocal()
        try:
            row = db.get(SessionRow, session_id)
            if not row:
                return
            extra = dict(row.extra or {})
            extra.update(durable)
            row.extra = extra
            db.commit()
        finally:
            db.close()

    def _persist_redis(self, sess: LiveSession) -> None:
        r = self._redis_client()
        if not r:
            return
        payload = {
            "session_id": sess.session_id,
            "presentation_id": sess.presentation_id,
            "bot_name": sess.bot_name,
            "meeting_url": sess.meeting_url,
            "agent_name": sess.agent_name,
            "agent_version": sess.agent_version,
            "customer_id": sess.customer_id,
            "bot_id": sess.bot_id,
            "recall_bot_id": sess.recall_bot_id,
            "state": sess.state,
            "last_status_code": sess.last_status_code,
            "last_status_message": sess.last_status_message,
            "extra": sess.extra,
            "updated_at": sess.updated_at,
        }
        r.setex(self._key(sess.session_id), get_settings().session_ttl_seconds, json.dumps(payload))


store = SessionStore()
