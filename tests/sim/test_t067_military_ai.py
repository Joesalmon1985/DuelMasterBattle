"""T067 military objectives and turn battle integration."""

from __future__ import annotations

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.legal import LegalActionGenerator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.units import MilitaryService
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t067"))
    state.clock["active_faction_id"] = "faction:a"
    state.factions["faction:a"] = {"id": "faction:a"}
    state.player["node_id"] = "n1"
    return state


def test_no_unobserved_enemy_strength_in_features() -> None:
    state = _world()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    director.group([u["id"]], faction_id="faction:a", node_id="n1")
    # Hidden enemy elsewhere — must not appear in attack benefits without observation.
    mil.spawn("unit.ancient.heavy", home_node_id="n9", faction_id="faction:b", era="prehistoric", factory_id="f")
    gen = LegalActionGenerator(state)
    view = {
        "faction_id": "faction:a",
        "legal_version": state.world_version,
        "knowledge": {"enemy_military_nodes": []},
    }
    cands = gen.enumerate(view, "military")
    attacks = [c for c in cands if c["action_kind"] == "military_objective" and c["params"].get("objective") == "attack"]
    assert attacks == []
    for c in cands:
        assert "enemy_strength" not in (c.get("benefit") or {})


def test_victory_no_automatic_ownership() -> None:
    state = _world()
    mil = MilitaryService(state)
    a = mil.spawn("unit.ancient.heavy", home_node_id="n2", faction_id="faction:a", era="prehistoric", factory_id="f")
    b = mil.spawn("unit.ancient.line", home_node_id="n2", faction_id="faction:b", era="prehistoric", factory_id="f")
    state.units[b["id"]]["current_health"] = 1
    state.buildings["centre1"] = {
        "id": "centre1",
        "node_id": "n2",
        "faction_id": "faction:b",
        "alive": True,
        "health": 10,
        "current_health": 10,
        "status": "active",
    }
    state.battles["battle:1"] = {
        "id": "battle:1",
        "node_id": "n2",
        "state": "OFFSCREEN",
        "participants": [a["id"], b["id"]],
        "buildings": ["centre1"],
        "entry_effective_health": {"faction:a": 180, "faction:b": 1},
        "prefer_local": False,
    }
    state.player["node_id"] = "n1"
    sched = TurnScheduler(state)
    runner = TurnRunner(state, sched)
    results = runner._resolve_pending_offscreen("faction:a")
    assert state.buildings["centre1"]["faction_id"] == "faction:b"
    assert any(r.get("ownership_transferred") is False for r in results)


def test_heuristic_ranks_defend() -> None:
    brain = HeuristicBrain()
    obs = {"own": {"vp": 0}, "public": {}}
    defend = {
        "id": "military_objective:o=defend",
        "action_kind": "military_objective",
        "params": {"objective": "defend"},
        "benefit": {},
    }
    noop = {"id": "noop:wait", "action_kind": "noop", "params": {}, "benefit": {}}
    assert brain.score(obs, defend) < brain.score(obs, noop)
