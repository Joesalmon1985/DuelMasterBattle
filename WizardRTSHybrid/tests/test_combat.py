"""OpenRA-rule combat: ranges, reload, projectile flight, Versus armor, buildings, turrets, cleanup, AI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import rules  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _world() -> HybridWorld:
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    return w


def _step(w: HybridWorld, quanta: int) -> None:
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(quanta):
        w.advance(100, base + i + 1, snapshot=False)


DEFS = {"tank": "openra.3tnk", "infantry": "openra.e1", "soldier": "widelands.soldier"}


def _unit(w: HybridWorld, faction: str, kind: str, tile: tuple[int, int] | None = None):
    """A fresh unit; every starting unit is removed first so the duel is isolated."""
    if w.units and not getattr(w, "_isolated", False):
        w.units.clear()
        w._isolated = True
    return w.units[w._unit(w.faction_info[faction]["id"], faction, kind, kind, DEFS[kind], tile or (0, 0))]


def _open_tile(w: HybridWorld, near: tuple[int, int]) -> tuple[int, int]:
    for r in range(0, 30):
        for dx in range(-r, r + 1):
            t = (near[0] + dx, near[1] + r)
            line = [(t[0] + k, t[1]) for k in range(0, 8)]
            if all(w.tile_in_map(*c) and c not in w.blocked and c not in w.tree_tiles and c not in w.road_tile_set for c in line):
                return t
    raise AssertionError("no open ground")


def test_rules_come_from_openra_data() -> None:
    e1, tank = rules.actor("openra.e1"), rules.actor("openra.3tnk")
    assert (e1["hp"], tank["hp"], tank["armor"]) == (5000, 60000, "Heavy")
    carbine, shell = rules.weapon("M1Carbine"), rules.weapon("105mm")
    assert carbine["range"] == 5.0 and carbine["reload"] == 20 and shell["range"] == 4.75 and shell["burst"] == 2
    assert shell["warheads"][0]["versus"]["None"] == 30 and carbine["warheads"][0]["versus"]["Heavy"] == 10
    assert rules.ms_per_cell(54) == 758 and rules.ms_per_cell(64) == 640


def test_tank_beats_rifleman_with_exact_versus_damage_and_reload() -> None:
    w = _world()
    base = w.buildings[next(i for i, b in w.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Red")]
    t = _open_tile(w, (base["tx"] + 8, base["ty"] + 6))
    tank, rifle = _unit(w, "Red", "tank", t), _unit(w, "Blue", "infantry", (t[0] + 4, t[1]))
    tank_hp, rifle_hp = tank["hp"], rifle["hp"]
    _step(w, 1)
    assert rifle["hp"] == rifle_hp  # the shell is still in the air (flight time from projectile speed)
    _step(w, 14)
    hits = [e for e in w.events if e["kind"] == "unit_hit" and e["unit"] == rifle["id"]]
    assert hits and hits[0]["dealt"] == 1200  # 4000 * Versus None 30 %
    rifle_hits = [e for e in w.events if e["kind"] == "unit_hit" and e["unit"] == tank["id"]]
    assert rifle_hits and rifle_hits[0]["dealt"] == 100  # 1000 * Versus Heavy 10 %
    assert tank["cooldown_ms"] <= 2800  # 70 ticks of reload
    _step(w, 200)
    assert rifle["alive"] is False and tank["alive"] is True and tank["hp"] < tank_hp
    assert rifle["id"] in [e["id"] for e in w.events if e["kind"] == "destroyed"]
    _step(w, 30)
    assert rifle["id"] not in w.units  # the corpse is removed


def test_out_of_range_units_do_not_shoot() -> None:
    w = _world()
    base = w.buildings[next(i for i, b in w.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Red")]
    t = _open_tile(w, (base["tx"] + 8, base["ty"] + 6))
    tank, rifle = _unit(w, "Red", "tank", t), _unit(w, "Blue", "infantry", (t[0] + 12, t[1]))
    _step(w, 40)
    assert rifle["hp"] == rifle["max_hp"] and tank["hp"] == tank["max_hp"]


def test_tank_shells_a_widelands_warehouse_in_steps_of_versus_wood() -> None:
    w = _world()
    target = next(i for i, b in w.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Blue")
    b = w.buildings[target]
    assert b["max_hp"] == 50_000 and b["armor"] == "Wood"
    t = _open_tile(w, (b["tx"] - 10, b["ty"] + 3))
    tank = _unit(w, "Red", "tank", t)
    w.order(tank["id"], target)
    _step(w, 120)
    lost = b["max_hp"] - b["hp"]
    assert lost > 0 and lost % 3000 == 0  # 4000 * Wood 75 %


def test_widelands_soldier_hurts_an_openra_building() -> None:
    w = _world()
    target = next(i for i, b in w.buildings.items() if b["kind"] == "barracks" and b["faction_name"] == "Blue")
    b = w.buildings[target]
    t = _open_tile(w, (b["tx"] - 6, b["ty"] + 3))
    soldier = _unit(w, "Red", "soldier", t)
    assert soldier["max_hp"] == 13000 and soldier["weapon"] == "WL_Axe"
    w.order(soldier["id"], target)
    _step(w, 400)
    assert b["hp"] < b["max_hp"] and (b["max_hp"] - b["hp"]) % 1400 == 0 or b["hp"] <= 0


def test_turret_shoots_enemy_units_in_range() -> None:
    w = _world()
    turret = next(b for b in w.buildings.values() if b["kind"] == "defense" and b["faction_name"] == "Purple")
    rifle = _unit(w, "Red", "infantry", (turret["tx"] + 3, turret["ty"]))
    hp = rifle["hp"]
    _step(w, 40)
    assert rifle["hp"] < hp
    assert next(e for e in w.events if e["kind"] == "unit_hit" and e["unit"] == rifle["id"])["dealt"] == 1200  # 6000 * None 20 %


def test_destroyed_building_burns_then_is_removed_with_its_roads_and_stock() -> None:
    w = _world()
    bar = next(i for i, b in w.buildings.items() if b["kind"] == "barracks" and b["faction_name"] == "Red")
    roads = [r for r, (a, c) in w.road_edges.items() if bar in (a, c)]
    assert roads
    w.damage_building(bar, 10**9, ["structure"], {})
    assert bar in w.buildings and w.buildings[bar]["operational"] is False
    _step(w, 160)
    assert bar not in w.buildings and bar not in w.stocks
    assert all(r not in w.roads for r in roads) and not [c for c in w.carriers.values() if c["road_id"] in roads]
    assert (w.units and True)


def test_ai_builds_recruits_and_attacks_without_free_goods() -> None:
    w = _world()
    w.ai_enabled = True
    before = {n: sum(1 for b in w.buildings.values() if b["faction_name"] == n and b["kind"] == "producer") for n in w.faction_info}
    # a Red squad already exists (as if the economy had delivered it): the AI should use it
    for _ in range(7):
        w._unit(w.faction_info["Red"]["id"], "Red", "infantry", "Rifleman", "openra.e1", _open_tile(w, (w.player["tx"] + 12, w.player["ty"] + 6)))
    _step(w, 6000)  # 10 game minutes
    after = {n: sum(1 for b in w.buildings.values() if b["faction_name"] == n and b["kind"] == "producer" and int(b["hp"]) > 0) for n in w.faction_info}
    assert after["Red"] >= 2 and sum(after.values()) >= 8, after  # the attacked faction may have lost some
    assert any(e["kind"] == "ai_attack" for e in w.events) or w.stats["attack"] > 0
    # nothing was free: every unit built by the AI consumed an ax or granite and plank
    made = w.stats.get("recruited", 0)
    assert made <= w.stats.get("consumed_ax", 0) + w.stats.get("consumed_granite", 0) // 2
