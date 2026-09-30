"""Stage-2 slice journeys + disposable render collector challenge."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.testing.visual_sim.contracts import load_contract
from sim.dmb.testing.visual_sim.oracle import run_oracle
from sim.dmb.testing.visual_sim.slices import run_slice_a_combat, run_slice_b_construction


def test_slice_b_construction_production_journey() -> None:
    contract = load_contract("slice_b_construction.json")
    assert contract["scenario_class"] == "PRODUCTION_JOURNEY"
    result = run_slice_b_construction(seed=507)
    assert result["ok"], result
    assert result["committed_order"]["status"] == "committed"
    auth = result["authority"]
    oracle = run_oracle(contract, authority=auth)
    assert oracle["status"] == "PASS"
    # Scaffold for committed order must not remain as an active order entity.
    oid = result["committed_order"]["id"]
    assert auth["orders"][oid]["status"] == "committed"


def test_slice_a_combat_attended_lease_lifecycle() -> None:
    contract = load_contract("slice_a_combat.json")
    result = run_slice_a_combat(seed=507)
    assert result["strategic_ok"] or result["attended_ok"], result
    # Stage 2 gate: attended required.
    assert result["attended_ok"], {
        "battle_seen": result["battle_seen"],
        "lease_opened": result["lease_opened"],
        "lease_closed": result["lease_closed"],
        "offscreen": result["offscreen_resolved"],
        "counts": result["authority"]["counts"],
    }
    oracle = run_oracle(contract, authority=result["authority"])
    assert oracle["status"] == "PASS"


def test_collector_oracle_on_disposable_render_manifest() -> None:
    """Faults injected into a disposable harvest (not production path)."""
    healthy = {
        "entities": [
            {
                "sim_id": "unit:1",
                "role": "body",
                "visible_in_tree": True,
                "in_viewport": True,
                "grid": [4, 4],
            },
            {
                "sim_id": "order:1",
                "role": "body",
                "sim_kind": "construction",
                "visible_in_tree": True,
                "in_viewport": True,
                "grid": [6, 6],
            },
        ]
    }
    base = {
        "scenario_id": "disp",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 1,
    }
    # Positive
    pos = {
        **base,
        "expectations": {"render": {"require_sim_ids": ["unit:1"], "forbid_sim_ids": ["order:gone"]}},
    }
    assert run_oracle(pos, render=healthy)["status"] == "PASS"

    # Remove
    missing = deepcopy(healthy)
    missing["entities"] = [e for e in missing["entities"] if e["sim_id"] != "unit:1"]
    assert (
        run_oracle({**base, "expectations": {"render": {"require_sim_ids": ["unit:1"]}}}, render=missing)[
            "failures"
        ][0]["code"]
        == "missing_render_entity"
    )

    # Duplicate
    dup = deepcopy(healthy)
    dup["entities"].append(dict(healthy["entities"][0]))
    assert (
        run_oracle({**base, "expectations": {"render": {"require_sim_ids": ["unit:1"]}}}, render=dup)["failures"][
            0
        ]["code"]
        == "duplicate_render_entity"
    )

    # Move
    moved = deepcopy(healthy)
    moved["entities"][0]["grid"] = [99, 99]
    assert (
        run_oracle(
            {**base, "expectations": {"render": {"grid_near": [{"sim_id": "unit:1", "grid": [4, 4], "tol": 0.5}]}}},
            render=moved,
        )["failures"][0]["code"]
        == "wrong_location"
    )

    # Hide
    hidden = deepcopy(healthy)
    hidden["entities"][0]["visible_in_tree"] = False
    assert (
        run_oracle({**base, "expectations": {"render": {"entity_visible": ["unit:1"]}}}, render=hidden)[
            "failures"
        ][0]["code"]
        == "hidden_or_off_viewport"
    )

    # Stale after transition
    stale = deepcopy(healthy)
    assert (
        run_oracle({**base, "expectations": {"render": {"forbid_sim_ids": ["order:1"]}}}, render=stale)[
            "failures"
        ][0]["code"]
        == "stale_render_entity"
    )
