#!/usr/bin/env python3
"""Production-scenario entrypoint established by T004 / connected by T023."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.dmb.testing.fixtures import load_fixture, run_fx_cargo, run_fx_clock  # noqa: E402

SCENARIO_OWNERS = {
    "FX-CLOCK": "T012/T024",
    "FX-CARGO": "T029-T038",
    "FX-INDUSTRY": "T049-T057",
    "FX-BATTLE": "T059-T068",
    "FX-HAZARD": "T069-T075",
    "FX-VILLAGE": "T077-T095",
    "FX-ERA": "T097-T106",
    "FX-SOLO": "T102/T106",
    "FX-CYCLE": "T125-T131",
    "FX-RECOVERY": "T019/T092/T152",
    "FX-RELEASE": "T151-T159",
}


def _record(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=sorted(SCENARIO_OWNERS))
    parser.add_argument("--record", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(SCENARIO_OWNERS, indent=2))
        return 0
    if not args.fixture or not args.record:
        parser.error("--fixture and --record are required unless --list is used")

    owner = SCENARIO_OWNERS[args.fixture]
    if args.fixture == "FX-CLOCK":
        try:
            sim = load_fixture("FX-CLOCK", seed=args.seed)
            result = run_fx_clock(sim)
            payload: dict[str, object] = {
                "fixture": args.fixture,
                "status": result.status,
                "owner": owner,
                "seed": args.seed,
                "details": result.details,
                "world_id": sim.state.world_id,
                "catalog_hash": sim.state.catalog_hash,
                "legacy_writers_disabled": (
                    not sim.state.legacy_godot_world_tick_enabled
                    and not sim.state.legacy_godot_world_save_enabled
                ),
            }
            _record(args.record, payload)
            print(json.dumps(payload, indent=2))
            return 0 if result.status == "PASS" else 1
        except Exception as exc:  # noqa: BLE001
            payload = {
                "fixture": args.fixture,
                "status": "FAIL",
                "owner": owner,
                "message": str(exc),
            }
            _record(args.record, payload)
            print(json.dumps(payload, indent=2))
            return 1

    if args.fixture == "FX-CARGO":
        try:
            sim = load_fixture("FX-CARGO", seed=args.seed)
            result = run_fx_cargo(sim, seed=args.seed)
            payload = {
                "fixture": args.fixture,
                "status": result.status,
                "owner": owner,
                "seed": args.seed,
                "details": result.details,
                "world_id": sim.state.world_id,
                "legacy_writers_disabled": (
                    not sim.state.legacy_godot_world_tick_enabled
                    and not sim.state.legacy_godot_world_save_enabled
                ),
            }
            _record(args.record, payload)
            print(json.dumps(payload, indent=2))
            return 0 if result.status == "PASS" else 1
        except Exception as exc:  # noqa: BLE001
            payload = {
                "fixture": args.fixture,
                "status": "FAIL",
                "owner": owner,
                "message": str(exc),
            }
            _record(args.record, payload)
            print(json.dumps(payload, indent=2))
            return 1

    payload = {
        "fixture": args.fixture,
        "status": "NOT_IMPLEMENTED",
        "owner": owner,
        "message": (
            f"{args.fixture} is reserved for {owner} and is not connected to the "
            "production runtime yet. No scenario was run and no PASS is claimed."
        ),
    }
    _record(args.record, payload)
    print(json.dumps(payload, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
