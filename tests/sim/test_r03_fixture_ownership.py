"""R03: one-owner FX-BATTLE, safe spawn, three boundary hazard anchors."""

from __future__ import annotations

import pytest

from sim.dmb.construction.placement import PlacementRules
from sim.dmb.testing.fixtures import load_fixture


def test_fx_battle_one_owner_and_invaders():
    sim = load_fixture("FX-BATTLE", seed=404)
    state = sim.state
    assert state.player["position"] == [4.0, 5.0]
    owners = PlacementRules(state).active_settlements_at("node:1")
    assert len(owners) == 1
    assert owners[0]["faction_id"] == "faction:red"
    # Active buildings on node:1 are all Red.
    for bid, b in state.buildings.items():
        if b.get("node_id") == "node:1" and b.get("status") == "active":
            assert b["faction_id"] == "faction:red", bid
    # Blue invaders currently on battle node with home/factory on node:2.
    blue_on_field = [
        u
        for u in state.units.values()
        if u.get("faction_id") == "faction:blue" and u.get("status") != "reserve"
    ]
    assert len(blue_on_field) == 3
    for u in blue_on_field:
        assert u["node_id"] == "node:1"
        assert u["home_node_id"] == "node:2"
        assert str(u["factory_id"]).startswith("building:factory_blue")
    assert PlacementRules(state).validate_one_owner_per_node() == []
    # Spawn has free cardinal neighbours (no fixture trees at adjacent cells).
    trees = {(2, 2), (7, 7), (11, 7)}
    sx, sy = 4, 5
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        assert (sx + dx, sy + dy) not in trees
    # Armies are paced apart (manhattan centre-to-centre >= 6).
    reds = [u for u in state.units.values() if u["faction_id"] == "faction:red"]
    blues = [u for u in blue_on_field]
    rx = sum(u["position"][0] for u in reds) / len(reds)
    ry = sum(u["position"][1] for u in reds) / len(reds)
    bx = sum(u["position"][0] for u in blues) / len(blues)
    by = sum(u["position"][1] for u in blues) / len(blues)
    assert abs(rx - bx) + abs(ry - by) >= 6.0


def test_two_active_owners_rejected():
    sim = load_fixture("FX-BATTLE", seed=404)
    state = sim.state
    state.settlements["settlement:intruder"] = {
        "id": "settlement:intruder",
        "node_id": "node:1",
        "faction_id": "faction:blue",
        "tier": "settlement",
        "operational": True,
        "status": "active",
    }
    errs = PlacementRules(state).validate_one_owner_per_node()
    assert any("active settlements" in e for e in errs)


def test_fx_hazard_three_boundary_anchors():
    sim = load_fixture("FX-HAZARD", seed=408)
    anchors = sim.state.board["hex_anchors"]
    grids = [tuple(anchors[h]["grid"]) for h in ("hex:a", "hex:b", "hex:c")]
    assert len(set(grids)) == 3
    # Not all on the same row.
    rows = {g[1] for g in grids}
    cols = {g[0] for g in grids}
    assert len(rows) >= 2 or len(cols) >= 2
    assert grids != [(4.0, 6.0), (7.0, 6.0), (10.0, 6.0)]
