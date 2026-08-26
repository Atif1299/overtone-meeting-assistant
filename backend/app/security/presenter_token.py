from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


def sign_presenter_token(*, session_id: str, presentation_id: str, ttl_hours: int = 24) -> str:
    settings = get_settings()
    secret = settings.presenter_token_secret or settings.supabase_jwt_secret or "dev-presenter-secret"
    now = datetime.now(timezone.utc)
    payload = {
        "typ": "presenter",
        "session_id": session_id,
        "presentation_id": presentation_id,
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_presenter_token(token: str, *, session_id: str, presentation_id: str) -> bool:
    settings = get_settings()
    secret = settings.presenter_token_secret or settings.supabase_jwt_secret or "dev-presenter-secret"
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    if payload.get("typ") != "presenter":
        return False
    return payload.get("session_id") == session_id and payload.get("presentation_id") == presentation_id
