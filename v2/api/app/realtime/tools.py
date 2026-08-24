from __future__ import annotations

import json
from typing import Any

from app.db import SessionLocal
from app.domain.session_store import store
from app.indexing.embeddings import generate_embedding
from app.indexing.vector_store import hybrid_search
from app.meetings.recall import RecallClient
from app.realtime.ws_hub import hub
from app.storage import PresentationStore

REALTIME_TOOLS = [
    {
        "type": "function",
        "name": "navigate_to_slide",
        "description": "Navigate the presenter to a specific slide page and return its content.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_number": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["page_number"],
        },
    },
    {
        "type": "function",
        "name": "get_slide_details",
        "description": "Get details for the current or specified slide from the indexed deck.",
        "parameters": {
            "type": "object",
            "properties": {"page_number": {"type": "integer"}},
        },
    },
    {
        "type": "function",
        "name": "search_and_answer",
        "description": "Search the indexed deck and answer from retrieved slide text only.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_question": {"type": "string"},
                "search_query": {"type": "string"},
            },
            "required": ["user_question", "search_query"],
        },
    },
    {
        "type": "function",
        "name": "mute_self",
        "description": "Mute bot audio output.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "unmute_self",
        "description": "Unmute bot audio output.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "leave_call",
        "description": "Leave the meeting after a short delay.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "send_chat_message",
        "description": "Send a chat message in the meeting.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
]


def _parse_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


class ToolExecutor:
    async def execute(self, session_id: str, tool_name: str, raw_arguments: Any) -> dict:
        args = _parse_args(raw_arguments)
        sess = store.get(session_id)
        if not sess:
            return {"ok": False, "error": "session_not_found"}
        handler = {
            "navigate_to_slide": self._navigate,
            "get_slide_details": self._details,
            "search_and_answer": self._search,
            "mute_self": self._mute,
            "unmute_self": self._unmute,
            "leave_call": self._leave,
            "send_chat_message": self._chat,
        }.get(tool_name)
        if not handler:
            return {"ok": False, "error": f"unknown_tool:{tool_name}"}
        return await handler(sess, args)

    async def _page_payload(self, presentation_id: str, page_number: int) -> dict:
        db = SessionLocal()
        try:
            pages = PresentationStore(db).load_index_pages(presentation_id)
        finally:
            db.close()
        page = next((p for p in pages if int(p.get("page_number") or 0) == page_number), None)
        if not page:
            return {
                "ok": False,
                "page_number": page_number,
                "slide_content": "",
                "instruction": "Page not found in index. Do not invent content.",
            }
        content = page.get("searchable_content") or page.get("content") or page.get("content_text") or ""
        return {
            "ok": True,
            "page_number": page_number,
            "slide_title": page.get("title") or "",
            "slide_content": content,
            "instruction": "Answer only from slide_content. If empty, say it is not in the deck.",
        }

    async def _navigate(self, sess, args: dict) -> dict:
        page = int(args.get("page_number") or 1)
        db = SessionLocal()
        try:
            pages = PresentationStore(db).load_index_pages(sess.presentation_id)
        finally:
            db.close()
        total = len(pages) or 1
        page = max(1, min(page, total))
        await hub.broadcast(
            sess.session_id,
            {"type": "navigate", "target_page": page, "page_number": page},
        )
        store.merge_extra(sess.session_id, current_page=page)
        payload = await self._page_payload(sess.presentation_id, page)
        payload["target_page"] = page
        return payload

    async def _details(self, sess, args: dict) -> dict:
        page = args.get("page_number")
        if page is None:
            page = (sess.extra or {}).get("current_page") or 1
        return await self._page_payload(sess.presentation_id, int(page))

    async def _search(self, sess, args: dict) -> dict:
        q = args.get("search_query") or args.get("user_question") or ""
        hits = await hybrid_search(sess.presentation_id, q, generate_embedding, top_k=3)
        if not hits:
            db = SessionLocal()
            try:
                pages = PresentationStore(db).load_index_pages(sess.presentation_id)
            finally:
                db.close()
            ql = q.lower()
            scored = []
            for p in pages:
                text = (p.get("searchable_content") or "").lower()
                score = 1.0 if ql and ql in text else 0.1
                scored.append((score, p))
            scored.sort(key=lambda x: x[0], reverse=True)
            hits = [
                {
                    "page_number": p.get("page_number"),
                    "title": p.get("title"),
                    "searchable_content": p.get("searchable_content"),
                    "score": s,
                }
                for s, p in scored[:3]
            ]

        if not hits or float(hits[0].get("score") or 0) < 0.15:
            return {
                "ok": True,
                "slide_content": "",
                "instruction": "No grounded match. Say you cannot find it in the deck. Do not invent.",
            }

        best = hits[0]
        page = int(best.get("page_number") or 1)
        await hub.broadcast(
            sess.session_id,
            {"type": "navigate", "target_page": page, "page_number": page},
        )
        store.merge_extra(sess.session_id, current_page=page)
        content = best.get("searchable_content") or best.get("content") or ""
        return {
            "ok": True,
            "target_page": page,
            "page_number": page,
            "navigated": True,
            "slide_content": content,
            "instruction": "Answer only from slide_content.",
        }

    async def _mute(self, sess, _args: dict) -> dict:
        store.merge_extra(sess.session_id, muted=True)
        await hub.broadcast(sess.session_id, {"type": "bot_muted"})
        if sess.recall_bot_id:
            await RecallClient().mute_bot(sess.recall_bot_id)
        return {"ok": True, "action": "muted"}

    async def _unmute(self, sess, _args: dict) -> dict:
        store.merge_extra(sess.session_id, muted=False)
        await hub.broadcast(sess.session_id, {"type": "bot_unmuted"})
        if sess.recall_bot_id:
            await RecallClient().unmute_bot(sess.recall_bot_id)
        return {"ok": True, "action": "unmuted"}

    async def _leave(self, sess, _args: dict) -> dict:
        import asyncio

        async def _later():
            await asyncio.sleep(3)
            if sess.recall_bot_id:
                await RecallClient().leave_call(sess.recall_bot_id)
            store.update(sess.session_id, state="done")

        asyncio.create_task(_later())
        return {"ok": True, "action": "left_call_scheduled"}

    async def _chat(self, sess, args: dict) -> dict:
        msg = (args.get("message") or "").strip()
        if not msg or not sess.recall_bot_id:
            return {"ok": False, "error": "missing_message_or_bot"}
        await RecallClient().send_chat_message(sess.recall_bot_id, msg)
        return {"ok": True, "action": "chat_message_sent"}


tools = ToolExecutor()
