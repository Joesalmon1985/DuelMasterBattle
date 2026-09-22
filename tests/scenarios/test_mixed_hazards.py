"""T123 — mixed hazard response and rollover combinations."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.responders import RESPONDER_CAPABILITY, HazardResponder
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.visits import VisitService

ROOT = Path(__file__).resolve().parents[2]
FX = ROOT / "godot_project/content/fixtures/mixed_hazards/fx_mixed_hazards.json"


def _load_mixed() -> tuple[WorldState, CatastropheService, dict[str, str]]:
    data = json.loads(FX.read_text())
    state = WorldState(world_id=WorldId("world:t123"))
    state.clock["era"] = data["era"]
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.board["node_hexes"] = {"n1": ["h1"], "n2": ["h2"], "n3": ["h3"]}
    svc = CatastropheService(state)
    ids = {}
    for row in data["cubes"]:
        cube = svc.add_cube(row["hex_id"], row["type"])["cube"]
        ids[f"{row['hex_id']}:{row['type']}"] = cube["id"]
    return state, svc, ids


def test_every_retained_type_has_route() -> None:
    for htype in RESPONDER_CAPABILITY:
        assert RESPONDER_CAPABILITY[htype]["eras"]


def test_pollution_never_duel_and_treat_with_cleanup() -> None:
    state, svc, ids = _load_mixed()
    pid = ids["h1:pollution"]
    assert HazardDuelService(state).can_start(pid)["reason"] == "pollution_no_duel"
    state.buildings["b:cleanup"] = {
        "id": "b:cleanup",
        "node_id": "n1",
        "cleanup_capable": True,
        "definition_id": "building.modern.cleanup",
    }
    mil = MilitaryService(state)
    u = mil.spawn("unit.future.line", home_node_id="n1", faction_id="faction:a", era="future", factory_id="f")
    out = HazardResponder(state).treat(str(u["formation_id"]), pid)
    assert out["status"] == "treated"


def test_rollover_resets_counter_not_cubes() -> None:
    state, svc, ids = _load_mixed()
    cat = svc._cat()
    cat["era_outbreaks"] = 5
    before = {cid: dict(c) for cid, c in cat["cubes"].items()}
    svc.rollover("future")
    assert svc._cat().get("era_outbreaks", 0) == 0
    for cid, prior in before.items():
        assert cat["cubes"][cid]["type"] == prior["type"]
        assert cat["cubes"][cid]["active"] == prior["active"]


def test_stale_duel_cannot_remove_other_type() -> None:
    state, svc, ids = _load_mixed()
    VisitService(state).arrive("n2", "travel", 1)
    alien = ids["h2:alien"]
    nuclear = ids["h3:nuclear"]
    duels = HazardDuelService(state)
    started = duels.begin(alien)
    assert started["status"] == "started"
    # Remove alien externally while duel open.
    svc.remove_cube(alien, "external")
    resolved = duels.resolve(started["duel"]["id"], success=True, command_id="cmd:stale")
    # Nuclear must remain active regardless of stale outcome.
    assert svc._cat()["cubes"][nuclear]["active"] is True
