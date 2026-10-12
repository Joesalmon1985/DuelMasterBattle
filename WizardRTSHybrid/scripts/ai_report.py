"""Long deterministic multi-seed AI evaluation with per-faction time series.

    python3 scripts/ai_report.py --minutes 40 --seeds 507 11 23 [--peace]

For every seed the six scripted factions play the real simulation headless (the same commands God Mode issues). Every game minute
each faction is sampled: command centres and territory, buildings and sites, army and navy, recruitment, movement, attacks launched,
defence orders, kills and losses, MCV production and deployment, production stock, blocked tasks (diagnostics.stuck_report). Every
ten minutes a state snapshot is kept. The result goes to docs/evidence/ai_report/<tag>/{metrics.json,REPORT.md}.

The point is not "no crash": `behaviour_checks` fails if the factions do not actually expand, recruit, move, attack and survive.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts import diagnostics, territory  # noqa: E402
from wizard_rts.world import FACTIONS, HybridWorld  # noqa: E402

OUT = HYB / "docs" / "evidence" / "ai_report"
NAVAL = ("naval", "lcraft")
GOODS = ("log", "plank", "granite", "coal", "iron_ore", "iron", "ax")


def sample(world: HybridWorld, last_attack: dict) -> dict:
    now = int(world.dmb.clock.get("game_ms", 0))
    stuck = diagnostics.stuck_report(world)
    row = {"minute": now // 60_000, "factions": {}, "wares_lost": world.stats.get("lost", 0), "stuck_total": len(stuck)}
    for name, _hex, _color in FACTIONS:
        units = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True)]
        army = [u for u in units if u.get("weapon") and u.get("loco") not in NAVAL]
        navy = [u for u in units if u.get("loco") in NAVAL]
        blds = [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]
        ccs = territory.command_centers(world, name)
        fs = world.fstats.get(name, {})
        stock = {g: sum(int(world.stocks.get(b["id"], {}).get(g, 0)) for b in ccs) for g in GOODS}
        cx = sum(u["tx"] for u in army) / len(army) if army else None
        cy = sum(u["ty"] for u in army) / len(army) if army else None
        row["factions"][name] = {
            "alive": bool(ccs), "command_centers": len(ccs), "territory_tiles": sum((2 * territory.radius_of(b) + 1) ** 2 for b in ccs),
            "buildings": len(blds), "sites": sum(1 for b in blds if b.get("constructing")),
            "completed": int(fs.get("buildings_completed", 0)), "ai_builds": int(fs.get("ai_build", 0)),
            "army": len(army), "navy": len(navy), "mcvs": sum(1 for u in units if u.get("definition") == territory.MCV_DEFINITION),
            "produced": int(fs.get("units_produced", 0)), "moving": sum(1 for u in units if u.get("order")),
            "army_centroid": [round(cx, 1), round(cy, 1)] if cx is not None else None,
            "attacks": int(fs.get("ai_attack", 0)), "defends": int(fs.get("ai_defend", 0)),
            "fleet_attacks": int(fs.get("ai_fleet_attack", 0)), "fleet_defends": int(fs.get("ai_fleet_defend", 0)),
            "unit_kills": int(fs.get("unit_kills", 0)), "building_kills": int(fs.get("building_kills", 0)),
            "unit_losses": int(fs.get("loss_value", 0)), "building_losses": int(fs.get("building_losses", 0)),
            "mcv_queued": int(fs.get("mcv_queued", 0)), "mcv_deployed": int(fs.get("command_centers_deployed", 0)),
            "stock": stock, "stuck": sum(1 for r in stuck if r["faction"] == name),
        }
    return row


def snapshot(world: HybridWorld) -> dict:
    return {
        "minute": int(world.dmb.clock.get("game_ms", 0)) // 60_000,
        "command_centers": [{"faction": b["faction_name"], "tile": [b["tx"], b["ty"]], "radius": territory.radius_of(b), "outpost": bool(b.get("outpost"))}
                            for b in territory.command_centers(world)],
        "units": {n: sum(1 for u in world.units.values() if u["faction_name"] == n and u.get("alive", True)) for n, _h, _c in FACTIONS},
        "stuck": diagnostics.stuck_report(world)[:12],
    }


def run(seed: int, minutes: int, aggressive: bool = True, map_size: str = "standard") -> dict:
    world = HybridWorld(seed=seed, map_size=map_size)
    world.ai_enabled = True  # the report is about the AI whatever HYBRID_AI says (unit tests switch it off by default)
    world.ai_aggressive = aggressive
    series, snaps = [], []
    seq = 0
    t0 = time.perf_counter()
    worst, worst_at = 0.0, 0.0
    for step in range(minutes * 600):
        seq += 1
        t = time.perf_counter()
        world.advance(100, seq, snapshot=False)
        dt = time.perf_counter() - t
        if dt > worst:
            worst, worst_at = dt, round((step + 1) / 600, 2)
        if (step + 1) % 600 == 0:
            series.append(sample(world, {}))
            if (step + 1) % 3000 == 0:
                print(f"    game minute {(step + 1) // 600}: {time.perf_counter() - t0:.0f} s wall, worst step so far {worst * 1000:.0f} ms", flush=True)
            if (step + 1) % 6000 == 0:
                snaps.append(snapshot(world))
    final = series[-1]
    return {
        "seed": seed, "minutes": minutes, "aggressive": aggressive, "wall_seconds": round(time.perf_counter() - t0, 1),
        "worst_step_ms": round(worst * 1000), "worst_step_at_minute": worst_at, "series": series, "snapshots": snaps, "final": final,
        "stuck_final": diagnostics.stuck_report(world)[:20], "state_hash": _hash(world),
        "checks": behaviour_checks({"series": series, "aggressive": aggressive, "minutes": minutes}),
    }


def _hash(world: HybridWorld) -> str:
    import hashlib

    parts = sorted((b["id"], b["tx"], b["ty"], int(b.get("hp", 0))) for b in world.buildings.values())
    parts += sorted((u["id"], u["tx"], u["ty"], int(u.get("hp", 0))) for u in world.units.values())
    return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]


def behaviour_checks(result: dict) -> dict[str, bool]:
    """Pass/fail statements about what the factions did, not about whether the process survived."""
    s = result["series"]
    last = s[-1]["factions"]
    names = list(last)
    mid = s[min(len(s) - 1, len(s) // 2)]["factions"]
    out = {
        "every_faction_built_a_working_economy": all(last[n]["completed"] >= 8 for n in names),
        "most_factions_deployed_a_second_command_centre": sum(1 for n in names if last[n]["mcv_deployed"] >= 1) >= 4,
        # the peak, not the end: a faction that expanded and was then pushed back still expanded. Outposts are small (33x33 against a
        # 69x69 home), so the measure is how many command centres existed at once, not the area.
        "territory_grew": max(sum(row["factions"][n]["command_centers"] for n in names) for row in s) >= 9,
        "armies_were_recruited": all(last[n]["produced"] >= 5 for n in names),
        "armies_moved": sum(last[n]["moving"] for n in names) + sum(last[n]["attacks"] + last[n]["defends"] for n in names) > 0,
        "some_factions_stayed_alive": sum(1 for n in names if last[n]["alive"]) >= 2,
    }
    if result.get("aggressive", True) and result.get("minutes", 0) >= 20:
        out["attacks_were_launched"] = sum(last[n]["attacks"] for n in names) >= 3
        out["enemies_were_damaged"] = sum(last[n]["unit_kills"] + last[n]["building_kills"] for n in names) >= 5
        out["more_than_one_faction_attacked"] = sum(1 for n in names if last[n]["attacks"] > 0) >= 3
    out["no_long_unresolved_stuck_entities"] = last_stuck(result) <= 6
    return out


def last_stuck(result: dict) -> int:
    return int(result["series"][-1].get("stuck_total", 0))


def markdown(results: list[dict]) -> str:
    lines = ["# AI behaviour report", "", "Deterministic headless runs of the real simulation; every faction scripted (`wizard_rts/ai.py`).", ""]
    for r in results:
        lines += [f"## Seed {r['seed']} - {r['minutes']} game minutes ({'war' if r['aggressive'] else 'peace'}), {r['wall_seconds']} s wall, worst step {r['worst_step_ms']} ms (game minute {r.get('worst_step_at_minute', '?')})",
                  f"State hash `{r['state_hash']}`.", "", "| check | result |", "| --- | --- |"]
        lines += [f"| {k.replace('_', ' ')} | {'PASS' if v else '**FAIL**'} |" for k, v in r["checks"].items()]
        lines += ["", "| faction | alive | CCs | territory | buildings | army | navy | produced | attacks | defends | kills (u/b) | losses (b) | MCV q/d | stuck |", "| --- " * 14 + "|"]
        for n, f in r["final"]["factions"].items():
            lines.append(f"| {n} | {f['alive']} | {f['command_centers']} | {f['territory_tiles']} | {f['buildings']} | {f['army']} | {f['navy']} | {f['produced']} | {f['attacks']} | {f['defends']} | {f['unit_kills']}/{f['building_kills']} | {f['building_losses']} | {f['mcv_queued']}/{f['mcv_deployed']} | {f['stuck']} |")
        lines += ["", "Command centres by minute: " + "; ".join(f"m{row['minute']}: " + ",".join(str(row['factions'][n]['command_centers']) for n in row['factions']) for row in r["series"][::5]), ""]
        if r["stuck_final"]:
            lines += ["Stalled entities at the end:", ""] + [f"- {e['class']} {e['id']} ({e['faction']}) at {e['tile']} for {e['stalled_ms'] // 1000} s: {e['blocked_reason']}" for e in r["stuck_final"][:8]] + [""]
    return "\n".join(lines)


def rescore(tag: str) -> None:
    """Recompute the behaviour checks and the report of a saved run (after a check was recalibrated)."""
    d = OUT / tag
    results = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
    for r in results:
        r["checks"] = behaviour_checks(r)
    (d / "metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (d / "REPORT.md").write_text(markdown(results), encoding="utf-8")
    print("rescored", d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=40)
    ap.add_argument("--seeds", type=int, nargs="+", default=[507])
    ap.add_argument("--peace", action="store_true")
    ap.add_argument("--map", default="standard")
    ap.add_argument("--tag", default="")
    ap.add_argument("--rescore", default="", help="recompute checks of docs/evidence/ai_report/<tag> and exit")
    args = ap.parse_args()
    if args.rescore:
        rescore(args.rescore)
        return
    results = []
    for seed in args.seeds:
        print(f"seed {seed} ...", flush=True)
        r = run(seed, args.minutes, not args.peace, args.map)
        print(f"  {r['wall_seconds']} s, checks: " + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in r["checks"].items()), flush=True)
        results.append(r)
    tag = args.tag or f"{args.minutes}m_{'peace' if args.peace else 'war'}"
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (out / "REPORT.md").write_text(markdown(results), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
