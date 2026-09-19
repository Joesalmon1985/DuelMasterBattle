"""T081 typed conditions and atomic effect dispatcher."""

from __future__ import annotations

import pytest

from sim.dmb.core.effects import apply_effect, apply_effects
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.narrative.conditions import evaluate_condition
from sim.dmb.people.registry import PeopleService


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t081"), ids=IdAllocator(WorldId("world:t081")))
    state.world_version = 5
    state.stocks = {"store:a": {"timber": 3}, "store:b": {"timber": 0}}
    state.people["person:1"] = {
        "id": "person:1",
        "name": "Mara",
        "alive": True,
        "status": "active",
        "relationship_map": {},
        "known_facts": [],
        "history_refs": [],
        "preferences": [],
    }
    state.items["item:1"] = {"id": "item:1", "alive": True, "container_id": None}
    state.quests["quest:1"] = {"id": "quest:1", "status": "active", "stage": 1}
    return state


def test_unknown_effect_fails_before_siblings() -> None:
    state = _world()
    people = PeopleService(state)
    people.ensure_profile_fields("person:1")
    out = apply_effects(
        state,
        [
            {
                "effect_id": "e1",
                "kind": "relationship_change",
                "target_id": "person:1",
                "other_id": "player",
                "delta": 10,
            },
            {"effect_id": "e2", "kind": "totally_fake", "target_id": "person:1"},
        ],
    )
    assert out["ok"] is False
    assert out["aborted"] is True
    assert state.people["person:1"]["relationship_map"] == {}


def test_repeated_effect_id_applies_once() -> None:
    state = _world()
    PeopleService(state).ensure_profile_fields("person:1")
    first = apply_effect(
        state,
        {
            "effect_id": "rel:once",
            "kind": "relationship_change",
            "target_id": "person:1",
            "other_id": "player",
            "delta": 5,
        },
    )
    assert first["status"] != "idempotent"
    second = apply_effect(
        state,
        {
            "effect_id": "rel:once",
            "kind": "relationship_change",
            "target_id": "person:1",
            "other_id": "player",
            "delta": 5,
        },
    )
    assert second["status"] == "idempotent"
    assert state.people["person:1"]["relationship_map"]["player"] == 5


def test_stale_target_aborts_rebranch() -> None:
    state = _world()
    state.people["person:1"]["alive"] = False
    state.people["person:1"]["status"] = "dead"
    out = apply_effects(
        state,
        [
            {
                "effect_id": "e1",
                "kind": "relationship_change",
                "target_id": "person:1",
                "delta": 1,
            }
        ],
    )
    assert out["ok"] is False
    assert out["rebranch"] is True
    assert out["error"] == "stale_target"


def test_conserved_transfer_cannot_mint_or_bypass_cart() -> None:
    state = _world()
    with pytest.raises(TypeValidationError, match="mint"):
        apply_effect(
            state,
            {
                "effect_id": "t1",
                "kind": "conserved_stock_transfer",
                "good": "timber",
                "amount": 1,
                "from_store": "store:a",
                "to_store": "store:b",
                "mint": True,
            },
        )
    with pytest.raises(TypeValidationError, match="bypass"):
        apply_effect(
            state,
            {
                "effect_id": "t2",
                "kind": "conserved_stock_transfer",
                "good": "timber",
                "amount": 1,
                "from_store": "store:a",
                "to_store": "store:b",
                "bypass_cart": True,
            },
        )
    ok = apply_effect(
        state,
        {
            "effect_id": "t3",
            "kind": "conserved_stock_transfer",
            "good": "timber",
            "amount": 2,
            "from_store": "store:a",
            "to_store": "store:b",
        },
    )
    assert ok["result"]["amount"] == 2
    assert state.stocks["store:a"]["timber"] == 1
    assert state.stocks["store:b"]["timber"] == 2


def test_condition_allowlist() -> None:
    state = _world()
    state.knowledge["person:1"] = {"known": True, "fact": "met", "role": "worker"}
    assert evaluate_condition(
        state,
        {
            "op": "all",
            "args": [
                {"op": "has_knowledge", "entity_id": "person:1", "fact": "met"},
                {"op": "quest_state", "quest_id": "quest:1", "status": "active"},
                {"op": "entity_status", "entity_id": "person:1", "status": "active"},
            ],
        },
    )
    with pytest.raises(TypeValidationError, match="unknown condition"):
        evaluate_condition(state, {"op": "eval", "code": "1==1"})
