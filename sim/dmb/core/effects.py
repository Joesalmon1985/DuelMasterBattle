"""Typed cross-system effect application (C07 / C10 / T065 / T081).

Validate an entire choice's effects before applying any; commit atomically.
Unknown kinds fail before siblings apply. Effect IDs are idempotent.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from sim.dmb.core.types import TypeValidationError
from sim.dmb.narrative.conditions import evaluate_condition

ALLOWED_EFFECT_KINDS = frozenset(
    {
        # Existing combat/destruction (T065)
        "destroy_unit",
        "destroy_person",
        "destroy_cart",
        "destroy_building",
        "apply_buff",
        # C10 narrative / adventure
        "relationship_change",
        "knowledge_reveal",
        "aspect_change",
        "quest_transition",
        "policy_commitment",
        "diplomatic_agreement",
        "item_transfer",
        "production_modifier",
        "conserved_stock_transfer",
        "hazard_treatment",
        "entity_relocation",
        "history_fact",
        "boulder_quest_accept",
    }
)


def validate_effect(effect: dict[str, Any]) -> None:
    kind = str(effect.get("kind") or "")
    if kind not in ALLOWED_EFFECT_KINDS:
        raise TypeValidationError(f"unknown effect kind {kind!r}")
    if not (effect.get("effect_id") or effect.get("command_id")):
        raise TypeValidationError("effect requires effect_id")


def validate_effects(effects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in effects:
        effect = dict(raw)
        validate_effect(effect)
        eid = str(effect.get("effect_id") or effect.get("command_id"))
        if eid in seen:
            # Duplicates in the same batch collapse to one apply.
            continue
        seen.add(eid)
        validated.append(effect)
    return validated


def apply_effect(state: Any, effect: dict[str, Any], *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Route one validated effect once; idempotent by effect_id/command_id."""
    validate_effect(effect)
    effect_id = str(effect.get("effect_id") or effect.get("command_id"))
    receipts = getattr(state, "command_receipts", None)
    if isinstance(receipts, dict) and effect_id in receipts:
        return {"status": "idempotent", "effect_id": effect_id, "result": receipts[effect_id]}

    if effect.get("condition") is not None:
        if not evaluate_condition(state, effect["condition"], context=context):
            return {"status": "condition_failed", "effect_id": effect_id}

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
    elif kind == "relationship_change":
        result = _relationship_change(state, effect)
    elif kind == "knowledge_reveal":
        result = _knowledge_reveal(state, effect)
    elif kind == "aspect_change":
        result = _aspect_change(state, effect)
    elif kind == "quest_transition":
        result = _quest_transition(state, effect)
    elif kind == "policy_commitment":
        result = _policy_commitment(state, effect)
    elif kind == "diplomatic_agreement":
        result = _diplomatic_agreement(state, effect)
    elif kind == "item_transfer":
        result = _item_transfer(state, effect)
    elif kind == "production_modifier":
        result = _production_modifier(state, effect)
    elif kind == "conserved_stock_transfer":
        result = _conserved_stock_transfer(state, effect)
    elif kind == "hazard_treatment":
        result = _hazard_treatment(state, effect)
    elif kind == "entity_relocation":
        result = _entity_relocation(state, effect)
    elif kind == "history_fact":
        result = _history_fact(state, effect)
    elif kind == "boulder_quest_accept":
        from sim.dmb.world.boulder_quest import accept_move

        result = accept_move(
            state,
            helper_person_id=str(effect.get("helper_person_id") or effect.get("person_id") or "") or None,
            effect_id=effect_id,
        )
    else:
        raise TypeValidationError(f"unknown effect kind {kind!r}")

    if result.get("status") == "stale_target":
        return {"status": "stale_target", "effect_id": effect_id, "result": result, "abort": True}

    if isinstance(receipts, dict):
        receipts[effect_id] = deepcopy(result)
    return {"status": result.get("status", "applied"), "effect_id": effect_id, "result": result}


def apply_effects(
    state: Any,
    effects: Iterable[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate all effects first; apply none if any are unknown; abort on stale target."""
    try:
        batch = validate_effects(effects)
    except TypeValidationError as exc:
        return {"ok": False, "applied": [], "error": str(exc), "aborted": True}

    # Revalidate live targets before first mutation.
    for effect in batch:
        stale = _stale_target(state, effect)
        if stale:
            return {
                "ok": False,
                "applied": [],
                "error": "stale_target",
                "aborted": True,
                "rebranch": True,
                "stale": stale,
            }

    applied: list[dict[str, Any]] = []
    snapshot = state.to_dict()
    try:
        for effect in batch:
            out = apply_effect(state, effect, context=context)
            if out.get("abort"):
                restored = type(state).from_dict(deepcopy(snapshot))
                state.__dict__.update(restored.__dict__)
                return {
                    "ok": False,
                    "applied": [],
                    "error": "stale_target",
                    "aborted": True,
                    "rebranch": True,
                    "stale": out,
                }
            applied.append(out)
    except Exception as exc:
        restored = type(state).from_dict(deepcopy(snapshot))
        state.__dict__.update(restored.__dict__)
        return {"ok": False, "applied": [], "error": str(exc), "aborted": True}
    return {"ok": True, "applied": applied, "aborted": False}


def _stale_target(state: Any, effect: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(effect.get("kind") or "")
    target_id = effect.get("target_id")
    if target_id is None:
        return None
    target_id = str(target_id)
    expected_version = effect.get("expected_world_version")
    if expected_version is not None and int(expected_version) != int(state.world_version):
        return {"entity_id": target_id, "reason": "world_version"}
    if kind.startswith("destroy_") or kind in {
        "apply_buff",
        "relationship_change",
        "entity_relocation",
        "item_transfer",
        "hazard_treatment",
    }:
        alive = _find_target(state, target_id)
        if alive is None:
            return {"entity_id": target_id, "reason": "missing"}
        if alive.get("alive") is False or alive.get("status") in {"dead", "destroyed"}:
            return {"entity_id": target_id, "reason": "destroyed"}
    return None


def _find_target(state: Any, entity_id: str) -> dict[str, Any] | None:
    for bucket_name in ("people", "buildings", "units", "carts", "items"):
        bucket = getattr(state, bucket_name, {}) or {}
        if entity_id in bucket:
            return bucket[entity_id]
    return None


def _relationship_change(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    from sim.dmb.people.registry import PeopleService

    person_id = str(effect["target_id"])
    other_id = str(effect.get("other_id") or "player")
    delta = int(effect.get("delta") or 0)
    person = state.people.get(person_id)
    if person is None or not person.get("alive", True):
        return {"status": "stale_target", "target_id": person_id}
    people = PeopleService(state)
    people.ensure_profile_fields(person_id)
    current = int((person.get("relationship_map") or {}).get(other_id, 0))
    people.set_relationship(person_id, other_id, current + delta)
    return {
        "status": "applied",
        "person_id": person_id,
        "other_id": other_id,
        "score": state.people[person_id]["relationship_map"][other_id],
    }


def _knowledge_reveal(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    from sim.dmb.narrative.knowledge import KnowledgeFact, reveal

    entity_id = str(effect["target_id"])
    role = effect.get("role")
    fact = str(effect.get("fact") or "met")
    reveal(state, entity_id, KnowledgeFact(entity_id, fact, role=role), role=role)
    if effect.get("name"):
        state.knowledge[entity_id]["name"] = str(effect["name"])
    return {"status": "applied", "entity_id": entity_id}


def _aspect_change(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    from sim.dmb.narrative.aspects import AspectService

    return AspectService(state).apply_change_once(
        str(effect.get("aspect_id") or effect.get("aspect")),
        int(effect.get("delta") or 0),
        change_id=str(effect.get("effect_id") or effect.get("command_id")),
        actor_id=str(effect.get("actor_id") or "player"),
    )


def _quest_transition(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    quest_id = str(effect["target_id"])
    quest = state.quests.get(quest_id)
    if quest is None:
        return {"status": "stale_target", "target_id": quest_id}
    quest["status"] = str(effect.get("to_status") or quest.get("status"))
    if effect.get("stage") is not None:
        quest["stage"] = effect["stage"]
    if effect.get("branch") is not None:
        quest["branch"] = effect["branch"]
    return {"status": "applied", "quest_id": quest_id, "quest": dict(quest)}


def _policy_commitment(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    policies = state.definitions.setdefault("policies", {})
    key = str(effect.get("policy_id") or effect["effect_id"])
    policies[key] = {
        "policy_id": key,
        "faction_id": effect.get("faction_id"),
        "commitment": effect.get("commitment"),
        "active": True,
    }
    return {"status": "applied", "policy_id": key}


def _diplomatic_agreement(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    diplo = state.definitions.setdefault("diplomacy", {})
    key = str(effect.get("agreement_id") or effect["effect_id"])
    diplo[key] = {
        "agreement_id": key,
        "parties": list(effect.get("parties") or []),
        "terms": effect.get("terms"),
        "active": True,
    }
    return {"status": "applied", "agreement_id": key}


def _item_transfer(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    item_id = str(effect["target_id"])
    item = state.items.get(item_id)
    if item is None:
        return {"status": "stale_target", "target_id": item_id}
    # One container: clear prior holder then set new.
    new_container = effect.get("to_container")
    new_ground = effect.get("to_ground")
    item["container_id"] = new_container
    item["ground"] = new_ground
    item["holder_id"] = effect.get("to_holder")
    return {"status": "applied", "item_id": item_id, "item": dict(item)}


def _production_modifier(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    mods = state.definitions.setdefault("production_modifiers", {})
    key = str(effect.get("modifier_id") or effect["effect_id"])
    if effect.get("remove"):
        mods.pop(key, None)
        return {"status": "removed", "modifier_id": key}
    mods[key] = {
        "modifier_id": key,
        "target_id": effect.get("target_id"),
        "kind": effect.get("modifier_kind") or effect.get("tag"),
        "active": True,
        "value": effect.get("value"),
    }
    return {"status": "applied", "modifier_id": key}


def _conserved_stock_transfer(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    """Transfer construction stock without minting; cart rules remain owner-side."""
    good = str(effect.get("good") or effect.get("resource_id") or "")
    amount = int(effect.get("amount") or 0)
    if amount <= 0 or not good:
        raise TypeValidationError("conserved transfer requires positive amount and good")
    if effect.get("mint"):
        raise TypeValidationError("conserved transfer cannot mint goods")
    if effect.get("bypass_cart"):
        raise TypeValidationError("conserved transfer cannot bypass cart rules")
    source_id = str(effect.get("from_store") or effect.get("from_id") or "")
    dest_id = str(effect.get("to_store") or effect.get("to_id") or "")
    stocks = state.stocks if isinstance(state.stocks, dict) else {}
    source = stocks.setdefault(source_id, {}) if source_id else None
    dest = stocks.setdefault(dest_id, {}) if dest_id else None
    if source is None or dest is None:
        raise TypeValidationError("conserved transfer requires from_store and to_store")
    available = int(source.get(good) or 0)
    if available < amount:
        raise TypeValidationError("insufficient stock for conserved transfer")
    source[good] = available - amount
    dest[good] = int(dest.get(good) or 0) + amount
    return {
        "status": "applied",
        "good": good,
        "amount": amount,
        "from_store": source_id,
        "to_store": dest_id,
    }


def _hazard_treatment(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    cube_id = str(effect["target_id"])
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    cube = cubes.get(cube_id)
    if cube is None or not cube.get("active", True):
        return {"status": "stale_target", "target_id": cube_id}
    cube["active"] = False
    cube["treated"] = True
    cube["treatment_id"] = effect.get("effect_id")
    return {"status": "applied", "cube_id": cube_id}


def _entity_relocation(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(effect["target_id"])
    record = _find_target(state, entity_id)
    if record is None or record.get("alive") is False:
        return {"status": "stale_target", "target_id": entity_id}
    if effect.get("node_id") is not None:
        record["node_id"] = effect["node_id"]
    if effect.get("grid") is not None:
        record["grid"] = list(effect["grid"])
    if effect.get("position") is not None:
        record["position"] = list(effect["position"])
    return {"status": "applied", "entity_id": entity_id, "record": dict(record)}


def _history_fact(state: Any, effect: dict[str, Any]) -> dict[str, Any]:
    history = state.definitions.setdefault("history_facts", {})
    fact_id = str(effect.get("fact_id") or effect["effect_id"])
    history[fact_id] = {
        "fact_id": fact_id,
        "subject": effect.get("subject") or effect.get("target_id"),
        "predicate": effect.get("predicate"),
        "value": effect.get("value"),
        "refs": list(effect.get("refs") or []),
    }
    person_id = effect.get("person_id")
    if person_id and person_id in state.people:
        from sim.dmb.people.registry import PeopleService

        PeopleService(state).append_history(str(person_id), fact_id)
    return {"status": "applied", "fact_id": fact_id}


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
