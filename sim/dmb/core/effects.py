"""Typed cross-system effect application (C07 / T065)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def apply_effect(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    """Route one validated effect once; idempotent by effect_id/command_id."""
    effect_id = effect.get("effect_id") or effect.get("command_id")
    if effect_id:
        receipts = getattr(state, "command_receipts", None)
        if isinstance(receipts, dict) and effect_id in receipts:
            return {"status": "idempotent", "effect_id": effect_id, "result": receipts[effect_id]}

    kind = str(effect.get("kind") or "")
    result: dict[str, Any]
    if kind == "destroy_unit":
        result = _destroy_unit(state, str(effect["target_id"]))
    elif kind == "destroy_person":
        result = _destroy_person(state, str(effect["target_id"]))
    elif kind == "destroy_cart":
        result = _destroy_cart(state, str(effect["target_id"]))
    elif kind == "destroy_building":
        from sim.dmb.construction.buildings import BuildingService

        out = BuildingService(state).destroy(str(effect["target_id"]), cause_id=str(effect_id or ""))
        result = {"status": "destroyed", "target_kind": "building", **out}
    elif kind == "apply_buff":
        from sim.dmb.military.buffs import BuffService

        buff = BuffService(state).apply(
            str(effect["target_id"]),
            str(effect["buff_kind"]),
            game_ms=int(effect.get("game_ms") or state.clock.get("game_ms", 0)),
            command_id=str(effect_id) if effect_id else None,
            frozen=bool(effect.get("frozen", False)),
        )
        result = {"status": "buffed", "buff": buff}
    else:
        raise ValueError(f"unknown effect kind {kind!r}")

    if effect_id and isinstance(getattr(state, "command_receipts", None), dict):
        state.command_receipts[str(effect_id)] = deepcopy(result)
    return result


def _destroy_unit(state: Any, unit_id: str) -> dict[str, Any]:
    unit = state.units.get(unit_id)
    if unit is None:
        return {"status": "missing", "target_id": unit_id, "idempotent": True}
    if not unit.get("alive", True):
        return {"status": "already_destroyed", "target_id": unit_id, "idempotent": True}
    unit["alive"] = False
    unit["current_health"] = 0
    unit["status"] = "dead"
    unit["target_id"] = None
    state.tombstones[unit_id] = {
        "kind": "unit",
        "display_name": unit.get("definition_id", unit_id),
        "faction_id": unit.get("faction_id"),
        "node_id": unit.get("node_id"),
        "alive": False,
    }
    return {"status": "destroyed", "target_kind": "unit", "target_id": unit_id}


def _destroy_person(state: Any, person_id: str) -> dict[str, Any]:
    person = state.people.get(person_id)
    if person is None:
        return {"status": "missing", "target_id": person_id, "idempotent": True}
    if person.get("status") == "dead" or not person.get("alive", True):
        return {"status": "already_destroyed", "target_id": person_id, "idempotent": True}
    person["alive"] = False
    person["status"] = "dead"
    # Clear job assignment consequences.
    person["job_id"] = None
    person["assigned_building_id"] = None
    state.tombstones[person_id] = {
        "kind": "person",
        "display_name": person.get("display_name", person_id),
        "node_id": person.get("node_id"),
        "alive": False,
    }
    return {"status": "destroyed", "target_kind": "person", "target_id": person_id}


def _destroy_cart(state: Any, cart_id: str) -> dict[str, Any]:
    cart = state.carts.get(cart_id)
    if cart is None:
        return {"status": "missing", "target_id": cart_id, "idempotent": True}
    if cart.get("status") == "destroyed" or not cart.get("alive", True):
        return {"status": "already_destroyed", "target_id": cart_id, "idempotent": True}
    cargo = dict(cart.get("cargo") or cart.get("load") or {})
    cart["alive"] = False
    cart["status"] = "destroyed"
    cart["cargo"] = {}
    cart["load"] = {}
    # Lost cargo is not restored to stock — real consequence.
    state.tombstones[cart_id] = {
        "kind": "cart",
        "display_name": cart.get("definition_id", cart_id),
        "node_id": cart.get("current_node") or cart.get("node_id"),
        "lost_cargo": cargo,
        "alive": False,
    }
    return {
        "status": "destroyed",
        "target_kind": "cart",
        "target_id": cart_id,
        "lost_cargo": cargo,
    }
