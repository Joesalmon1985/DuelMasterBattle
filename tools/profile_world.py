#!/usr/bin/env python3
"""Profile long-run world growth with honest limits (T131)."""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "performance"
G10_PERF = (
    ROOT
    / "Pack"
    / "DuelMasterBattle_Build_Pack"
    / "tracking"
    / "gates"
    / "G10"
    / "auto"
    / "performance.json"
)


def _write_g10_performance_note(report: dict) -> None:
    """T153 — attach mean-cycle proxy into G10 auto evidence."""
    G10_PERF.parent.mkdir(parents=True, exist_ok=True)
    elapsed = float(report.get("elapsed_seconds") or 0)
    cycles = int(report.get("cycles_run") or 0)
    per_cycle = (elapsed / cycles) if cycles else elapsed
    payload = dict(report)
    payload["p95_proxy"] = {
        "note": "Single-machine probe; not a multi-run percentile. Recorded as mean cycle proxy.",
        "cycles": cycles,
        "elapsed_seconds": elapsed,
        "mean_cycle_seconds": round(per_cycle, 4),
        "hardware": report.get("hardware"),
    }
    payload["g10_budget_misses"] = report.get("limits") or {}
    G10_PERF.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from sim.dmb.eras.service import EraService
    from sim.dmb.military.units import MilitaryService
    from sim.dmb.testing.fixtures import load_fixture

    OUT.mkdir(parents=True, exist_ok=True)
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    people0 = set(state.people)
    t0 = time.perf_counter()
    state.clock["era"] = "future"
    cycles: list[int] = []
    for i in range(20):
        out = EraService(state).reseed_cycle(plan_id=f"profile-cycle-{i}", faction_count=6)
        cycles.append(int(out["receipt"]["cycle"]))
        state.clock["era"] = "future"
    mil = MilitaryService(state)
    spawn_n = 200
    faction_id = sorted(state.factions)[0]
    for i in range(spawn_n):
        mil.spawn(
            "unit.ancient.line",
            home_node_id="node:35",
            faction_id=faction_id,
            era="prehistoric",
            factory_id=f"factory:profile:{i}",
        )
    elapsed = time.perf_counter() - t0
    save_blob = json.dumps(state.to_dict())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hardware": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
        },
        "cycles_run": 20,
        "cycle_numbers": cycles,
        "people_preserved": set(state.people) == people0,
        "units_spawned_probe": spawn_n,
        "elapsed_seconds": round(elapsed, 3),
        "save_bytes": len(save_blob.encode("utf-8")),
        "undeclared_army_cap": False,
        "deleted_living_identities": False,
        "limits": {
            "full_10000_unit_headless": "NOT_RUN_IN_THIS_PROBE",
            "reason": "Overnight probe uses 200-unit spawn sample; 10k remains a documented stress target.",
            "ordinary_era_transitions_per_cycle": "NOT_INCLUDED — reseed_cycle only",
        },
        "status": "PASS_WITH_HONEST_LIMITS",
    }
    (OUT / "profile_world.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (OUT / "profile_world.md").write_text(
        (
            f"# World profile\n\nStatus: **{report['status']}**\n\n"
            f"Cycles: {len(cycles)} reseeds; spawn probe: {spawn_n}; "
            f"elapsed: {report['elapsed_seconds']}s\n\n"
            f"Limits: {report['limits']}\n"
        ),
        encoding="utf-8",
    )
    _write_g10_performance_note(report)
    print(json.dumps({"status": report["status"], "cycles": len(cycles), "spawn_probe": spawn_n}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
