"""T059 individual unit, formation and buff state."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.buffs import BuffService
from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.units import MilitaryService, era_factor


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t059"))


def test_spawn_unique_ids_and_era_once() -> None:
    state = _world()
    mil = MilitaryService(state)
    a = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:1",
        faction_id="faction:a",
        era="prehistoric",
        factory_id="factory:1",
    )
    b = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:1",
        faction_id="faction:a",
        era="historic",
        factory_id="factory:1",
    )
    assert a["id"] != b["id"]
    assert a["max_health"] == 100 * era_factor("prehistoric")
    assert a["derived_attack"] == 15
    assert b["max_health"] == 100 * era_factor("historic")
    assert b["derived_attack"] == 15 * 10
    assert b["base_attack"] == 15
    # era applied once — derived_attack already includes factor
    assert b["derived_attack"] == b["base_attack"] * b["era_factor"]


def test_unit_belongs_to_at_most_one_formation() -> None:
    state = _world()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u1 = mil.spawn("unit.ancient.skirmisher", home_node_id="node:1", faction_id="faction:a", era="prehistoric", factory_id="f")
    u2 = mil.spawn("unit.ancient.line", home_node_id="node:1", faction_id="faction:a", era="prehistoric", factory_id="f")
    director.group([u1["id"], u2["id"]], faction_id="faction:a", node_id="node:1")
    try:
        director.group([u1["id"]], faction_id="faction:a", node_id="node:1")
        raise AssertionError("expected double-group failure")
    except ValueError as exc:
        assert "already in formation" in str(exc)
    director.assert_exclusive_membership()


def test_health_buff_shield_roundtrip() -> None:
    state = _world()
    mil = MilitaryService(state)
    buffs = BuffService(state)
    unit = mil.spawn(
        "unit.ancient.heavy",
        home_node_id="node:1",
        faction_id="faction:a",
        era="prehistoric",
        factory_id="f",
        position=[3.5, 4.25],
    )
    buffs.apply(unit["id"], "shield", game_ms=0, command_id="cmd:1")
    buffs.apply(unit["id"], "frequency", game_ms=0, command_id="cmd:2")
    unit["current_health"] = 120
    unit["remaining_attack_cooldown_ms"] = 400
    restored = WorldState.from_dict(state.to_dict())
    runit = restored.units[unit["id"]]
    assert runit["current_health"] == 120
    assert runit["remaining_attack_cooldown_ms"] == 400
    assert runit["position"] == [3.5, 4.25]
    assert runit["shield_remaining"] == 45  # 25% of 180
    assert len(runit["buffs"]) == 2
    assert restored.formations == state.formations
