"""Build, save, and load the presentation manifest (sections + page titles)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_manifest(
    presentation_id: str,
    filename: str,
    page_metadata_list: list[dict[str, Any]],
) -> dict:
    """
    Build a manifest dict from per-page metadata.

    Sections are built by grouping consecutive pages that share the same
    section_label. Non-consecutive occurrences of the same label become
    separate section entries.
    """
    pages = []
    sections: list[dict] = []
    current_label: str | None = None

    for meta in page_metadata_list:
        page_num = meta.get("page_number", len(pages) + 1)
        section_label = str(meta.get("section_label") or "Content")
        content_type = str(meta.get("content_type") or "content")
        title = str(meta.get("title") or f"Page {page_num}")

        pages.append(
            {
                "page_number": page_num,
                "title": title,
                "section_label": section_label,
                "content_type": content_type,
            }
        )

        if section_label != current_label:
            sections.append({"label": section_label, "pages": [page_num]})
            current_label = section_label
        else:
            sections[-1]["pages"].append(page_num)

    return {
        "presentation_id": presentation_id,
        "filename": filename,
        "total_pages": len(page_metadata_list),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "pages": pages,
    }


def _manifest_path(presentation_id: str, root: Path) -> Path:
    return root / presentation_id / "manifest.json"


def save_manifest(
    presentation_id: str,
    manifest: dict,
    root: Path | None = None,
) -> None:
    if root is None:
        from services.storage import presentations_root
        root = presentations_root()
    path = _manifest_path(presentation_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def load_manifest(
    presentation_id: str,
    root: Path | None = None,
) -> dict | None:
    if root is None:
        from services.storage import presentations_root
        root = presentations_root()
    path = _manifest_path(presentation_id, root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
