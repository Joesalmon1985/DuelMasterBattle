#!/usr/bin/env python3
"""Summarise auto-gate screenshot/metadata evidence for morning review.

Usage:
  python tools/auto_visual_gate_report.py --gate G06
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True)
    args = ap.parse_args()
    gate = args.gate.upper()
    auto = TRACKING / gate / "auto"
    result_path = auto / "result.json"
    if not result_path.is_file():
        raise SystemExit(f"missing {result_path}; run tools/run_auto_gate.py --gate {gate}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    shots_dir = auto / "screenshots"
    shots = sorted(shots_dir.glob("**/*")) if shots_dir.is_dir() else []
    layout = TRACKING / gate / "layout_captures"
    layout_shots = sorted(layout.glob("*.png")) if layout.is_dir() else []
    meta = {
        "gate": gate,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "auto_status": result.get("status"),
        "steps_passed": sum(1 for r in result.get("results") or [] if r.get("status") == "PASS"),
        "steps_failed": sum(1 for r in result.get("results") or [] if r.get("status") != "PASS"),
        "auto_screenshots": [str(p.relative_to(ROOT)) for p in shots if p.is_file()],
        "layout_captures": [str(p.relative_to(ROOT)) for p in layout_shots],
        "human_acceptance": "PENDING",
    }
    out = auto / "visual_report.json"
    out.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "status": meta["auto_status"], "report": str(out.relative_to(ROOT))}))
    return 0 if meta["auto_status"] == "AUTO_READY_FOR_OWNER_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
