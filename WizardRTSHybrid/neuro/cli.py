"""Command line of the neuroevolution programme (execution plan T3.2 `play`, T5.4 the rest). The root `train_ai.py` calls `main()`.

    train_ai.py play --genome random|random:<n>|best|<file> --seed 7 --minutes 60 --seat Red [--map standard] [--record out.jsonl.gz] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
for p in (str(HYB), str(HYB.parent)):
    if p not in sys.path:
        sys.path.append(p)

MODELS = HYB / "neuro" / "models"


def load_genome(spec: str):
    """`random` / `random:<n>` (a random genome from stream n), `best` (the saved champion), or a path to a model json or a raw .npy genome."""
    import numpy as np

    from neuro import nets

    if spec == "random" or spec.startswith("random:"):
        n = int(spec.split(":", 1)[1]) if ":" in spec else 0
        return nets.random_genome(np.random.default_rng(n))
    if spec == "best":
        spec = str(MODELS / "best_ai.json")
    path = Path(spec)
    if path.suffix == ".npy":
        g = np.load(path)
        return g.astype(np.float32)
    from neuro import persist

    genome, _meta = persist.load_model(path)
    return genome


def cmd_play(a: argparse.Namespace) -> int:
    os.environ.setdefault("HYBRID_AI", "1")
    from neuro import nets
    from neuro.controller import Controller, DecisionLog
    from neuro.episode import EpisodeConfig, run_episode

    genome = load_genome(a.genome)
    cfg = EpisodeConfig(seed=a.seed, game_minutes=a.minutes, map_size=a.map, agent_seats=tuple(a.seat), tactical=bool(a.tactical))
    log = DecisionLog(a.record) if a.record else None
    ctls = {s: Controller(None, s, nets.Nets(genome), cfg, a.seed, log) for s in a.seat}
    res = run_episode(cfg, ctls)
    if log is not None:
        log.close()
    out = {"seed": a.seed, "end_reason": res.end_reason, "t_end_min": res.t_end_min, "state_hash": res.state_hash, "outbreaks": res.outbreaks,
           "seats": [s.__dict__ for s in res.seats], "controls": [s.__dict__ for s in res.control_seats], "stats": {s: c.stats() for s, c in ctls.items()},
           "wall_s": res.wall_s, "books_ok": bool(res.vp_replay_ok and res.ledger_ok)}
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    seats = ", ".join(f"{s.faction} fitness {s.fitness} (VP {s.vp}, {s.state})" for s in res.seats)
    print(f"game over: {res.end_reason} at {res.t_end_min:.1f} min in {res.wall_s:.0f} s; {seats}; state {res.state_hash}")
    for s, c in ctls.items():
        st = c.stats()
        print(f"  {s}: {st['ticks']} ticks, {st['commands']} commands ({st['rejected']} rejected), {st['tick_ms_mean']:.1f} ms/tick, heads {st['by_head']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="train_ai.py", description="Hierarchical neuroevolution of the faction controllers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play", help="play one game with a genome in some seats")
    p.add_argument("--genome", default="random")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--minutes", type=int, default=60)
    p.add_argument("--seat", nargs="+", default=["Red"])
    p.add_argument("--map", default="standard")
    p.add_argument("--record", default="")
    p.add_argument("--json", default="")
    p.add_argument("--tactical", action="store_true")
    p.set_defaults(fn=cmd_play)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    sys.exit(main())
