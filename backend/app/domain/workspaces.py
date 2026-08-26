from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import Subscription, User, Workspace, WorkspaceMember


def bootstrap_user_workspace(
    db: Session,
    *,
    user_id: str,
    email: str,
    full_name: str | None = None,
) -> tuple[User, Workspace]:
    user = db.get(User, user_id)
    if not user:
        user = User(id=user_id, email=email, full_name=full_name or "")
        db.add(user)
        db.flush()
    elif full_name and not user.full_name:
        user.full_name = full_name

    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user_id)
        .first()
    )
    if membership:
        workspace = db.get(Workspace, membership.workspace_id)
        if workspace:
            db.commit()
            db.refresh(user)
            return user, workspace

    workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
    workspace = Workspace(
        id=workspace_id,
        name=f"{(full_name or email.split('@')[0]).strip()}'s workspace",
        owner_user_id=user_id,
    )
    db.add(workspace)
    db.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="owner"))
    db.add(
        Subscription(
            workspace_id=workspace_id,
            plan="free",
            status="active",
        )
    )
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace


def get_user_workspace(db: Session, user_id: str) -> Workspace | None:
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user_id)
        .order_by(WorkspaceMember.created_at.asc())
        .first()
    )
    if not membership:
        return None
    return db.get(Workspace, membership.workspace_id)
