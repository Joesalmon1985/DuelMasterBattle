"""R06: Mastermind scoring reference + retained Challenge path.

Production StartHazardDuel grants a ward-duel lease for GameBoard/DmbBattleSim.
Mastermind remains reference scoring evidence only.
"""

from __future__ import annotations

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.adventure.mastermind import MastermindDuel, score_guess
from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture


def _env(sim, command_id: str, kind: str, payload: dict) -> CommandEnvelope:
    return CommandEnvelope(
        protocol_version=1,
        session_id="t",
        world_id=sim.state.world_id,
        command_id=command_id,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )


def test_c10_feedback_example():
    exact, colour = score_guess([0, 0, 1, 2], [0, 1, 0, 3])
    assert exact == 1
    assert colour == 2


def test_production_challenge_rejects_guess_panel_and_resolves_via_lease():
    sim = load_fixture("FX-HAZARD", seed=408)
    cubes = sim.state.hazards["catastrophe"]["cubes"]
    cube_id = next(iter(cubes))
    start = sim.dispatch(_env(sim, "start-1", "StartHazardDuel", {"cube_id": cube_id}))
    assert start.status == "ACCEPTED"
    public = start.payload["public"]
    duel_id = public["duel_id"]
    assert public.get("engine") == "DmbBattleSim"
    assert public.get("kind") == "hazard_ward_duel"
    assert "secret" not in public
    assert "mastermind" not in (sim.state.leases[duel_id] or {})
    bad = sim.dispatch(_env(sim, "ch-1", "HazardDuelAction", {"duel_id": duel_id, "action": "channel"}))
    assert bad.status == "REJECTED"
    assert bad.code == "USE_RETAINED_BOARD"
    guess = sim.dispatch(
        _env(sim, "guess-1", "HazardDuelAction", {"duel_id": duel_id, "action": "guess", "guess": [0, 1, 2, 3]})
    )
    assert guess.status == "REJECTED"
    assert guess.code == "USE_RETAINED_BOARD"
    win = sim.dispatch(_env(sim, "resolve-win", "ResolveHazardDuel", {"duel_id": duel_id, "success": True}))
    assert win.status == "ACCEPTED"
    assert win.payload.get("status") == "success"
    assert cubes[cube_id].get("active") is False
    again = sim.dispatch(_env(sim, "resolve-dup", "ResolveHazardDuel", {"duel_id": duel_id, "success": True}))
    assert again.status == "ACCEPTED"
    assert again.payload.get("status") == "idempotent"


def test_mastermind_reference_scoring_still_available():
    sim = load_fixture("FX-HAZARD", seed=408)
    cube_id = next(iter(sim.state.hazards["catastrophe"]["cubes"]))
    started = HazardDuelService(sim.state).begin_mastermind_reference(cube_id)
    assert started["status"] == "started"
    assert "mastermind" in started["duel"]
    secret = list(started["duel"]["mastermind"]["secret"])
    result = MastermindDuel.submit_guess(started["duel"], secret)
    assert result.get("outcome") == "success"


def test_mastermind_public_hides_secret():
    duel = {"id": "lease:x", "cube_id": "c", "hex_id": "hex:a"}
    MastermindDuel.attach(duel)
    pub = MastermindDuel.public_view(duel)
    assert "secret" not in pub
    assert pub["slot_count"] == 4
    assert pub["colour_count"] == 6
    assert pub["max_casts"] == 10
