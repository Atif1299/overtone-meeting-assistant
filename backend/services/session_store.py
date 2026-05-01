from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import uuid
from typing import Any

from models.bot_session import AgentMode, BotSession, BotSessionState

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - handled at runtime when redis is missing
    redis_async = None

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Session index with optional Redis durability.

    Memory remains the fast local cache. When Redis is configured, sessions are also
    persisted and can be rehydrated across process restarts.
    """

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._ttl = ttl_seconds
        self._by_session: dict[str, BotSession] = {}
        self._bot_to_session: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._redis_url = ""
        self._redis_prefix = "voicenav"
        self._redis_client: Any | None = None
        self._redis_disabled = True
        self._redis_warned = False

    def set_ttl_seconds(self, ttl_seconds: int) -> None:
        self._ttl = max(0, int(ttl_seconds))

    def configure_redis(self, redis_url: str, key_prefix: str = "voicenav") -> None:
        self._redis_url = (redis_url or "").strip()
        self._redis_prefix = (key_prefix or "voicenav").strip() or "voicenav"
        self._redis_client = None
        self._redis_disabled = not bool(self._redis_url)
        self._redis_warned = False

    async def load_from_redis(self) -> int:
        """
        Rehydrate sessions from Redis into memory.
        Returns number of sessions loaded.
        """
        redis = await self._get_redis()
        if not redis:
            return 0

        loaded = 0
        ids = await redis.smembers(self._redis_sessions_set_key())
        now = _now_utc()
        async with self._lock:
            for session_id in ids:
                raw = await redis.get(self._redis_session_key(session_id))
                if not raw:
                    await redis.srem(self._redis_sessions_set_key(), session_id)
                    continue
                try:
                    session = BotSession.model_validate_json(raw)
                except Exception:
                    await redis.delete(self._redis_session_key(session_id))
                    await redis.srem(self._redis_sessions_set_key(), session_id)
                    continue
                if _is_expired(session, now):
                    await redis.delete(self._redis_session_key(session_id))
                    if session.bot_id:
                        await redis.delete(self._redis_bot_key(session.bot_id))
                    await redis.srem(self._redis_sessions_set_key(), session_id)
                    continue
                self._by_session[session_id] = session
                if session.bot_id:
                    self._bot_to_session[session.bot_id] = session_id
                loaded += 1
        return loaded

    async def active_count(self) -> int:
        await self.load_from_redis()
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            return len(self._by_session)

    def _evict_expired_locked(self, now: datetime) -> int:
        expired_ids = [
            session_id
            for session_id, session in self._by_session.items()
            if _is_expired(session, now)
        ]
        for session_id in expired_ids:
            sess = self._by_session.pop(session_id, None)
            if sess and sess.bot_id:
                self._bot_to_session.pop(sess.bot_id, None)
        return len(expired_ids)

    async def prune_expired(self) -> int:
        async with self._lock:
            return self._evict_expired_locked(_now_utc())

    async def clear(self) -> None:
        async with self._lock:
            self._by_session.clear()
            self._bot_to_session.clear()
        redis = await self._get_redis()
        if redis:
            ids = await redis.smembers(self._redis_sessions_set_key())
            if ids:
                session_keys = [self._redis_session_key(session_id) for session_id in ids]
                await redis.delete(*session_keys)
            bot_keys = [key async for key in redis.scan_iter(match=f"{self._redis_prefix}:bot:*")]
            if bot_keys:
                await redis.delete(*bot_keys)
            await redis.delete(self._redis_sessions_set_key())

    async def create_session(
        self,
        *,
        presentation_id: str,
        bot_name: str,
        meeting_url: str,
        agent_mode: AgentMode = AgentMode.REALTIME,
        agent_name: str = "default",
        agent_version: int | None = None,
        bot_id: str | None = None,
        session_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> BotSession:
        sid = session_id or str(uuid.uuid4())
        now = _now_utc()
        expires_at = now + timedelta(seconds=self._ttl) if self._ttl > 0 else None
        sess = BotSession(
            session_id=sid,
            presentation_id=presentation_id,
            bot_id=bot_id,
            bot_name=bot_name,
            meeting_url=meeting_url,
            agent_mode=agent_mode,
            agent_name=agent_name,
            agent_version=agent_version,
            state=BotSessionState.CREATED.value,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            extra=extra or {},
        )
        async with self._lock:
            self._evict_expired_locked(now)
            self._by_session[sid] = sess
            if bot_id:
                self._bot_to_session[bot_id] = sid
        await self._persist_session(sess)
        return sess

    async def register_session(self, sess: BotSession) -> None:
        """Register an existing BotSession object into the in-memory store.

        Used when a session is loaded from a persistent store (e.g. SQL DB) and
        needs to be visible to tool calls that look it up via get_by_session_id.
        """
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            self._by_session[sess.session_id] = sess
            if sess.bot_id:
                self._bot_to_session[sess.bot_id] = sess.session_id

    async def attach_bot_id(self, session_id: str, bot_id: str) -> None:
        updated: BotSession | None = None
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            s = self._by_session.get(session_id)
            if not s:
                return
            if s.bot_id and s.bot_id in self._bot_to_session:
                del self._bot_to_session[s.bot_id]
            s.bot_id = bot_id
            s.updated_at = _now_utc()
            self._bot_to_session[bot_id] = session_id
            updated = s
        if updated:
            await self._persist_session(updated)

    async def get_by_session_id(self, session_id: str) -> BotSession | None:
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            cached = self._by_session.get(session_id)
            if cached:
                return cached
        restored = await self._restore_session_from_redis(session_id)
        if restored:
            async with self._lock:
                self._by_session[session_id] = restored
                if restored.bot_id:
                    self._bot_to_session[restored.bot_id] = session_id
        return restored

    async def get_by_bot_id(self, bot_id: str) -> BotSession | None:
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            sid = self._bot_to_session.get(bot_id)
            if sid:
                return self._by_session.get(sid)
        redis = await self._get_redis()
        if not redis:
            return None
        sid = await redis.get(self._redis_bot_key(bot_id))
        if not sid:
            return None
        restored = await self._restore_session_from_redis(sid)
        if restored:
            async with self._lock:
                self._by_session[sid] = restored
                if restored.bot_id:
                    self._bot_to_session[restored.bot_id] = sid
        return restored

    async def update_session(self, session_id: str, **fields: Any) -> BotSession | None:
        updated: BotSession | None = None
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            s = self._by_session.get(session_id)
            if not s:
                return None
            for k, v in fields.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            s.updated_at = _now_utc()
            updated = s
        if updated:
            await self._persist_session(updated)
        return updated

    async def merge_extra(self, session_id: str, **fields: Any) -> BotSession | None:
        updated: BotSession | None = None
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            s = self._by_session.get(session_id)
            if not s:
                return None
            s.extra.update(fields)
            s.updated_at = _now_utc()
            updated = s
        if updated:
            await self._persist_session(updated)
        return updated

    async def update_bot_status(
        self,
        bot_id: str,
        *,
        code: str | None,
        message: str | None = None,
    ) -> BotSession | None:
        updated: BotSession | None = None
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            sid = self._bot_to_session.get(bot_id)
            if not sid:
                return None
            s = self._by_session.get(sid)
            if not s:
                return None
            s.last_status_code = code
            s.last_status_message = message
            s.state = _map_recall_status(code)
            s.updated_at = _now_utc()
            updated = s
        if updated:
            await self._persist_session(updated)
        return updated

    async def set_transcript_snippet(self, bot_id: str, text: str) -> BotSession | None:
        updated: BotSession | None = None
        async with self._lock:
            self._evict_expired_locked(_now_utc())
            sid = self._bot_to_session.get(bot_id)
            if not sid:
                return None
            s = self._by_session.get(sid)
            if not s:
                return None
            s.last_transcript_snippet = text[:500]
            s.updated_at = _now_utc()
            updated = s
        if updated:
            await self._persist_session(updated)
        return updated

    async def _persist_session(self, session: BotSession) -> None:
        redis = await self._get_redis()
        if not redis:
            return
        ttl_seconds = _ttl_seconds_for_session(session)
        kwargs = {"ex": ttl_seconds} if ttl_seconds is not None else {}
        await redis.set(self._redis_session_key(session.session_id), session.model_dump_json(), **kwargs)
        await redis.sadd(self._redis_sessions_set_key(), session.session_id)
        if session.bot_id:
            await redis.set(self._redis_bot_key(session.bot_id), session.session_id, **kwargs)

    async def _restore_session_from_redis(self, session_id: str) -> BotSession | None:
        redis = await self._get_redis()
        if not redis:
            return None
        raw = await redis.get(self._redis_session_key(session_id))
        if not raw:
            return None
        try:
            return BotSession.model_validate_json(raw)
        except Exception:
            await redis.delete(self._redis_session_key(session_id))
            await redis.srem(self._redis_sessions_set_key(), session_id)
            return None

    async def _get_redis(self):
        if self._redis_disabled or not self._redis_url:
            return None
        if self._redis_client is not None:
            return self._redis_client
        if redis_async is None:
            if not self._redis_warned:
                logger.warning("REDIS_URL is set but redis package is unavailable; using in-memory sessions")
                self._redis_warned = True
            self._redis_disabled = True
            return None
        try:
            client = redis_async.from_url(self._redis_url, decode_responses=True)
            await client.ping()
        except Exception as exc:  # pragma: no cover - depends on runtime infrastructure
            if not self._redis_warned:
                logger.warning("Redis unavailable (%s); using in-memory sessions", exc)
                self._redis_warned = True
            self._redis_disabled = True
            return None
        self._redis_client = client
        return self._redis_client

    def _redis_session_key(self, session_id: str) -> str:
        return f"{self._redis_prefix}:session:{session_id}"

    def _redis_bot_key(self, bot_id: str) -> str:
        return f"{self._redis_prefix}:bot:{bot_id}"

    def _redis_sessions_set_key(self) -> str:
        return f"{self._redis_prefix}:sessions"


def _map_recall_status(code: str | None) -> BotSessionState:
    if not code:
        return BotSessionState.UNKNOWN
    mapping = {
        "joining_call": BotSessionState.JOINING,
        "in_waiting_room": BotSessionState.IN_WAITING_ROOM,
        "in_call_not_recording": BotSessionState.IN_CALL,
        "in_call_recording": BotSessionState.RECORDING,
        "call_ended": BotSessionState.CALL_ENDED,
        "done": BotSessionState.DONE,
        "fatal": BotSessionState.FATAL,
        "ready": BotSessionState.UNKNOWN,
    }
    return mapping.get(code, BotSessionState.UNKNOWN)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(session: BotSession, now: datetime) -> bool:
    return bool(session.expires_at and session.expires_at <= now)


def _ttl_seconds_for_session(session: BotSession) -> int | None:
    if not session.expires_at:
        return None
    remaining = int((session.expires_at - _now_utc()).total_seconds())
    return max(1, remaining)


store = SessionStore()
