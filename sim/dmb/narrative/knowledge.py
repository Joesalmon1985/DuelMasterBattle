"""Knowledge filtering and semantic observation tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError


@dataclass(frozen=True)
class KnowledgeFact:
    entity_id: str
    fact: str
    role: str | None = None


def filter_entity(state: WorldState, entity_id: str) -> dict[str, Any]:
    record = state.knowledge.get(entity_id)
    if not record:
        return {"entity_id": entity_id, "label": "unknown", "known": False, "name": None}
    name = record.get("name")
    role = record.get("role")
    # known == personal name learned; role may be known earlier via Observe.
    if name:
        label = str(name)
        known = True
    elif role:
        label = str(role)
        known = False
    else:
        label = str(record.get("fact") or "unknown")
        known = False
    return {
        "entity_id": entity_id,
        "label": label,
        "known": known,
        "name": name,
        "role": role,
    }


def reveal(state: WorldState, entity_id: str, fact: KnowledgeFact | str, *, role: str | None = None) -> None:
    if isinstance(fact, KnowledgeFact):
        state.knowledge[entity_id] = {
            "fact": fact.fact,
            "role": fact.role,
            "name": None,
            "known": True,
        }
    else:
        state.knowledge[entity_id] = {"fact": fact, "role": role, "name": None, "known": True}


def mint_token(state: WorldState, entity_id: str, *, visible: bool, in_range: bool) -> dict[str, Any]:
    if not visible or not in_range:
        raise TypeValidationError("remote/invisible magic target token cannot be minted")
    view = filter_entity(state, entity_id)
    return {"token": f"obs:{entity_id}", "view": view}


def player_projection(state: WorldState) -> dict[str, Any]:
    people = {}
    for entity_id in state.people:
        people[entity_id] = filter_entity(state, entity_id)
    return {
        "world_id": state.world_id,
        "people": people,
        # debug-only fields intentionally omitted from player projection
    }


def debug_projection(state: WorldState) -> dict[str, Any]:
    payload = player_projection(state)
    payload["debug"] = {
        "leases": dict(state.leases),
        "command_receipts": dict(state.command_receipts),
        "knowledge_raw": dict(state.knowledge),
    }
    return payload
