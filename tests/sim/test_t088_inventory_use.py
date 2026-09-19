"""T088 allowlisted item use/combine and mandatory recovery routes."""

from __future__ import annotations

import pytest

from sim.dmb.adventure.item_recovery import ItemRecoveryService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.player.inventory import InventoryService, load_item_catalog


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t088"), ids=IdAllocator(WorldId("world:t088")))


def test_combine_consumes_exact_inputs_once() -> None:
    state = _world()
    inv = InventoryService(state)
    rope = inv.spawn_ground(definition_id="item.rope", area_id="a", position=[0, 0], quantity=1, stackable=True)
    hook = inv.spawn_ground(definition_id="item.hook", area_id="a", position=[1, 0], quantity=1, stackable=True)
    inv.pickup(rope["id"])
    inv.pickup(hook["id"])
    out = inv.combine(combination_id="combine.rope_hook")
    assert out["status"] == "combined"
    assert state.items[rope["id"]]["alive"] is False
    assert state.items[hook["id"]]["alive"] is False
    result_id = out["result"]["id"]
    assert state.items[result_id]["definition_id"] == "item.grappling_hook"
    assert state.items[result_id]["holder_id"] == "player"
    # Second combine cannot invent materials.
    with pytest.raises(TypeValidationError, match="insufficient"):
        inv.combine(combination_id="combine.rope_hook")


def test_invalid_use_does_not_consume_unrelated_item() -> None:
    state = _world()
    inv = InventoryService(state)
    brick = inv.spawn_ground(definition_id="item.brick", area_id="a", position=[0, 0], quantity=3, stackable=True)
    salve = inv.spawn_ground(
        definition_id="item.herb_salve", area_id="a", position=[1, 0], quantity=2, stackable=True
    )
    inv.pickup(brick["id"])
    inv.pickup(salve["id"])
    with pytest.raises(TypeValidationError, match="no allowlisted uses"):
        inv.use(brick["id"])
    assert state.items[brick["id"]]["quantity"] == 3
    assert state.items[salve["id"]]["quantity"] == 2
    # Wrong target for handle: reject without consume.
    handle = inv.spawn_ground(definition_id="item.sluice_handle", area_id="a", position=[2, 0], quest_bound=True)
    inv.pickup(handle["id"])
    with pytest.raises(TypeValidationError, match="invalid use target"):
        inv.use(handle["id"], target="receptor.wrong")
    assert state.items[handle["id"]]["alive"] is True
    assert state.items[handle["id"]]["holder_id"] == "player"


def test_lost_required_handle_remains_recoverable() -> None:
    state = _world()
    inv = InventoryService(state)
    recovery = ItemRecoveryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice.workshop",
        position=[2.0, 1.0],
        quest_bound=True,
    )
    inv.pickup(handle["id"])
    inv.drop(handle["id"], area_id="area.destroyed_wing", position=[9.0, 9.0])
    assert recovery.is_recoverable("item.sluice_handle")
    out = recovery.open_destroyed_location_route(
        "item.sluice_handle",
        destroyed_area_id="area.destroyed_wing",
        command_id="cmd.recover.handle.1",
    )
    assert out["status"] == "route_opened"
    assert state.items[handle["id"]]["ground"]["area_id"] == "area.sluice.entrance"
    assert recovery.is_recoverable("item.sluice_handle")
    # Idempotent receipt.
    again = recovery.open_destroyed_location_route(
        "item.sluice_handle",
        destroyed_area_id="area.destroyed_wing",
        command_id="cmd.recover.handle.1",
    )
    assert again["status"] == "idempotent"


def test_layout_change_records_one_relocation() -> None:
    state = _world()
    inv = InventoryService(state)
    recovery = ItemRecoveryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice.old_cellar",
        position=[4.0, 4.0],
        quest_bound=True,
    )
    out = recovery.relocate_stranded(
        handle["id"],
        accessible_area_ids={"area.sluice.workshop", "area.sluice.entrance"},
        command_id="cmd.relocate.1",
    )
    assert out["status"] == "relocated"
    assert out["receipt"]["kind"] == "relocation"
    assert state.items[handle["id"]]["ground"]["area_id"] in {
        "area.sluice.workshop",
        "area.sluice.entrance",
    }
    receipts = state.definitions["item_recovery"]
    assert list(receipts.keys()) == ["cmd.relocate.1"]
    # Same command does not double-relocate.
    again = recovery.relocate_stranded(
        handle["id"],
        accessible_area_ids={"area.sluice.workshop", "area.sluice.entrance"},
        command_id="cmd.relocate.1",
    )
    assert again["status"] == "idempotent"
    assert len(state.definitions["item_recovery"]) == 1


def test_valid_use_applies_typed_effects() -> None:
    state = _world()
    inv = InventoryService(state)
    salve = inv.spawn_ground(
        definition_id="item.herb_salve", area_id="a", position=[0, 0], quantity=2, stackable=True
    )
    inv.pickup(salve["id"])
    out = inv.use(salve["id"], use_id="use.apply_salve", command_id="cmd.use.salve")
    assert out["status"] == "used"
    assert out["consumed"] is True
    assert state.items[salve["id"]]["quantity"] == 1
    assert "fact.salve_applied" in state.definitions.get("history_facts", {})


def test_catalog_loads_allowlists() -> None:
    catalog = load_item_catalog()
    assert any(i["id"] == "item.sluice_handle" for i in catalog["items"])
    assert any(c["id"] == "combine.rope_hook" for c in catalog["combinations"])
    assert "item.sluice_handle" in catalog["recovery"]
