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
    fishing = any(c == "findspace" and a.get("resource") == "fish" for p in (wl_defs.worker_programs(r) or {} for r in spec["worker_for_program"].values()) for steps in p.values() for c, a in steps)
    w = HybridWorld(minimal=True, terrain=fishing)  # fishing sites need real water: they run on the generated terrain
    fid = w.faction_info["Red"]["id"]
    wh = next(b for b in w.buildings.values() if b["kind"] == "warehouse")
    base = (wh["tx"] + 10, wh["ty"])
    if fishing:
        lx, ly = w.terrain.meta["homes"][0]["lake"]
        base = next(p for r in range(8, 16) for p in __import__("wizard_rts.grid", fromlist=["ring"]).ring(lx, ly, r) if w.terrain.can_build(p[0], p[1], "small"))
    bid = w._building(fid, "Red", spec["kind"], base, spec["label"], spec["definition"])
    if fishing:  # a fish breeder only has work where the grounds were fished down
        for dy in range(-9, 10):
            for dx in range(-9, 10):
                x, y = base[0] + dx, base[1] + dy
                if w.terrain.in_bounds(x, y) and w.terrain.res_kind[y * w.terrain.w + x] == 5:
                    w.terrain.res_amt[y * w.terrain.w + x] //= 2
    for res in (RESOURCES if not fishing else ()):
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
    from wizard_rts import imm

    slots = sorted(
        ((base[0] + dx, base[1] + dy) for dx in range(-5, 0) for dy in range(-5, 6)),
        key=lambda t: (abs(t[0] - base[0]) + abs(t[1] - base[1]), t),
    )
    seen_attr: set[str] = set()
    for imm_name, info in wl_defs.defs()["immovables"].items():
        attrs = info["attributes"]
        if any(a.startswith(("ripe_", "tree_")) and not a.endswith(("sapling", "pole")) and a not in ("ripe_wheat", "tree") for a in attrs) or ("normal_tree" in attrs and imm_name.endswith("_old")) or "flowering" in attrs:
            if all(a in seen_attr for a in attrs):
                continue  # one object per attribute is enough for the bench
            seen_attr.update(attrs)
            while slots and (slots[0] in w.tree_tiles or slots[0] in w.blocked):
                slots.pop(0)
            if slots:
                imm.make(w, slots.pop(0), imm_name)
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
        planted = w.stats.get("saplings_planted", 0) + w.stats.get("fields_planted", 0) + w.stats.get("recruited", 0) + w.stats.get("breed_fish", 0)
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
