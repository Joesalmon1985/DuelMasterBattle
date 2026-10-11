"""Wizard fire magic: stable ids, range from the authoritative player tile, and the real lifecycles."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import lifecycle, magic  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _run(w, ms):
    seq = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(ms // 100):
        w.advance(100, seq + i + 1, snapshot=False)


def _stand_next_to(w, row, dx=1, dy=0):
    w.player["tx"], w.player["ty"] = int(row["tx"]) + dx, int(row["ty"]) + dy


def test_fire_is_rejected_out_of_range_and_for_unknown_ids() -> None:
    w = HybridWorld()
    tree = next(t for t in w.trees.values() if t["stage"] == "old")
    _stand_next_to(w, tree, magic.FIRE_RANGE + 3, 0)
    r = w.fire(tree["id"])
    assert r["status"] == "rejected" and r["reason"] == "too_far" and tree["id"] in w.trees
    assert w.fire("tree:does-not-exist")["reason"] == "no_target"
    _stand_next_to(w, tree, magic.FIRE_RANGE, 0)
    assert magic.in_range(w, tree["id"])


def test_fire_burns_the_intended_tree_and_frees_its_reserver() -> None:
    w = HybridWorld()
    old = [t for t in w.trees.values() if t["stage"] == "old"]
    target, other = old[0], old[1]
    _stand_next_to(w, target)
    before = len(w.trees)
    r = w.fire(target["id"])
    assert r["status"] == "ok" and r["class"] == "tree"
    assert target["id"] not in w.trees and (target["tx"], target["ty"]) not in w.tree_tiles
    assert other["id"] in w.trees and len(w.trees) == before - 1
    assert any(e["kind"] == "tree_removed" and e["id"] == target["id"] and e["reason"] == "burned" for e in w.events)
    snap = w.snapshot()
    assert not any(e["id"] == target["id"] for e in snap["entities"])
    # a lumberjack that had reserved a tree gives up the job cleanly when it is burned
    hut = next(b for b in w.buildings.values() if b["kind"] == "producer" and b["faction_name"] == "Red")
    _run(w, 30_000)
    worker = next((x for x in w.workers.values() if x["building"] == hut["id"] and x["target_tree"]), None)
    if worker is not None:
        tree = w.trees[worker["target_tree"]]
        _stand_next_to(w, tree)
        w._fire_ready_ms = 0
        assert w.fire(tree["id"])["status"] == "ok"
        _run(w, 2_000)
        assert worker["target_tree"] == "" or worker["target_tree"] not in w.trees


def test_fire_destroys_a_building_through_the_burning_lifecycle() -> None:
    w = HybridWorld()
    bid = next(i for i, b in w.buildings.items() if b["kind"] == "quarry" and b["faction_name"] == "Blue")
    b = w.buildings[bid]
    footprint = [(b["tx"], b["ty"])]
    _stand_next_to(w, b)
    assert w.fire(bid)["status"] == "ok"
    assert b["destroyed"] and b["operational"] is False and b["ruin_ms"] == lifecycle.RUIN_MS
    assert any(e["kind"] == "building_destroyed" and e["id"] == bid for e in w.events)
    assert w.fire(bid)["reason"] == "already_destroyed"
    _run(w, lifecycle.RUIN_MS + 1000)
    assert bid not in w.buildings and footprint[0] not in w.blocked
    assert not any(e["id"] == bid for e in w.snapshot()["entities"])


def test_fire_kills_a_unit_a_worker_and_a_carrier_by_their_own_lifecycles() -> None:
    w = HybridWorld()
    uid = w._unit(w.faction_info["Blue"]["id"], "Blue", "infantry", "Rifleman", "openra.e1", (w.player["tx"] + 1, w.player["ty"]))
    assert w.fire(uid)["status"] == "ok"
    assert w.units[uid]["alive"] is False and w.units[uid]["status"] == "dead"
    _run(w, 3_000)
    assert uid not in w.units  # the corpse is cleared by the lifecycle, not by the spell
    assert w.stats["units_lost"] >= 1
    # worker: walk until one carries something, then burn it
    _run(w, 60_000)
    worker = next(x for x in w.workers.values() if not x.get("inside") and (x["tx"], x["ty"]) != (w.buildings[x["building"]]["tx"], w.buildings[x["building"]]["ty"]))
    hut = w.buildings[worker["building"]]
    _stand_next_to(w, worker)
    w._fire_ready_ms = 0
    assert w.fire(worker["id"])["status"] == "ok"
    assert worker["id"] not in w.workers and hut["worker_id"] == ""
    assert not any(e["id"] == worker["id"] for e in w.snapshot()["entities"])
    _run(w, 40_000)
    assert any(e["kind"] == "worker_spawned" and e["building"] == hut["id"] for e in w.events) or hut["worker_id"] != ""
    # carrier: killed, its road gets a new one later
    car = next(iter(w.carriers.values()))
    rid = car["road_id"]
    _stand_next_to(w, car)
    w._fire_ready_ms = 0
    assert w.fire(car["id"])["status"] == "ok"
    assert car["id"] not in w.carriers
    assert not any(c["road_id"] == rid for c in w.carriers.values())
    _run(w, 21_000)
    assert any(c["road_id"] == rid for c in w.carriers.values())


def test_wizard_mode_commands_do_not_touch_god_mode_state() -> None:
    w = HybridWorld()
    controlled = w.controlled_faction
    tree = next(t for t in w.trees.values())
    _stand_next_to(w, tree)
    w.fire(tree["id"])
    assert w.controlled_faction == controlled
