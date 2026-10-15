"""Judge the M6 proving run (execution plan T6.2; design section 12).

    py -3 WizardRTSHybrid/scripts/judge_proof.py [--run proving] [--seeds 8] [--workers 14] [--out docs/evidence/neuroevo/m6_proof] [--skip-games]

Acceptance: a held-out evaluation of the generation-0 best against the final generation's best, on `--seeds` held-out seeds (both legs each): the final best's mean advantage
is higher with a bootstrap 90% lower bound above 0, and it wins every one of the paired held-out seeds. "A run that merely completes fails."
The report holds the learning curves (table and curves.svg), the behaviour grid, decision statistics, the lineage comparison (imitation against random), the verdict, and, on
a failure, the four diagnoses of the plan in order. With --skip-games the held-out games are not replayed (the report is built from the run's own logs).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

HYB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HYB), str(HYB.parent)]

from neuro import cli, heldout, persist  # noqa: E402
from neuro.evolve import STREAM_HELDOUT, stream_seed  # noqa: E402
from neuro.report import read_generations  # noqa: E402
from neuro.workers import GamePool  # noqa: E402


def svg_curves(gens: list[dict], path: Path) -> None:
    xs = [g["generation"] for g in gens]
    series = {"best": [g.get("best_advantage") for g in gens], "mean": [g.get("mean_advantage") for g in gens]}
    vals = [v for s in series.values() for v in s if v is not None]
    if not vals or len(xs) < 2:
        return
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or 1.0
    lo, hi = lo - pad, hi + pad
    W, H, M = 640, 320, 40
    sx = lambda x: M + (x - xs[0]) / max(1, xs[-1] - xs[0]) * (W - 2 * M)  # noqa: E731
    sy = lambda y: H - M - (y - lo) / (hi - lo) * (H - 2 * M)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="11">',
           f'<rect width="{W}" height="{H}" fill="white"/>', f'<line x1="{M}" y1="{sy(0) if lo < 0 < hi else H - M}" x2="{W - M}" y2="{sy(0) if lo < 0 < hi else H - M}" stroke="#999" stroke-dasharray="4"/>']
    for name, color in (("best", "#1b7837"), ("mean", "#2166ac")):
        pts = " ".join(f"{sx(x):.1f},{sy(v):.1f}" for x, v in zip(xs, series[name]) if v is not None)
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>')
    out.append(f'<text x="{M}" y="16" fill="#1b7837">best advantage</text><text x="{M + 110}" y="16" fill="#2166ac">mean advantage</text>')
    out.append(f'<text x="{M}" y="{H - 10}">generation {xs[0]} .. {xs[-1]}</text><text x="4" y="{M}">{hi:.0f}</text><text x="4" y="{H - M}">{lo:.0f}</text></svg>')
    path.write_text("\n".join(out), encoding="utf-8")


def diagnose(gens: list[dict]) -> list[str]:
    """The plan's four checks, in order."""
    notes = []
    cpt = [g["commands_per_tick"] for g in gens if "commands_per_tick" in g]
    if cpt:
        m = float(np.mean(cpt))
        flag = "FAIL" if m < 0.3 or m > 3.7 else "ok"
        notes.append(f"1. commands per tick: mean {m:.2f} (min {min(cpt):.2f}, max {max(cpt):.2f}) -> {flag} (near 0 or constantly near 4 means the selection rule or the temperatures)")
    rej = [g["rejected_fraction"] for g in gens if "rejected_fraction" in g]
    if rej:
        m = float(np.mean(rej))
        notes.append(f"2. rejection rate: mean {100 * m:.2f}% -> {'FAIL' if m > 0.2 else 'ok'} (above 20% means candidate generation)")
    within, between = [], []
    for g in gens:
        es = g.get("entries", [])
        if len(es) >= 4:
            within.append(float(np.mean([e.get("sd", 0.0) / max(1.0, np.sqrt(e.get("n", 1))) for e in es])))
            between.append(float(np.std([e["adv"] for e in es])))
    if within:
        w, b = float(np.mean(within)), float(np.mean(between))
        notes.append(f"3. evaluation noise: standard error of one child's advantage {w:.1f} against the spread between children {b:.1f} -> {'FAIL (increase seeds per generation)' if w > b else 'ok'}")
    sig = [np.mean([v["sigma_mean"] for v in g.get("lineages", {}).values()]) for g in gens if g.get("lineages")]
    if sig:
        notes.append(f"4. sigma: first {sig[0]:.3f}, last {sig[-1]:.3f}, min {min(sig):.3f}, max {max(sig):.3f} -> {'FAIL (collapsed or exploded)' if min(sig) <= 0.011 or max(sig) >= 0.199 else 'ok'}")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="proving")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", default=str(HYB.parent / "docs" / "evidence" / "neuroevo" / "m6_proof"))
    ap.add_argument("--skip-games", action="store_true")
    a = ap.parse_args()
    run_dir = cli.resolve_run(a.run) or (cli.runs_root() / a.run)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    gens = [g for g in read_generations(run_dir) if not g.get("aborted")]
    if len(gens) < 2:
        print("fewer than two finished generations: nothing to judge", file=sys.stderr)
        return 2
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    cfg = manifest.get("config", {})
    g0 = run_dir / "best_by_gen" / f"gen_{gens[0]['generation']:06d}.npy"
    gl = run_dir / "best_by_gen" / f"gen_{gens[-1]['generation']:06d}.npy"
    summary, pairs = None, []
    if not a.skip_games:
        pool = GamePool(a.workers, code_dir=run_dir / "code")
        seeds = [stream_seed(cfg.get("run_seed", 1), STREAM_HELDOUT, 200_000 + k) for k in range(a.seeds)]
        pairs = heldout.paired_heldout(pool, out / "games", gl, g0, seeds, cfg.get("game_minutes", 60), cfg.get("map_size", "standard"), "C0", 1.0, cfg.get("wall_cap_s", 3600))
        summary = heldout.summarize(pairs)
        (out / "heldout.json").write_text(json.dumps({"summary": summary, "pairs": [{k: v for k, v in p.items() if k not in ("stats", "metrics")} for p in pairs]}, indent=1), encoding="utf-8")
    svg_curves(gens, out / "curves.svg")
    passed = bool(summary and summary["lower90"] > 0 and summary["mean_advantage"] > 0 and summary["seed_wins"] == summary["seeds"] == a.seeds)
    state = persist.load_checkpoint(run_dir) or {}
    lines = ["# M6 proof of evolution — report", "", f"Run `{run_dir.name}` ({cfg.get('name')}): {len(gens)} generations, {cfg.get('game_minutes')}-minute games, population {cfg.get('population')}, "
             f"{cfg.get('seeds_per_generation')} seeds per generation, catastrophe level {manifest.get('catastrophe_level')} (outbreak scale {manifest.get('outbreak_interval_scale')}).", ""]
    if summary:
        lines += ["## Verdict", "", f"**{'PASS' if passed else 'FAIL'}**: final best (generation {gens[-1]['generation']}) against generation-0 best on {summary['seeds']} held-out seeds x 2 legs: "
                  f"mean advantage {summary['mean_advantage']:+.1f}, 90% lower bound {summary['lower90']:+.1f}, seeds won {summary['seed_wins']}/{summary['seeds']}, "
                  f"collective-loss rate {summary['loss_rate_candidate']:.2f} vs {summary['loss_rate_reference']:.2f}.", "",
                  "Acceptance rule: mean advantage above 0 with a bootstrap 90% lower bound above 0, and every paired held-out seed won. A run that merely completes fails.", ""]
    else:
        lines += ["## Verdict", "", "Held-out games were skipped (`--skip-games`): no verdict.", ""]
    lines += ["## Learning curves", "", "![curves](curves.svg)", "", "| generation | best advantage | mean advantage | best raw fitness | commands per tick | rejected % | sigma | best from |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for g in gens:
        sig = np.mean([v["sigma_mean"] for v in g.get("lineages", {}).values()]) if g.get("lineages") else float("nan")
        lines.append(f"| {g['generation']} | {g.get('best_advantage', float('nan')):.1f} | {g.get('mean_advantage', float('nan')):.1f} | {g.get('best_raw_fitness', float('nan')):.1f} | "
                     f"{g.get('commands_per_tick', 0):.2f} | {100 * g.get('rejected_fraction', 0):.2f} | {sig:.3f} | {(g.get('best_entry') or {}).get('lineage', '')} |")
    imit = [g for g in gens if "imitation" in g.get("lineages", {})]
    if imit:
        pr = [g["lineages"]["random"]["parent_adv"] for g in imit if "random" in g["lineages"]]
        pi = [g["lineages"]["imitation"]["parent_adv"] for g in imit]
        wins = sum(1 for g in gens if (g.get("best_entry") or {}).get("lineage") == "imitation")
        lines += ["", "## Imitation-seeded lineage", "", f"Parent advantage, imitation lineage: mean {np.mean(pi):+.1f} (first {pi[0]:+.1f}, last {pi[-1]:+.1f}); random lineage: mean {np.mean(pr):+.1f} "
                  f"(first {pr[0]:+.1f}, last {pr[-1]:+.1f}). The imitation lineage held the best entry in {wins} of {len(gens)} generations; adoptions: {sum(1 for g in gens if g.get('adopted'))}."]
    grid = state.get("grid", {}).get("cells", {})
    lines += ["", f"## Behaviour grid ({len(grid)}/18 cells)", ""] + [f"- cell {k}: raw fitness {v['fitness']:.1f} ({v.get('lineage')}, generation {v.get('generation')})" for k, v in sorted(grid.items())]
    last = gens[-1]
    lines += ["", "## Decision statistics (last generation)", "", f"Heads used: {', '.join(f'{h} {100 * x:.0f}%' for h, x in last.get('heads_used', {}).items())}; commands per tick "
              f"{last.get('commands_per_tick', 0):.2f}; rejected {100 * last.get('rejected_fraction', 0):.2f}%.", ""]
    lines += ["## Diagnosis checklist", ""] + [f"- {n}" for n in diagnose(gens)]
    champ = (run_dir / "champions" / "current.txt")
    lines += ["", f"Champion promotions during the run: {sum(1 for g in gens if g.get('promotion') and g['promotion'].get('champion'))}; current champion: "
              f"{champ.read_text(encoding='utf-8').strip() if champ.exists() else 'none'}."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report written to {out / 'report.md'}; verdict: {'PASS' if passed else ('FAIL' if summary else 'no games')}")
    return 0 if passed or not summary else 1


if __name__ == "__main__":
    sys.exit(main())
