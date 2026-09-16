#!/usr/bin/env python3
"""Production-scenario entrypoint established by T004.

Known scenarios fail clearly until their owning implementation task connects
them to the production runtime. This script never substitutes a miniature test
simulation or fabricated success record.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


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
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(SCENARIO_OWNERS, indent=2))
        return 0
    if not args.fixture or not args.record:
        parser.error("--fixture and --record are required unless --list is used")

    owner = SCENARIO_OWNERS[args.fixture]
    payload: dict[str, object] = {
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
