"""T106 — FX-ERA / FX-SOLO era transition scenario regressions."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.state import WorldState
from sim.dmb.eras.service import EraService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler
from sim.dmb.world.boulder_quest import QUEST_INSTANCE_ID, ROCKFALL_ID, get_rockfall


def test_fx_era_wait_triggers_single_transition() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    fx = state.board["fx_era"]
    winner = fx["winner_faction_id"]
    loser = fx["loser_faction_id"]
    assert ScoreService(state).score(winner) == 9
    people_before = set(state.people)
    rock_before = deepcopy(get_rockfall(state))
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    out = runner.execute_wait("node:35", "t106-wait")
    assert out.get("interrupted") is True
    assert state.clock.get("era") == "historic"
    assert state.clock.get("last_era_transition_id")
    receipts = state.command_receipts.get("era_transition") or {}
    assert len([r for r in receipts.values() if r.get("status") == "committed"]) == 1
    assert set(state.people) == people_before
    assert get_rockfall(state)["id"] == ROCKFALL_ID
    assert rock_before.get("status") == get_rockfall(state).get("status")
    assert QUEST_INSTANCE_ID in state.quests
    # Loser collapsed
    assert (state.factions.get(loser) or {}).get("status") == "collapsed"
    # Player start is a Historic core with operational industry
    core = state.settlements["settlement:3"]
    assert core.get("node_id") == "node:35"
    assert core.get("historic_core") or core.get("era") == "historic"
    # Second wait must not re-transition
    before_tid = state.clock.get("last_era_transition_id")
    runner2 = TurnRunner(state, TurnScheduler(state.clock))
    runner2.execute_wait("node:35", "t106-wait-2")
    assert state.clock.get("last_era_transition_id") == before_tid


def test_fx_era_save_load_matches() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "save-load")
    snap = deepcopy(state.to_dict())
    reloaded = WorldState.from_dict(snap)
    assert reloaded.clock.get("era") == "historic"
    assert set(reloaded.people) == set(state.people)
    assert EraService(reloaded).maybe_trigger_from_interrupt(event_id="nope") is None


def test_fx_solo_loader_builds() -> None:
    sim = load_fixture("FX-SOLO", seed=808)
    assert sim.state.board.get("fx_solo")
    assert ScoreService(sim.state).score(sim.state.board["fx_era"]["winner_faction_id"]) == 9


def test_person_and_rockfall_continuity_across_transition() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    known = list(state.board["fx_era"]["known_person_ids"])
    assert known
    pid = known[0]
    before = deepcopy(state.people[pid])
    winner = state.board["fx_era"]["winner_faction_id"]
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "continuity")
    after = state.people[pid]
    assert after["id"] == before["id"]
    assert after.get("alive", True) is True
    assert after.get("node_id") == before.get("node_id")
