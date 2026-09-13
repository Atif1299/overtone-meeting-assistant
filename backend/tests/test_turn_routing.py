from __future__ import annotations

from app.realtime.turn_routing import is_current_slide_query, parse_nav_command


def test_current_slide_query_matches_this_slide():
    assert is_current_slide_query("what is on this slide")
    assert is_current_slide_query("what does that mean")
    assert not is_current_slide_query("what is the pricing model")


def test_parse_nav_next_back_and_numbered():
    assert parse_nav_command("next slide", current_page=4) == {
        "page_number": 5,
        "reason": "next_slide",
    }
    assert parse_nav_command("go back", current_page=4) == {
        "page_number": 3,
        "reason": "previous_slide",
    }
    assert parse_nav_command("jump to slide 9", current_page=1) == {
        "page_number": 9,
        "reason": "numbered_slide",
    }
    assert parse_nav_command("what is churn", current_page=1) is None
