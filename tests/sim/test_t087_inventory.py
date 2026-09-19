"""T087 persistent inventory: unique IDs, no duplicate transfer, no construction pay."""

from __future__ import annotations

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.player.inventory import InventoryService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t087"), ids=IdAllocator(WorldId("world:t087")))


def test_pickup_drop_revisit_retains_one_id() -> None:
    state = _world()
    inv = InventoryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice",
        position=[3.0, 4.0],
        quest_bound=True,
        label="Handle",
    )
    iid = handle["id"]
    inv.pickup(iid)
    assert state.items[iid]["ground"] is None
    inv.drop(iid, area_id="area.sluice", position=[5.0, 5.0])
    # Revisit / save round-trip — still one ID.
    restored = WorldState.from_dict(state.to_dict())
    assert list(restored.items.keys()) == [iid]
    assert restored.items[iid]["ground"]["area_id"] == "area.sluice"
    assert restored.items[iid]["quantity"] == 1


def test_transfer_cannot_duplicate_quantity() -> None:
    state = _world()
    inv = InventoryService(state)
    stack = inv.spawn_ground(
        definition_id="item.coin",
        area_id="area.v",
        position=[1.0, 1.0],
        quantity=5,
        stackable=True,
    )
    inv.pickup(stack["id"])
    out = inv.give(stack["id"], to_holder="npc:1", quantity=2)
    assert out["status"] == "split"
    assert state.items[stack["id"]]["quantity"] == 3
    given_id = out["given"]["id"]
    assert state.items[given_id]["quantity"] == 2
    total = sum(int(i["quantity"]) for i in state.items.values() if i.get("alive", True))
    assert total == 5


def test_wrong_owner_and_range_rejected() -> None:
    state = _world()
    inv = InventoryService(state)
    item = inv.spawn_ground(definition_id="item.key", area_id="a", position=[0.0, 0.0])
    with pytest.raises(TypeValidationError, match="out of range"):
        inv.pickup(item["id"], in_range=False)
    inv.pickup(item["id"])
    with pytest.raises(TypeValidationError, match="wrong owner"):
        inv.give(item["id"], to_holder="npc:1", from_holder="other")


def test_personal_item_cannot_pay_faction_construction() -> None:
    state = _world()
    inv = InventoryService(state)
    item = inv.spawn_ground(definition_id="item.brick", area_id="a", position=[0.0, 0.0])
    inv.pickup(item["id"])
    with pytest.raises(TypeValidationError, match="faction construction"):
        inv.as_construction_payment(item["id"])
