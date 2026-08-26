from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import ApiKey, Subscription, Workspace, WorkspaceMember


def migrate_legacy_customers(db: Session) -> None:
    """Map v2_api_keys.customer_id values to v2_workspaces for existing data."""
    keys = db.query(ApiKey).filter(ApiKey.is_active.is_(True)).all()
    for key in keys:
        if key.customer_id == "operator":
            continue
        workspace = db.get(Workspace, key.customer_id)
        if not workspace:
            db.add(
                Workspace(
                    id=key.customer_id,
                    name=key.customer_name or key.customer_id,
                    owner_user_id=f"legacy_{key.customer_id}",
                )
            )
            db.add(
                WorkspaceMember(
                    workspace_id=key.customer_id,
                    user_id=f"legacy_{key.customer_id}",
                    role="owner",
                )
            )
            db.add(
                Subscription(
                    workspace_id=key.customer_id,
                    plan="free",
                    status="active",
                )
            )
    db.commit()


def ensure_default_workspace(db: Session) -> str:
    """Create a default workspace for orphan presentations without customer_id."""
    default_id = "ws_default_legacy"
    if not db.get(Workspace, default_id):
        db.add(
            Workspace(
                id=default_id,
                name="Legacy default workspace",
                owner_user_id="legacy_system",
            )
        )
        db.add(
            WorkspaceMember(
                workspace_id=default_id,
                user_id="legacy_system",
                role="owner",
            )
        )
        db.add(
            Subscription(
                workspace_id=default_id,
                plan="free",
                status="active",
            )
        )
        db.commit()
    return default_id
