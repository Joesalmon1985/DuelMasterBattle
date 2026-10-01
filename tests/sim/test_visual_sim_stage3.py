"""Stage 3 — generalized asserts + inert instrumentation check."""

from __future__ import annotations

from sim.dmb.testing.visual_sim.asserts import (
    assert_committed_order_without_active_scaffold,
    assert_unique_body_per_sim_id,
)
from sim.dmb.testing.visual_sim.oracle import run_oracle
from sim.dmb.testing.visual_sim.slices import run_slice_a_combat, run_slice_b_construction


def test_generalized_construction_assert() -> None:
    result = run_slice_b_construction(seed=507)
    assert result["ok"]
    oid = result["committed_order"]["id"]
    # Sim-only: no Godot render; empty entities means no stale scaffold bodies observed.
    render = {"entities": [], "node_backed_count": 0}
    assert_committed_order_without_active_scaffold(result["authority"], render, oid)


def test_generalized_unique_render_bodies() -> None:
    render = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "node_backed": True, "source": "layers"},
            {"sim_id": "unit:1", "role": "label", "node_backed": True, "source": "layers"},
            {"sim_id": "unit:1", "role": "body", "node_backed": True, "source": "overworld"},
        ]
    }
    # Two distinct body sources for same id → duplicate
    try:
        assert_unique_body_per_sim_id(render, sim_ids=["unit:1"])
        raise AssertionError("expected duplicate failure")
    except AssertionError as exc:
        assert "duplicate" in str(exc)
    ok = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "node_backed": True, "source": "layers"},
            {"sim_id": "unit:1", "role": "label", "node_backed": True, "source": "layers"},
        ]
    }
    assert_unique_body_per_sim_id(ok, sim_ids=["unit:1"])
    bad = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "node_backed": True, "source": "layers"},
            {"sim_id": "unit:1", "role": "body", "node_backed": True, "source": "layers"},
        ]
    }
    try:
        assert_unique_body_per_sim_id(bad, sim_ids=["unit:1"])
        raise AssertionError("expected duplicate failure")
    except AssertionError as exc:
        assert "duplicate" in str(exc)


def test_disabling_duplicate_checker_breaks_negative(monkeypatch) -> None:
    """Disabling the duplicate checker causes the negative assertion itself to fail."""
    import pytest

    import sim.dmb.testing.visual_sim.oracle as oracle_mod

    contract = {
        "scenario_id": "neg_dup_meta",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {"render": {"require_sim_ids": ["unit:1"]}},
    }
    render = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "node_backed": True},
            {"sim_id": "unit:1", "role": "body", "node_backed": True},
        ]
    }
    healthy = run_oracle(contract, render=render)
    assert healthy["status"] == "FAIL"
    assert healthy["failures"][0]["code"] == "duplicate_render_entity"

    def _noop_bodies(_render):
        return {"unit:1": [{"sim_id": "unit:1", "role": "body", "node_backed": True}]}

    monkeypatch.setattr(oracle_mod, "_bodies_by_sim_id", _noop_bodies)
    broken = run_oracle(contract, render=render)

    def _negative_assertion() -> None:
        assert broken["status"] == "FAIL"
        assert broken["failures"][0]["code"] == "duplicate_render_entity"

    with pytest.raises(AssertionError):
        _negative_assertion()


def test_slice_a_still_attended() -> None:
    result = run_slice_a_combat(seed=507)
    assert result["attended_ok"]
