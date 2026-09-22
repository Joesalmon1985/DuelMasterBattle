"""T129 — Utopia path validation without Utopia content."""

from __future__ import annotations

import pytest

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.eras.path_selection import (
    baseline_path_or_default,
    set_next_future_path,
    utopia_pack_installed,
)


def test_baseline_is_dystopia_without_pack() -> None:
    state = WorldState(world_id=WorldId("world:t129"))
    assert utopia_pack_installed() is False
    assert baseline_path_or_default(state) == "dystopia"
    assert state.clock["next_future_path"] == "dystopia"


def test_utopia_rejected_without_pack() -> None:
    state = WorldState(world_id=WorldId("world:t129b"))
    with pytest.raises(TypeValidationError, match="utopia_pack_missing"):
        set_next_future_path(state, "utopia", quest_flag=True)


def test_dystopia_always_allowed() -> None:
    state = WorldState(world_id=WorldId("world:t129c"))
    out = set_next_future_path(state, "dystopia")
    assert out["next_future_path"] == "dystopia"
