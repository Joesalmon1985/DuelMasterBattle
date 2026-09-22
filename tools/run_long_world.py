#!/usr/bin/env python3
"""Run FX-LONG-WORLD headless soak and write G05 long-run evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.dmb.testing.fixtures import load_fixture  # noqa: E402
from sim.dmb.testing.long_run import major_event_fingerprint, run_long_world  # noqa: E402

GATE_DIR = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates" / "G05"
REPORT_PATH = GATE_DIR / "long_run_report.md"
CHECKPOINT_DIR = GATE_DIR / "long_run"


def _write_report(report: dict, events: list, *, determinism_ok: bool) -> None:
    counts = report.get("counts") or {}
    lines = [
        "# G05 long-run report — FX-LONG-WORLD",
        "",
        f"- Fixture: `{report.get('fixture')}` mode=`{report.get('mode')}`",
        f"- Seed: `{report.get('seed')}`",
        f"- World turns advanced: **{report.get('world_turns')}** (cap {report.get('max_turns')})",
        f"- Game Time: `{report.get('game_ms_start')}` → `{report.get('game_ms_end')}` ms",
        f"- Settlements: {report.get('settlements_start')} → {report.get('settlements_end')}",
        f"- Cities: {report.get('cities_start')} → {report.get('cities_end')}",
        f"- Roads: {report.get('roads_start')} → {report.get('roads_end')}",
        f"- Units: {report.get('units_start')} → {report.get('units_end')}",
        f"- Determinism (two runs, same seed): **{'PASS' if determinism_ok else 'FAIL'}**",
        "",
        "## Major event counts",
        "",
    ]
    for kind, n in counts.items():
        lines.append(f"- `{kind}`: {n}")
    lines.extend(["", "## Units produced by faction", ""])
    for fac, n in sorted((report.get("units_produced_by_faction") or {}).items()):
        lines.append(f"- `{fac}`: {n}")
    stag = report.get("stagnation") or []
    lines.extend(["", "## Stagnation flags", ""])
    if stag:
        for item in stag:
            lines.append(f"- `{item}`")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Chronology", ""])
    if not events:
        lines.append("_No major events detected within the turn cap._")
    else:
        for ev in events:
            detail = ", ".join(
                f"{k}={v}" for k, v in ev.items() if k not in {"kind", "turn"}
            )
            lines.append(f"- Turn {ev.get('turn')}: **{ev.get('kind')}**" + (f" — {detail}" if detail else ""))
    lines.extend(["", "## Checkpoints", ""])
    for name, meta in (report.get("checkpoints") or {}).items():
        lines.append(
            f"- `{name}`: turn={meta.get('turn')} roads={meta.get('roads')} "
            f"settlements={meta.get('settlements')} units={meta.get('units')}"
        )
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=507)
    parser.add_argument("--max-turns", type=int, default=300)
    parser.add_argument("--quanta-per-wait", type=int, default=5)
    parser.add_argument("--skip-determinism", action="store_true")
    args = parser.parse_args(argv)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    sim_a = load_fixture("FX-LONG-WORLD", seed=args.seed)
    report_a, events_a = run_long_world(
        sim_a,
        max_turns=args.max_turns,
        advance_game_quanta_per_wait=args.quanta_per_wait,
    )

    determinism_ok = True
    if not args.skip_determinism:
        sim_b = load_fixture("FX-LONG-WORLD", seed=args.seed)
        report_b, events_b = run_long_world(
            sim_b,
            max_turns=args.max_turns,
            advance_game_quanta_per_wait=args.quanta_per_wait,
        )
        determinism_ok = major_event_fingerprint(events_a) == major_event_fingerprint(events_b)
        report_a["determinism_ok"] = determinism_ok
        report_a["determinism_b_counts"] = report_b.get("counts")

    # Schematic checkpoint JSONs (authoritative snapshot summaries — not GPU screenshots).
    for name, snap in (report_a.get("checkpoint_snapshots") or {}).items():
        path = CHECKPOINT_DIR / f"{name}.json"
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Slim report payload without huge nested snapshots duplicated in markdown.
    slim = dict(report_a)
    slim.pop("checkpoint_snapshots", None)
    slim.pop("major_events", None)
    (CHECKPOINT_DIR / "report.json").write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    (CHECKPOINT_DIR / "events.json").write_text(json.dumps(events_a, indent=2) + "\n", encoding="utf-8")

    _write_report(report_a, events_a, determinism_ok=determinism_ok)

    print(json.dumps({"report": str(REPORT_PATH), "counts": report_a.get("counts"), "determinism_ok": determinism_ok, "world_turns": report_a.get("world_turns"), "stagnation": report_a.get("stagnation")}, indent=2))
    return 0 if determinism_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
