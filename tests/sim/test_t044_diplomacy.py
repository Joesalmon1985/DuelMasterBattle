"""T044 diplomacy and transit permissions."""

from __future__ import annotations

from sim.dmb.ai.diplomacy import DiplomacyService, REL_ALLIANCE, REL_EMBARGO, REL_WAR
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.routes import RoutePlanner


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t044"), ids=IdAllocator(WorldId("world:t044")))
    state.factions = {"faction:a": {"id": "faction:a"}, "faction:b": {"id": "faction:b"}}
    state.roads["road:ab"] = {
        "id": "road:ab",
        "faction_id": "faction:b",
        "a": "node:1",
        "b": "node:2",
    }
    return state


def test_attack_establishes_war() -> None:
    state = _world()
    diplo = DiplomacyService(state)
    diplo.declare_war("faction:a", "faction:b")
    assert diplo.relation("faction:a", "faction:b") == REL_WAR


def test_embargo_blocks_route() -> None:
    state = _world()
    diplo = DiplomacyService(state)
    diplo.set_embargo("faction:a", "faction:b")
    routes = RoutePlanner(state)
    ok, reason = routes.validate_next_edge("faction:a", "node:1", "node:2")
    assert not ok
    assert reason == "diplomacy_blocked"
    assert routes.route("faction:a", "node:1", "node:2")["path"] is None


def test_alliance_permits_transit() -> None:
    state = _world()
    diplo = DiplomacyService(state)
    prop = diplo.propose("faction:a", "faction:b", "alliance")
    diplo.respond(prop["id"], accept=True)
    assert diplo.relation("faction:a", "faction:b") == REL_ALLIANCE
    routes = RoutePlanner(state)
    assert ("node:1", "node:2") in routes.constructed_edges("faction:a")
    ok, reason = routes.validate_next_edge("faction:a", "node:1", "node:2")
    assert ok and reason == "ok"


def test_duplicate_proposal_one_effect() -> None:
    state = _world()
    diplo = DiplomacyService(state)
    first = diplo.propose("faction:a", "faction:b", "alliance", proposal_id="proposal:dup")
    second = diplo.propose("faction:a", "faction:b", "alliance", proposal_id="proposal:dup")
    assert first["id"] == second["id"]
    diplo.respond("proposal:dup", accept=True)
    history_before = len(diplo._store()["history"])
    again = diplo.respond("proposal:dup", accept=True)
    assert again["status"] == "accepted"
    # No additional relation history row from duplicate respond.
    relation_events = [h for h in diplo._store()["history"] if h.get("kind") == "relation"]
    assert len(relation_events) == 1
    assert diplo.relation("faction:a", "faction:b") == REL_ALLIANCE
    assert len(diplo._store()["history"]) == history_before  # respond short-circuit
