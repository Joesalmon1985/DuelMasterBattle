"""Canonical ontology: Person ↔ Unit linkage and no presentation-minted people."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.core.ids import IdAllocator
from sim.dmb.military.units import MilitaryService
from sim.dmb.narrative.semantic import SemanticResolver
from sim.dmb.persistence.migrate import SCHEMA_VERSION, ensure_unit_person_links, migrate_world_dict
from sim.dmb.testing.fixtures import load_fixture


def test_spawn_unit_creates_linked_person():
    state = WorldState(world_id=WorldId("world:ont"), ids=IdAllocator(WorldId("world:ont")))
    mil = MilitaryService(state)
    unit = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:1",
        faction_id="faction:red",
        era="prehistoric",
        factory_id="building:factory",
        position=[2.0, 3.0],
    )
    assert unit["person_id"]
    person = state.people[unit["person_id"]]
    assert person["alive"]
    assert person["unit_id"] == unit["id"]
    assert person["role"] == "soldier"
    assert person["occupation"] == "soldier"
    assert unit["person_name"] == person["name"]


def test_unit_death_kills_linked_person_once():
    state = WorldState(world_id=WorldId("world:ont2"), ids=IdAllocator(WorldId("world:ont2")))
    mil = MilitaryService(state)
    unit = mil.spawn(
        "unit.ancient.skirmisher",
        home_node_id="node:1",
        faction_id="faction:blue",
        era="prehistoric",
        factory_id="building:f",
    )
    pid = unit["person_id"]
    mil.apply_casualties({unit["id"]: 10_000})
    assert unit["alive"] is False
    assert state.people[pid]["alive"] is False
    assert state.people[pid]["status"] == "dead"
    # Idempotent second kill path
    mil.apply_casualties({unit["id"]: 10_000})
    assert state.tombstones[pid]["kind"] == "person"


def test_migration_creates_exactly_one_person_per_legacy_unit():
    world = {
        "world_id": "world:legacy",
        "ids": {"world_id": "world:legacy", "counters": {"unit": 1}},
        "people": {},
        "units": {
            "unit:1": {
                "id": "unit:1",
                "alive": True,
                "status": "available",
                "faction_id": "faction:red",
                "node_id": "node:1",
                "home_node_id": "node:1",
                "definition_id": "unit.ancient.line",
                "person_name": "Tovin",
                "position": [1.0, 1.0],
            }
        },
        "tombstones": {},
    }
    migrated = migrate_world_dict(world, from_schema=1)
    assert migrated["_schema_version"] == SCHEMA_VERSION
    unit = migrated["units"]["unit:1"]
    assert unit["person_id"] in migrated["people"]
    assert migrated["people"][unit["person_id"]]["name"] == "Tovin"
    again = migrate_world_dict(migrated, from_schema=2)
    assert len(again["people"]) == 1
    assert again["units"]["unit:1"]["person_id"] == unit["person_id"]


def test_fx_battle_units_have_person_ids():
    sim = load_fixture("FX-BATTLE", seed=404)
    ensure_unit_person_links(sim.state)
    living = [u for u in sim.state.units.values() if u.get("alive", True)]
    assert living
    for unit in living:
        assert unit.get("person_id") in sim.state.people
        person = sim.state.people[unit["person_id"]]
        assert person.get("unit_id") == unit["id"]


def test_soldier_semantic_includes_talk():
    sim = load_fixture("FX-BATTLE", seed=404)
    ensure_unit_person_links(sim.state)
    unit_id = next(uid for uid, u in sim.state.units.items() if u.get("alive", True))
    unit = sim.state.units[unit_id]
    # Place wizard beside unit for nearby actions.
    sim.state.player["node_id"] = unit.get("node_id")
    sim.state.player["position"] = list(unit.get("position") or [0.0, 0.0])
    resolver = SemanticResolver(sim.state)
    actions = {a["id"] for a in resolver.available_actions(unit_id)}
    assert "observe" in actions
    assert "talk" in actions
    assert "destroy" in actions


def test_industry_does_not_mint_carrier_people():
    sim = load_fixture("FX-INDUSTRY", seed=303)
    before = set(sim.state.people.keys())
    created = sim.industry.projection.sync_carrier_jobs() if hasattr(sim.industry, "projection") else None
    from sim.dmb.industry.projection import IndustryProjection

    proj = IndustryProjection(sim.state)
    minted = proj.sync_carrier_jobs()
    assert minted == []
    after = set(sim.state.people.keys())
    # May vacate old carriers but must not add new person IDs.
    assert after <= before or after == before or True
    new_ids = after - before
    assert not new_ids
    workers = proj.workers()
    for row in workers:
        assert row["person_id"] in sim.state.people
        # Occupation must not be the word "carrier" as identity.
        assert str(row.get("role")) != "carrier" or row.get("occupation")


def test_at_most_one_active_unit_per_person():
    sim = load_fixture("FX-BATTLE", seed=404)
    ensure_unit_person_links(sim.state)
    seen: dict[str, str] = {}
    for uid, unit in sim.state.units.items():
        if not unit.get("alive", True):
            continue
        pid = unit["person_id"]
        assert pid not in seen
        seen[pid] = uid
