"""T092 duel checkpoint, recovery routing, and outcome revalidation."""

from __future__ import annotations

from sim.dmb.adventure.duels import HazardDuelService, score_feedback
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.player.recovery import RecoveryService
from sim.dmb.player.visits import VisitService


def _ready() -> tuple[WorldState, str]:
    state = WorldState(world_id=WorldId("world:t092"))
    state.board["nodes"] = {
        "n1": {"id": "n1"},
        "n2": {"id": "n2"},
        "n3": {"id": "n3"},
        "n4": {"id": "n4"},
    }
    state.board["adjacency"] = {
        "n1": ["n2", "n3"],
        "n2": ["n1", "n4"],
        "n3": ["n1"],
        "n4": ["n2"],
    }
    state.board["node_hexes"] = {"n1": ["h1"], "n2": ["h2"], "n3": ["h3"], "n4": ["h4"]}
    state.player["node_id"] = "n1"
    state.clock["turn"] = 3
    state.clock["game_ms"] = 12_000
    VisitService(state).arrive("n1", "travel", 3)
    # Spend visit allowance on another hex first so we can prove it stays spent.
    visit = state.player["visits"]["current"]
    visit["treated_hexes"] = ["h_other"]
    visit["success_count"] = 1
    cube = CatastropheService(state).add_cube("h1", "demon")["cube"]
    return state, cube["id"]


def test_mid_window_resume_same_next_feedback() -> None:
    state, cube_id = _ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    duel_id = started["duel"]["id"]
    secret = [0, 0, 1, 2]
    guess = [0, 1, 0, 3]
    exact, colour = score_feedback(secret, guess)
    saved = duels.save_checkpoint(
        duel_id,
        {
            "secret": secret,
            "rng_state": {"stream": 7},
            "window": {"index": 2, "remaining_ms": 4000},
            "input": {"partial": [0, 1]},
            "next_feedback": {"exact": exact, "colour_only": colour},
            "guesses": [{"guess": guess, "exact": exact, "colour_only": colour}],
        },
    )
    assert saved["status"] == "saved"
    # Reject secret reroll.
    rejected = duels.save_checkpoint(duel_id, {"secret": [9, 9, 9, 9]})
    assert rejected["status"] == "rejected"
    resumed = duels.resume(duel_id)
    assert resumed["secret"] == secret
    assert resumed["next_feedback"] == {"exact": 1, "colour_only": 2}
    assert resumed["window"]["index"] == 2


def test_sixty_second_duel_adds_zero_world_time() -> None:
    state, cube_id = _ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    out = duels.tick_duel_clock(started["duel"]["id"], duel_ms=60_000)
    assert out["duel_ms"] == 60_000
    assert out["world_turn"] == 3
    assert out["world_game_ms"] == 12_000
    assert state.clock["turn"] == 3
    assert state.clock["game_ms"] == 12_000


def test_duplicate_win_removes_one_cube() -> None:
    state, cube_id = _ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    first = duels.resolve(started["duel"]["id"], success=True, command_id="win:1")
    assert first["status"] == "success"
    again = duels.resolve(started["duel"]["id"], success=True, command_id="win:1")
    assert again["status"] == "idempotent"
    active = [
        c
        for c in state.hazards["catastrophe"]["cubes"].values()
        if c.get("active", True)
    ]
    assert active == []
    assert state.hazards["catastrophe"]["cubes"][cube_id]["active"] is False


def test_missing_friendly_settlement_falls_back_deterministically() -> None:
    state, _cube_id = _ready()
    state.settlements = {
        "s_hostile": {
            "id": "s_hostile",
            "node_id": "n2",
            "wizard_relation": -80,
            "alive": True,
        },
        "s_neutral": {
            "id": "s_neutral",
            "node_id": "n3",
            "wizard_relation": 0,
            "alive": True,
        },
        "s_far": {
            "id": "s_far",
            "node_id": "n4",
            "wizard_relation": 5,
            "alive": True,
            "last_friendly": True,
        },
    }
    # Destroy the last_friendly settlement → fall back to nearest neutral-or-better.
    state.settlements["s_far"]["destroyed"] = True
    choice = RecoveryService(state).choose_return_node(from_node_id="n1")
    assert choice["kind"] == "friendly"
    assert choice["node_id"] == "n3"
    # No settlements → wilderness / least affected (deterministic by cube count + id).
    state.settlements = {}
    wild = RecoveryService(state).choose_return_node(from_node_id="n1")
    assert wild["kind"] in {"wilderness", "least_affected"}
    again = RecoveryService(state).choose_return_node(from_node_id="n1")
    assert again["node_id"] == wild["node_id"]


def test_same_turn_visit_remains_spent_after_recovery() -> None:
    state, cube_id = _ready()
    visit_before = dict(state.player["visits"]["current"])
    assert "h_other" in visit_before["treated_hexes"]
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    state.settlements = {
        "s1": {"id": "s1", "node_id": "n2", "wizard_relation": 10, "alive": True, "last_friendly": True}
    }
    out = duels.resolve(
        started["duel"]["id"],
        success=False,
        command_id="fail:1",
        apply_recovery_on_failure=True,
    )
    assert out["status"] == "failed"
    assert state.clock["turn"] == 3
    # Same-turn visit ledger still has the spent hex — recovery did not refresh.
    current = state.player["visits"]["current"]
    assert current is not None
    # Either retained current visit or restored same-turn ledger with spent hex.
    ledgers = state.player["visits"]["ledgers"]
    spent = any("h_other" in (v.get("treated_hexes") or []) for v in ledgers.values())
    assert spent
    assert visit_before["success_count"] == 1
