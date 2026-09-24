"""T118 — pollution cleanup capability."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.responders import HazardResponder
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.military.units import MilitaryService

ROOT = Path(__file__).resolve().parents[2]
POLLUTION = ROOT / "godot_project" / "content" / "source" / "hazards" / "pollution.json"


def test_pollution_content_forbids_duel() -> None:
    data = json.loads(POLLUTION.read_text(encoding="utf-8"))
    assert data["hazard_type"] == "pollution"
    assert data["duel_allowed"] is False
    assert "cleanup" in data["response"]["kind"]


def test_pollution_suppresses_source_and_persists_type() -> None:
    state = WorldState(world_id=WorldId("world:t118"))
    state.clock["era"] = "modern"
    svc = CatastropheService(state)
    cube = svc.add_cube("h1", "pollution")["cube"]
    assert svc.is_source_blocked("h1") is True
    assert cube["type"] == "pollution"
    svc.rollover("future")
    assert cube["type"] == "pollution"
    assert cube["active"] is True


def test_cleanup_facility_treats_one_ineligible_cannot() -> None:
    state = WorldState(world_id=WorldId("world:t118b"))
    state.clock["era"] = "modern"
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.board["node_hexes"] = {"n1": ["h1"]}
    mil = MilitaryService(state)
    plain = mil.spawn(
        "unit.modern.line",
        home_node_id="n1",
        faction_id="faction:a",
        era="modern",
        factory_id="f1",
    )
    form_id = str(plain["formation_id"])
    svc = CatastropheService(state)
    cube = svc.add_cube("h1", "pollution")["cube"]
    responder = HazardResponder(state)
    assert responder.treat(form_id, cube["id"])["status"] == "rejected"

    state.buildings["building:cleanup"] = {
        "id": "building:cleanup",
        "node_id": "n1",
        "definition_id": "building.modern.cleanup",
        "cleanup_capable": True,
        "faction_id": "faction:a",
    }
    out = responder.treat(form_id, cube["id"])
    assert out["status"] == "treated"
    assert out["edges_moved"] == 0
    assert not svc.cubes_on_hex("h1")


def test_wizard_pollution_duel_rejected() -> None:
    state = WorldState(world_id=WorldId("world:t118c"))
    state.board["node_hexes"] = {"n1": ["h1"]}
    state.player["node_id"] = "n1"
    cube = CatastropheService(state).add_cube("h1", "pollution")["cube"]
    gate = HazardDuelService(state).can_start(cube["id"])
    assert gate["ok"] is False
    assert gate["reason"] == "pollution_no_duel"
