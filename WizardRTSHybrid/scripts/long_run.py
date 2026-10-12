"""Bounded autonomous run of the six factions, with an HTML report.

    py -3 WizardRTSHybrid/scripts/long_run.py --minutes 30 --seeds 507 11 23

Runs the authoritative world headless with every faction under AI control,
samples it every game minute, and writes docs/evidence/long_run/report.html and
metrics.json. A seed that stalls, crashes, or breaks an invariant is kept with
its failure so it can be replayed (`HybridWorld(seed=...)` is deterministic).
"""

from __future__ import annotations

import argparse
import base64
import collections
import html
import json
import os
import sys
import time
import traceback
from pathlib import Path

HYBRID = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYBRID))
sys.path.insert(0, str(HYBRID.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts.logistics import in_flight  # noqa: E402
from wizard_rts.world import FACTIONS, HybridWorld  # noqa: E402

OUT = HYBRID / "docs" / "evidence" / "long_run"
GOODS = ("log", "plank", "granite", "coal", "iron_ore", "iron", "ax")


def sample(world: HybridWorld) -> dict:
    row: dict = {"t": int(world.dmb.clock.get("game_ms", 0)) // 60_000, "factions": {}}
    for name, _hex, _color in FACTIONS:
        units = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True)]
        blds = [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]
        wh = [b for b in blds if b["kind"] == "warehouse"]
        stock = {g: sum(int(world.stocks.get(b["id"], {}).get(g, 0)) for b in wh) for g in GOODS}
        row["factions"][name] = {
            "units": len(units), "buildings": len(blds), "sites": sum(1 for b in blds if b.get("constructing")),
            "warehouse": bool(wh), "stock": stock, "queued": sum(len(b.get("queue", [])) for b in blds),
            "moving": sum(1 for u in units if u.get("order")),
        }
    row["trees"] = len(world.trees)
    row["rocks"] = len(world.rocks)
    row["workers"] = len(world.workers)
    row["carriers_busy"] = sum(1 for c in world.carriers.values() if c["cargo"])
    row["stats"] = {k: v for k, v in world.stats.items() if not k.startswith(("made_", "consumed_"))}
    row["wares_in_flight"] = in_flight(world)
    return row


def check(world: HybridWorld, last: dict | None) -> list[str]:
    problems = []
    for b in world.buildings.values():
        if "hp" in b and not (0 <= int(b["hp"]) <= int(b["max_hp"])):
            problems.append(f"hp out of range {b['id']}")
    for u in world.units.values():
        if u.get("alive", True) and not (0 < int(u["hp"]) <= int(u["max_hp"])):
            problems.append(f"unit hp out of range {u['id']}")
    for g in GOODS:
        total = sum(int(s.get(g, 0)) for s in world.stocks.values()) + in_flight(world, g)
        if total < 0:
            problems.append(f"negative {g}")
    return problems


def run_seed(seed: int, minutes: int) -> dict:
    result: dict = {"seed": seed, "samples": [], "problems": [], "status": "ok"}
    started = time.time()
    try:
        world = HybridWorld(seed=seed, map_size=os.environ.get("HYBRID_MAP", "standard"))
        world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
        seq = 0
        last_signature = None
        stalled = 0
        for minute in range(1, minutes + 1):
            for _ in range(60):
                seq += 1
                world.advance(1000, seq, snapshot=False)
            row = sample(world)
            row["wall_s"] = round(time.time() - started, 1)
            result["samples"].append(row)
            result["problems"] += check(world, None)
            signature = (row["wares_in_flight"], tuple(sorted(row["stats"].items())))
            stalled = stalled + 1 if signature == last_signature else 0
            last_signature = signature
            if stalled >= 5:
                result["problems"].append(f"stall: no change for {stalled} minutes at minute {minute}")
                break
        result["event_counts"] = dict(collections.Counter(e["kind"] for e in world.events))
        result["final_stats"] = {k: v for k, v in world.stats.items()}
        result["ai_events"] = [e for e in world.events if e["kind"].startswith("ai_")][-12:]
    except Exception:  # noqa: BLE001 - a crash is a result, with its seed kept for replay
        result["status"] = "crash"
        result["problems"].append(traceback.format_exc())
    result["wall_s"] = round(time.time() - started, 1)
    if result["problems"] and result["status"] == "ok":
        result["status"] = "fail"
    return result


def spark(values: list[float], color: str, width: int = 260, height: int = 48) -> str:
    if not values:
        return ""
    hi = max(max(values), 1)
    pts = " ".join(f"{i * width / max(len(values) - 1, 1):.1f},{height - 4 - (v / hi) * (height - 8):.1f}" for i, v in enumerate(values))
    return f'<svg width="{width}" height="{height}" role="img"><polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>'


def embed(path: Path) -> str:
    if not path.is_file():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img alt="{html.escape(path.name)}" src="data:image/png;base64,{data}" style="max-width:100%;border:1px solid var(--line);border-radius:6px">'


def report(results: list[dict], minutes: int) -> str:
    colors = {n: c for n, _h, c in FACTIONS}
    parts = [
        "<!doctype html><title>WizardRTSHybrid long run</title>",
        "<style>:root{--bg:#fafafa;--fg:#1d1d22;--line:#d6d6dc;--ok:#1f8a4c;--bad:#c0392b}"
        "@media(prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#ececf1;--line:#3a3a44}}"
        "body{background:var(--bg);color:var(--fg);font:14px system-ui;margin:0;padding:1rem 1.25rem;max-width:1100px}"
        "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:.3rem .5rem;text-align:left}"
        ".ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}pre{overflow:auto;background:rgba(127,127,127,.12);padding:.5rem}</style>",
        f"<h1>Six-faction autonomous run</h1><p>{minutes} game minutes per seed, every faction under AI control, one continuous world. "
        "Expected: economies run, units are produced from delivered goods, squads form and fight, buildings fall, nobody stalls or crashes.</p>",
        "<table><tr><th>Seed</th><th>Status</th><th>Wall s</th><th>Recruited</th><th>Units lost</th><th>Buildings lost</th><th>Attacks</th><th>Problems</th></tr>",
    ]
    for r in results:
        s = r.get("final_stats", {})
        cls = "ok" if r["status"] == "ok" else "bad"
        parts.append(
            f"<tr><td>{r['seed']}</td><td class={cls}>{r['status'].upper()}</td><td>{r['wall_s']}</td><td>{s.get('recruited', 0)}</td>"
            f"<td>{s.get('units_lost', 0)}</td><td>{s.get('buildings_lost', 0)}</td><td>{s.get('attack', 0)}</td><td>{len(r['problems'])}</td></tr>"
        )
    parts.append("</table>")
    for r in results:
        parts.append(f"<h2>Seed {r['seed']}</h2>")
        if r["problems"]:
            parts.append("<pre>" + html.escape("\n".join(r["problems"])[:3000]) + "</pre>")
        samples = r["samples"]
        if samples:
            parts.append("<table><tr><th>Faction</th><th>Units over time</th><th>Buildings over time</th><th>Final</th></tr>")
            for name in colors:
                u = [s["factions"][name]["units"] for s in samples]
                b = [s["factions"][name]["buildings"] for s in samples]
                last = samples[-1]["factions"][name]
                parts.append(
                    f"<tr><td style='color:{colors[name]};font-weight:700'>{name}</td><td>{spark(u, colors[name])}</td><td>{spark(b, colors[name])}</td>"
                    f"<td>{last['units']} units, {last['buildings']} buildings, queue {last['queued']}, "
                    f"{'HQ standing' if last['warehouse'] else 'HQ DESTROYED'}</td></tr>"
                )
            parts.append("</table>")
            parts.append("<p>Trees: " + spark([s["trees"] for s in samples], "#3f8f3f") + " Rocks: " + spark([s["rocks"] for s in samples], "#888") + "</p>")
        if r.get("event_counts"):
            top = sorted(r["event_counts"].items(), key=lambda kv: -kv[1])[:14]
            parts.append("<p>Events in the retained log window: " + ", ".join(f"{k} {v}" for k, v in top) + "</p>")
        if r.get("ai_events"):
            parts.append("<pre>" + html.escape("\n".join(json.dumps(e) for e in r["ai_events"])) + "</pre>")
    shots = sorted((HYBRID / "docs" / "evidence" / "war").glob("*.png"))
    if shots:
        parts.append("<h2>Headed war screenshots</h2>")
        parts += [f"<p>{html.escape(p.name)}<br>{embed(p)}</p>" for p in shots[:12]]
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=30)
    ap.add_argument("--seeds", type=int, nargs="+", default=[507, 11, 23])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for seed in args.seeds:
        print(f"LONG_RUN seed={seed} minutes={args.minutes}", flush=True)
        r = run_seed(seed, args.minutes)
        print(f"LONG_RUN seed={seed} {r['status']} wall={r['wall_s']}s problems={len(r['problems'])}", flush=True)
        results.append(r)
    (OUT / "metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (OUT / "report.html").write_text(report(results, args.minutes), encoding="utf-8")
    failed = [r["seed"] for r in results if r["status"] != "ok"]
    print("LONG_RUN_DONE", "FAILED seeds " + str(failed) if failed else "all seeds ok", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
