"""Run every runnable Widelands production site in an isolated bench world.

For each building from data/widelands_defs.json the bench places it beside a
warehouse, stocks its input wares (re-stocked every game minute so a recipe
that needs more than the cap still runs), surrounds it with deposits, trees,
fields, rocks and game, and runs it. A building passes when it makes at least
one of its output wares from that setup. Failures keep their reason.

    py -3 WizardRTSHybrid/scripts/verify_generic_buildings.py [--minutes 20] [--only name ...]

Writes docs/generic_building_results.json, which build_catalogue.py reads.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HYBRID = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYBRID))
sys.path.insert(0, str(HYBRID.parent))
os.environ["HYBRID_AI"] = "0"

from wizard_rts import wl_defs  # noqa: E402
from wizard_rts.animals import spawn_animal  # noqa: E402
from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.workers import plant_tree  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

OUT = HYBRID / "docs" / "generic_building_results.json"
RESOURCES = ("coal", "iron", "gold", "stones", "water")


def bench(name: str, minutes: int) -> dict:
    spec = wl_defs.building_spec(name)
    w = HybridWorld(minimal=True)
    fid = w.faction_info["Red"]["id"]
    wh = next(b for b in w.buildings.values() if b["kind"] == "warehouse")
    base = (wh["tx"] + 10, wh["ty"])
    bid = w._building(fid, "Red", spec["kind"], base, spec["label"], spec["definition"])
    for res in RESOURCES:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                w.resources.setdefault((base[0] + dx, base[1] + dy), {})[res] = 8
    for k in range(14):
        tile = (base[0] - 5 + (k % 5) * 2, base[1] + 4 + (k // 5) * 2)
        if tile not in w.blocked and tile not in w.tree_tiles:
            plant_tree(w, tile, "old")
    for k in range(8):
        tile = (base[0] + 3 + k % 4, base[1] - 4 - k // 4)
        if tile not in w.tree_tiles:
            plant_tree(w, tile, "ripe", "wheat")
    for k in range(6):
        tile = (base[0] - 6, base[1] - 5 + k)
        w.rocks[f"rock:b{k}"] = {"id": f"rock:b{k}", "class": "rock", "kind": "rock", "definition": "widelands.rocks", "tx": tile[0], "ty": tile[1], "amount": 6, "reserved_by": ""}
    for k in range(8):
        spawn_animal(w, (base[0] + 6 + k % 3, base[1] + k // 3), "deer")
    caps = dict(spec["inputs"])
    seq = 0
    for minute in range(minutes):
        for good, cap in caps.items():
            have = int(w.stocks[bid].get(good, 0))
            if have < cap:
                produce(w, bid, good, cap - have)
        for _ in range(60):
            seq += 1
            w.advance(1000, seq, snapshot=False)
        made = {g: w.stats.get("made_" + g, 0) for g in spec["outputs"]}
        planted = w.stats.get("saplings_planted", 0) + w.stats.get("fields_planted", 0) + w.stats.get("recruited", 0)
        if (any(made.values()) or (not spec["outputs"] and planted)) and minute >= 2:
            break
    made = {g: w.stats.get("made_" + g, 0) for g in spec["outputs"]}
    shortages = {k[1]: v for k, v in w.shortages.items() if k[0] == bid}
    return {
        "name": name, "tribe": spec["tribe"], "passed": any(made.values()) or (not spec["outputs"] and planted > 0), "planted": planted, "made": made, "outputs": spec["outputs"],
        "game_minutes": minute + 1, "shortages": shortages, "workers": sorted(spec["worker_for_program"].values()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=20)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    names = args.only or wl_defs.runnable_names()
    results = []
    started = time.time()
    for name in names:
        try:
            r = bench(name, args.minutes)
        except Exception as exc:  # noqa: BLE001 - a crashing definition is a result
            r = {"name": name, "passed": False, "error": repr(exc)}
        results.append(r)
        print(f"{'PASS' if r['passed'] else 'FAIL'} {name} {r.get('made', r.get('error', ''))}", flush=True)
    if not args.only:
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    passed = sum(1 for r in results if r["passed"])
    print(f"GENERIC_BUILDINGS passed={passed} of {len(results)} in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
