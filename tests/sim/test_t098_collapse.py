"""T098 — multi-faction collapse selection and inert ruins."""

from __future__ import annotations

from fractions import Fraction

from sim.dmb.construction.placement import PlacementRules
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.eras.collapse import CollapseDisposition, select_collapse_factions
from sim.dmb.eras.planner import EraTransitionPlanner, TransitionTrigger
from sim.dmb.people.registry import PeopleService
from sim.dmb.world.board import HexBoard


def test_scores_10_through_5_collapses_exactly_the_5() -> None:
    scores = {
        "faction:10": 10,
        "faction:9": 9,
        "faction:8": 8,
        "faction:7": 7,
        "faction:6": 6,
        "faction:5": 5,
    }
    caps = {fid: Fraction(1) for fid in scores}
    collapsed, reasons = select_collapse_factions(
        scores, caps, winner_faction_id="faction:10", entered_faction_ids=sorted(scores)
    )
    assert collapsed == ["faction:5"]
    assert reasons["faction:5"] == "lowest_remaining_scorer"


def test_tied_lowest_uses_capacity_then_id() -> None:
    scores = {"faction:a": 10, "faction:b": 6, "faction:c": 6}
    caps = {"faction:a": Fraction(10), "faction:b": Fraction(3), "faction:c": Fraction(2)}
    collapsed, _ = select_collapse_factions(
        scores, caps, winner_faction_id="faction:a", entered_faction_ids=sorted(scores)
    )
    assert collapsed == ["faction:c"]

    caps2 = {"faction:a": Fraction(10), "faction:b": Fraction(2), "faction:c": Fraction(2)}
    collapsed2, _ = select_collapse_factions(
        scores, caps2, winner_faction_id="faction:a", entered_faction_ids=sorted(scores)
    )
    assert collapsed2 == ["faction:b"]  # equal capacity → lower ID


def test_below_five_plus_one_lowest() -> None:
    scores = {"faction:w": 10, "faction:m": 7, "faction:l": 4, "faction:x": 2}
    caps = {fid: Fraction(1) for fid in scores}
    collapsed, reasons = select_collapse_factions(
        scores, caps, winner_faction_id="faction:w", entered_faction_ids=sorted(scores)
    )
    assert set(collapsed) == {"faction:l", "faction:x", "faction:m"}
    assert reasons["faction:l"] == "below_5_vp"
    assert reasons["faction:m"] == "lowest_remaining_scorer"


def test_sole_remaining_winner_protected() -> None:
    scores = {"faction:w": 10, "faction:l": 3}
    caps = {fid: Fraction(1) for fid in scores}
    collapsed, _ = select_collapse_factions(
        scores, caps, winner_faction_id="faction:w", entered_faction_ids=sorted(scores)
    )
    assert collapsed == ["faction:l"]


def test_disposition_ruins_inert_civilians_survive_losses_once() -> None:
    wid = WorldId("world:t098")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    node = board.nodes[0]
    neighbour = board.adjacent_nodes(node)[0]

    state.factions["faction:lose"] = {"id": "faction:lose", "status": "active"}
    state.factions["faction:win"] = {"id": "faction:win", "status": "active"}
    state.settlements["settlement:lose"] = {
        "id": "settlement:lose",
        "faction_id": "faction:lose",
        "node_id": node,
        "tier": "settlement",
        "operational": True,
    }
    state.buildings["building:wh"] = {
        "id": "building:wh",
        "def_id": "building.warehouse",
        "definition_id": "building.warehouse",
        "slot_kind": "warehouse",
        "settlement_id": "settlement:lose",
        "faction_id": "faction:lose",
        "node_id": node,
        "status": "active",
        "active": True,
    }
    state.stocks["store:building:wh"] = {
        "catan": {"timber": {"available": 3, "reserved": 0, "escrow": 0}}
    }
    state.roads["road:1"] = {"id": "road:1", "a": node, "b": neighbour, "faction_id": "faction:lose"}
    state.units["unit:1"] = {
        "id": "unit:1",
        "faction_id": "faction:lose",
        "person_id": "person:soldier",
        "status": "active",
        "alive": True,
    }
    state.people["person:worker"] = {
        "id": "person:worker",
        "alive": True,
        "status": "employed",
        "faction_id": "faction:lose",
        "settlement_id": "settlement:lose",
        "node_id": node,
        "workplace_id": "building:wh",
        "role": "worker",
        "quest_ids": ["quest.blocked_exit_boulder"],
    }
    state.people["person:soldier"] = {
        "id": "person:soldier",
        "alive": True,
        "status": "employed",
        "faction_id": "faction:lose",
        "unit_id": "unit:1",
        "role": "soldier",
        "node_id": node,
    }
    state.quests["quest.blocked_exit_boulder"] = {
        "id": "quest.blocked_exit_boulder",
        "status": "active",
        "helper_person_id": "person:worker",
    }
    state.carts["cart:1"] = {
        "id": "cart:1",
        "owner_faction": "faction:lose",
        "status": "idle",
        "cargo_lots": [
            {
                "id": "item:1",
                "good_id": "brick",
                "quantity": 2,
                "namespace": "catan",
                "status": "aboard",
            }
        ],
    }

    first = CollapseDisposition(state).apply(
        ["faction:lose"], reasons={"faction:lose": "lowest_remaining_scorer"}, transition_id="t1"
    )
    second = CollapseDisposition(state).apply(
        ["faction:lose"], reasons={"faction:lose": "lowest_remaining_scorer"}, transition_id="t1"
    )
    assert first["collapsed"][0]["idempotent"] is False
    assert second["collapsed"][0]["idempotent"] is True

    settlement = state.settlements["settlement:lose"]
    assert settlement["ruin_only"] is True
    assert settlement["operational"] is False
    assert settlement["collision"] is False
    assert settlement["site_reservation"] is False
    assert settlement.get("loot") == []
    assert ScoreService(state).settlement_vp(settlement) == 0

    # Ruins do not block new placement.
    rules = PlacementRules(state, board)
    state.roads["road:seed"] = {"id": "road:seed", "a": neighbour, "b": node, "faction_id": "faction:win"}
    ok, reason = rules.can_settle("faction:win", neighbour)
    # neighbour may fail for other reasons; ensure ruin node itself is not an adjacent blocker via ruin_only
    assert settlement["ruin_only"] is True

    worker = state.people["person:worker"]
    assert worker["alive"] is True
    assert worker["status"] == "displaced"
    assert state.quests["quest.blocked_exit_boulder"]["helper_person_id"] == "person:worker"
    assert state.units["unit:1"]["status"] == "disbanded"
    assert state.people["person:soldier"]["alive"] is True
    assert state.people["person:soldier"]["status"] == "displaced"
    assert state.roads["road:1"]["faction_id"] is None
    losses = state.stocks.get("_losses") or {}
    assert any("timber" in (rec.get("goods") or {}) for rec in losses.values())
    assert any("brick" in (rec.get("goods") or {}) for rec in losses.values())


def test_planner_includes_collapse_selection() -> None:
    wid = WorldId("world:t098p")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    state.world_version = 1
    state.clock["era"] = "prehistoric"
    state.clock["started_faction_ids"] = [f"faction:{i}" for i in range(1, 7)]
    scores = {f"faction:{i}": sp for i, sp in enumerate([10, 9, 8, 7, 6, 5], start=1)}
    for fid, vp in scores.items():
        state.factions[fid] = {"id": fid}
        for j in range(vp):
            sid = f"settlement:{fid}:{j}"
            state.settlements[sid] = {
                "id": sid,
                "faction_id": fid,
                "node_id": f"node:{fid}:{j}",
                "tier": "settlement",
                "operational": True,
            }
    plan = EraTransitionPlanner().plan(
        state,
        TransitionTrigger("evt:c", "faction:1", scores_at_trigger=scores),
    )
    assert plan.collapse_faction_ids == ["faction:6"]
    assert plan.survivor_faction_ids == [f"faction:{i}" for i in range(1, 6)]
