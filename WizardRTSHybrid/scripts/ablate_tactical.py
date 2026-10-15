"""M8 ablation: the same genome with the tactical controller N11 on (candidate) and off (reference), paired on held-out seeds.

    py -3 WizardRTSHybrid/scripts/ablate_tactical.py --genome <file.npy> [--code RUN_CODE_DIR] [--seeds 6] [--minutes 60] [--out docs/evidence/neuroevo/m8_tactical]

Adopt the tactical controller as the default only if the 90% lower bound of the paired advantage is above 0. N11's weights are whatever the genome holds: a genome trained with
`tactical` off carries the random initial N11, so this measures the cost of untrained micro-management; a fair test of a trained N11 needs a run trained with `tactical: true`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HYB), str(HYB.parent)]

from neuro import heldout  # noqa: E402
from neuro.evolve import STREAM_HELDOUT, stream_seed  # noqa: E402
from neuro.workers import GamePool  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--genome", required=True)
    ap.add_argument("--code", default=None)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--map", default="standard")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--base", type=int, default=400_000)
    ap.add_argument("--out", default=str(HYB.parent / "docs" / "evidence" / "neuroevo" / "m8_tactical"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    g = Path(a.genome).resolve()
    seeds = [stream_seed(1, STREAM_HELDOUT, a.base + k) for k in range(a.seeds)]
    pool = GamePool(a.workers, code_dir=a.code)
    pairs = heldout.paired_heldout(pool, out / "games", g, g, seeds, a.minutes, a.map, "C0", 1.0, 3600, tactical=True, ref_tactical=False)
    s = heldout.summarize(pairs)
    orders = [sum(st.get("by_head", {}).get("N11", [0, 0])[0:1]) for p in pairs for st in p["stats"].values()]
    s["tactical_orders_total"] = int(sum(orders))
    (out / "ablation.json").write_text(json.dumps({"summary": s, "pairs": [{k: v for k, v in p.items() if k not in ("stats", "metrics")} for p in pairs]}, indent=1), encoding="utf-8")
    verdict = "ADOPT" if s["lower90"] > 0 else "DO NOT ADOPT"
    print(f"tactical on against off: {s['n_pairs']} paired games: mean advantage {s['mean_advantage']:+.1f} [90% lower {s['lower90']:+.1f}, upper {s['upper90']:+.1f}], seeds won "
          f"{s['seed_wins']}/{s['seeds']}, tactical orders issued {s['tactical_orders_total']} -> {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
