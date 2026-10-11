"""The AI's economic decisions on terrain: where it builds, what it rebuilds, and who is served first.

Level B/D: the live decisions of `ai.py` against the generated map.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["HYBRID_AI"] = "0"

from wizard_rts import ai, construction as con  # noqa: E402
from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.logistics import scan_requests_and_outputs  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _run(w, seconds):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(seconds):
        w.advance(1000, base + i + 1, snapshot=False)


def test_woodcutters_are_placed_beside_trees_and_foresters_beside_woodcutters() -> None:
    w = HybridWorld(507)
    wh = con.faction_warehouse(w, "Blue")
    produce(w, wh["id"], "log", 20)
    site = ai._place_near(w, "Blue", "producer", wh)
    assert site is not None
    b = w.buildings[site]
    here = ai._trees_near(w, (b["tx"], b["ty"]))
    assert here >= 20, here  # a real stand of trees within its reach
    for b2 in [x for x in w.buildings.values() if x["faction_name"] == "Blue"]:
        b2.pop("constructing", None)
    forester = ai._place_near(w, "Blue", "ranger", wh)
    assert forester is not None
    fb = w.buildings[forester]
    cutters = [x for x in w.buildings.values() if x["faction_name"] == "Blue" and ai._policy(x["kind"]) == "woodcutter"]
    assert min(abs(fb["tx"] - c["tx"]) + abs(fb["ty"] - c["ty"]) for c in cutters) <= 12


def test_a_worked_out_mine_is_replaced_where_the_deposit_remains() -> None:
    w = HybridWorld(507)
    w.ai_aggressive = False
    wh = con.faction_warehouse(w, "Red")
    for b in w.buildings.values():
        if b["faction_name"] == "Red" and b["kind"] == "mine":
            b["deposit_exhausted"] = True
    produce(w, wh["id"], "log", 30)
    produce(w, wh["id"], "plank", 30)
    produce(w, wh["id"], "granite", 10)
    before = {b["id"] for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "mine"}
    for k in range(60):
        for b in list(w.buildings.values()):
            if b["faction_name"] == "Red" and b.get("constructing") and b["kind"] != "mine":
                b.pop("constructing", None)
                b["operational"] = True
        ai.economy_step(w, "Red")
        if {b["id"] for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "mine"} - before:
            break
    new = [b for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "mine" and b["id"] not in before]
    assert new, "no replacement mine"
    assert w.resource_total((new[0]["tx"], new[0]["ty"]), 2, "coal") > 0  # built on coal that is still there


def test_construction_sites_are_served_before_the_sawmill() -> None:
    w = HybridWorld(507)
    w.ai_enabled = False
    wh = con.faction_warehouse(w, "Red")
    sawmill = next(b for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "processor")
    from wizard_rts.economy import _supply

    for b in w.buildings.values():
        have = int(w.stocks.get(b["id"], {}).get("log", 0))
        if have:
            _supply(w, b["id"]).remove_wares("log", have)
    produce(w, wh["id"], "log", 3)
    res = None
    for r in range(4, 20):
        res = w.build("Red", "producer", wh["tx"] + r, wh["ty"] + 5)
        if res["status"] == "ok":
            break
    assert res["status"] == "ok"
    w.road("Red", res["id"], wh["id"])
    w.events.clear()
    scan_requests_and_outputs(w)
    filled = [e for e in w.events if e["kind"] == "request_filled" and e["good"] == "log"]
    assert filled and filled[0]["building"] == res["id"], filled  # the site's request was filled first
    assert sawmill["id"] != res["id"]
