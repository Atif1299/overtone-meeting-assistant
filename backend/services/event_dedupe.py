from __future__ import annotations

import asyncio
import time
from typing import Any


class EventDeduper:
    """Tracks webhook event IDs for a short TTL to avoid duplicate processing."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = max(1, int(ttl_seconds))
        self._seen_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def set_ttl_seconds(self, ttl_seconds: int) -> None:
        self._ttl = max(1, int(ttl_seconds))

    async def is_duplicate(self, event_id: str | None) -> bool:
        if not event_id:
            return False
        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            expires_at = self._seen_until.get(event_id)
            if expires_at and expires_at > now:
                return True
            self._seen_until[event_id] = now + self._ttl
            return False

    async def seen_count(self) -> int:
        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            return len(self._seen_until)

    async def clear(self) -> None:
        async with self._lock:
            self._seen_until.clear()

    def _prune_locked(self, now: float) -> None:
        stale = [event_id for event_id, expiry in self._seen_until.items() if expiry <= now]
        for event_id in stale:
            self._seen_until.pop(event_id, None)


def extract_event_id(headers: dict[str, str], payload: dict[str, Any]) -> str | None:
    for header_name in (
        "svix-id",
        "x-svix-id",
        "webhook-id",
        "x-webhook-id",
        "x-recall-event-id",
    ):
        header_value = headers.get(header_name)
        if header_value:
            return str(header_value)

    for key in ("id", "event_id", "request_id"):
        value = payload.get(key)
        if value:
            return str(value)

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("id", "event_id"):
            value = data.get(key)
            if value:
                return str(value)
    return None


event_deduper = EventDeduper()
