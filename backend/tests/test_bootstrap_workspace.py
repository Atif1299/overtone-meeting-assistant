from __future__ import annotations

from app.db import SessionLocal
from app.db.models import Subscription, WorkspaceMember
from app.domain.workspaces import bootstrap_user_workspace


def test_bootstrap_assigns_free_plan():
    db = SessionLocal()
    try:
        user, workspace = bootstrap_user_workspace(
            db,
            user_id="user_trial_bootstrap",
            email="trial@example.com",
            full_name="Trial User",
        )
        membership = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.user_id == user.id, WorkspaceMember.workspace_id == workspace.id)
            .one()
        )
        sub = (
            db.query(Subscription)
            .filter(Subscription.workspace_id == workspace.id)
            .one()
        )
        assert membership.role == "owner"
        assert sub.plan == "free"
        assert sub.status == "active"
        again_user, again_workspace = bootstrap_user_workspace(
            db,
            user_id="user_trial_bootstrap",
            email="trial@example.com",
        )
        assert again_user.id == user.id
        assert again_workspace.id == workspace.id
    finally:
        db.close()
