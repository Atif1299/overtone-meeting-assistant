from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from config import Settings, get_settings
from orchestrator import rag_retriever


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate_to_slide",
            "description": "Navigate to a specific slide number (1-indexed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["page_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_answer",
            "description": "Search deck and answer using RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_query": {"type": "string"},
                    "user_question": {"type": "string"},
                },
                "required": ["search_query", "user_question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_external_data",
            "description": "Fetch data NOT in the deck (e.g. historical performance, external stats).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slide_details",
            "description": "Fetch raw structured metadata for a specific page number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                },
                "required": ["page_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ignore_utterance",
            "description": "No presentation action needed.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]


class NavigationDecision:
    def __init__(
        self,
        *,
        navigate_to: int | None = None,
        answer_text: str | None = None,
        ignore: bool = False,
        page_metadata: dict[str, Any] | None = None,
        tool_call: dict[str, Any] | None = None,
    ) -> None:
        self.navigate_to = navigate_to
        self.answer_text = answer_text
        self.ignore = ignore
        self.page_metadata = page_metadata
        self.tool_call = tool_call


def _format_manifest_context(manifest: dict | None) -> str:
    if not manifest:
        return ""
    sections = manifest.get("sections", [])
    pages = manifest.get("pages", [])
    total = manifest.get("total_pages", 0)

    sections_str = "\n".join(
        f"Slides {s['pages'][0]}-{s['pages'][-1]}: {s['label']}"
        if len(s["pages"]) > 1
        else f"Slide {s['pages'][0]}: {s['label']}"
        for s in sections
    )
    pages_str = "\n".join(
        f"Page {p['page_number']}: \"{p['title']}\""
        for p in pages
    )

    return (
        f"\n\nPRESENTATION STRUCTURE ({total} slides):\n"
        f"{sections_str}\n\n"
        f"PAGE TITLES:\n{pages_str}\n"
    )


async def decide(
    utterance: str,
    presentation_id: str,
    *,
    current_page: int = 1,
    agent_system_prompt: str | None = None,
    settings: Settings | None = None,
) -> NavigationDecision:
    settings = settings or get_settings()
    if settings.openai_api_key:
        return await _openai_decide(
            utterance,
            presentation_id,
            current_page=current_page,
            settings=settings,
            agent_system_prompt=agent_system_prompt,
        )
    return _heuristic_decide(utterance, presentation_id)


def _heuristic_decide(utterance: str, presentation_id: str) -> NavigationDecision:
    low = utterance.lower()
    m = re.search(r"\b(?:slide|page)\s*(\d+)\b", low)
    if m:
        return NavigationDecision(navigate_to=int(m.group(1)))
    m2 = re.search(r"\bgo to\s+(\d+)\b", low)
    if m2:
        return NavigationDecision(navigate_to=int(m2.group(1)))
    if "next" in low and "slide" in low:
        return NavigationDecision(answer_text="Say 'go to slide N' for a specific slide.")
    if "?" in utterance or any(w in low for w in ("what", "why", "how", "explain", "tell me")):
        return NavigationDecision(
            answer_text="Configure OPENAI_API_KEY and Azure AI Search for full Q&A."
        )
    return NavigationDecision(ignore=True)


async def _openai_decide(
    utterance: str,
    presentation_id: str,
    settings: Settings,
    *,
    current_page: int = 1,
    agent_system_prompt: str | None = None,
) -> NavigationDecision:
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Load manifest for section/page context
    from indexer.manifest import load_manifest
    manifest = load_manifest(presentation_id)
    manifest_context = _format_manifest_context(manifest)

    ctx: list[dict] = []
    if _looks_like_content_question(utterance):
        ctx = await rag_retriever.search_presentation(utterance, presentation_id, settings)
    ctx_str = json.dumps(ctx[:3], indent=2) if ctx else "[]"

    prompt_prefix = (agent_system_prompt or "").strip()
    if prompt_prefix:
        prompt_prefix = f"{prompt_prefix}\n\n"

    messages = [
        {
            "role": "system",
            "content": (
                f"{prompt_prefix}"
                "You are Overtone, a live voice assistant and presentation guide. \n\n"
                f"CURRENT CONTEXT: You are currently on Slide {current_page}.\n"
                "CORE INTERACTION RULES:\n"
                "• For content questions about the presentation, use search_and_answer.\n"
                "• For questions about visual details on the current slide, use get_slide_details.\n"
                "• For news, current events, or any topic clearly NOT in the deck, use fetch_external_data immediately.\n\n"
                "TOOL USAGE:\n"
                "• You have access to: navigate_to_slide, search_and_answer, get_slide_details, fetch_external_data, and ignore_utterance.\n"
                "• If the user asks about 'this page', 'here', or current metrics, use get_slide_details for Page {current_page}.\n"
                "• Use search_and_answer if the user is asking about the slides generally.\n"
                "• Use fetch_external_data if the user is asking for external information, context, or data not found in the deck.\n\n"
                f"{manifest_context}"
                f"RAG context (may be empty): {ctx_str}"
            ),
        },
        {"role": "user", "content": utterance},
    ]

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return NavigationDecision(answer_text=msg.content or "")

    args0: dict[str, Any] = {}
    name = ""
    for tc in msg.tool_calls:
        name = tc.function.name
        try:
            args0 = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args0 = {}
        break

    if name == "navigate_to_slide":
        n = int(args0.get("page_number", 1))
        return NavigationDecision(navigate_to=n)

    if name == "fetch_external_data":
        # Pass through the tool call to the relay
        return NavigationDecision(tool_call={"name": name, "arguments": args0})

    if name == "get_slide_details":
        return NavigationDecision(tool_call={"name": name, "arguments": args0})

    if name == "search_and_answer":
        q = args0.get("user_question") or utterance
        search_query = (args0.get("search_query") or q).strip()
        if search_query.lower() == utterance.strip().lower() and ctx:
            hits = ctx
        else:
            hits = await rag_retriever.search_presentation(search_query, presentation_id, settings)

        if hits:
            h = hits[0]
            answer_source = (
                h.get("parent_content_text")
                or h.get("searchable_content")
                or h.get("content_text", "")
            )
            ans = (
                f"From slide {h.get('page_number')}: "
                f"{h.get('title', '')} — {str(answer_source)[:400]}"
            )
            # Always navigate to the relevant slide when answering a content question.
            # Only skip navigation for explicit follow-up phrases about the current slide.
            should_navigate = _should_navigate_for_content_answer(q)
            page_metadata = {
                "title": h.get("title"),
                "section_label": h.get("section_label"),
                "content_type": h.get("content_type"),
                "has_table": h.get("has_table", False),
                "has_chart": h.get("has_chart", False),
                "has_diagram": h.get("has_diagram", False),
                "page_id": h.get("page_id"),
            }
            return NavigationDecision(
                navigate_to=h.get("page_number") if should_navigate else None,
                answer_text=ans,
                page_metadata=page_metadata,
            )
        return NavigationDecision(
            answer_text="I could not find relevant content in the indexed presentation."
        )

    return NavigationDecision(ignore=True)


def _looks_like_content_question(utterance: str) -> bool:
    low = utterance.lower()
    keywords = ("what", "why", "how", "explain", "summarize", "summary", "tell me", "describe")
    return "?" in utterance or any(word in low for word in keywords)


def _should_navigate_for_content_answer(utterance: str) -> bool:
    """
    Returns True (navigate) for all content questions.

    Only returns False for explicit follow-up phrases where the participant
    wants to stay on the current slide. Default is always navigate.
    """
    low = (utterance or "").lower()
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
        "walk me through this",
    )
    return not any(marker in low for marker in stay_on_current_slide)
