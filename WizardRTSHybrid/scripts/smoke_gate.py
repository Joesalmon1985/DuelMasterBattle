"""Smoke gate (plan v2 11.6): a few minutes, must stay green before every push.

    python3 scripts/smoke_gate.py

Content-graph static checks, catalogue audit, the fast infrastructure and draft tests, and a 5-minute three-seed state-hash comparison
against docs/perf/hash_baseline.json (so a behaviour change in the simulation is caught here). Exit code 0 only if every step passes."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
STEPS = [
    ("content graph static checks", [sys.executable, "-c", "import sys; sys.path[:0]=['%s','%s']; from wizard_rts.content import graph; p=graph.check(); print(p); sys.exit(1 if p else 0)" % (HYB, HYB.parent)]),
    ("catalogue audit runs", [sys.executable, str(HYB / "scripts" / "audit_catalogues.py")]),
    ("fast tests", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HYB / "tests" / "test_supervisor.py"), str(HYB / "tests" / "test_native_astar.py"),
                    str(HYB / "tests" / "test_content_graph.py"), str(HYB / "tests" / "test_draft_v2.py"), "-k", "not seven_rounds and not pick_times and not phase_opens "
                    "and not pick_removes and not leftover and not early_vp and not debounced and not split and not collapse and not bonus_hand"]),
    ("5-minute state-hash equality", [sys.executable, str(HYB / "scripts" / "hash_gate.py"), "check", "--baseline", str(HYB / "docs" / "perf" / "hash_baseline.json"),
                                       "--limit-minutes", "5"]),
]


def main() -> int:
    bad = 0
    for name, cmd in STEPS:
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HYB))
        ok = p.returncode == 0
        bad += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name} ({time.time() - t0:.0f} s)")
        if not ok:
            print((p.stdout + p.stderr)[-1500:])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
