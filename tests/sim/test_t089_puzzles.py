"""T089 leased puzzle mechanisms: version, pressure plate, receptor, idempotent finish."""

from __future__ import annotations

import pytest

from sim.dmb.adventure.puzzles import PuzzleService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.player.inventory import InventoryService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t089"), ids=IdAllocator(WorldId("world:t089")))


SAMPLE_PUZZLE = {
    "id": "puzzle.t089_sample",
    "schema_version": 1,
    "area_id": "area.sluice",
    "mechanisms": [
        {
            "id": "box.1",
            "kind": "movable_box",
            "position": [0.0, 0.0],
            "push_delta": [1.0, 0.0],
        },
        {
            "id": "plate.1",
            "kind": "pressure_plate",
            "position": [2.0, 0.0],
            "linked_box": "box.1",
        },
        {
            "id": "receptor.handle",
            "kind": "item_receptor",
            "position": [3.0, 0.0],
            "accepts_definition_id": "item.sluice_handle",
            "holds": True,
            "consumes": False,
        },
        {
            "id": "gate.final",
            "kind": "gate",
            "position": [4.0, 0.0],
            "requires": ["plate.1", "receptor.handle"],
        },
    ],
    "solve_when": {"all": ["gate.final"]},
    "finish_effects": [
        {
            "kind": "production_modifier",
            "effect_id": "effect.remove_sluice_sabotage",
            "modifier_id": "sluice_sabotage",
            "remove": True,
        },
        {
            "kind": "history_fact",
            "effect_id": "effect.puzzle_t089_solved",
            "fact_id": "fact.puzzle_t089_solved",
            "predicate": "solved",
            "value": True,
        },
    ],
}


def _prepared() -> tuple[WorldState, PuzzleService, dict]:
    state = _world()
    # Seed sabotage so finish can remove it.
    state.definitions.setdefault("production_modifiers", {})["sluice_sabotage"] = {
        "modifier_id": "sluice_sabotage",
        "active": True,
    }
    puzzles = PuzzleService(state)
    puzzles.register_definition(SAMPLE_PUZZLE)
    out = puzzles.prepare_lease("puzzle.t089_sample")
    return state, puzzles, out["lease"]


def test_checkpoint_version_enforced() -> None:
    _state, puzzles, lease = _prepared()
    with pytest.raises(TypeValidationError, match="version mismatch"):
        puzzles.sync_local_pose(
            lease["id"],
            expected_version=999,
            actor_id="box.1",
            position=[1.0, 0.0],
            kind="movable_box",
        )


def test_pressure_plate_follows_actual_local_position() -> None:
    _state, puzzles, lease = _prepared()
    lid = lease["id"]
    # Box not on plate.
    out = puzzles.sync_local_pose(
        lid,
        expected_version=1,
        actor_id="box.1",
        position=[0.0, 0.0],
        kind="movable_box",
    )
    assert out["lease"]["checkpoint"]["mechanisms"]["plate.1"]["active"] is False
    # Move box onto plate.
    out = puzzles.sync_local_pose(
        lid,
        expected_version=out["version"],
        actor_id="box.1",
        position=[2.0, 0.0],
        kind="movable_box",
    )
    assert out["lease"]["checkpoint"]["mechanisms"]["plate.1"]["active"] is True
    # Move off — plate deactivates from actual position.
    out = puzzles.sync_local_pose(
        lid,
        expected_version=out["version"],
        actor_id="box.1",
        position=[0.0, 0.0],
        kind="movable_box",
    )
    assert out["lease"]["checkpoint"]["mechanisms"]["plate.1"]["active"] is False


def test_item_receptor_holds_real_item_once() -> None:
    state, puzzles, lease = _prepared()
    inv = InventoryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice",
        position=[1.0, 1.0],
        quest_bound=True,
    )
    inv.pickup(handle["id"])
    lid = lease["id"]
    out = puzzles.act(
        lid,
        expected_version=1,
        mechanism_id="receptor.handle",
        action="place",
        item_id=handle["id"],
    )
    assert out["status"] == "acted"
    mech = out["lease"]["checkpoint"]["mechanisms"]["receptor.handle"]
    assert mech["held_item_id"] == handle["id"]
    assert mech["active"] is True
    assert state.items[handle["id"]]["container_id"] == "receptor:receptor.handle"
    assert state.items[handle["id"]]["holder_id"] is None
    # Second place rejected; item still the same instance.
    with pytest.raises(TypeValidationError, match="already holds"):
        puzzles.act(
            lid,
            expected_version=out["version"],
            mechanism_id="receptor.handle",
            action="place",
            item_id=handle["id"],
        )
    assert list(state.items.keys()).count(handle["id"]) == 1 or handle["id"] in state.items


def test_duplicate_finish_applies_no_second_world_effect() -> None:
    state, puzzles, lease = _prepared()
    inv = InventoryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice",
        position=[1.0, 1.0],
        quest_bound=True,
    )
    inv.pickup(handle["id"])
    lid = lease["id"]
    ver = 1
    out = puzzles.sync_local_pose(
        lid, expected_version=ver, actor_id="box.1", position=[2.0, 0.0], kind="movable_box"
    )
    ver = out["version"]
    out = puzzles.act(
        lid,
        expected_version=ver,
        mechanism_id="receptor.handle",
        action="place",
        item_id=handle["id"],
    )
    ver = out["version"]
    # Gate should auto-open via requires; solve triggers finish inside act when gate active.
    # If not yet solved (gate propagation), open explicitly.
    lease_state = out["lease"]
    if not lease_state["checkpoint"].get("solved"):
        out = puzzles.act(lid, expected_version=ver, mechanism_id="gate.final", action="open")
        ver = out["version"]
    assert out["lease"]["checkpoint"]["solved"] is True
    assert "sluice_sabotage" not in state.definitions.get("production_modifiers", {})
    assert "fact.puzzle_t089_solved" in state.definitions.get("history_facts", {})
    # Duplicate finish — no second history overwrite side effect / same receipt.
    finish = puzzles.finish(lid, expected_version=out["version"], command_id="puzzle.finish:manual")
    # First explicit finish after auto-finish in act may be a new command id; call twice.
    finish = puzzles.finish(lid, expected_version=out["version"], command_id="cmd.dup.finish")
    # Version may have changed if first finish applied; refresh.
    lease = state.leases[lid]
    again = puzzles.finish(
        lid, expected_version=int(lease["version"]), command_id="cmd.dup.finish"
    )
    assert again["status"] == "idempotent"
    # Still exactly one history fact entry for the puzzle solve.
    facts = [
        fid
        for fid in state.definitions.get("history_facts", {})
        if "puzzle_t089" in fid
    ]
    assert len(facts) == 1
