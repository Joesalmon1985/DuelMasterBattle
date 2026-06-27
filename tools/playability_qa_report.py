#!/usr/bin/env python3
"""Playability QA checks for PLAYABILITY_VISUAL_PRD.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "qa" / "reports"

CAST_THUMB_MIN_Y = 0.60
FEEDBACK_LOCK_MAX_S = 1.2
DRAG_THRESHOLD_MIN = 12


def load_audit() -> dict:
    p = REPORTS / "capture_audit.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"touch_targets": [], "playability": {}}


def check_cast_thumb_zone(targets: list, viewport_h: float = 1280.0) -> list[str]:
    warnings: list[str] = []
    cast_targets = [t for t in targets if t.get("role") == "cast"]
    if not cast_targets:
        warnings.append("No cast button in touch audit")
        return warnings
    for t in cast_targets:
        gy = float(t.get("global_y", 0))
        h = float(t.get("height", 0))
        center_ratio = (gy + h * 0.5) / viewport_h
        if center_ratio <= CAST_THUMB_MIN_Y:
            warnings.append(
                f"Cast button center Y ratio {center_ratio:.2f} below {CAST_THUMB_MIN_Y}"
            )
    return warnings


def check_touch_mins(targets: list) -> list[str]:
    warnings: list[str] = []
    mins = {"cast": 96, "locus": 72, "essence": 72, "secondary": 56, "utility": 48}
    for t in targets:
        role = t.get("role", "utility")
        min_sz = mins.get(role, 48)
        w = float(t.get("width", 0))
        h = float(t.get("height", 0))
        if w < min_sz or h < min_sz:
            warnings.append(f"Touch '{t.get('name', '?')}' ({role}) {w:.0f}x{h:.0f} < {min_sz}")
    return warnings


def check_playability_block(data: dict) -> list[str]:
    warnings: list[str] = []
    pb = data.get("playability", {})
    if pb.get("drag_threshold_px", DRAG_THRESHOLD_MIN) < DRAG_THRESHOLD_MIN:
        warnings.append("Drag threshold below 12px")
    if pb.get("feedback_lock_duration_s", 0) > FEEDBACK_LOCK_MAX_S:
        warnings.append("Feedback lock exceeds 1.2s")
    if pb.get("picker_above_locus") is False:
        warnings.append("Picker opens below locus (finger occlusion risk)")
    if pb.get("ftue_completable") is False:
        warnings.append("FTUE first cast not completable without help modal")
    return warnings


def main() -> int:
    audit = load_audit()
    targets = audit.get("touch_targets", [])
    warnings: list[str] = []
    warnings.extend(check_cast_thumb_zone(targets))
    warnings.extend(check_touch_mins(targets))
    warnings.extend(check_playability_block(audit))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pass": len(warnings) == 0,
        "warnings": warnings,
        "checks": {
            "cast_thumb_zone_min_y": CAST_THUMB_MIN_Y,
            "drag_threshold_min_px": DRAG_THRESHOLD_MIN,
            "feedback_lock_max_s": FEEDBACK_LOCK_MAX_S,
        },
    }
    out = REPORTS / "playability_qa_latest.json"
    out.write_text(json.dumps(report, indent=2))
    md = REPORTS / "playability_qa_latest.md"
    lines = [
        "# Playability QA",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Pass:** {'yes' if report['pass'] else 'no'}",
        "",
    ]
    if warnings:
        lines.append("## Warnings")
        lines.extend(f"- {w}" for w in warnings)
    else:
        lines.append("All playability checks passed.")
    md.write_text("\n".join(lines) + "\n")
    print(md.read_text())
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
