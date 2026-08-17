from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import get_db
from models.api_key import ApiKey

OPERATOR_CUSTOMER_ID = "operator"
OPERATOR_CUSTOMER_NAME = "Operator"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix) :].strip()
    return None


def _operator_key(provided: str | None) -> ApiKey:
    return ApiKey(
        key=provided or "operator",
        customer_id=OPERATOR_CUSTOMER_ID,
        customer_name=OPERATOR_CUSTOMER_NAME,
        is_active=True,
    )


async def require_customer_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiKey:
    """
    Customer API auth gate.

    Accepts a row from the api_keys table, or the configured ADMIN_API_KEY
    (dashboard operator). If ADMIN_API_KEY is unset, unauthenticated local
    access is allowed — same open-dev behavior as require_admin_key.
    """
    provided = x_api_key or api_key or _extract_bearer_token(authorization)
    admin_key = (settings.admin_api_key or "").strip()

    if admin_key and provided == admin_key:
        return _operator_key(provided)

    if provided:
        api_key_record = (
            db.query(ApiKey)
            .filter(ApiKey.key == provided, ApiKey.is_active == True)
            .first()
        )
        if api_key_record:
            return api_key_record
        raise HTTPException(401, "Invalid API key")

    if not admin_key:
        return _operator_key(None)

    raise HTTPException(401, "API key missing")


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
    required_key = (settings.admin_api_key or "").strip()
    if not required_key:
        return

    provided = x_api_key or _extract_bearer_token(authorization)
    if provided != required_key:
        raise HTTPException(401, "Admin API key missing or invalid")
