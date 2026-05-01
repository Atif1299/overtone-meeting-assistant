from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


_DEFAULT_AUDIO_ROOT = Path(__file__).resolve().parent.parent / "generated_audio"
_AUDIO_ROOT = Path(
    os.getenv("GENERATED_AUDIO_ROOT", str(_DEFAULT_AUDIO_ROOT))
).expanduser()
_CLIP_ID_RE = re.compile(r"^[a-f0-9-]{8,64}$")


def audio_root() -> Path:
    _AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    return _AUDIO_ROOT


def save_mp3(content: bytes) -> str:
    clip_id = str(uuid.uuid4())
    path = audio_root() / f"{clip_id}.mp3"
    path.write_bytes(content)
    return clip_id


def resolve_mp3(clip_id: str) -> Path | None:
    if not _CLIP_ID_RE.fullmatch(clip_id):
        return None
    path = audio_root() / f"{clip_id}.mp3"
    if not path.is_file():
        return None
    return path
