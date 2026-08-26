from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Subscription, UsageCounter
from app.domain.plans import limits_for_plan


def _period_month(now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    return ts.strftime("%Y-%m")


def get_active_plan(db: Session, workspace_id: str) -> str:
    sub = (
        db.query(Subscription)
        .filter(Subscription.workspace_id == workspace_id, Subscription.status.in_(["active", "trialing"]))
        .order_by(Subscription.updated_at.desc())
        .first()
    )
    if sub and sub.plan:
        return sub.plan
    return "free"


def get_usage(db: Session, workspace_id: str, metric: str) -> int:
    period = _period_month()
    row = (
        db.query(UsageCounter)
        .filter(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.metric == metric,
            UsageCounter.period_month == period,
        )
        .first()
    )
    return row.count if row else 0


def usage_snapshot(db: Session, workspace_id: str) -> dict:
    plan = get_active_plan(db, workspace_id)
    limits = limits_for_plan(plan)
    launches = get_usage(db, workspace_id, "launches")
    uploads = get_usage(db, workspace_id, "uploads")
    return {
        "plan": plan,
        "period_month": _period_month(),
        "launches": {"used": launches, "limit": limits.launches},
        "uploads": {"used": uploads, "limit": limits.uploads},
    }


def check_quota(db: Session, workspace_id: str, metric: str) -> None:
    plan = get_active_plan(db, workspace_id)
    limits = limits_for_plan(plan)
    limit = limits.launches if metric == "launches" else limits.uploads
    used = get_usage(db, workspace_id, metric)
    if used >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "message": f"Monthly {metric} limit reached for {plan} plan ({limit}). Upgrade to continue.",
                "plan": plan,
                "metric": metric,
                "used": used,
                "limit": limit,
            },
        )


def increment_usage(db: Session, workspace_id: str, metric: str) -> None:
    period = _period_month()
    row = (
        db.query(UsageCounter)
        .filter(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.metric == metric,
            UsageCounter.period_month == period,
        )
        .first()
    )
    if row:
        row.count += 1
    else:
        db.add(
            UsageCounter(
                workspace_id=workspace_id,
                metric=metric,
                period_month=period,
                count=1,
            )
        )
    db.commit()
