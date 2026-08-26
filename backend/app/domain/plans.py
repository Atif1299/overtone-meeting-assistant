from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanLimits:
    launches: int
    uploads: int


PLAN_LIMITS: dict[str, PlanLimits] = {
    "free": PlanLimits(launches=1, uploads=1),
    "starter": PlanLimits(launches=5, uploads=3),
    "pro": PlanLimits(launches=20, uploads=10),
}


def limits_for_plan(plan: str) -> PlanLimits:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
