import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

def load_and_dedupe_brief_sections(file_paths: list[str]) -> dict[str, Any]:
    """Load multiple JSON brief files and deduplicate by section key."""
    merged: dict[str, Any] = {}
    for path in file_paths:
        try:
            if not os.path.exists(path):
                continue
            with open(path, "r") as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                logger.warning("Brief file %s is not a JSON object", path)
                continue

            for key, val in data.items():
                if val is not None:
                    # Deduplicate: latest file wins for overlap
                    merged[key] = val
        except Exception as e:
            logger.warning("Failed to load brief file %s: %s", path, e)
    return merged

MAX_CHUNK_CHARS = 4000

def convert_sections_to_chunks(sections: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert parsed sections into searchable chunks with size safety."""
    chunks = []
    for section_name, content in sections.items():
        _chunk_recursive(section_name, content, chunks)
    return chunks

def _chunk_recursive(name: str, data: Any, results: list[dict[str, Any]]):
    """Recursively split data until it fits within MAX_CHUNK_CHARS."""
    # Build text representation with a header for better keyword matching
    raw_text = json.dumps(data, indent=None) if not isinstance(data, str) else data
    header = f"SECTION: {name}\n"
    text = header + raw_text
    
    # If it fits, we are done
    if len(text) < MAX_CHUNK_CHARS:
        results.append({
            "section": name,
            "content_text": text
        })
        return

    # If too big, try to split
    if isinstance(data, list) and len(data) > 1:
        for i, item in enumerate(data):
            _chunk_recursive(f"{name} > item_{i}", item, results)
    elif isinstance(data, dict) and len(data) > 1:
        for key, val in data.items():
            # Keep the hierarchical path in the name
            _chunk_recursive(f"{name} > {key}", val, results)
    else:
        # Fallback for massive strings or single-element lists/dicts that are still too big
        for i in range(0, len(text), MAX_CHUNK_CHARS):
            results.append({
                "section": name,
                "content_text": text[i : i + MAX_CHUNK_CHARS]
            })
