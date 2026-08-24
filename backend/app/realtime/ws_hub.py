from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class PresentationHub:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms.setdefault(session_id, set()).add(ws)

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            peers = self._rooms.get(session_id)
            if peers and ws in peers:
                peers.discard(ws)
            if peers is not None and not peers:
                self._rooms.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload)
        async with self._lock:
            peers = list(self._rooms.get(session_id, set()))
        dead: list[WebSocket] = []
        for ws in peers:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(session_id, ws)


hub = PresentationHub()
