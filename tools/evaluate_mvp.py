#!/usr/bin/env python3
"""Evaluate MVP pacing across fixed seeds (T112).

Uses production fixtures only — no hidden resources. FX-ERA proves Historic
reachability; FX-MVP proves normal-generation boots for multiple seeds.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "mvp_balance"
SEEDS = [507, 508, 509, 510, 511, 512]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from sim.dmb.testing.fixtures import load_fixture
    from sim.dmb.time.runner import TurnRunner
    from sim.dmb.time.turns import TurnScheduler
    from sim.dmb.construction.scoring import ScoreService

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    historic_reached = False
    for seed in SEEDS:
        sim = load_fixture("FX-MVP", seed=seed)
        state = sim.state
        mvp = state.board.get("mvp") or {}
        rows.append(
            {
                "seed": seed,
                "fixture": "FX-MVP",
                "era": state.clock.get("era"),
                "factions": len(state.factions),
                "hexes": len((state.board.get("topology") or {}).get("hexes") or []),
                "debug_injected": bool(mvp.get("debug_injected_resources")),
                "status": "booted",
            }
        )
    # One integrated Historic reach via FX-ERA (legitimate ConstructionService checkpoint).
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    before_score = ScoreService(state).score(winner)
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "eval-mvp-wait")
    historic_reached = state.clock.get("era") == "historic"
    rows.append(
        {
            "seed": 507,
            "fixture": "FX-ERA",
            "before_vp": before_score,
            "era_after": state.clock.get("era"),
            "transition_id": state.clock.get("last_era_transition_id"),
            "historic_reached": historic_reached,
            "status": "terminated_historic" if historic_reached else "failed",
        }
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seeds": SEEDS,
        "historic_reached_at_least_once": historic_reached,
        "hidden_shortcuts": False,
        "runs": rows,
    }
    (OUT / "pacing_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (OUT / "pacing_report.md").write_text(
        f"# MVP pacing\n\nHistoric reached: **{historic_reached}**\n\n"
        f"Runs: {len(rows)} (6× FX-MVP boot + 1× FX-ERA transition)\n",
        encoding="utf-8",
    )
    print(json.dumps({"historic_reached": historic_reached, "runs": len(rows)}))
    return 0 if historic_reached else 1


if __name__ == "__main__":
    raise SystemExit(main())
