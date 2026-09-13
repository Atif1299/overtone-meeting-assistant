from __future__ import annotations

from app.realtime.retrieval import SEARCH_THRESHOLD, choose_hit, keyword_hits, keyword_score


def test_keyword_score_uses_tokens_not_full_substring():
    text = "Gross margin expanded to 72 percent in Q3"
    assert keyword_score("gross margin Q3", text) == 1.0
    assert keyword_score("unit economics rocket", text) < SEARCH_THRESHOLD


def test_keyword_hits_rank_token_overlap():
    pages = [
        {"page_number": 1, "title": "A", "searchable_content": "welcome agenda"},
        {"page_number": 2, "title": "B", "searchable_content": "pricing starter pro launches"},
        {"page_number": 3, "title": "C", "searchable_content": "team hiring plan"},
    ]
    hits = keyword_hits(pages, "starter pricing", top_k=3)
    assert hits[0]["page_number"] == 2
    assert hits[0]["score"] > hits[1]["score"]


def test_choose_hit_abstains_below_threshold():
    hits = [{"page_number": 2, "score": 0.2, "searchable_content": "weak"}]
    assert choose_hit(hits, current_page=1) is None


def test_choose_hit_prefers_current_slide_within_bias():
    hits = [
        {"page_number": 4, "score": 0.34, "searchable_content": "other"},
        {"page_number": 2, "score": 0.33, "searchable_content": "current"},
    ]
    best = choose_hit(hits, current_page=2)
    assert best is not None
    assert int(best["page_number"]) == 2
