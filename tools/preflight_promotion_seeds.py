#!/usr/bin/env python3
"""Preflight all G09 promotion seeds before training/evaluation.

Proves each locked promotion seed generates a legal world with a rockfall quest
blocking a real connected exit. Returns non-zero on any failure.

Usage:
  python tools/preflight_promotion_seeds.py
  python tools/preflight_promotion_seeds.py --fixture FX-MVP --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "policy_evaluations"
sys.path.insert(0, str(ROOT))


def _preflight_one(fixture: str, seed: int) -> dict:
    from sim.dmb.testing.fixtures import load_fixture
    from sim.dmb.world.boulder_quest import get_rockfall, rockfall_blocks_travel, eligible_boulder_helpers
    from sim.dmb.time.runner import TurnRunner
    from sim.dmb.time.turns import TurnScheduler

    sim = load_fixture(fixture, seed=seed)
    state = sim.state
    g05 = state.board.get("g05") or {}
    start = str(g05.get("start_node_id") or (state.player or {}).get("node_id") or "")
    if not start:
        raise AssertionError("missing start settlement")
    rockfall = get_rockfall(state)
    if not rockfall:
        raise AssertionError("rockfall missing")
    to_node = str(rockfall.get("target_node_id") or "")
    from_node = str(rockfall.get("node_id") or "")
    if not to_node or not from_node:
        raise AssertionError("rockfall missing edge endpoints")
    if not rockfall_blocks_travel(state, from_node, to_node):
        raise AssertionError("rockfall does not block selected exit")
    helpers = eligible_boulder_helpers(state, from_node)
    if not helpers:
        raise AssertionError("no eligible helpers")
    # One legal Wait step
    runner = TurnRunner(state, TurnScheduler(state.clock))
    factions = sorted(state.factions)
    state.clock["scheduled_faction_ids"] = factions
    state.clock["active_faction_id"] = factions[0]
    runner.execute_wait(start, f"preflight-{seed}")
    # No negative stock
    for stock in (state.stocks or {}).values():
        for _k, v in (stock.items() if isinstance(stock, dict) else []):
            if isinstance(v, (int, float)) and v < 0:
                raise AssertionError(f"negative stock {_k}={v}")
    return {
        "seed": seed,
        "fixture": fixture,
        "start_node_id": start,
        "exit_id": rockfall.get("exit_id"),
        "direction": rockfall.get("direction"),
        "helpers": len(helpers),
        "status": "ok",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default="FX-ERA", choices=["FX-ERA", "FX-MVP"])
    ap.add_argument("--limit", type=int, default=0, help="0 = all promotion seeds")
    ap.add_argument("--seeds-file", type=Path, default=None)
    args = ap.parse_args()
    from training.collect import PROMOTION_SEEDS

    seeds = list(PROMOTION_SEEDS)
    if args.seeds_file and args.seeds_file.is_file():
        payload = json.loads(args.seeds_file.read_text(encoding="utf-8"))
        seeds = [int(s) for s in payload.get("seeds") or seeds]
    if args.limit:
        seeds = seeds[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    started = time.monotonic()
    for seed in seeds:
        try:
            rows.append(_preflight_one(args.fixture, seed))
        except Exception as exc:  # noqa: BLE001
            row = {"seed": seed, "fixture": args.fixture, "status": "fail", "error": str(exc)}
            rows.append(row)
            failures.append(row)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": args.fixture,
        "seed_count": len(seeds),
        "passed": len(seeds) - len(failures),
        "failed": len(failures),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "failures": failures[:50],
        "rows": rows,
    }
    out_path = OUT / "promotion_seed_preflight.json"
    out_path.write_text(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2) + "\n", encoding="utf-8")
    (OUT / "promotion_seed_preflight_full.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "failed": report["failed"], "out": str(out_path.relative_to(ROOT))}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
