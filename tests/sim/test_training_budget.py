"""ComputeBudget target-met accounting."""

from __future__ import annotations

from training.budget import ComputeBudget


def test_reaching_decision_target_is_complete_not_incomplete() -> None:
    budget = ComputeBudget(max_seconds=3600, max_decisions=100, label="imitation")
    for _ in range(100):
        budget.note_decision()
    snap = budget.snapshot()
    assert snap["stopped_reason"] == "max_decisions"
    assert snap["decisions"] == 100
    assert snap["complete"] is True
    assert snap["incomplete_batch"] is False


def test_time_budget_before_target_is_incomplete() -> None:
    budget = ComputeBudget(max_seconds=0.0, max_decisions=1000, label="imitation")
    budget.note_decision(10)
    assert budget.exhausted()
    snap = budget.snapshot()
    assert snap["stopped_reason"] == "max_seconds"
    assert snap["complete"] is False
    assert snap["incomplete_batch"] is True


def test_premature_mark_before_target() -> None:
    budget = ComputeBudget(max_seconds=3600, max_decisions=500, label="imitation")
    budget.note_decision(50)
    budget.mark_premature("environment_error")
    snap = budget.snapshot()
    assert snap["complete"] is False
    assert snap["incomplete_batch"] is True
