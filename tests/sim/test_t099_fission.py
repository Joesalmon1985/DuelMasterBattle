"""T099 — compact fission pairing and successor ownership."""

from __future__ import annotations

from sim.dmb.ai.diplomacy import DiplomacyService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.eras.fission import (
    FissionDisposition,
    choose_compact_pairing,
    plan_fission,
)
from sim.dmb.world.board import HexBoard


def _four_sites_on_line(board: HexBoard) -> list[dict]:
    """Pick four nodes where one pairing is clearly closest."""
    # Use a hex centre's six corners — adjacent corners are distance 1.
    hid = board.hexes[0]
    corners = list(board.nodes_of_hex(hid))
    assert len(corners) == 6
    # Adjacent pair (0,1) and opposite-ish (3,4) → small within-pair sum.
    # Cross pairing would be larger.
    nodes = [corners[0], corners[1], corners[3], corners[4]]
    return [
        {"settlement_id": f"settlement:{i}", "node_id": nodes[i], "faction_id": "faction:parent"}
        for i in range(4)
    ]


def test_known_distance_fixture_chooses_minimum_pairing() -> None:
    board = HexBoard.radius2()
    sites = _four_sites_on_line(board)
    choice = choose_compact_pairing(sites, board)
    cores = {frozenset(pair["cores"]) for pair in choice["pairing"]}
    expected = {
        frozenset({"settlement:0", "settlement:1"}),
        frozenset({"settlement:2", "settlement:3"}),
    }
    assert cores == expected
    assert choice["within_pair_distance_sum"] == 2  # 1 + 1


def test_tie_is_stable_by_sorted_ids() -> None:
    board = HexBoard.radius2()
    # Four corners of one hex: many pairings may share distance sums of 2+2 or similar.
    hid = board.hexes[len(board.hexes) // 2]
    corners = list(board.nodes_of_hex(hid))
    sites = [
        {"settlement_id": f"settlement:{label}", "node_id": corners[i]}
        for i, label in enumerate(("d", "c", "b", "a"))
    ]
    first = choose_compact_pairing(sites, board)
    second = choose_compact_pairing(list(reversed(sites)), board)
    assert first["pairing"] == second["pairing"]
    assert first["within_pair_distance_sum"] == second["within_pair_distance_sum"]


def test_assignments_cargo_people_diplomacy() -> None:
    wid = WorldId("world:t099")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    sites = _four_sites_on_line(board)
    state.factions["faction:parent"] = {"id": "faction:parent", "status": "active"}
    for site in sites:
        state.settlements[site["settlement_id"]] = {
            **site,
            "tier": "settlement",
            "operational": True,
        }
    # Extra settlement nearer to first pair.
    extra_node = board.adjacent_nodes(sites[0]["node_id"])[0]
    state.settlements["settlement:extra"] = {
        "id": "settlement:extra",
        "faction_id": "faction:parent",
        "node_id": extra_node,
        "tier": "settlement",
        "operational": True,
    }
    state.roads["road:1"] = {
        "id": "road:1",
        "a": sites[0]["node_id"],
        "b": sites[1]["node_id"],
        "faction_id": "faction:parent",
    }
    state.units["unit:1"] = {
        "id": "unit:1",
        "faction_id": "faction:parent",
        "home_settlement_id": "settlement:0",
        "node_id": sites[0]["node_id"],
    }
    state.carts["cart:1"] = {
        "id": "cart:1",
        "owner_faction": "faction:parent",
        "settlement_id": "settlement:2",
        "node_id": sites[2]["node_id"],
        "cargo_lots": [
            {"id": "item:keep", "good_id": "wool", "quantity": 1, "status": "aboard", "namespace": "catan"}
        ],
    }
    state.people["person:1"] = {
        "id": "person:1",
        "faction_id": "faction:parent",
        "settlement_id": "settlement:0",
        "node_id": sites[0]["node_id"],
        "alive": True,
    }
    state.research["faction:parent"] = {
        "owned": {"tech:1": {"id": "tech:1", "definition_id": "tech.prehistoric.primary_flow"}},
        "active_stacks": {},
        "inactive_archive": {},
        "activated_definition_ids": ["tech.prehistoric.primary_flow"],
        "acquisition_receipts": [],
        "activation_receipts": [],
    }

    plan = plan_fission(
        state,
        parent_faction_id="faction:parent",
        successor_faction_ids=["faction:succ:a", "faction:succ:b"],
        split=True,
    )
    # Every parent asset assigned exactly once.
    assert set(plan["settlement_assignments"]) == {
        "settlement:0",
        "settlement:1",
        "settlement:2",
        "settlement:3",
        "settlement:extra",
    }
    assert len(plan["settlement_assignments"]) == len(set(plan["settlement_assignments"]))
    assert plan["unit_assignments"]["unit:1"] == plan["settlement_assignments"]["settlement:0"]
    assert plan["cart_assignments"]["cart:1"] == plan["settlement_assignments"]["settlement:2"]

    before_cargo = [dict(lot) for lot in state.carts["cart:1"]["cargo_lots"]]
    before_people = set(state.people)
    result = FissionDisposition(state).apply(plan, transition_id="fx")
    assert result["idempotent"] is False
    assert state.carts["cart:1"]["cargo_lots"] == before_cargo
    assert set(state.people) == before_people
    assert state.people["person:1"]["id"] == "person:1"
    assert state.people["person:1"]["faction_id"] == plan["person_assignments"]["person:1"]
    dip = DiplomacyService(state)
    assert dip.trade_permitted("faction:succ:a", "faction:succ:b") is True
    assert dip.relation("faction:succ:a", "faction:succ:b") == "neutral"
    assert "faction:succ:a" in state.research
    assert state.research["faction:succ:a"]["activated_definition_ids"] == [
        "tech.prehistoric.primary_flow"
    ]
    # Second apply is idempotent.
    again = FissionDisposition(state).apply(plan, transition_id="fx")
    assert again["idempotent"] is True
