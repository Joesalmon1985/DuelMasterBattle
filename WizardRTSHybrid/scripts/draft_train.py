"""Train the neural drafting module by imitation of the heuristic drafter and report held-out accuracy (plan v2 9.3 step 2).

    python3 scripts/draft_train.py --data ~/dmb_runs/draft_data --out ~/dmb_runs/draft_models/scorer_v1.json

Samples are split BY SEED (whole games), never by pick, so the held-out accuracy is on games the network never saw. Baselines: choosing
at random and always choosing the first offer. Accuracy against the heuristic is an imitation metric only; whether the learned drafter
plays as well is measured in games by scripts/draft_swap_eval.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))

from wizard_rts.learn.draft_module import DraftScorer  # noqa: E402


def load(data: Path) -> dict[int, list[dict]]:
    out = {}
    for f in sorted(data.glob("seed_*.jsonl")):
        text = f.read_text().strip()
        if text:
            out[int(f.stem.split("_")[1])] = [json.loads(line) for line in text.splitlines()]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path.home() / "dmb_runs" / "draft_data"))
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "draft_models" / "scorer_v1.json"))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--hidden", type=int, nargs="+", default=[48, 24])
    ap.add_argument("--holdout", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    games = load(Path(a.data).expanduser())
    seeds = sorted(games)
    n_hold = max(1, int(len(seeds) * a.holdout))
    held, train = seeds[-n_hold:], seeds[:-n_hold]
    tr = [s for k in train for s in games[k]]
    te = [s for k in held for s in games[k]]
    print(f"{len(seeds)} games, {len(tr)} train picks ({len(train)} games), {len(te)} held-out picks ({len(held)} games)")
    rng = np.random.RandomState(a.seed)
    rand = float(np.mean([1.0 / len(s["cards"]) for s in te]))
    first = float(np.mean([s["target"] == 0 for s in te]))
    sc = DraftScorer(tuple(a.hidden), seed=a.seed)
    curve = sc.train(tr, epochs=a.epochs, seed=a.seed)
    res = {"games": len(seeds), "train_picks": len(tr), "heldout_picks": len(te), "random_top1": round(rand, 3), "first_offer_top1": round(first, 3),
           "train_top1": round(sc.accuracy(tr), 3), "heldout_top1": round(sc.accuracy(te), 3), "loss_first": round(curve[0], 3), "loss_last": round(curve[-1], 3),
           "params": sc.net.n_params(), "hidden": a.hidden, "epochs": a.epochs}
    # by era, to see whether later eras (fewer samples) are learnt worse
    for era in range(4):
        sub = [s for s in te if s["era"] == era]
        if sub:
            res[f"heldout_top1_era{era}"] = round(sc.accuracy(sub), 3)
            res[f"heldout_n_era{era}"] = len(sub)
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    sc.save(str(out))
    print(json.dumps(res, indent=1))
    if a.report:
        Path(a.report).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
