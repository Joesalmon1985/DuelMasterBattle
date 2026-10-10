"""Authoritative hybrid world: clock, economy, combat, duel, identity."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.coords import tile_to_hex  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def test_hex_cross_does_not_advance_time() -> None:
    world = HybridWorld()
    start = world.snapshot()
    q, r = start["player"]["hex"]
    # Walk east until the hex changes, or twenty steps.
    tx, ty = start["player"]["tx"], start["player"]["ty"]
    crossed = 0
    for _ in range(40):
        nxt = (tx + 1, ty)
        reply = world.set_pose(*nxt, "right")
        if reply["status"] != "ok":
            break
        tx, ty = nxt
        if reply["snapshot"]["player"]["hex"] != [q, r]:
            crossed += 1
            q, r = reply["snapshot"]["player"]["hex"]
    assert crossed >= 1
    assert world.snapshot()["game_ms"] == 0
    assert world.snapshot()["world_id"] == start["world_id"]
    assert world.entity_ids() == HybridWorld().entity_ids() or world.entity_ids() == start["entity_ids"]


def test_twenty_hex_crossings_keep_one_world() -> None:
    world = HybridWorld()
    world_id = world.snapshot()["world_id"]
    ids = world.entity_ids()
    tx, ty = world.player["tx"], world.player["ty"]
    crossed = 0
    last = tile_to_hex(tx, ty)
    # Serpentine walk across the map.
    for row in range(30):
        direction = 1 if row % 2 == 0 else -1
        for _ in range(40):
            nxt = (tx + direction, ty)
            reply = world.set_pose(nxt[0], nxt[1], "right" if direction > 0 else "left")
            if reply["status"] != "ok":
                break
            tx, ty = nxt
            here = tuple(reply["snapshot"]["player"]["hex"])
            if here != last:
                crossed += 1
                last = here
        step = world.set_pose(tx, ty + 1, "down")
        if step["status"] != "ok":
            break
        ty += 1
        here = tuple(step["snapshot"]["player"]["hex"])
        if here != last:
            crossed += 1
            last = here
        if crossed >= 20:
            break
    assert crossed >= 20
    snap = world.snapshot()
    assert snap["world_id"] == world_id
    assert snap["entity_ids"] == ids
    assert snap["game_ms"] == 0


def test_idle_advance_produces_and_delivers() -> None:
    world = HybridWorld()
    # Clear the hazard so the road is usable, without calling it a duel win.
    cube = world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]
    cube["active"] = False
    before = _total(world, "log")
    world.advance(180_000, 1)
    snap = world.snapshot()
    assert snap["game_ms"] == 180_000
    assert _total(world, "log") + _total(world, "plank") > before
    assert any(event["kind"] == "deliver" for event in world.events)


def test_hazard_blocks_delivery_until_removed() -> None:
    world = HybridWorld()
    red = _faction_named(world, "Red")
    world.advance(120_000, 1)
    assert world.stats["blocked"] > 0
    hut = next(i for i, b in world.buildings.items() if b["kind"] == "producer" and b["faction"] == red)
    assert world.node_wares.get(hut)  # logs wait at the hut: the hazard blocks the road


def test_military_moves_and_resolves_a_hit() -> None:
    world = HybridWorld()
    cube = world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]
    cube["active"] = False
    red = next(i for i, u in world.units.items() if u["kind"] == "tank" and u["faction_name"] == "Red")
    blue = next(i for i, u in world.units.items() if u["kind"] == "tank" and u["faction_name"] == "Blue")
    world.move([red], world.units[blue]["tx"] - 3, world.units[blue]["ty"], attack_move=True)
    for i in range(1500):
        world.advance(100, i + 1)
        if world.stats["attack"] > 0:
            break
    assert world.stats["move"] > 0
    assert world.stats["attack"] > 0


def test_duel_pauses_and_outcomes_differ() -> None:
    won = HybridWorld()
    _walk_to_hazard(won)
    started = won.interact()
    assert started["status"] == "started"
    duel_id = started["payload"]["duel"]["id"]
    paused = won.advance(5_000, 1)
    assert paused["quanta"] == 0
    assert paused["snapshot"]["game_ms"] == 0
    assert paused["snapshot"]["paused"] is True
    resolved = won.resolve(duel_id, True, command_id="cmd-win")
    assert resolved["status"] == "success"
    assert resolved["snapshot"]["hazard_active"] is False
    again = won.resolve(duel_id, True, command_id="cmd-win")
    assert again["status"] == "idempotent"
    resumed = won.advance(10_000, 2)
    assert resumed["quanta"] == 100
    assert resumed["snapshot"]["paused"] is False

    lost = HybridWorld()
    _walk_to_hazard(lost)
    started_loss = lost.interact()
    lost.resolve(started_loss["payload"]["duel"]["id"], False, command_id="cmd-loss")
    assert lost.snapshot()["hazard_active"] is True
    red = _faction_named(lost, "Red")
    lost.advance(240_000, 1)
    assert lost.node_wares.get(next(i for i, b in lost.buildings.items() if b["kind"] == "producer" and b["faction"] == red))
    assert lost.stats["blocked"] > 0


def test_second_advance_is_not_caused_by_hex_cross() -> None:
    world = HybridWorld()
    world.advance(1_000, 1)
    ms = world.snapshot()["game_ms"]
    tx, ty = world.player["tx"], world.player["ty"]
    for _ in range(15):
        reply = world.set_pose(tx + 1, ty, "right")
        if reply["status"] != "ok":
            break
        tx += 1
    assert world.snapshot()["game_ms"] == ms


def _walk_to_hazard(world: HybridWorld) -> None:
    assert world.hazard_tile is not None
    hx, hy = world.hazard_tile
    # Stand on a neighbouring free tile.
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        reply = world.set_pose(hx + dx, hy + dy, "down")
        if reply["status"] == "ok":
            return
    raise AssertionError("no adjacent tile")


def _faction_named(world: HybridWorld, name: str) -> str:
    for building in world.buildings.values():
        if building["faction_name"] == name:
            return str(building["faction"])
    raise AssertionError(name)


def _warehouse(world: HybridWorld, faction: str) -> str:
    for building_id, building in world.buildings.items():
        if building["faction"] == faction and building["kind"] == "warehouse":
            return building_id
    raise AssertionError(faction)


def _total(world: HybridWorld, good: str) -> int:
    return sum(int(stock.get(good, 0)) for stock in world.stocks.values())
