from __future__ import annotations

import re

_CURRENT_SLIDE_RE = re.compile(
    r"\b("
    r"this slide|this one|this page|current slide|on (?:this|the) slide|"
    r"on screen|what(?:'s| is) (?:that|this)|what does (?:that|this) mean|"
    r"explain (?:this|that)|walk me through this"
    r")\b",
    re.I,
)

_NEXT_RE = re.compile(r"\b(next( slide| page)?|go forward|advance)\b", re.I)
_PREV_RE = re.compile(r"\b((go )?back|previous( slide| page)?|last slide)\b", re.I)
_SLIDE_N_RE = re.compile(r"\b(?:slide|page)\s+(\d+)\b", re.I)


def _text(*parts: str) -> str:
    return " ".join(p for p in parts if p).strip()


def is_current_slide_query(*parts: str) -> bool:
    blob = _text(*parts)
    if not blob:
        return False
    return bool(_CURRENT_SLIDE_RE.search(blob))


def parse_nav_command(*parts: str, current_page: int = 1, total_pages: int | None = None) -> dict | None:
    blob = _text(*parts)
    if not blob:
        return None
    page = int(current_page or 1)
    numbered = _SLIDE_N_RE.search(blob)
    if numbered:
        target = int(numbered.group(1))
        return {"page_number": target, "reason": "numbered_slide"}
    if _NEXT_RE.search(blob):
        target = page + 1
        if total_pages:
            target = min(target, int(total_pages))
        return {"page_number": target, "reason": "next_slide"}
    if _PREV_RE.search(blob):
        return {"page_number": max(1, page - 1), "reason": "previous_slide"}
    return None
