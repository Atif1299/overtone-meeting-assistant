from __future__ import annotations

import httpx
import jwt
from fastapi import HTTPException

from app.config import get_settings


def _identity(user_id: str, email: str = "", full_name: str = "") -> dict:
    return {
        "user_id": str(user_id),
        "email": email or "",
        "full_name": full_name or "",
    }


def _identity_from_payload(payload: dict) -> dict:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    metadata = payload.get("user_metadata") or {}
    return _identity(
        sub,
        payload.get("email") or "",
        metadata.get("full_name") or metadata.get("name") or "",
    )


def _identity_from_auth_api(token: str) -> dict:
    settings = get_settings()
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    data = response.json()
    user_id = data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    metadata = data.get("user_metadata") or {}
    return _identity(
        user_id,
        data.get("email") or "",
        metadata.get("full_name") or metadata.get("name") or "",
    )


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as exc:
            if not (settings.supabase_url and settings.supabase_anon_key):
                raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
        else:
            return _identity_from_payload(payload)

    if settings.supabase_url and settings.supabase_anon_key:
        return _identity_from_auth_api(token)

    raise HTTPException(status_code=503, detail="Supabase auth not configured")
