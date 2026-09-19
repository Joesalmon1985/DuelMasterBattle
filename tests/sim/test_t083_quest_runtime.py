"""T083 quest state machine and invalidation."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.quests.runtime import QuestService


def _quest(state: WorldState) -> str:
    qid = state.ids.new("quest")
    state.quests[qid] = {
        "id": qid,
        "status": "offered",
        "stage": 0,
        "stage_count": 4,
        "effect_receipts": [],
        "invalid_target_branch": "displaced_loss",
    }
    return qid


def test_world_fix_first_resolved_by_world() -> None:
    state = WorldState(world_id=WorldId("world:t083"), ids=IdAllocator(WorldId("world:t083")))
    svc = QuestService(state)
    qid = _quest(state)
    svc.accept(qid)
    out = svc.evaluate(qid, world_signals={"world_repaired": True})
    assert out["status"] == "resolved_by_world"
    assert state.quests[qid]["status"] == "resolved_by_world"
    assert state.quests[qid]["resolution"] == "world_fix_first"


def test_target_destruction_follows_declared_branch() -> None:
    state = WorldState(world_id=WorldId("world:t083b"), ids=IdAllocator(WorldId("world:t083b")))
    svc = QuestService(state)
    qid = _quest(state)
    svc.accept(qid)
    out = svc.evaluate(qid, world_signals={"target_destroyed": True})
    assert out["status"] == "failed_with_consequence"
    assert state.quests[qid]["branch"] == "displaced_loss"


def test_simultaneous_choices_reward_once() -> None:
    state = WorldState(world_id=WorldId("world:t083c"), ids=IdAllocator(WorldId("world:t083c")))
    state.people["person:1"] = {
        "id": "person:1",
        "alive": True,
        "relationship_map": {},
        "preferences": [],
        "known_facts": [],
        "history_refs": [],
    }
    svc = QuestService(state)
    qid = _quest(state)
    svc.accept(qid)
    effects = [
        {
            "effect_id": "reward:once",
            "kind": "relationship_change",
            "target_id": "person:1",
            "other_id": "player",
            "delta": 10,
        }
    ]
    a = svc.choose_branch(qid, "demon", effects=effects, choice_id="choice:1")
    b = svc.choose_branch(qid, "demon", effects=effects, choice_id="choice:1")
    assert a["status"] == "chosen"
    assert b["status"] == "idempotent"
    assert state.people["person:1"]["relationship_map"]["player"] == 10


def test_era_flag_alone_neither_completes_nor_cancels() -> None:
    state = WorldState(world_id=WorldId("world:t083d"), ids=IdAllocator(WorldId("world:t083d")))
    svc = QuestService(state)
    qid = _quest(state)
    svc.accept(qid)
    out = svc.evaluate(qid, world_signals={"era_id": "historic", "era_flag": True})
    assert out["status"] == "unchanged"
    assert out["reason"] == "era_flag_alone"
    assert state.quests[qid]["status"] == "active"
