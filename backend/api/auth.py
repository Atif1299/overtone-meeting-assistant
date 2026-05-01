from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import get_db
from models.api_key import ApiKey


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix) :].strip()
    return None


async def require_customer_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiKey:
    """
    Customer API auth gate:
    Checks the provided API key against the api_keys table in the database.
    Allows passing key via X-API-Key header, Authorization header, or api_key query param.
    """
    provided = x_api_key or api_key or _extract_bearer_token(authorization)
    if not provided:
        raise HTTPException(401, "API key missing")

    api_key_record = (
        db.query(ApiKey)
        .filter(ApiKey.key == provided, ApiKey.is_active == True)
        .first()
    )
    if not api_key_record:
        print(f"[auth] Invalid or inactive key provided: {provided!r}")
        raise HTTPException(401, "Invalid API key")

    print(f"[auth] Customer {api_key_record.customer_name!r} validated")
    return api_key_record


async def require_admin_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """
    Optional admin auth gate:
    - If ADMIN_API_KEY is unset, routes remain open for local development.
    - If ADMIN_API_KEY is set, callers must pass either:
      - X-API-Key: <key>
      - Authorization: Bearer <key>
    """
    # Debug prints for local testing
    print(f"[auth] settings.admin_api_key(raw)={settings.admin_api_key!r}")
    required_key = settings.admin_api_key.strip()
    if not required_key:
        print("[auth] Admin API key not configured - allowing open access")
        return

    provided = x_api_key or _extract_bearer_token(authorization)
    print(
        f"[auth] provided admin x_api_key={x_api_key!r} authorization={authorization!r} extracted={provided!r}"
    )
    if provided != required_key:
        print("[auth] Admin API key missing or invalid")
        raise HTTPException(401, "Admin API key missing or invalid")
    print("[auth] Admin API key validated")
