from __future__ import annotations

import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[session_id].append(websocket)
        logger.info(
            "WS connected session_id=%s clients=%d",
            session_id, len(self._rooms[session_id]),
        )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        conns = self._rooms.get(session_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        remaining = len(self._rooms.get(session_id, []))
        logger.info(
            "WS disconnected session_id=%s remaining_clients=%d",
            session_id, remaining,
        )
        if not conns:
            del self._rooms[session_id]

    async def broadcast_json(self, session_id: str, message: dict) -> None:
        conns = list(self._rooms.get(session_id, []))
        if not conns:
            # Navigation message lost — no presentation page connected.
            # This is the "no navigation" failure mode.
            logger.warning(
                "WS broadcast DROPPED session_id=%s msg_type=%s — no clients connected",
                session_id, message.get("type", "?"),
            )
            return
        dead: list[WebSocket] = []
        text = json.dumps(message)
        sent = 0
        for ws in conns:
            try:
                await ws.send_text(text)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)
        logger.info(
            "WS broadcast session_id=%s msg_type=%s sent=%d dead=%d",
            session_id, message.get("type", "?"), sent, len(dead),
        )


ws_manager = WSManager()
