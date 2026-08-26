from __future__ import annotations

import jwt
from fastapi import HTTPException

from app.config import get_settings


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Supabase auth not configured")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    return {
        "user_id": str(sub),
        "email": payload.get("email") or "",
        "full_name": payload.get("user_metadata", {}).get("full_name")
        or payload.get("user_metadata", {}).get("name")
        or "",
    }
