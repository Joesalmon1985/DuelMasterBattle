"""R06: Mastermind audit + Channel shortcut rejection."""

from __future__ import annotations

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


def test_channel_shortcut_rejected_and_guess_wins():
    sim = load_fixture("FX-HAZARD", seed=408)
    cubes = sim.state.hazards["catastrophe"]["cubes"]
    cube_id = next(iter(cubes))
    start = sim.dispatch(_env(sim, "start-1", "StartHazardDuel", {"cube_id": cube_id}))
    assert start.status == "ACCEPTED"
    duel_id = start.payload["public"]["duel_id"]
    assert "secret" not in (start.payload.get("public") or {})
    bad = sim.dispatch(_env(sim, "ch-1", "HazardDuelAction", {"duel_id": duel_id, "action": "channel"}))
    assert bad.status == "REJECTED"
    assert bad.code == "FORBIDDEN_SHORTCUT"
    secret = list(sim.state.leases[duel_id]["mastermind"]["secret"])
    win = sim.dispatch(
        _env(sim, "guess-win", "HazardDuelAction", {"duel_id": duel_id, "action": "guess", "guess": secret})
    )
    assert win.status == "ACCEPTED"
    assert win.payload.get("status") == "success" or win.payload.get("removal") is not None
    assert cubes[cube_id].get("active") is False


def test_mastermind_public_hides_secret():
    duel = {"id": "lease:x", "cube_id": "c", "hex_id": "hex:a"}
    MastermindDuel.attach(duel)
    pub = MastermindDuel.public_view(duel)
    assert "secret" not in pub
    assert pub["slot_count"] == 4
    assert pub["colour_count"] == 6
    assert pub["max_casts"] == 10
