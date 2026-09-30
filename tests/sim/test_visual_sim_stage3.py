"""Stage 3 — generalized asserts + inert instrumentation check."""

from __future__ import annotations

from sim.dmb.testing.visual_sim.asserts import (
    assert_committed_order_without_active_scaffold,
    assert_unique_body_per_sim_id,
)
from sim.dmb.testing.visual_sim.slices import run_slice_a_combat, run_slice_b_construction


def test_generalized_construction_assert() -> None:
    result = run_slice_b_construction(seed=507)
    assert result["ok"]
    oid = result["committed_order"]["id"]
    assert_committed_order_without_active_scaffold(result["authority"], oid)


def test_generalized_unique_render_bodies() -> None:
    render = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "source": "layers"},
            {"sim_id": "unit:1", "role": "label", "source": "layers"},
            {"sim_id": "unit:1", "role": "body", "source": "overworld"},
        ]
    }
    assert_unique_body_per_sim_id(render, sim_ids=["unit:1"])
    bad = {
        "entities": [
            {"sim_id": "unit:1", "role": "body", "source": "layers"},
            {"sim_id": "unit:1", "role": "body", "source": "layers"},
        ]
    }
    try:
        assert_unique_body_per_sim_id(bad, sim_ids=["unit:1"])
        raise AssertionError("expected duplicate failure")
    except AssertionError as exc:
        assert "duplicate" in str(exc)


def test_slice_a_still_attended() -> None:
    result = run_slice_a_combat(seed=507)
    assert result["attended_ok"]
