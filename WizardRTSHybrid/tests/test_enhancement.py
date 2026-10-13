"""Widelands enhancements (metal workshop -> ax workshop -> warmill, brewery, inn, deep mines...) exist only as paid, in-place upgrades."""
from __future__ import annotations

import json

import pytest

from wizard_rts import ai, construction as con, wl_defs
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld


def _run(w, steps):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(steps):
        w.advance(100, base + i + 1, snapshot=False)


def test_every_enhancement_target_costs_wares_and_cannot_be_placed_directly():
    d = wl_defs.defs()["buildings"]
    targets = [n for n, b in d.items() if b.get("enhanced_from") and b.get("runnable")]
    assert len(targets) >= 20
    for n in targets:
        spec = con.build_spec("wl:" + n)
        assert spec["cost"], n  # the old importer left these free
        assert spec["enhancement_of"] == "wl:" + d[n]["enhanced_from"]
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    name = next(f for f, i in w.faction_info.items() if i["tribe"] == "barbarians")
    why, _ctx = con.check_placement(w, name, "wl:barbarians_warmill", 0, 0)
    assert why == "enhancement_only"


def test_enhancing_pays_the_cost_retires_the_worker_and_the_new_building_works():
    w = HybridWorld(507, profile="test_showcase")
    w.ai_enabled = False
    name = next(f for f, i in w.faction_info.items() if i["tribe"] == "barbarians")
    wh = con.faction_warehouse(w, name)
    base_kind = "wl:barbarians_micro_brewery"
    for g, n in con.build_spec(base_kind)["cost"].items():
        produce(w, wh["id"], g, n + 5)
    bid = ai._place_near(w, name, base_kind, wh)
    assert bid  # _place_near also roads the site to the warehouse
    _run(w, 1500)
    b = w.buildings[bid]
    assert b["operational"], "the micro brewery should have been built from stocked wares"
    cost = con.build_spec("wl:barbarians_brewery")["cost"]
    assert cost and cost != con.build_spec(base_kind)["cost"]
    consumed_before = {g: w.stats.get("consumed_" + g, 0) for g in cost}
    for g, n in cost.items():
        produce(w, wh["id"], g, n + 3)
    r = con.enhance_building(w, name, bid)
    assert r["status"] == "ok" and r["kind"] == "wl:barbarians_brewery" and b["kind"] == "wl:barbarians_brewery"
    assert not b["operational"] and b["constructing"]["cost"] == cost and not any(x.get("building") == bid for x in w.workers.values())
    assert con.enhance_building(w, name, bid)["status"] == "rejected"  # the brewery is the end of the line and is under construction
    _run(w, 1500)
    assert b["operational"] and b["kind"] == "wl:barbarians_brewery" and not b.get("constructing")
    for g, n in cost.items():
        assert w.stats.get("consumed_" + g, 0) - consumed_before[g] >= n  # paid for in delivered wares
    assert con.enhance_building(w, name, bid)["reason"] == "not_upgradeable"
