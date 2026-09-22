"""U05 retained ward duel / soldier observation (updated for Person-linked units)."""

from __future__ import annotations

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture


def test_observe_public_soldier_label_without_forcing_personal_name() -> None:
    sim = load_fixture("FX-BATTLE", seed=404)
    unit_id = next(uid for uid, u in sim.state.units.items() if u.get("alive", True))
    unit = sim.state.units[unit_id]
    assert unit.get("person_id") in sim.state.people
    person_name = unit.get("person_name") or sim.state.people[unit["person_id"]]["name"]
    assert person_name

    env = CommandEnvelope(
        protocol_version=1,
        session_id="s",
        world_id=str(sim.state.world_id),
        command_id="obs:1",
        expected_world_version=sim.state.world_version,
        kind="Observe",
        payload={"entity_id": unit_id},
    )
    result = sim._handle_observe(env)
    assert result.status == "ACCEPTED"
    # Personal name is not forced into knowledge on Observe (Talk reveals it).
    assert not (sim.state.knowledge.get(unit_id) or {}).get("name")
    label = sim.state.board["fx_battle"]["labels"][unit_id]
    assert "Skirmisher" in label or "Line" in label or "Heavy" in label or "Soldier" in label
    # Stable Person link preserved across observes.
    env2 = CommandEnvelope(
        protocol_version=1,
        session_id="s",
        world_id=str(sim.state.world_id),
        command_id="obs:2",
        expected_world_version=sim.state.world_version,
        kind="Observe",
        payload={"entity_id": unit_id},
    )
    sim._handle_observe(env2)
    assert sim.state.units[unit_id]["person_id"] == unit["person_id"]
    assert sim.state.units[unit_id]["person_name"] == person_name


def test_talk_to_soldier_person_reveals_name() -> None:
    sim = load_fixture("FX-BATTLE", seed=404)
    unit_id = next(uid for uid, u in sim.state.units.items() if u.get("alive", True))
    person_id = sim.state.units[unit_id]["person_id"]
    person = sim.state.people[person_id]
    env = CommandEnvelope(
        protocol_version=1,
        session_id="s",
        world_id=str(sim.state.world_id),
        command_id="talk:1",
        expected_world_version=sim.state.world_version,
        kind="Interact",
        payload={"action": "talk", "entity_id": person_id},
    )
    result = sim.dispatch(env)
    assert result.status == "ACCEPTED"
    assert sim.state.knowledge[person_id].get("name") == person.get("name")
