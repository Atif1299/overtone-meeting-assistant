from app.indexing.vision import is_stub_page


def test_stub_gate_detects_slide_n():
    assert is_stub_page({"title": "Slide 4", "content": "", "searchable_content": ""})


def test_stub_gate_allows_real_content():
    assert not is_stub_page(
        {
            "title": "Market Opportunity",
            "content": "Frontier AI spend is expanding across enterprises with clear budget owners.",
            "searchable_content": "Frontier AI spend is expanding across enterprises with clear budget owners.",
        }
    )
