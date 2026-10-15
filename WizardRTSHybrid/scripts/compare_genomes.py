"""Paired held-out comparison of two genome files (candidate against reference), both playing the same seats against three `plus` opponents on held-out seeds.

    py -3 WizardRTSHybrid/scripts/compare_genomes.py --run proving --pairs random:theta/gen_000022_ran.npy:theta0.npy imitation:theta/gen_000022_imi.npy:theta0_imitation.npy [--seeds 6] [--out DIR]

Each pair is `label:candidate:reference` with paths relative to the run folder. Used for the M6 report: the judge compares the best entries of two generations; this compares each lineage's final
parent mean with the genome it started from, which does not depend on which entry happened to score highest on the training seeds.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HYB), str(HYB.parent)]

from neuro import cli, heldout  # noqa: E402
from neuro.evolve import STREAM_HELDOUT, stream_seed  # noqa: E402
from neuro.workers import GamePool  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="proving")
    ap.add_argument("--pairs", nargs="+", required=True)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--base", type=int, default=300_000)
    ap.add_argument("--out", default=str(HYB.parent / "docs" / "evidence" / "neuroevo" / "m6_proof"))
    a = ap.parse_args()
    run = cli.resolve_run(a.run) or (cli.runs_root() / a.run)
    cfg = json.loads((run / "manifest.json").read_text(encoding="utf-8")).get("config", {})
    pool = GamePool(a.workers, code_dir=run / "code")
    seeds = [stream_seed(cfg.get("run_seed", 1), STREAM_HELDOUT, a.base + k) for k in range(a.seeds)]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for spec in a.pairs:
        label, cand, ref = spec.split(":")
        pairs = heldout.paired_heldout(pool, out / "games_compare" / label, run / cand, run / ref, seeds, cfg.get("game_minutes", 60), cfg.get("map_size", "standard"), "C0", 1.0,
                                       cfg.get("wall_cap_s", 3600))
        s = heldout.summarize(pairs)
        result[label] = {"candidate": cand, "reference": ref, **s}
        print(f"{label}: {cand} against {ref}: mean advantage {s['mean_advantage']:+.1f} [90% lower {s['lower90']:+.1f}, upper {s['upper90']:+.1f}], seeds won {s['seed_wins']}/{s['seeds']}, "
              f"candidate fitness {s['mean_f_candidate']:.1f} vs {s['mean_f_reference']:.1f}", flush=True)
    (out / "compare_genomes.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
