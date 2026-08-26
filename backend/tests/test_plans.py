from __future__ import annotations

from app.domain.plans import limits_for_plan


def test_plan_limits():
    free = limits_for_plan("free")
    assert free.launches == 1
    assert free.uploads == 1
    starter = limits_for_plan("starter")
    assert starter.launches == 5
    assert starter.uploads == 3
    pro = limits_for_plan("pro")
    assert pro.launches == 20
    assert pro.uploads == 10
