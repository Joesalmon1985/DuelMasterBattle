#!/usr/bin/env python3
"""Headless civilisation tournament: the improved AI ("plus", wizard_rts/ai_plus.py) against the original AI ("baseline", ai.py).

Every game is the normal, complete HybridWorld update in the shipped `campaign` profile (primitive start, cards gated, no God or
developer grants, no fixtures, no era forcing): workers, carriers, construction, drafting, VP and eras, outbreaks, disruptions,
unrest, history (decline/split/collapse) and both AIs run exactly as in the Godot game. Nothing is skipped to go faster.

Pairing (default `mirror`): each seed is played twice with the same map; in game A the plus AI plays Red, Green and Purple and the
baseline plays Blue, Yellow and Orange, in game B the sides swap. Every start position therefore plays both policies on every seed,
so a positional advantage cancels out. `--pairing all-plus` / `all-baseline` run one game per seed with a single policy.

Modes: `war` (normal competition), `peace` (ai_aggressive off: an explicit test-only switch; economy and drafting only), `crisis`
(outbreak cadence doubled; optional `--wizard-pilot` adds the scripted wizard agent that walks and treats by the public rules),
`historical` (normal rules for long horizons; reports eras, splits and collapses).

Outputs in --report-dir: run_manifest.json, games.csv, factions.csv, timeseries.csv, events.jsonl, validation_failures.json,
summary.json and report.html (self-contained, inline SVG; no plotting dependency).

    python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --mode war --seeds 507 11 23 --minutes 60 \\
        --report-dir ~/dmb_runs/civ_smoke --jobs 3
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))

SIDE_A = ("Red", "Green", "Purple")
FACTIONS = ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")
MAJOR = ("era_advanced", "card_drafted", "draft_lapsed", "deployed", "settlement_destroyed", "vp_conquest", "faction_declined", "faction_recovered",
         "faction_split", "faction_collapsed", "outbreak", "outbreak_cube", "catastrophe_destroyed", "disrupted", "disruption_cleared",
         "treatment_done", "ai_attack", "ai_retreat", "ai_expand_deploy", "ai_expand_rejected", "cycle_due", "terminal_loss", "building_destroyed",
         "ai_industry_placed", "ai_link_outpost", "tribe_fallback", "nest_spawned", "nest_cube_cleared", "nest_destroyed", "caravan_sent",
         "caravan_traded", "caravan_refused")
GAMES = {"widelands": "wl", "openra": "ora", "hybrid": "hyb", "mindustry": "mdy"}


def source_game(kind: str, definition: str) -> str:
    if kind.startswith("mdy:") or definition.startswith("mindustry."):
        return "mindustry"
    if definition.startswith("openra."):
        return "openra"
    if definition.startswith("dmb."):
        return "hybrid"
    return "widelands"


def policies(pairing: str, leg: str) -> dict[str, str]:
    if pairing == "all-plus":
        return {f: "plus" for f in FACTIONS}
    if pairing == "all-baseline":
        return {f: "baseline" for f in FACTIONS}
    a = leg == "A"
    return {f: ("plus" if (f in SIDE_A) == a else "baseline") for f in FACTIONS}


def sample(world, t_wall: float, step_ms: list[float]) -> list[dict]:
    from wizard_rts import ai, ai_plus, disruption, territory, vp, history

    now = int(world.dmb.clock.get("game_ms", 0))
    era = vp.snapshot(world)
    hist = history.state(world)["faction"]
    rg = world.__dict__.get("regions")
    rows = []
    for name in list(world.faction_info):
        blds = [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]
        units = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True)]
        army = [u for u in units if u.get("weapon")]
        ccs = territory.command_centers(world, name)
        stock: Counter = Counter()
        for cc in ccs:
            stock.update({g: int(v) for g, v in world.stocks.get(cc["id"], {}).items()})
        by_game = Counter(source_game(b["kind"], b.get("definition", "")) for b in blds if not b.get("constructing"))
        fs = world.fstats.get(name, {})
        recs = [r for r in world.dmb.settlements.values() if r["faction"] == name and r["state"] == "standing"]
        rows.append({
            "minute": now // 60_000, "faction": name, "policy": ai.policy_of(world, name), "tribe": world.faction_info[name].get("tribe", ""),
            "parent": world.faction_info[name].get("parent", ""), "state": hist.get(name, {}).get("state", "active"),
            "era": era["era_index"], "vp": vp.faction_vp(world, name), "settlements": len(ccs), "cards": len(world.tech.get(name, {}).get("cards", [])),
            "buildings": len(blds), "sites": sum(1 for b in blds if b.get("constructing")), "working": sum(1 for b in blds if b.get("working")),
            "disrupted": sum(1 for b in blds if b.get("disrupted")),
            "wl": by_game["widelands"], "ora": by_game["openra"], "hyb": by_game["hybrid"], "mdy": by_game["mindustry"],
            "army": len(army), "army_strength": round(sum(ai_plus.unit_strength(u) for u in army), 1),
            "units_produced": int(fs.get("units_produced", 0)), "unit_kills": int(fs.get("unit_kills", 0)), "building_kills": int(fs.get("building_kills", 0)),
            "building_losses": int(fs.get("building_losses", 0)), "loss_value": int(fs.get("loss_value", 0)),
            "attacks": int(fs.get("ai_attack", 0)), "defends": int(fs.get("ai_defend", 0)), "founded": int(fs.get("command_centers_deployed", 0)),
            "nest_cubes_cleared": int(fs.get("nest_cubes_cleared", 0)), "trades": int(fs.get("trades_done", 0)), "caravans": int(fs.get("caravans_sent", 0)),
            "disruptions": int(fs.get("disruptions", 0)), "repairs": int(fs.get("repairs", 0)),
            "log": stock["log"], "plank": stock["plank"], "granite": stock["granite"], "coal": stock["coal"], "iron": stock["iron"], "gold": stock["gold"],
            "ration": stock["ration"], "food": sum(stock[g] for g in ("ration", "bread", "meat", "fish", "smoked_fish", "smoked_meat")),
            "unrest": round(max((float(r.get("unrest", 0.0)) for r in recs), default=0.0), 3),
            "outbreak_cubes": sum(rg.cubes[rg.region_at(r["tile"][0], r["tile"][1])] for r in recs) if rg else 0,
            "wall_s": round(t_wall, 1), "step_ms_p95": round(sorted(step_ms)[int(len(step_ms) * 0.95)] if step_ms else 0.0, 2),
        })
    return rows


def play(job: dict) -> dict:
    """One game, in its own process (spawned, so it also works on Windows). Returns rows and the summary; heavy output is written by the parent."""
    os.environ["HYBRID_AI"] = "1"
    from wizard_rts import history, ledger, vp
    from wizard_rts.world import HybridWorld

    t0 = time.time()
    w = HybridWorld(job["seed"], profile="campaign", map_size=job["map"])
    w.ai_enabled = True
    w.ai_policy = dict(job["policies"])
    w.ai_aggressive = job["mode"] != "peace"
    if job.get("nocards"):
        w.nocards = True  # plan v2 P2: drafting off, foundation set only, no settlement quota
    if job.get("draft"):
        w.cardset, w.draft_v2 = "v2", True  # plan v2 P3: generated 1-2 entity cards, era-start seven-round ring draft
    if job["mode"] == "crisis":
        w.outbreak_interval_scale = 0.5
    pilot = None
    if job.get("wizard_pilot"):
        from wizard_rts import wizard_pilot

        pilot = wizard_pilot.WizardPilot(w)
    initial = ledger.snapshot_totals(w)
    series, events, failures = [], [], []
    seen = 0
    step_ms: list[float] = []
    total_s = job["minutes"] * 60
    for s in range(total_s):
        a = time.perf_counter()
        w.advance(1000, s + 1, snapshot=False)
        if pilot is not None:
            pilot.step()
        step_ms.append((time.perf_counter() - a) * 1000.0)
        evs = w.events
        new = getattr(evs, "total", len(evs)) - seen  # the window is trimmed now and then: count from the log's own total
        for e in (evs[-new:] if 0 < new <= len(evs) else (evs if new > 0 else [])):
            if e.get("kind") in MAJOR:
                events.append({"game_ms": int(w.dmb.clock.get("game_ms", 0)), **{k: v for k, v in e.items() if isinstance(v, (str, int, float, bool, list))}})
        seen = getattr(evs, "total", len(evs))
        if (s + 1) % job["every"] == 0 or s + 1 == total_s:
            series += sample(w, time.time() - t0, step_ms[-job["every"]:])
            neg = [(b, g, v) for b, st in w.stocks.items() for g, v in st.items() if v < 0]
            if neg:
                failures.append({"minute": (s + 1) // 60, "kind": "negative_stock", "detail": neg[:5]})
    bad = ledger.check(w, initial)
    if bad:
        failures.append({"kind": "ledger", "detail": bad[:10]})
    if vp.replay(w) != vp.totals(w):
        failures.append({"kind": "vp_replay_mismatch", "live": vp.totals(w), "replay": vp.replay(w)})
    era = vp.era_state(w)
    summary = {"seed": job["seed"], "leg": job["leg"], "mode": job["mode"], "map": job["map"], "minutes": job["minutes"], "wall_s": round(time.time() - t0, 1),
               "era": era["index"], "era_log": era["log"], "vp": vp.totals(w), "history": {n: f["state"] for n, f in history.state(w)["faction"].items()},
               "chronicle": history.state(w)["chronicle"], "outbreaks": getattr(w.__dict__.get("regions"), "outbreaks", 0),
               "stats": {k: v for k, v in w.stats.items() if not k.startswith(("made_", "consumed_"))}, "state_hash": w.state_hash(),
               "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1),
               "step_ms_p50": round(sorted(step_ms)[len(step_ms) // 2], 2), "step_ms_p95": round(sorted(step_ms)[int(len(step_ms) * 0.95)], 2),
               "step_ms_max": round(max(step_ms), 1), "policies": job["policies"], "pilot": bool(pilot), "pilot_log": pilot.log[-40:] if pilot else []}
    return {"job": job, "series": series, "events": events, "failures": failures, "summary": summary}


# ------------------------------------------------------------------ report

def _mean(xs):
    xs = [float(x) for x in xs]
    return sum(xs) / len(xs) if xs else 0.0


def _ci95(xs):
    xs = [float(x) for x in xs]
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return 1.96 * sd / math.sqrt(len(xs))


def final_rows(results: list[dict]) -> list[dict]:
    out = []
    for r in results:
        last = max(x["minute"] for x in r["series"]) if r["series"] else 0
        for row in r["series"]:
            if row["minute"] == last:
                out.append({**row, "seed": r["job"]["seed"], "leg": r["job"]["leg"]})
    return out


def compare(results: list[dict]) -> dict:
    rows = final_rows(results)
    keys = ("vp", "settlements", "cards", "buildings", "army", "army_strength", "units_produced", "unit_kills", "building_kills", "building_losses",
            "founded", "food", "iron", "unrest", "nest_cubes_cleared", "trades", "disruptions")
    out = {}
    for pol in ("plus", "baseline"):
        sel = [r for r in rows if r["policy"] == pol and not r["parent"]]
        alive = [r for r in sel if r["state"] != "collapsed"]
        out[pol] = {"n": len(sel), "survived": len(alive), "collapsed": len(sel) - len(alive),
                    **{k: round(_mean([r[k] for r in sel]), 2) for k in keys}, **{k + "_ci95": round(_ci95([r[k] for r in sel]), 2) for k in ("vp", "army_strength", "buildings")}}
    # head-to-head per game: which side holds more VP at the end (ties count half)
    wins = {"plus": 0.0, "baseline": 0.0}
    for r in results:
        last = final_rows([r])
        tot = {p: sum(x["vp"] for x in last if x["policy"] == p) for p in ("plus", "baseline")}
        if tot["plus"] > tot["baseline"]:
            wins["plus"] += 1
        elif tot["plus"] < tot["baseline"]:
            wins["baseline"] += 1
        else:
            wins["plus"] += 0.5
            wins["baseline"] += 0.5
    out["game_wins_by_vp"] = wins
    return out


def svg_lines(series: dict[str, list[tuple[float, float]]], title: str, w: int = 560, h: int = 220, colours: dict | None = None) -> str:
    pts = [p for s in series.values() for p in s]
    if not pts:
        return ""
    x1 = max(p[0] for p in pts) or 1
    y1 = max(p[1] for p in pts) or 1
    pal = colours or {}
    default = ["#2a6fdb", "#d6455c", "#3fae49", "#e0a400", "#8e4ad0", "#e8892e", "#555", "#0aa"]
    body = [f'<text x="8" y="16" font-size="13" font-weight="600">{title}</text>',
            f'<line x1="40" y1="{h-24}" x2="{w-10}" y2="{h-24}" stroke="#999"/><line x1="40" y1="24" x2="40" y2="{h-24}" stroke="#999"/>',
            f'<text x="2" y="30" font-size="10">{y1:g}</text><text x="{w-60}" y="{h-8}" font-size="10">{x1:g} min</text>']
    for k, (name, s) in enumerate(sorted(series.items())):
        col = pal.get(name, default[k % len(default)])
        path = " ".join(f"{40 + (x / x1) * (w - 52):.1f},{(h - 24) - (y / y1) * (h - 48):.1f}" for x, y in s)
        body.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{path}"/>')
        body.append(f'<text x="{w-120}" y="{36 + 13 * k}" font-size="11" fill="{col}">{name}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="background:#fff;border:1px solid #ddd;margin:4px">{"".join(body)}</svg>'


def html_report(results: list[dict], cmp: dict, manifest: dict) -> str:
    ts: dict[str, dict[str, list]] = {}
    for metric in ("vp", "army_strength", "buildings", "settlements", "cards", "food", "unrest"):
        agg: dict[str, dict[int, list]] = {"plus": {}, "baseline": {}}
        for r in results:
            for row in r["series"]:
                if row["parent"]:
                    continue
                agg[row["policy"]].setdefault(row["minute"], []).append(row[metric])
        ts[metric] = {p: sorted((m, _mean(v)) for m, v in d.items()) for p, d in agg.items()}
    col = {"plus": "#2a6fdb", "baseline": "#d6455c"}
    charts = "".join(svg_lines(ts[m], f"mean {m} per faction", colours=col) for m in ts)
    era_rows = []
    for r in results:
        s = r["summary"]
        eras = ", ".join(f"{e['era']} @ {e['game_ms'] // 60000} min ({e['reason']})" for e in s["era_log"]) or "prehistoric throughout"
        chron = Counter(c["event"] for c in s["chronicle"])
        era_rows.append(f"<tr><td>{s['seed']}{s['leg']}</td><td>{s['minutes']}</td><td>{eras}</td><td>{dict(chron)}</td><td>{s['outbreaks']}</td>"
                        f"<td>{s['vp']}</td><td>{s['wall_s']}</td><td>{s['step_ms_p95']}</td><td>{len(r['failures'])}</td></tr>")
    cmp_rows = "".join(f"<tr><td>{k}</td><td>{cmp['plus'].get(k)}</td><td>{cmp['baseline'].get(k)}</td></tr>" for k in cmp["plus"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Civilisation tournament</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;background:#fafafa;color:#222}}table{{border-collapse:collapse;margin:8px 0}}td,th{{border:1px solid #ccc;padding:3px 6px;font-size:13px}}th{{background:#eee}}</style></head><body>
<h1>Civilisation tournament: plus vs baseline</h1>
<p>Mode <b>{manifest['mode']}</b>, pairing <b>{manifest['pairing']}</b>, seeds {manifest['seeds']}, {manifest['minutes']} game minutes, map {manifest['map']},
commit <code>{manifest['git_sha'][:10]}</code>{' (dirty)' if manifest['git_dirty'] else ''}. Game wins by end VP: {cmp['game_wins_by_vp']}.</p>
<h2>Per-faction means at the end (root factions)</h2><table><tr><th>metric</th><th>plus</th><th>baseline</th></tr>{cmp_rows}</table>
<h2>Over time</h2>{charts}
<h2>Games</h2><table><tr><th>seed</th><th>min</th><th>eras (reason)</th><th>chronicle</th><th>outbreaks</th><th>final VP</th><th>wall s</th><th>p95 step ms</th><th>validation failures</th></tr>{''.join(era_rows)}</table>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--mode", choices=("war", "peace", "crisis", "historical"), default="war")
    ap.add_argument("--seeds", type=int, nargs="+", default=[507, 11, 23])
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--map", choices=("small", "standard", "large"), default="standard")
    ap.add_argument("--pairing", choices=("mirror", "all-plus", "all-baseline"), default="mirror")
    ap.add_argument("--every", type=int, default=60, help="sample period in game seconds")
    ap.add_argument("--jobs", type=int, default=2, help="games played in parallel (the T460 has 4 cores; keep 2-3)")
    ap.add_argument("--allow-sha-mismatch", action="store_true", help="reuse finished games saved by a different commit when resuming")
    ap.add_argument("--nocards", action="store_true", help="no-card civilisation: drafting off, foundation set only (plan v2 P2)")
    ap.add_argument("--draft", action="store_true", help="drafting v2 with the generated content-graph cards (plan v2 P3)")
    ap.add_argument("--wizard-pilot", action="store_true", help="crisis mode: add the scripted wizard agent (public moves only)")
    ap.add_argument("--report-dir", default=str(Path.home() / "dmb_runs" / "civ_latest"))
    args = ap.parse_args()
    out = Path(os.path.expanduser(args.report_dir))
    out.mkdir(parents=True, exist_ok=True)
    legs = ("A", "B") if args.pairing == "mirror" else ("-",)
    jobs = [{"seed": s, "leg": leg, "mode": args.mode, "map": args.map, "minutes": args.minutes, "every": args.every,
             "policies": policies(args.pairing, leg), "wizard_pilot": args.wizard_pilot, "nocards": args.nocards, "draft": args.draft} for s in args.seeds for leg in legs]
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(HYB)).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "wizard_rts"], capture_output=True, text=True, cwd=str(HYB)).stdout.strip())
    manifest = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "git_sha": sha, "git_dirty": dirty, "mode": args.mode, "pairing": args.pairing,
                "seeds": args.seeds, "minutes": args.minutes, "map": args.map, "every_s": args.every, "jobs": args.jobs, "profile": "campaign",
                "wizard_pilot": args.wizard_pilot, "machine": {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count()},
                "argv": sys.argv}
    t0 = time.time()
    results = []
    # Resume (plan v2 11.3): every finished game is written atomically to <report-dir>/games/; a re-run with the same arguments loads those and
    # plays only the rest. A game from a different commit (or an edited wizard_rts) is not reused unless --allow-sha-mismatch.
    games_dir = out / "games"
    games_dir.mkdir(exist_ok=True)
    stamp = {"sha": sha, "dirty": dirty}

    def save_game(r: dict) -> None:
        path = games_dir / f"{r['job']['seed']}{r['job']['leg']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"stamp": stamp, "result": r}, default=str))
        os.replace(tmp, path)

    todo = []
    for j in jobs:
        path = games_dir / f"{j['seed']}{j['leg']}.json"
        if path.exists():
            try:
                saved = json.loads(path.read_text())
                if saved["result"]["job"] == j and (saved["stamp"] == stamp or args.allow_sha_mismatch):
                    results.append(saved["result"])
                    print(f"resumed seed {j['seed']}{j['leg']} from {path.name}", flush=True)
                    continue
                print(f"not reusing {path.name}: different arguments or code version", flush=True)
            except (OSError, ValueError, KeyError):
                print(f"unreadable {path.name}: playing it again", flush=True)
        todo.append(j)
    jobs = todo
    if args.jobs > 1 and jobs:
        import multiprocessing as mp

        with mp.get_context("spawn").Pool(args.jobs) as pool:
            for r in pool.imap_unordered(play, jobs):
                results.append(r)
                save_game(r)
                s = r["summary"]
                print(f"seed {s['seed']}{s['leg']}: era {s['era']} vp {s['vp']} wall {s['wall_s']} s failures {len(r['failures'])}", flush=True)
    else:
        for j in jobs:
            r = play(j)
            results.append(r)
            save_game(r)
            s = r["summary"]
            print(f"seed {s['seed']}{s['leg']}: era {s['era']} vp {s['vp']} wall {s['wall_s']} s failures {len(r['failures'])}", flush=True)
    results.sort(key=lambda r: (r["job"]["seed"], r["job"]["leg"]))
    manifest["wall_s"] = round(time.time() - t0, 1)
    cmp = compare(results)
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    (out / "summary.json").write_text(json.dumps({"compare": cmp, "games": [r["summary"] for r in results]}, indent=1, default=str))
    (out / "validation_failures.json").write_text(json.dumps([{"seed": r["job"]["seed"], "leg": r["job"]["leg"], **f} for r in results for f in r["failures"]], indent=1, default=str))
    with (out / "events.jsonl").open("w") as fh:
        for r in results:
            for e in r["events"]:
                fh.write(json.dumps({"seed": r["job"]["seed"], "leg": r["job"]["leg"], **e}, default=str) + "\n")
    rows = [{"seed": r["job"]["seed"], "leg": r["job"]["leg"], **row} for r in results for row in r["series"]]
    if rows:
        with (out / "timeseries.csv").open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        fin = final_rows(results)
        with (out / "factions.csv").open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(fin[0]))
            wr.writeheader()
            wr.writerows(fin)
    with (out / "games.csv").open("w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["seed", "leg", "minutes", "final_era", "era_transitions", "vp_threshold_transitions", "stall_guard_transitions", "splits", "collapses",
                     "declines", "outbreaks", "settlements_destroyed", "wall_s", "step_ms_p95", "peak_rss_mb", "failures"])
        for r in results:
            s = r["summary"]
            ch = Counter(c["event"] for c in s["chronicle"])
            wr.writerow([s["seed"], s["leg"], s["minutes"], s["era"], len(s["era_log"]), sum(1 for e in s["era_log"] if e["reason"] == "vp_threshold"),
                         sum(1 for e in s["era_log"] if e["reason"] == "stall_guard"), ch["split"], ch["collapsed"], ch["declined"], s["outbreaks"],
                         sum(1 for e in r["events"] if e["kind"] == "settlement_destroyed"), s["wall_s"], s["step_ms_p95"], s["peak_rss_mb"], len(r["failures"])])
    (out / "report.html").write_text(html_report(results, cmp, manifest))
    print(json.dumps(cmp, indent=1))
    print("report:", out / "report.html")


if __name__ == "__main__":
    main()
