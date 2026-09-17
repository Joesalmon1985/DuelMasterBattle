"""T021 knowledge and semantic projection checks."""

from __future__ import annotations

import pytest

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.narrative.semantic import (
    KnowledgeFact,
    debug_projection,
    filter_entity,
    mint_token,
    player_projection,
    reveal,
)


def test_unknown_person_label_omits_name() -> None:
    state = WorldState(world_id=WorldId("world:t021"))
    state.people["person:1"] = {"definition_id": "npc.guard"}
    view = filter_entity(state, "person:1")
    assert view["label"] == "unknown"
    assert view["name"] is None


def test_observation_reveals_permitted_role() -> None:
    state = WorldState(world_id=WorldId("world:t021"))
    reveal(state, "person:1", KnowledgeFact("person:1", "met", role="guard"))
    view = filter_entity(state, "person:1")
    assert view["known"] is True
    assert view["role"] == "guard"


def test_remote_invisible_token_cannot_be_minted() -> None:
    state = WorldState(world_id=WorldId("world:t021"))
    with pytest.raises(TypeValidationError, match="cannot be minted"):
        mint_token(state, "person:1", visible=False, in_range=True)


def test_debug_fields_never_reach_player_projection() -> None:
    state = WorldState(world_id=WorldId("world:t021"))
    state.leases["lease:1"] = {"secret": True}
    player = player_projection(state)
    debug = debug_projection(state)
    assert "debug" not in player
    assert "debug" in debug
    assert "leases" in debug["debug"]
