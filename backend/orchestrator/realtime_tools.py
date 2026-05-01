from __future__ import annotations

import json
import logging
import time
from typing import Any

from config import Settings, get_settings
from indexer.manifest import load_manifest
from orchestrator import rag_retriever
from orchestrator.ws_manager import ws_manager
from services.session_store import store
from services.recall_client import RecallClient
import asyncio

logger = logging.getLogger(__name__)


async def _get_session(session_id: str):
    """
    Look up a BotSession by session_id.
    Checks in-memory store first; falls back to the persistent DB so that tool
    calls survive server restarts (no in-memory state requirement).
    """
    sess = await store.get_by_session_id(session_id)
    if sess:
        return sess
    try:
        from database import SessionLocal
        from models.bot_session import BotSession as BotSessionModel
        db = SessionLocal()
        try:
            db_sess = db.query(BotSessionModel).filter(
                BotSessionModel.session_id == session_id
            ).first()
            if db_sess:
                # Re-register in the in-memory store so subsequent lookups are instant
                await store.register_session(db_sess)
            return db_sess
        finally:
            db.close()
    except Exception as exc:
        logger.warning("DB session fallback failed session_id=%s: %s", session_id, exc)
        return None

REALTIME_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "navigate_to_slide",
        "description": (
            "Navigate directly to a specific slide number. "
            "Use for explicit navigation commands: 'go to slide 5', 'jump to pricing', "
            "'show me the architecture slide'. "
            "IMPORTANT: If the user says 'go back' or 'previous', they mean the preceding "
            "slide number (e.g., 4 to 3). "
            "WARNING: Do not confuse table row numbers or list item numbers with "
            "slide numbers. Only navigate if the user asks for a SLIDE or PAGE. "
            "Do NOT use this for content questions — use search_and_answer instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "page_number": {"type": "integer", "minimum": 1},
                "reason": {"type": "string"},
            },
            "required": ["page_number"],
        },
    },
    {
        "type": "function",
        "name": "search_and_answer",
        "description": (
            "IMPORTANT: BEFORE calling this tool, check if the answer is in your HIGH-PRIORITY ACCOUNT BRIEFING "
            "(pre_answered_qa or talking_points). If it is, DO NOT call this tool; answer directly.\n\n"
            "Search BOTH the visual presentation AND the underlying Account Briefing (Briefcase) "
            "for content and answer the user's question if it's not in the high-priority briefing. "
            "Use this for metrics (ROAS, CPA, Spend), campaign details, and performance trends. "
            "\n\n"
            "NAVIGATION DECISION — follow these rules in order:\n"
            "1. STAY on the current slide if it already contains the answer OR if the info "
            "comes from the Account Briefing (which has no slide number).\n"
            "2. NAVIGATE to another slide only when the question is specifically about "
            "a different visual section (e.g. 'show me pricing').\n"
            "3. Trust the 'Briefcase' results for deep metrics that aren't visible on the slide.\n"
            "\n"
            "Provide search_query as a concise 3-6 word keyword phrase for the TOPIC. "
            "Your spoken response must come ONLY from the tool results (slide_content or brief_content)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_question": {
                    "type": "string",
                    "description": "The participant's exact question.",
                },
                "search_query": {
                    "type": "string",
                    "description": "Concise 3-6 word keyword phrase describing the topic to find.",
                },
            },
            "required": ["user_question", "search_query"],
        },
    },
    {
        "type": "function",
        "name": "leave_call",
        "description": (
            "Make the bot leave the current meeting call immediately. "
            "Use when someone says: 'leave the call', 'hang up', 'disconnect', "
            "'bye', 'end the call', 'you can leave', 'that's all'. "
            "Say a brief goodbye BEFORE calling this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "mute_self",
        "description": (
            "Mute yourself — go completely silent in the meeting. "
            "Once muted you will NOT hear or respond to ANY speech from participants. "
            "You can only be unmuted externally via the control panel or by an explicit "
            "unmute command. "
            "Use when someone says: 'mute yourself', 'go on mute', 'be quiet', "
            "'stop talking', 'mute', 'shhh', 'shut up'. "
            "Say ONE brief confirmation BEFORE calling this tool, e.g. 'Going on mute.' "
            "then call it immediately. Do NOT say anything after calling it."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "unmute_self",
        "description": (
            "Unmute yourself — resume speaking in the meeting. "
            "Use ONLY when someone EXPLICITLY commands you to unmute (e.g., 'unmute yourself', "
            "'unmute', 'you can speak now', 'we need you back', 'come off mute'). "
            "DO NOT call this if someone just says 'hello' or is talking to someone else. "
            "Call this tool FIRST, then speak your response."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "fetch_external_data",
        "description": (
            "Use to fetch deep metrics and data that is NOT on the slides (e.g., 'tell me about the last 16 months performance', 'what are the ad groups'). "
            "Use this ONLY if you could not find the answer in the deck using search_and_answer. "
            "This spins up an asynchronous background task to search the detailed Account Briefing. "
            "When you call this tool, immediately say something like: "
            "'I'm running a deep search on that — give me a moment.' "
            "You do NOT need to wait. You will be notified when the data is ready, at which point "
            "you MUST ask the participant if they'd like you to walk them through the results before sharing anything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific query to send to the external data API.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_slide_details",
        "description": (
            "Retrieve the full rich structured metadata for a SPECIFIC page number. "
            "Use this if you or the user identifies a specific slide (e.g., 'Look at page 3', 'What is on the next slide?'). "
            "Returns structured metrics, visual descriptions, and specific grounding data for that page."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "page_number": {
                    "type": "integer",
                    "description": "The 1-indexed page number to retrieve.",
                }
            },
            "required": ["page_number"],
        },
    },
    {
        "type": "function",
        "name": "send_chat_message",
        "description": (
            "Send a text message into the meeting chat that all participants can see. "
            "Use this to share links, summaries, references, key takeaways, or follow-up items. "
            "For example, when someone asks for a link or reference, or when you want to share a "
            "text summary of data you just discussed. Keep messages concise and professional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The text message to send in the meeting chat (1-4096 chars).",
                },
            },
            "required": ["message"],
        },
    },
]


class RealtimeToolExecutor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def execute(
        self,
        *,
        session_id: str,
        tool_name: str,
        raw_arguments: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        args = _parse_tool_args(raw_arguments)
        if tool_name == "navigate_to_slide":
            return await self._navigate_to_slide(session_id=session_id, args=args)
        if tool_name == "search_and_answer":
            return await self._search_and_answer(session_id=session_id, args=args)
        if tool_name == "leave_call":
            return await self._leave_call(session_id=session_id)
        if tool_name == "mute_self":
            return await self._mute_self(session_id=session_id)
        if tool_name == "unmute_self":
            return await self._unmute_self(session_id=session_id)
        if tool_name == "fetch_external_data":
            return await self._fetch_external_data(session_id=session_id, args=args)
        if tool_name == "get_slide_details":
            return await self._get_slide_details(session_id=session_id, args=args)
        if tool_name == "send_chat_message":
            return await self._send_chat_message(session_id=session_id, args=args)
        raise ValueError(f"Unsupported realtime tool '{tool_name}'")

    async def _fetch_external_data(self, *, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Trigger an asynchronous background search.
        The relay handles the simulation and injection of results.
        """
        query = args.get("query", "")
        logger.info("🔧 [TOOL TRIGGERED] fetch_external_data | Query: %s | Session: %s", query, session_id)

        return {
            "ok": True,
            "action": "async_job_started",
            "query": query,
            "message": "Background job started. Say 'Let me fetch that, it might take a couple of minutes'."
        }

    async def _leave_call(self, *, session_id: str) -> dict[str, Any]:
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")
        recall_bot_id = getattr(sess, "recall_bot_id", None)
        if not recall_bot_id:
            return {"ok": False, "error": "No recall_bot_id on session — cannot leave call."}

        client = RecallClient(self._settings)

        async def _delayed_leave(bot_id: str):
            logger.info("Delaying leave_call for 3 seconds to allow final audio to play... session_id=%s", session_id)
            await asyncio.sleep(3.0)
            try:
                await client.leave_call(bot_id)
                logger.info("leave_call dispatched session_id=%s recall_bot_id=%s", session_id, bot_id)
            except Exception as exc:
                logger.warning("leave_call Recall API error session_id=%s: %s", session_id, exc)

            # Update persistent state to DONE
            try:
                from database import SessionLocal
                from models.bot_session import BotSession as BotSessionModel, BotSessionState
                db = SessionLocal()
                try:
                    db_sess = db.query(BotSessionModel).filter(
                        BotSessionModel.session_id == session_id
                    ).first()
                    if db_sess:
                        db_sess.state = BotSessionState.DONE.value
                        db.commit()
                        logger.info("Bot status set to done session_id=%s", session_id)
                finally:
                    db.close()
            except Exception as exc:
                logger.warning("Failed to update bot status to done session_id=%s: %s", session_id, exc)

        asyncio.create_task(_delayed_leave(recall_bot_id))
        return {"ok": True, "action": "left_call_scheduled"}

    async def _mute_self(self, *, session_id: str) -> dict[str, Any]:
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")
        sess.extra = {**sess.extra, "muted": True}
        logger.info("mute_self: session muted session_id=%s", session_id)
        await ws_manager.broadcast_json(session_id, {"type": "bot_muted"})
        return {"ok": True, "action": "muted"}

    async def _unmute_self(self, *, session_id: str) -> dict[str, Any]:
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")
        sess.extra = {**sess.extra, "muted": False}
        logger.info("unmute_self: session unmuted session_id=%s", session_id)
        await ws_manager.broadcast_json(session_id, {"type": "bot_unmuted"})
        return {"ok": True, "action": "unmuted"}

    async def _navigate_to_slide(self, *, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        t_start = time.monotonic()
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")
        page_raw = args.get("page_number")
        if page_raw is None:
            raise ValueError("Missing required argument: page_number")

        try:
            requested_page = int(page_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("page_number must be an integer") from exc

        total_pages = await rag_retriever.get_total_pages(sess.presentation_id)
        target_page = max(1, min(requested_page, total_pages))

        await ws_manager.broadcast_json(
            session_id,
            {
                "type": "navigate",
                "target_page": target_page,
            },
        )

        # 1. Load slide content (for natural narration)
        slide_content = ""
        slide_title = ""
        try:
            from services import storage as storage_mod
            pages = storage_mod.load_index_pages(sess.presentation_id)
            for page in (pages or []):
                if int(page.get("page_number", 0)) == target_page:
                    slide_content = str(
                        page.get("searchable_content") or page.get("content_text") or ""
                    ).strip()[:1500]
                    slide_title = str(page.get("title") or "")
                    break
        except Exception:
            pass

        # 2. Load rich metadata (for precision grounding)
        rich_metadata = {}
        try:
            all_meta = storage_mod.load_provided_metadata(sess.presentation_id) or {}
            rich_metadata["presentation_context"] = {
                "account": all_meta.get("account_name"),
                "industry": all_meta.get("industry"),
                "glossary": all_meta.get("glossary"),
                "known_contradictions": all_meta.get("known_contradictions"),
            }
            page_list = all_meta.get("pages", [])
            page_data = next((p for p in page_list if int(p.get("page_number", 0)) == target_page), None)
            rich_metadata["page_details"] = page_data or {}
        except Exception:
            pass

        duration_ms = (time.monotonic() - t_start) * 1000
        logger.info(
            "Realtime navigate session_id=%s requested=%s target=%s duration_ms=%.1f",
            session_id, requested_page, target_page, duration_ms,
        )

        return {
            "ok": True,
            "page_number": target_page,
            "slide_title": slide_title,
            "slide_content": slide_content,
            "rich_metadata": rich_metadata,
            "instruction": (
                f"You are now showing '{slide_title}'. "
                f"Narrate 2-3 sentences about this slide using BOTH slide_content AND rich_metadata. "
                f"Prioritize specific metrics, KPIs, and chart descriptions from rich_metadata for maximum accuracy. "
                f"Do NOT mention slide numbers. Keep the presentation moving."
            ),
        }

    async def _search_and_answer(self, *, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        t_start = time.monotonic()
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")

        user_question = str(args.get("user_question") or "").strip()
        search_query = str(args.get("search_query") or user_question).strip()
        if not search_query:
            raise ValueError("search_query or user_question is required")

        # Get brief file paths from session
        brief_file_paths = sess.extra.get("brief_file_paths", [])

        # --- Tier 1 & 2: Parallel Search ---
        # Manifest check (instant, no parallel needed)
        manifest_page = _resolve_from_manifest(user_question, sess.presentation_id)
        if manifest_page is None:
            manifest_page = _resolve_from_manifest(search_query, sess.presentation_id)

        # Start searches in parallel
        slide_task = rag_retriever.search_presentation(
            search_query,
            sess.presentation_id,
            self._settings,
        )
        brief_task = rag_retriever.search_meeting_briefs(
            search_query,
            brief_file_paths,
            self._settings,
            sess.presentation_id,
        )

        slide_hits, brief_hits = await asyncio.gather(slide_task, brief_task)

        # Promotion: If manifest found a strong structural match, promote that page in slide_hits
        if manifest_page is not None and slide_hits:
            for i, hit in enumerate(slide_hits):
                if int(hit.get("page_number") or 0) == manifest_page:
                    slide_hits.insert(0, slide_hits.pop(i))
                    break
            else:
                # Manifest page wasn't in RAG results — override navigation target
                # but keep the original content as fallback or generic answer
                slide_hits[0] = {**slide_hits[0], "page_number": manifest_page, "is_manifest_override": True}

        # --- Tiered Selection (Modified: Hybrid Response) ---
        top_slide = slide_hits[0] if (slide_hits and slide_hits[0].get("score", 0) > 0.7) else None
        top_brief = brief_hits[0] if (brief_hits and brief_hits[0].get("score", 0) > 0.5) else None

        if not top_slide and not top_brief:
            # Priority 3: External Data Fallback
            logger.info("Hybrid search: NO HITS. Triggering Tier 3 (External Data) session_id=%s", session_id)
            return {
                "ok": True,
                "answer_text": "I couldn't find that in the slides or the briefing. I'll search my external advertising database for you.",
                "action": "trigger_external_search",
                "query": search_query,
                "total_ms": (time.monotonic() - t_start) * 1000,
            }

        # 1. Prepare Slide Content if any
        current_page = int(sess.extra.get("current_page") or 1)
        res_navigated = False
        res_target_page = current_page
        slide_info = ""
        if top_slide:
            s_page = int(top_slide.get("page_number") or current_page)
            s_content = str(top_slide.get("searchable_content") or top_slide.get("content_text") or "").strip()
            # Clean and limit
            s_content = " ".join(s_content.split())[:1500]
            slide_info = f"SOURCE: SLIDE {s_page} ({top_slide.get('title', 'Content')})\nCONTENT: {s_content}\n"

            # Decide if we should navigate
            # If slide is stronger than brief, navigate. Else stay.
            if top_slide.get("score", 0) > (top_brief.get("score", 0) if top_brief else 0) and top_slide.get("score", 0) > 1.5:
                res_target_page = s_page
                res_navigated = True

                # Visual Sync: Broadcast the navigation to the UI
                try:
                    from orchestrator.ws_manager import ws_manager
                    # We pass the metadata to the UI so it can render the slide quickly
                    page_metadata = {
                        "title": top_slide.get("title"),
                        "section_label": top_slide.get("section_label"),
                        "content_type": top_slide.get("content_type"),
                        "page_id": top_slide.get("page_id"),
                    }
                    await ws_manager.broadcast_json(
                        session_id,
                        {
                            "type": "navigate",
                            "target_page": res_target_page,
                            "page_metadata": page_metadata,
                        },
                    )
                    # Persist current page in session
                    sess.extra["current_page"] = res_target_page
                except Exception as e:
                    logger.warning("Failed to broadcast navigation sync: %s", e)
            else:
                res_navigated = False
        else:
            res_navigated = False

        # 2. Prepare Briefing Content if any
        brief_info = ""
        if top_brief:
            b_section = top_brief.get("section", "Metrics")
            b_content = top_brief.get("content_text", "").strip()
            brief_info = f"SOURCE: ACCOUNT BRIEFCASE SECTION '{b_section}'\nDATA: {b_content}\n"

        # 3. Rich Metadata Injection (Hybrid)
        rich_metadata = {}
        try:
            from services import storage as storage_mod
            global_meta = storage_mod.load_provided_metadata(sess.presentation_id) or {}

            # Presentation-level context
            rich_metadata["presentation_context"] = {
                "account": global_meta.get("account_name"),
                "industry": global_meta.get("industry"),
                "glossary": global_meta.get("glossary"),
                "known_contradictions": global_meta.get("known_contradictions"),
            }

            # Page-level details if we have a slide
            if top_slide:
                page_meta_raw = top_slide.get("full_metadata_json")
                if page_meta_raw:
                    import json
                    rich_metadata["page_details"] = json.loads(page_meta_raw)
        except Exception:
            pass

        # 4. Assemble and return
        logger.info(
            "Hybrid search DONE session_id=%s slide_hit=%s brief_hit=%s navigated=%s",
            session_id, bool(top_slide), bool(top_brief), res_navigated
        )

        return {
            "ok": True,
            "target_page": res_target_page,
            "navigated": res_navigated,
            "slide_content": slide_info,
            "brief_content": brief_info,
            "rich_metadata": rich_metadata,
            "instruction": (
                "I found relevant info from both the slides and the account briefing. "
                "Synthesize an answer using BOTH slide_content and brief_content. "
                "Trust the brief_content (from the Briefcase) for metrics and the slide_content for visual elements. "
                f"{'Moved to slide ' + str(res_target_page) if res_navigated else 'Staying on current slide'}. "
                "Respond in 2-3 short, natural sentences. Do NOT mention slide numbers."
            ),
            "total_ms": (time.monotonic() - t_start) * 1000,
        }

    async def _get_slide_details(self, *, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """Directly retrieve the metadata for a specific page number from the provided source."""
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")

        page_number = int(args.get("page_number") or 1)

        from services import storage as storage_mod

        # 1. Load the source metadata (the gold standard for rich content)
        all_meta = storage_mod.load_provided_metadata(sess.presentation_id)
        if not all_meta or "pages" not in all_meta:
            return {"ok": False, "error": "No rich metadata found for this presentation."}

        # 2. Find the page (Helix format uses 1-indexed page_number or we can use index)
        pages = all_meta.get("pages", [])
        page_data = next((p for p in pages if int(p.get("page_number", 0)) == page_number), None)

        if not page_data:
            # Fallback: if we can't find by explicit ID, try index if it's within bounds
            if 0 < page_number <= len(pages):
                page_data = pages[page_number - 1]

        if not page_data:
            return {"ok": False, "error": f"Page {page_number} not found."}

        # 3. Assemble response with both the page's rich details and global context
        rich_metadata = {
            "page_details": page_data,
            "presentation_context": {
                "account": all_meta.get("account_name"),
                "industry": all_meta.get("industry"),
                "glossary": all_meta.get("glossary"),
                "known_contradictions": all_meta.get("known_contradictions"),
            }
        }

        return {
            "ok": True,
            "page_number": page_number,
            "title": page_data.get("title") or f"Page {page_number}",
            "slide_content": str(page_data.get("content") or ""),
            "rich_metadata": rich_metadata,
        }

    async def _send_chat_message(self, *, session_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """Send a message into the meeting chat via Recall.ai."""
        sess = await _get_session(session_id)
        if not sess:
            raise ValueError("Session not found")

        message = str(args.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")

        recall_bot_id = getattr(sess, "recall_bot_id", None)
        if not recall_bot_id:
            logger.warning("send_chat_message: no recall_bot_id for session_id=%s", session_id)
            return {"ok": False, "error": "Bot is not connected to a Recall meeting. Cannot send chat."}

        try:
            from services.recall_client import RecallClient
            client = RecallClient(self._settings)
            await client.send_chat_message(recall_bot_id, message)
            logger.info(
                "send_chat_message: sent to meeting session_id=%s recall_bot_id=%s msg=%r",
                session_id, recall_bot_id, message[:80],
            )
            return {
                "ok": True,
                "action": "chat_message_sent",
                "instruction": "The message has been sent to the meeting chat. Briefly confirm to the audience that you sent it.",
            }
        except Exception as exc:
            logger.error("send_chat_message failed: session_id=%s error=%s", session_id, exc)
            return {"ok": False, "error": f"Failed to send chat message: {exc}"}


def _resolve_from_manifest(question: str, presentation_id: str) -> int | None:
    """Return page_number if the question clearly matches a section/title, else None.

    Uses simple word-overlap heuristic — only trusts matches with 2+ significant
    words in common. This catches structural queries like "show me pricing" or
    "go to case studies" without any API call.
    """
    manifest = load_manifest(presentation_id)
    if not manifest:
        return None
    q_lower = question.lower()
    best_page: int | None = None
    best_score = 0

    # Check section labels (e.g. "Pricing", "Case Studies", "Architecture")
    for section in manifest.get("sections", []):
        label = section.get("label", "").lower()
        words = [w for w in label.split() if len(w) > 3]
        score = sum(1 for w in words if w in q_lower)
        if score > best_score:
            best_score = score
            best_page = section["pages"][0]

    # Check individual page titles — must beat section match convincingly
    for page in manifest.get("pages", []):
        title = page.get("title", "").lower()
        words = [w for w in title.split() if len(w) > 3]
        score = sum(1 for w in words if w in q_lower)
        if score > best_score + 1:
            best_score = score
            best_page = page["page_number"]

    # Only trust strong matches (2+ word overlap)
    if best_score >= 2:
        logger.info("Manifest routing: %r → page %s (score=%d)", question[:60], best_page, best_score)
        return best_page
    return None


def _parse_tool_args(raw_arguments: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    text = str(raw_arguments).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Tool arguments are not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must decode to an object")
    return parsed


def _should_navigate_for_content_answer(question: str) -> bool:
    """
    Returns True (navigate) for all content questions.

    The ONLY exception is explicit follow-up phrases where the participant
    wants to stay on the current slide and hear more about it.
    Default is always navigate so the participant sees the slide being discussed.
    """
    low = (question or "").lower()
    # These are the only cases where we intentionally stay on the current slide
    stay_on_current_slide = (
        "tell me more",
        "what else",
        "continue",
        "go on",
        "elaborate",
        "more about this",
        "on this slide",
        "this slide",
        "keep going",
        "and then",
        "walk me through this",
    )
    return not any(marker in low for marker in stay_on_current_slide)
