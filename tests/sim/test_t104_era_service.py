"""T104 — atomic EraService commit and Historic industry."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.construction.orders import ConstructionService
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.eras.planner import EraTransitionPlanner, TransitionTrigger, validate_plan_freshness
from sim.dmb.eras.service import EraService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.board import HexBoard
from sim.dmb.world.boulder_quest import QUEST_INSTANCE_ID, ROCKFALL_ID, get_rockfall


def _near_threshold_world() -> WorldState:
    """Two-faction world at 9 VP for winner path; loser at 4 VP."""
    wid = WorldId("world:t104")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    state.board["hex_terrain"] = {hid: "woodland" for hid in board.hexes}
    # Alternate terrains for cross-terrain binding.
    for i, hid in enumerate(board.hexes):
        state.board["hex_terrain"][hid] = (
            "woodland" if i % 2 == 0 else "clay_mountains"
        )
    state.board["node_hexes"] = {nid: list(board.touching_hexes(nid)) for nid in board.nodes}
    state.clock["era"] = "prehistoric"
    state.clock["started_faction_ids"] = ["faction:win", "faction:lose"]
    state.factions["faction:win"] = {"id": "faction:win", "status": "active", "operational": True}
    state.factions["faction:lose"] = {"id": "faction:lose", "status": "active", "operational": True}

    def _settlement(fid: str, sid: str, node: str, *, n_extra: int = 0) -> None:
        state.settlements[sid] = {
            "id": sid,
            "faction_id": fid,
            "node_id": node,
            "tier": "settlement",
            "operational": True,
            "warehouse_id": f"{sid}:wh",
            "centre_id": f"{sid}:centre",
        }
        state.buildings[f"{sid}:centre"] = {
            "id": f"{sid}:centre",
            "def_id": "building.centre",
            "slot_kind": "centre",
            "settlement_id": sid,
            "faction_id": fid,
            "node_id": node,
            "status": "active",
            "active": True,
        }
        state.buildings[f"{sid}:wh"] = {
            "id": f"{sid}:wh",
            "def_id": "building.warehouse",
            "slot_kind": "warehouse",
            "settlement_id": sid,
            "faction_id": fid,
            "node_id": node,
            "status": "active",
            "active": True,
        }
        for i in range(3):
            state.buildings[f"{sid}:primary:{i}"] = {
                "id": f"{sid}:primary:{i}",
                "def_id": "building.primary",
                "slot_kind": "primary",
                "slot_index": i,
                "settlement_id": sid,
                "faction_id": fid,
                "node_id": node,
                "status": "active",
                "active": True,
            }
        state.buildings[f"{sid}:processor"] = {
            "id": f"{sid}:processor",
            "def_id": "building.processor",
            "slot_kind": "processor",
            "settlement_id": sid,
            "faction_id": fid,
            "node_id": node,
            "status": "active",
            "active": True,
        }
        for i in range(3):
            state.buildings[f"{sid}:factory:{i}"] = {
                "id": f"{sid}:factory:{i}",
                "def_id": "building.factory",
                "slot_kind": "factory",
                "slot_index": i,
                "settlement_id": sid,
                "faction_id": fid,
                "node_id": node,
                "status": "active",
                "active": True,
            }
        for i in range(n_extra):
            esid = f"{sid}:extra:{i}"
            enode = board.nodes[(board.nodes.index(node) + 2 + i) % len(board.nodes)]
            state.settlements[esid] = {
                "id": esid,
                "faction_id": fid,
                "node_id": enode,
                "tier": "settlement",
                "operational": True,
            }

    nodes = list(board.nodes)
    # Prefer a node that already touches two terrains after alternating assignment.
    core_node = nodes[0]
    for nid in nodes:
        touching = list(board.touching_hexes(nid))
        terrains = {state.board["hex_terrain"].get(h) for h in touching}
        if len(terrains) >= 2:
            core_node = nid
            break
    else:
        # Force two terrains onto any multi-hex node.
        for nid in nodes:
            touching = list(board.touching_hexes(nid))
            if len(touching) >= 2:
                core_node = nid
                state.board["hex_terrain"][touching[0]] = "woodland"
                state.board["hex_terrain"][touching[1]] = "clay_mountains"
                break
    _settlement("faction:win", "settlement:core", core_node, n_extra=8)
    # Loser: 4 settlements → 4 VP (avoid overlapping the chosen core).
    lose_candidates = [n for n in nodes if n != core_node]
    lose_node = lose_candidates[min(9, len(lose_candidates) - 1)]
    _settlement("faction:lose", "settlement:lose", lose_node, n_extra=3)
    state.people["person:worker"] = {
        "id": "person:worker",
        "alive": True,
        "status": "employed",
        "faction_id": "faction:win",
        "settlement_id": "settlement:core",
        "node_id": core_node,
        "workplace_id": "settlement:core:factory:0",
        "role": "worker",
        "occupation": "Factory worker",
    }
    state.hazards = {
        "catastrophe": {
            "cubes": {
                "cube:1": {
                    "id": "cube:1",
                    "hex_id": list(board.hexes)[0],
                    "type": "demon",
                    "cause_id": "cause:1",
                    "active": True,
                }
            },
            "era_completed_rounds": 5,
            "escalation": 2,
        }
    }
    assert ScoreService(state).score("faction:win") == 9
    assert ScoreService(state).score("faction:lose") == 4
    return state


def test_atomic_transition_once_and_idempotent() -> None:
    state = _near_threshold_world()
    # Reach 10 VP by founding one more settlement legally via direct score bump of new settlement.
    node = list(HexBoard.radius2().nodes)[20]
    state.settlements["settlement:tenth"] = {
        "id": "settlement:tenth",
        "faction_id": "faction:win",
        "node_id": node,
        "tier": "settlement",
        "operational": True,
    }
    assert ScoreService(state).score("faction:win") == 10
    people_before = set(state.people)
    cube_before = set((state.hazards["catastrophe"]["cubes"]).keys())

    svc = EraService(state)
    plan = svc.request_transition("faction:win", "evt:t104")
    assert plan.next_era == "historic"
    result = svc.commit(plan)
    assert result["idempotent"] is False
    receipt = result["receipt"]
    assert receipt["status"] == "committed"
    assert state.clock["era"] == "historic"
    assert state.clock["last_era_transition_id"] == "evt:t104"
    assert set(state.people) == people_before
    assert set((state.hazards["catastrophe"]["cubes"]).keys()) == cube_before
    assert state.hazards["catastrophe"]["era_completed_rounds"] == 0
    assert state.factions["faction:lose"]["status"] == "collapsed"

    again = svc.commit(plan)
    assert again["idempotent"] is True


def test_stale_plan_rejected() -> None:
    state = _near_threshold_world()
    state.settlements["settlement:tenth"] = {
        "id": "settlement:tenth",
        "faction_id": "faction:win",
        "node_id": list(HexBoard.radius2().nodes)[20],
        "tier": "settlement",
        "operational": True,
    }
    svc = EraService(state)
    plan = svc.request_transition("faction:win", "evt:stale")
    state.world_version += 1
    try:
        svc.commit(plan)
        assert False, "expected stale rejection"
    except TypeValidationError as exc:
        assert "stale" in str(exc)


def test_no_half_converted_after_commit() -> None:
    state = _near_threshold_world()
    state.settlements["settlement:tenth"] = {
        "id": "settlement:tenth",
        "faction_id": "faction:win",
        "node_id": list(HexBoard.radius2().nodes)[20],
        "tier": "settlement",
        "operational": True,
    }
    EraService(state).commit(
        EraService(state).request_transition("faction:win", "evt:full")
    )
    assert state.clock.get("era") == "historic"
    assert not state.clock.get("era_transition_frozen")
    assert not state.board.get("era_transition_pending")
    # Collapsed have ruins; surviving cores historic or legacy marked.
    for sid, s in state.settlements.items():
        if s.get("faction_id_before_collapse") == "faction:lose" or (
            s.get("ruin_only") and s.get("collapse_reason")
        ):
            assert s.get("ruin_only") is True
            assert ScoreService(state).settlement_vp(s) == 0


def test_historic_core_industry_operational() -> None:
    state = _near_threshold_world()
    state.settlements["settlement:tenth"] = {
        "id": "settlement:tenth",
        "faction_id": "faction:win",
        "node_id": list(HexBoard.radius2().nodes)[20],
        "tier": "settlement",
        "operational": True,
    }
    result = EraService(state).commit(
        EraService(state).request_transition("faction:win", "evt:ind")
    )
    industries = result["receipt"]["historic_industry"]
    assert any(row.get("status") == "operational" for row in industries), industries
    op = next(row for row in industries if row.get("status") == "operational")
    assert op.get("recipe_id")
    assert op.get("processor_id")
    assert op.get("factory_ids")
    # Factory era historic
    fid = op["factory_ids"][0]
    assert state.industry["factories"][fid]["era"] == "historic"
    assert "historic" in str(state.industry["factories"][fid]["unit_def_id"])


def test_rockfall_survives_fx_village_transition_path() -> None:
    """Smoke: continuity intact when EraService runs on FX-VILLAGE with forced VP."""
    sim = load_fixture("FX-VILLAGE", seed=507)
    state = sim.state
    factions = sorted(state.factions)
    winner = factions[0] if factions else "faction:1"
    board = HexBoard.from_dict(state.board["topology"])
    occupied = {
        str(s.get("node_id"))
        for s in state.settlements.values()
        if s.get("node_id") and not s.get("ruin_only")
    }
    free_nodes = [n for n in board.nodes if n not in occupied]
    while ScoreService(state).score(winner) < 10 and free_nodes:
        node = free_nodes.pop(0)
        sid = state.ids.new("settlement")
        state.settlements[sid] = {
            "id": sid,
            "faction_id": winner,
            "node_id": node,
            "tier": "settlement",
            "operational": True,
        }
    # If still short, upgrade existing to city for VP (2 each) — still production-legal tier.
    for sid, s in list(state.settlements.items()):
        if ScoreService(state).score(winner) >= 10:
            break
        if s.get("faction_id") == winner and s.get("tier") != "city":
            s["tier"] = "city"
    assert ScoreService(state).score(winner) >= 10
    rock_before = deepcopy(get_rockfall(state))
    quest_before = deepcopy(state.quests.get(QUEST_INSTANCE_ID))
    people_before = set(state.people)
    # Multi-faction start: do not force sole fission.
    state.clock["started_faction_ids"] = list(factions)
    state.clock["sole_era_starter"] = False
    state.clock["mandatory_split_ids"] = []
    EraService(state).commit(EraService(state).request_transition(winner, "evt:fx"))
    assert set(state.people) == people_before
    if rock_before:
        assert get_rockfall(state)["id"] == ROCKFALL_ID
    if quest_before:
        assert QUEST_INSTANCE_ID in state.quests
