"""T108 — FX-MVP integrated two-era sandbox (normal generation)."""

from __future__ import annotations

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler


def test_fx_mvp_is_normal_prehistoric_sandbox() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    state = sim.state
    mvp = state.board.get("mvp") or {}
    assert mvp.get("fixture") == "FX-MVP"
    assert mvp.get("debug_injected_resources") is False
    assert mvp.get("forces_game_over") is False
    assert str(state.clock.get("era") or "prehistoric") == "prehistoric"
    assert len(state.factions) >= 2
    topo = state.board.get("topology") or {}
    assert len(topo.get("hexes") or []) == 19
    assert len(topo.get("nodes") or []) == 54


def test_fx_era_checkpoint_still_reaches_historic_once() -> None:
    """Accelerated gate checkpoint remains valid for Historic continuation proof."""
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    people_before = set(state.people)
    assert ScoreService(state).score(winner) == 9
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "t108-mvp-wait")
    assert state.clock.get("era") == "historic"
    assert set(state.people) == people_before
    # Demonstration endpoint does not force Game Over.
    assert state.clock.get("game_over") not in {True, "true", 1}
