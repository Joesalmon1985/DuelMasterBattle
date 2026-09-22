"""T082 cause detection and quest binding."""

from __future__ import annotations

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.people.registry import PeopleService
from sim.dmb.quests.binding import QuestBinder
from sim.dmb.quests.causes import CauseTracker


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t082"), ids=IdAllocator(WorldId("world:t082")))
    people = PeopleService(state)
    mara = people.create_person(
        name="Mara",
        node_id="node:v",
        role="worker",
        workplace_id="building:factory",
        job_id="job.factory_worker",
        anchor=True,
    )
    state.buildings["building:factory"] = {
        "id": "building:factory",
        "node_id": "node:v",
        "active": True,
        "definition_id": "building.factory",
    }
    state._mara_id = mara["id"]  # type: ignore[attr-defined]
    return state


def test_revisit_creates_no_duplicate_quest() -> None:
    state = _world()
    tracker = CauseTracker(state)
    binder = QuestBinder(state, tracker)
    binder.register_template(
        {
            "id": "quest.factory_shortage",
            "required_cause": {"kinds": ["factory_output_shortage"]},
            "binding": {"stakeholder_id": state.people[next(iter(state.people))]["id"]},
        }
    )
    events = [
        {
            "kind": "factory_output_shortage",
            "affected_entity_id": "building:factory",
            "stakeholder_id": next(iter(state.people)),
            "site_id": "node:v",
            "template_id": "quest.factory_shortage",
        }
    ]
    first = tracker.observe_changes(events)[0]
    assert first["status"] == "created"
    cause = first["cause"]
    q1 = binder.bind("quest.factory_shortage", cause)
    assert q1["status"] == "bound"
    # Revisit / re-observe same fault.
    second = tracker.observe_changes(events)[0]
    assert second["status"] == "deduped"
    assert second["cause"]["id"] == cause["id"]
    q2 = binder.bind("quest.factory_shortage", cause)
    assert q2["status"] == "deduped"
    assert q2["quest"]["id"] == q1["quest"]["id"]
    assert len(state.quests) == 1


def test_resolve_then_recurring_fault_new_cause() -> None:
    state = _world()
    tracker = CauseTracker(state)
    event = {
        "kind": "factory_output_shortage",
        "affected_entity_id": "building:factory",
        "template_id": "quest.factory_shortage",
    }
    first = tracker.observe_changes([event])[0]["cause"]
    tracker.resolve(first["id"], reason="repaired")
    again = tracker.observe_changes([event])[0]
    assert again["status"] == "created"
    assert again["cause"]["id"] != first["id"]
    assert again["cause"]["occurrence_key"] == first["occurrence_key"]


def test_dead_stakeholder_cannot_be_fabricated() -> None:
    state = _world()
    people = PeopleService(state)
    mara_id = next(iter(state.people))
    people.record_death(mara_id, cause_id="cause:x")
    tracker = CauseTracker(state)
    binder = QuestBinder(state, tracker)
    binder.register_template(
        {
            "id": "quest.factory_shortage",
            "required_cause": {"kinds": ["factory_output_shortage"]},
            "binding": {"stakeholder_id": mara_id},
        }
    )
    cause = tracker.observe_changes(
        [
            {
                "kind": "factory_output_shortage",
                "affected_entity_id": "building:factory",
                "stakeholder_id": mara_id,
                "template_id": "quest.factory_shortage",
            }
        ]
    )[0]["cause"]
    with pytest.raises(TypeValidationError, match="dead person"):
        binder.bind("quest.factory_shortage", cause)
