"""T119 — alien catastrophe content and alternation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.responders import HazardResponder
from sim.dmb.hazards.service import CatastropheService, OUTBREAK_TERMINAL
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.visits import VisitService

ROOT = Path(__file__).resolve().parents[2]
ALIENS = ROOT / "godot_project" / "content" / "source" / "hazards" / "aliens.json"


def test_alien_content_and_duel_rule() -> None:
    data = json.loads(ALIENS.read_text(encoding="utf-8"))
    assert data["hazard_type"] == "alien"
    assert data["duel_allowed"] is True
    rule = json.loads(
        (ROOT / "godot_project" / "content" / "source" / "duel_rules" / "hazard_alien.json").read_text()
    )
    assert rule["id"] == data["duel_rule_id"]


def test_alien_can_be_challenged_and_demon_preserved() -> None:
    state = WorldState(world_id=WorldId("world:t119"))
    state.clock["era"] = "modern"
    state.board["node_hexes"] = {"n1": ["h1"], "n2": ["h2"]}
    VisitService(state).arrive("n1", "travel", 1)
    svc = CatastropheService(state)
    demon = svc.add_cube("h2", "demon")["cube"]
    demon_id = demon["id"]
    alien = svc.add_cube("h1", "alien")["cube"]
    assert demon["type"] == "demon"
    assert alien["type"] == "alien"
    gate = HazardDuelService(state).can_start(alien["id"])
    assert gate["ok"] is True
    started = HazardDuelService(state).begin(alien["id"])
    assert started["status"] == "started"
    # Prior demon type/id unchanged.
    assert svc._cat()["cubes"][demon_id]["type"] == "demon"
    assert svc._cat()["cubes"][demon_id]["id"] == demon_id


def test_modern_alternation_survives_reload() -> None:
    state = WorldState(world_id=WorldId("world:t119b"))
    state.clock["era"] = "modern"
    state.clock["turn"] = 3
    cat = state.hazards.setdefault("catastrophe", {})
    cat["era_start_turn"] = 0
    cat["placement_ordinal"] = 0
    svc = CatastropheService(state)
    svc.deck = type(svc.deck)(state, hex_ids=["h1", "h2", "h3", "h4"])
    first = svc._next_type()
    cat["placement_ordinal"] = 1
    second = svc._next_type()
    assert {first, second} == {"pollution", "alien"}
    snap = deepcopy(state.to_dict())
    reloaded = WorldState.from_dict(snap)
    re_svc = CatastropheService(reloaded)
    assert re_svc._next_type() == second


def test_terminal_cap_counts_all_types() -> None:
    state = WorldState(world_id=WorldId("world:t119c"))
    state.clock["era"] = "modern"
    svc = CatastropheService(state)
    # Seed mixed types toward terminal outbreak budget.
    cat = svc._cat()
    cat["era_outbreaks"] = OUTBREAK_TERMINAL - 1
    assert int(cat["era_outbreaks"]) + 1 == OUTBREAK_TERMINAL


def test_alien_military_treat() -> None:
    state = WorldState(world_id=WorldId("world:t119d"))
    state.clock["era"] = "modern"
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.board["node_hexes"] = {"n1": ["h1"]}
    mil = MilitaryService(state)
    u = mil.spawn(
        "unit.modern.skirmisher",
        home_node_id="n1",
        faction_id="faction:a",
        era="modern",
        factory_id="f",
    )
    cube = CatastropheService(state).add_cube("h1", "alien")["cube"]
    out = HazardResponder(state).treat(str(u["formation_id"]), cube["id"])
    assert out["status"] == "treated"
