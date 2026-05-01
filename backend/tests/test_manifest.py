from __future__ import annotations

import json
from pathlib import Path

import pytest

from indexer.manifest import build_manifest, load_manifest, save_manifest


SAMPLE_PAGES = [
    {"page_number": 1, "title": "Overtone — Voice AI", "section_label": "Cover", "content_type": "title_slide"},
    {"page_number": 2, "title": "The Problem", "section_label": "Problem Statement", "content_type": "content"},
    {"page_number": 3, "title": "Current Pain Points", "section_label": "Problem Statement", "content_type": "content"},
    {"page_number": 4, "title": "Our Solution", "section_label": "Solution Overview", "content_type": "content"},
    {"page_number": 5, "title": "Architecture Diagram", "section_label": "Architecture", "content_type": "diagram"},
]


def test_build_manifest_structure():
    manifest = build_manifest("pres-001", "deck.pptx", SAMPLE_PAGES)

    assert manifest["presentation_id"] == "pres-001"
    assert manifest["filename"] == "deck.pptx"
    assert manifest["total_pages"] == 5
    assert "indexed_at" in manifest
    assert len(manifest["pages"]) == 5
    assert manifest["pages"][0]["page_number"] == 1
    assert manifest["pages"][0]["title"] == "Overtone — Voice AI"


def test_build_manifest_groups_sections():
    manifest = build_manifest("pres-001", "deck.pptx", SAMPLE_PAGES)

    sections = {s["label"]: s["pages"] for s in manifest["sections"]}
    assert sections["Cover"] == [1]
    assert sections["Problem Statement"] == [2, 3]
    assert sections["Solution Overview"] == [4]
    assert sections["Architecture"] == [5]


def test_save_and_load_manifest_round_trip(tmp_path):
    manifest = build_manifest("pres-abc", "slides.pdf", SAMPLE_PAGES)

    save_manifest("pres-abc", manifest, root=tmp_path)
    loaded = load_manifest("pres-abc", root=tmp_path)

    assert loaded is not None
    assert loaded["presentation_id"] == "pres-abc"
    assert loaded["total_pages"] == 5
    assert loaded["pages"][2]["title"] == "Current Pain Points"


def test_load_manifest_returns_none_when_missing(tmp_path):
    result = load_manifest("nonexistent-id", root=tmp_path)
    assert result is None


def test_save_manifest_creates_parent_dirs(tmp_path):
    manifest = build_manifest("pres-xyz", "x.pdf", SAMPLE_PAGES)
    # Root dir doesn't exist yet — should be created
    nested_root = tmp_path / "nested" / "deeper"
    save_manifest("pres-xyz", manifest, root=nested_root)
    assert (nested_root / "pres-xyz" / "manifest.json").exists()
