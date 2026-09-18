"""T072 visit ledgers and treatment allowances."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.player.visits import VisitService


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t072"))
    state.board["node_hexes"] = {"n1": ["h1", "h2", "h3"]}
    state.player["node_id"] = "n1"
    return state


def test_three_adjacent_one_each() -> None:
    state = _world()
    visits = VisitService(state)
    visits.arrive("n1", "travel", 1)
    for hid in ("h1", "h2", "h3"):
        assert visits.can_treat(hid)["ok"]
        assert visits.record_success(hid, f"eff:{hid}")["status"] == "recorded"
    assert visits.can_treat("h1")["ok"] is False
    assert visits.record_success("h1", "eff:again")["status"] == "rejected"


def test_wait_load_no_refresh() -> None:
    state = _world()
    visits = VisitService(state)
    visits.arrive("n1", "travel", 5)
    visits.record_success("h1", "e1")
    visits.arrive("n1", "wait", 5)
    assert visits.can_treat("h1")["ok"] is False
    visits.arrive("n1", "load", 5)
    assert visits.can_treat("h1")["ok"] is False


def test_later_strategic_return_new_visit() -> None:
    state = _world()
    visits = VisitService(state)
    visits.arrive("n1", "travel", 1)
    visits.record_success("h1", "e1")
    visits.arrive("n2", "travel", 2)
    again = visits.arrive("n1", "travel", 3)
    assert again["status"] == "new"
    assert visits.can_treat("h1")["ok"] is True
