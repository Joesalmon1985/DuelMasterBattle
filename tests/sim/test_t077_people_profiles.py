"""T077 deep person profiles: preferences, goals, dialogue, relationships, vacancy."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.people.registry import (
    PeopleService,
    load_people_content,
    relationship_band,
)


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t077"), ids=IdAllocator(WorldId("world:t077")))


def test_typed_preferences_and_dialogue_profile() -> None:
    state = _world()
    people = PeopleService(state)
    person = people.create_person(
        name="Ada",
        node_id="node:1",
        preferences=[
            {"trait_id": "pref.diligent", "kind": "work", "strength": 2},
            "curious",
            {"trait_id": "pref.loyal", "kind": "social", "strength": 1},
        ],
        dialogue_profile="dialogue.factory_worker",
        goal_ids=["goal.keep_production"],
    )
    assert person["preferences"][0]["trait_id"] == "pref.diligent"
    assert person["preferences"][0]["kind"] == "work"
    assert person["preferences"][1]["trait_id"] == "pref.curious"
    assert person["dialogue_profile"]["profile_id"] == "dialogue.factory_worker"
    assert person["goal_ids"] == ["goal.keep_production"]
    assert person["profile_schema_version"] == 1


def test_promote_preserves_relationships_and_history() -> None:
    state = _world()
    people = PeopleService(state)
    person = people.create_person(name="Ben", node_id="node:1", role="worker")
    pid = person["id"]
    people.set_relationship(pid, "person:other", 40)
    people.add_known_fact(
        pid,
        {
            "id": "fact.shortage",
            "subject": "factory:1",
            "predicate": "production_stopped",
            "value": True,
            "kind": "verified",
        },
    )
    people.set_goals(pid, ["goal.keep_production", "goal.protect_kin"])
    people.append_history(pid, "hist.hired")
    before = state.people[pid]
    asserted = {
        "rels": dict(before["relationship_map"]),
        "facts": list(before["known_facts"]),
        "goals": list(before["goal_ids"]),
        "hist": list(before["history_refs"]),
        "prefs": list(before["preferences"]),
        "dialogue": dict(before["dialogue_profile"]),
    }
    promoted = people.promote_profile(pid, anchor=True, to_leader=True)
    assert promoted["id"] == pid
    assert promoted["role"] == "leader"
    assert promoted["anchor"] is True
    assert "leader" in promoted["profile_flags"]
    assert "anchor" in promoted["profile_flags"]
    assert promoted["relationship_map"] == asserted["rels"]
    assert promoted["known_facts"] == asserted["facts"]
    assert promoted["goal_ids"] == asserted["goals"]
    assert promoted["history_refs"] == asserted["hist"]
    assert promoted["preferences"] == asserted["prefs"]
    assert promoted["dialogue_profile"] == asserted["dialogue"]
    assert relationship_band(40) == 1


def test_death_keeps_tombstone_and_profile_refs() -> None:
    state = _world()
    people = PeopleService(state)
    person = people.create_person(
        name="Cara",
        node_id="node:1",
        dialogue_profile={"profile_id": "dialogue.anchor", "voice_id": "voice.common"},
        goal_ids=["goal.protect_kin"],
        history_refs=["hist.born"],
    )
    pid = person["id"]
    people.record_death(pid, cause_id="cause:flood")
    dead = state.people[pid]
    assert dead["alive"] is False
    assert dead["status"] == "dead"
    assert dead["dialogue_profile"]["profile_id"] == "dialogue.anchor"
    assert dead["goal_ids"] == ["goal.protect_kin"]
    assert dead["history_refs"] == ["hist.born"]
    tomb = state.tombstones[pid]
    assert tomb["kind"] == "person"
    assert tomb["display_name"] == "Cara"
    assert tomb["profile_refs"]["dialogue_profile_id"] == "dialogue.anchor"
    assert tomb["profile_refs"]["goal_ids"] == ["goal.protect_kin"]


def test_production_job_living_anchor_or_explicit_vacancy() -> None:
    state = _world()
    people = PeopleService(state)
    buildings = BuildingService(state)
    plant = buildings.create("building.factory", node_id="node:1", faction_id="f:1", slot_index=0)
    occupied = people.create_person(
        name="Dana",
        node_id="node:1",
        workplace_id=plant["id"],
        job_id="job.factory_worker",
    )
    people.assign_job(occupied["id"], "job.factory_worker", plant["id"])
    slot = people.production_job_occupancy(plant["id"], "job.factory_worker")
    assert slot["vacant"] is False
    assert slot["person_id"] == occupied["id"]
    people.promote_profile(occupied["id"], anchor=True)
    assert state.people[occupied["id"]]["anchor"] is True

    people.displace(occupied["id"])
    vacant = people.ensure_production_job_anchor(plant["id"], "job.factory_worker", node_id="node:1")
    assert vacant["vacant"] is True
    assert vacant["person_id"] is None
    key = f"{plant['id']}:job.factory_worker"
    assert state.definitions["job_vacancies"][key]["vacant"] is True


def test_profile_states_without_replacing_record() -> None:
    state = _world()
    people = PeopleService(state)
    person = people.create_person(name="Eve", node_id="node:1", role="worker")
    pid = person["id"]
    people.apply_profile_state(pid, "anchor", enabled=True)
    people.apply_profile_state(pid, "displaced", enabled=True)
    updated = state.people[pid]
    assert updated["id"] == pid
    assert "anchor" in updated["profile_flags"]
    assert "displaced" in updated["profile_flags"]
    assert updated["status"] == "displaced"
    assert updated["alive"] is True


def test_save_preserves_all_profile_refs() -> None:
    state = _world()
    people = PeopleService(state)
    person = people.create_person(
        name="Finn",
        node_id="node:1",
        preferences=[{"trait_id": "pref.pragmatic", "kind": "work", "strength": 2}],
        dialogue_profile="dialogue.leader",
        goal_ids=["goal.keep_production"],
        cultural_appearance={"culture_id": "culture.north", "appearance_id": "appearance.a"},
        relationship_map={"person:x": 30},
        known_facts=[{"id": "fact.a", "subject": "node:1", "predicate": "safe", "value": True}],
        history_refs=["hist.1"],
        anchor=True,
    )
    pid = person["id"]
    payload = state.to_dict()
    loaded = WorldState.from_dict(payload)
    restored = loaded.people[pid]
    assert restored["preferences"][0]["trait_id"] == "pref.pragmatic"
    assert restored["dialogue_profile"]["profile_id"] == "dialogue.leader"
    assert restored["goal_ids"] == ["goal.keep_production"]
    assert restored["cultural_appearance"]["culture_id"] == "culture.north"
    assert restored["relationship_map"]["person:x"] == 30
    assert restored["known_facts"][0]["id"] == "fact.a"
    assert restored["history_refs"] == ["hist.1"]
    assert restored["anchor"] is True
    assert "anchor" in restored["profile_flags"]


def test_people_content_catalogues_present() -> None:
    content = load_people_content()
    pref_ids = {item["id"] for item in content["preferences"]}
    dialogue_ids = {item["id"] for item in content["dialogue_profiles"]}
    goal_ids = {item["id"] for item in content["goals"]}
    assert "pref.diligent" in pref_ids
    assert "dialogue.factory_worker" in dialogue_ids
    assert "goal.keep_production" in goal_ids
