"""T105 — Chronicle + transition presentation contracts."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.state import WorldState
from sim.dmb.eras.service import EraService
from sim.dmb.history.chronicle import HistoryService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.board import HexBoard


def _force_10(state, winner: str) -> None:
    while ScoreService(state).score(winner) < 10:
        board = HexBoard.from_dict(state.board["topology"])
        occupied = {str(s.get("node_id")) for s in state.settlements.values() if s.get("node_id")}
        free = [n for n in board.nodes if n not in occupied]
        assert free
        sid = state.ids.new("settlement")
        state.settlements[sid] = {
            "id": sid,
            "faction_id": winner,
            "node_id": free[0],
            "tier": "settlement",
            "operational": True,
        }


def test_chronicle_records_transition_and_filters() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    _force_10(state, winner)
    EraService(state).commit(EraService(state).request_transition(winner, "evt:t105"))
    hist = HistoryService(state)
    debug = hist.query_known_history(debug=True)
    assert any(e.get("kind") == "vp_threshold" for e in debug)
    assert any(e.get("kind") == "historic_core" for e in debug)
    known = hist.query_known_history(debug=False)
    assert any(e.get("kind") == "vp_threshold" for e in known)


def test_reload_keeps_committed_historic_without_second_transition() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    _force_10(state, winner)
    result = EraService(state).commit(EraService(state).request_transition(winner, "evt:once"))
    people = set(state.people)
    tid = result["receipt"]["transition_id"]
    snap = deepcopy(state.to_dict())
    # Idempotent re-commit
    again = EraService(state).commit(result["receipt"])
    assert again.get("idempotent") is True
    assert state.clock.get("last_era_transition_id") == tid
    assert set(state.people) == people
    reloaded = WorldState.from_dict(snap)
    assert reloaded.clock.get("era") == "historic"
    assert reloaded.clock.get("last_era_transition_id") == tid
    # maybe_trigger must no-op after commit
    assert EraService(reloaded).maybe_trigger_from_interrupt(event_id="evt:dup") is None
