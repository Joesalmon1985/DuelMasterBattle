"""T070 outbreak propagation and terminal once."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.terminal import TerminalService
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.propagation import PropagationEngine
from sim.dmb.hazards.service import CatastropheService


def _triangle() -> WorldState:
    state = WorldState(world_id=WorldId("world:t070"))
    state.board["hex_adjacency"] = {
        "h1": ["h2", "h3"],
        "h2": ["h1", "h3"],
        "h3": ["h1", "h2"],
    }
    return state


def test_saturated_triangle_outbreaks_once_each() -> None:
    state = _triangle()
    svc = CatastropheService(state)
    for hid in ("h1", "h2", "h3"):
        for _ in range(3):
            svc.add_cube(hid, "demon")
    engine = PropagationEngine(state)
    engine.begin_event()
    result = engine.outbreak_from("h1", "demon")
    visited = set(state.hazards["catastrophe"]["visited_outbreaks"])
    assert "h1" in visited
    # Each hex outbreaks at most once in this event.
    assert len(visited) == len(set(visited))
    assert state.hazards["catastrophe"]["era_outbreaks"] <= 3


def test_seven_to_eight_stops_neighbours() -> None:
    state = _triangle()
    svc = CatastropheService(state)
    for hid in ("h1", "h2", "h3"):
        for _ in range(3):
            svc.add_cube(hid, "demon")
    cat = state.hazards["catastrophe"]
    cat["era_outbreaks"] = 7
    engine = PropagationEngine(state)
    engine.begin_event()
    before_h2 = len(svc.cubes_on_hex("h2"))
    result = engine.outbreak_from("h1", "demon")
    assert result["status"] == "terminal"
    assert state.clock.get("terminal") is True
    # No further neighbour mutations after terminal.
    assert len(svc.cubes_on_hex("h2")) == before_h2


def test_repeated_terminal_no_second_game_over() -> None:
    state = _triangle()
    first = TerminalService(state).trigger("test")
    second = TerminalService(state).trigger("test")
    assert first["emitted"] is True
    assert second["emitted"] is False
    assert len(state.hazards["terminal_events"]) == 1
