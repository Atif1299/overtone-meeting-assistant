"""Pre-loaded filler audio clips for instant playback during tool execution."""

from __future__ import annotations

import base64
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

_FILLERS_DIR = Path(__file__).resolve().parent.parent / "static" / "fillers"
_cache: list[str] = []  # base64-encoded mp3 data


def _load() -> None:
    """Load all filler mp3 files into memory as base64 strings."""
    if _cache:
        return
    files = sorted(_FILLERS_DIR.glob("filler_*.mp3"))
    for f in files:
        _cache.append(base64.b64encode(f.read_bytes()).decode("ascii"))
    logger.info("Loaded %d filler audio clips from %s", len(_cache), _FILLERS_DIR)


def get_random_filler_b64() -> str | None:
    """Return a random filler clip as a base64-encoded mp3 string."""
    _load()
    if not _cache:
        return None
    return random.choice(_cache)
