"""The lumberjack scenario: real tree, real walk, real log, separate carrier."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402


def _red(world: HybridWorld, kind: str) -> str:
    return next(i for i, b in world.buildings.items() if b["kind"] == kind and b["faction_name"] == "Red")


def _run(world: HybridWorld, until, limit_ms: int = 600_000) -> int:
    seq = world.dmb.clock.get("clock_sequence", 0)
    for step in range(limit_ms // 100):
        world.advance(100, int(seq) + step + 1)
        if until():
            return step
    raise AssertionError("condition not reached")


def test_lumberjack_fells_real_tree_and_carrier_delivers() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    hut = _red(world, "producer")
    warehouse = _red(world, "warehouse")
    start_ids = set(world.trees)
    old_trees = {i for i, t in world.trees.items() if t["stage"] == "old"}
    assert len(old_trees) >= 5
    assert world.stocks[hut].get("log", 0) == 0

    _run(world, lambda: any(e["kind"] == "tree_reserved" for e in world.events))
    reserved = next(e for e in world.events if e["kind"] == "tree_reserved" and e["tree"] in old_trees)
    tree_id = reserved["tree"]
    worker = world.workers[reserved["worker"]]
    assert worker["role"] == "lumberjack" and world.trees[tree_id]["reserved_by"] == worker["id"]

    # He is walking, not teleporting: the tile changes one step at a time.
    seen = []
    _run(world, lambda: (seen.append((worker["tx"], worker["ty"])) or worker["anim"] == "hack"))
    steps = [b for a, b in zip(seen, seen[1:]) if a != b]
    assert steps and all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1 for a, b in zip(seen, seen[1:]) if a != b)
    assert (worker["tx"], worker["ty"]) == (world.trees[tree_id]["tx"], world.trees[tree_id]["ty"])
    assert world.stocks[hut].get("log", 0) == 0 and not world.node_wares.get(hut)

    # Chopping takes real time; the tree is still standing partway through.
    _run(world, lambda: worker["wait_ms"] <= 8_000)
    assert world.trees[tree_id]["stage"] == "old"
    _run(world, lambda: world.trees[tree_id]["stage"] == "felled")
    assert world.stocks[hut].get("log", 0) == 0 and not world.node_wares.get(hut)  # carried, not yet stored
    _run(world, lambda: worker["carrying"] == "log")
    created = [e for e in world.events if e["kind"] == "log_created" and e["worker"] == worker["id"]]
    assert created and created[-1]["tree"] == tree_id

    _run(world, lambda: any(e["kind"] == "ware_stored" and e["worker"] == worker["id"] for e in world.events))
    # carried home, into the hut output; carrier is a different entity
    carrier = next(c for c in world.carriers.values() if hut in world.road_edges[c["road_id"]])
    assert carrier["id"] != worker["id"]
    _run(world, lambda: any(e["kind"] == "pickup" and e["id"] == carrier["id"] and e["from"] == hut for e in world.events))
    def _log_delivered() -> bool:
        return any(e["kind"] == "deliver" and e["dest"] == warehouse and e["good"] == "log" and e["id"] == carrier["id"] for e in world.events)

    _run(world, _log_delivered)
    delivered = [e for e in world.events if e["kind"] == "deliver" and e["dest"] == warehouse and e["good"] == "log"]
    assert delivered and delivered[-1]["id"] == carrier["id"]
    # the felled tree disappears after its fall animation
    _run(world, lambda: tree_id not in world.trees, limit_ms=60_000)
    assert tree_id in old_trees and len(old_trees) >= 1


def test_logs_become_planks_at_sawmill() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    warehouse = _red(world, "warehouse")
    _run(world, lambda: world.stocks[warehouse].get("plank", 0) >= 1, limit_ms=900_000)


def test_ranger_plants_and_sapling_grows() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    _run(world, lambda: any(e["kind"] == "sapling_planted" for e in world.events))
    planted = next(e for e in world.events if e["kind"] == "sapling_planted")
    tree = world.trees[planted["tree"]]
    assert tree["stage"] == "sapling"
    _run(world, lambda: world.trees.get(planted["tree"], {"stage": "gone"})["stage"] in ("pole", "gone"), limit_ms=300_000)


def test_cannot_harvest_before_old_and_depletion() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    hut = _red(world, "producer")
    for tree in world.trees.values():
        if tree["stage"] == "old":
            tree["stage"] = "mature"
            tree["timer_ms"] = 10_000_000
    _run(world, lambda: any(e["kind"] == "worker_failed" and e["reason"] == "no_tree" for e in world.events), limit_ms=120_000)
    assert world.stocks[hut].get("log", 0) == 0


def test_destroyed_workplace_cancels_job_and_releases_tree() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    hut = _red(world, "producer")
    _run(world, lambda: any(e["kind"] == "tree_reserved" for e in world.events))
    reserved = next(e for e in world.events if e["kind"] == "tree_reserved")
    world.damage_building(hut, 10**9, ["structure"], {})
    _run(world, lambda: reserved["worker"] not in world.workers, limit_ms=1_000)
    assert world.buildings[hut]["operational"] is False
    assert reserved["worker"] not in world.workers
    assert world.trees[reserved["tree"]]["reserved_by"] == ""
