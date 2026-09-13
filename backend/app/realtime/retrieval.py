from __future__ import annotations

import re
from typing import Any

SEARCH_THRESHOLD = 0.32
CURRENT_SLIDE_BIAS = 0.05
MATCH_CONTENT_CHARS = 1200

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def query_tokens(query: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((query or "").lower()) if len(t) > 2]


def keyword_score(query: str, text: str) -> float:
    tokens = query_tokens(query)
    if not tokens:
        return 0.0
    hay = (text or "").lower()
    hits = sum(1 for token in tokens if token in hay)
    return hits / len(tokens)


def keyword_hits(pages: list[dict], query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict]] = []
    for page in pages:
        text = page.get("searchable_content") or page.get("content") or ""
        scored.append((keyword_score(query, text), page))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "page_number": page.get("page_number"),
            "title": page.get("title"),
            "searchable_content": page.get("searchable_content") or page.get("content") or "",
            "score": score,
        }
        for score, page in scored[:top_k]
    ]


def choose_hit(
    hits: list[dict],
    current_page: int,
    *,
    threshold: float = SEARCH_THRESHOLD,
    bias: float = CURRENT_SLIDE_BIAS,
) -> dict | None:
    if not hits:
        return None
    current = int(current_page or 0)
    ranked: list[tuple[float, dict]] = []
    for hit in hits:
        score = float(hit.get("score") or 0)
        page = int(hit.get("page_number") or 0)
        if page == current:
            score += bias
        ranked.append((score, hit))
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best = ranked[0]
    if best_score < threshold:
        return None
    return best


def match_payloads(hits: list[dict], limit: int = 3) -> list[dict[str, Any]]:
    matches = []
    for hit in hits[:limit]:
        content = hit.get("searchable_content") or hit.get("content") or ""
        matches.append(
            {
                "page_number": hit.get("page_number"),
                "title": hit.get("title") or "",
                "score": float(hit.get("score") or 0),
                "slide_content": content[:MATCH_CONTENT_CHARS],
            }
        )
    return matches
