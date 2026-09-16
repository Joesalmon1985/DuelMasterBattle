"""T009 world state and immutable views."""

from __future__ import annotations

import pytest

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.core.views import assert_id_kinds_separated


def test_read_view_mutation_cannot_modify_state() -> None:
    state = WorldState(world_id=WorldId("world:t009"))
    view = state.read_view()
    with pytest.raises(TypeError):
        view["player"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        view["player"]["node_id"] = "node:hack"  # type: ignore[index]
    assert state.player["node_id"] == "node:1"


def test_dangling_live_reference_fails() -> None:
    state = WorldState(world_id=WorldId("world:t009"))
    state.people["person:1"] = {"definition_id": "npc.guard", "workplace_id": "building:missing"}
    with pytest.raises(TypeValidationError, match="dangling"):
        WorldState.from_dict(state.to_dict())


def test_retired_referenced_person_retains_identity() -> None:
    state = WorldState(world_id=WorldId("world:t009"))
    state.people["person:1"] = {"definition_id": "npc.guard", "workplace_id": "building:1"}
    state.buildings["building:1"] = {"id": "building:1"}
    state.tombstones["building:1"] = {"kind": "building", "display_name": "Ruins"}
    del state.buildings["building:1"]
    restored = WorldState.from_dict(state.to_dict())
    assert "person:1" in restored.people
    assert restored.tombstones["building:1"]["display_name"] == "Ruins"


def test_definition_and_instance_ids_cannot_be_interchanged() -> None:
    with pytest.raises(TypeValidationError):
        assert_id_kinds_separated("person:1", "person:1")
    assert_id_kinds_separated("npc.guard", "person:1")
