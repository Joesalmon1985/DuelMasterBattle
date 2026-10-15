"""The session report and the status text (execution plan T5.6; design 10.5): what the owner reads after a night of training.

`build_report(run_dir, session)` -> markdown. `session` carries what only the trainer knows: {"first_generation", "start", "end", "workers", "hours", "notes": [...]}.
Everything else is read from the run directory (generations.jsonl, champions/, grid, STATUS.json).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from neuro import persist

VERDICT_WINDOW = 5
VERDICT_BAND = 8.0  # fitness points: a change in the best-advantage trend smaller than this is "FLAT"


def read_generations(run_dir: Path) -> list[dict]:
    p = Path(run_dir) / "generations.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def _num(x: Any, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def verdict(gens: list[dict]) -> tuple[str, str]:
    """(label, detail): best advantage of the last 5 generations against the 5 before."""
    vals = [g.get("best_advantage") for g in gens if not g.get("aborted") and g.get("best_advantage") is not None]
    if len(vals) < 2 * VERDICT_WINDOW:
        return "TOO EARLY TO SAY", f"{len(vals)} generations so far; the verdict needs {2 * VERDICT_WINDOW}"
    last, before = float(np.mean(vals[-VERDICT_WINDOW:])), float(np.mean(vals[-2 * VERDICT_WINDOW:-VERDICT_WINDOW]))
    d = last - before
    label = "IMPROVING" if d > VERDICT_BAND else ("WORSE" if d < -VERDICT_BAND else "FLAT")
    return label, f"best advantage {last:+.1f} over the last {VERDICT_WINDOW} generations against {before:+.1f} over the {VERDICT_WINDOW} before ({d:+.1f})"


def build_report(run_dir: str | Path, session: dict) -> str:
    run_dir = Path(run_dir)
    gens = read_generations(run_dir)
    first = int(session.get("first_generation", 0))
    mine = [g for g in gens if g.get("generation", 0) >= first and not g.get("aborted")]
    aborted = [g for g in gens if g.get("aborted") and g.get("generation", 0) >= first]
    label, detail = verdict(gens)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")) if (run_dir / "manifest.json").exists() else {}
    cfg = manifest.get("config", {})
    games = sum(g.get("games", 0) for g in mine)
    controls = sum(len(g.get("seeds", [])) for g in mine)
    sim_h = sum(g.get("sim_minutes", 0.0) for g in mine) / 60.0
    wall_h = max(1e-9, (float(session.get("end", time.time())) - float(session.get("start", time.time()))) / 3600.0)
    worker_h = sum(g.get("worker_wall_s", 0.0) for g in mine) / 3600.0
    speed = sim_h / worker_h if worker_h else 0.0
    champ = _champion(run_dir)
    ch_gens = [g for g in mine if g.get("promotion") and g["promotion"].get("champion")]
    lines = [f"# AI training session report — {time.strftime('%Y-%m-%d %H:%M', time.localtime(session.get('end', time.time())))} — run {run_dir.name}", "",
             f"Verdict: {label}   ({detail})", ""]
    if mine:
        lines.append(f"This session: generations {mine[0]['generation']}..{mine[-1]['generation']} ({len(mine)} new), {games} games ({controls} controls), {sim_h:.1f} simulated hours in "
                     f"{wall_h:.2f} wall hours ({speed:.0f}x real time per worker), {session.get('workers', cfg.get('workers', '?'))} workers.")
    else:
        lines.append("This session: no generation finished" + (f" ({len(aborted)} aborted)." if aborted else "."))
    if champ:
        ev = champ.get("evaluation", {})
        lines.append(f"Champion: {champ['id']} (promoted this session: {'yes' if ch_gens else 'no'}; held-out: mean advantage {_num(ev.get('mean_advantage'), 1)} "
                     f"[90% lower bound {_num(ev.get('lower90'), 1)}], collective-loss rate {_num(ev.get('loss_rate_candidate'), 2)} vs control {_num(ev.get('loss_rate_reference'), 2)}). "
                     f"Saved to WizardRTSHybrid/neuro/models/best_ai.json.")
    else:
        lines.append("Champion: none yet (no candidate has beaten the heuristic AI on held-out games). The best genome of each generation is kept under best_by_gen/.")
    lc = [g["control_loss_rate"] for g in mine if g.get("control_loss_rate") is not None]
    lvl = manifest.get("catastrophe_level", cfg.get("curriculum", {}).get("current", "C0"))
    scale = manifest.get("outbreak_interval_scale", 1.0)
    lines.append(f"Collective loss: controls {_num(float(np.mean(lc)) if lc else None, 2)} of worlds (catastrophe level {lvl}, outbreak scale {scale}); candidates' own loss rates are in the held-out figures above.")
    lines += ["", "| generation | best advantage | mean advantage | best raw fitness | control loss rate | commands per tick | rejected % | sigma (mean) | lineage of best |",
              "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for g in mine:
        sig = np.mean([v["sigma_mean"] for v in g.get("lineages", {}).values()]) if g.get("lineages") else None
        be = g.get("best_entry") or {}
        lines.append(f"| {g['generation']} | {_num(g.get('best_advantage'))} | {_num(g.get('mean_advantage'))} | {_num(g.get('best_raw_fitness'))} | {_num(g.get('control_loss_rate'), 2)} | "
                     f"{_num(g.get('commands_per_tick'), 2)} | {_num(100 * g.get('rejected_fraction', 0), 2)} | {_num(sig, 3)} | {be.get('lineage', '')} |")
    grid = _grid(run_dir)
    lines += ["", f"Behaviour grid: {len(grid)}/18 cells filled (military share / expansion / cooperation); best per cell:"]
    for cell, v in sorted(grid.items()):
        lines.append(f"  - cell {cell}: raw fitness {v['fitness']:.1f} ({v.get('lineage', '')}, generation {v.get('generation', '?')})")
    if mine:
        g = mine[-1]
        heads = ", ".join(f"{h} {100 * x:.0f}%" for h, x in g.get("heads_used", {}).items())
        lines.append("")
        lines.append(f"Decision statistics (last generation, all candidate games): heads used: {heads or 'n/a'}; commands per tick {_num(g.get('commands_per_tick'), 2)}; "
                     f"rejected {_num(100 * g.get('rejected_fraction', 0), 2)}%.")
    imit = [g for g in mine if g.get("imitation_lineage")]
    if imit:
        r = [x["lineages"].get("random", {}).get("parent_adv") for x in imit]
        i = [x["lineages"].get("imitation", {}).get("parent_adv") for x in imit]
        r, i = [x for x in r if x is not None], [x for x in i if x is not None]
        lines.append(f"Imitation lineage: parent advantage {_num(float(np.mean(i)) if i else None)} against the random lineage's {_num(float(np.mean(r)) if r else None)} "
                     f"(means over this session); adoptions: {sum(1 for g in imit if g.get('adopted'))}.")
    size_gb = persist.dir_size(run_dir) / 1e9
    last_ck = max((int(p.stem.split('_')[1]) for p in (run_dir / "checkpoints").glob("ckpt_*.pkl")), default=None)
    lines += ["", f"Disk: {size_gb:.2f} GB in the run (cap {cfg.get('max_run_gb', 20)}); last checkpoint generation {last_ck}.",
              'To continue: double-click "Train AI.bat" (it resumes this run). To test the champion: "Evaluate Best AI.bat".']
    notes = list(session.get("notes", []))
    voided = sum(g.get("voided", 0) for g in mine)
    if voided:
        notes.append(f"{voided} games were voided (crash twice, stall or wall-cap); details in games/*/repro.json and the generation events.")
    if aborted:
        notes.append(f"{len(aborted)} generation(s) aborted without an update: " + "; ".join(str(a.get("reason")) for a in aborted))
    ev = [e for g in mine for e in g.get("events", [])]
    if ev:
        notes.append("worker events: " + ", ".join(sorted({f"{e['job']}:{e['event']}" for e in ev})[:12]))
    lines.append("Notes: " + (" ".join(notes) if notes else "none."))
    return "\n".join(lines) + "\n"


def _champion(run_dir: Path) -> dict | None:
    cur = (run_dir / "champions" / "current.txt")
    if not cur.exists():
        return None
    cid = cur.read_text(encoding="utf-8").strip()
    try:
        rec = json.loads((run_dir / "champions" / f"{cid}.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"id": cid}
    ev = rec.get("evaluation", {}).get("heldout", rec.get("evaluation", {}))
    return {"id": cid, "evaluation": ev}


def _grid(run_dir: Path) -> dict[str, dict]:
    state = persist.load_checkpoint(run_dir)
    if not state:
        return {}
    return state.get("grid", {}).get("cells", {})


def write_report(run_dir: str | Path, session: dict, models_dir: Path | None) -> Path:
    run_dir = Path(run_dir)
    text = build_report(run_dir, session)
    rep_dir = run_dir / "reports"
    rep_dir.mkdir(exist_ok=True)
    n = len(list(rep_dir.glob("session_*.md"))) + 1 if not session.get("report_index") else int(session["report_index"])
    path = rep_dir / f"session_{n:03d}.md"
    path.write_text(text, encoding="utf-8")
    if models_dir is not None:
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / "LAST_SESSION_REPORT.md").write_text(text, encoding="utf-8")
    return path


def status_text(run_dir: Path) -> str:
    gens = read_generations(run_dir)
    label, detail = verdict(gens)
    st = {}
    if (run_dir / "STATUS.json").exists():
        try:
            st = json.loads((run_dir / "STATUS.json").read_text(encoding="utf-8"))
        except ValueError:
            pass
    champ = _champion(run_dir)
    out = [f"Run {run_dir.name}: {st.get('state', 'unknown')} (updated {st.get('updated', '?')})", f"Verdict: {label} ({detail})",
           f"Generations finished: {len(gens)}; in progress: generation {st.get('generation', '?')}, games {st.get('jobs_done', '?')}/{st.get('jobs_total', '?')}, "
           f"elapsed {st.get('elapsed_s', 0) / 3600.0:.2f} h", f"Champion: {champ['id'] if champ else 'none yet'}"]
    if gens:
        g = [x for x in gens if not x.get("aborted")][-1:] or gens[-1:]
        if g:
            out.append(f"Last generation {g[0].get('generation')}: best advantage {_num(g[0].get('best_advantage'))}, mean {_num(g[0].get('mean_advantage'))}")
    return "\n".join(out)
