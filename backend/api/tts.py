from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services import audio_store

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("/{clip_id}.mp3")
async def get_tts_audio(clip_id: str) -> FileResponse:
    path = audio_store.resolve_mp3(clip_id)
    if not path:
        raise HTTPException(status_code=404, detail="Audio clip not found")
    return FileResponse(path, media_type="audio/mpeg")
