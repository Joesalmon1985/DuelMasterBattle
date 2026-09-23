#!/usr/bin/env python3
"""Drive headed in-world visual review captures at multiple resolutions.

Does not invent PASS — writes an owner-readable report under G11/visual_review.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates" / "G11" / "visual_review"
SCRIPT = "res://client/tests/run_visual_review_harness.gd"


def _godot() -> str:
    env = os.environ.get("GODOT", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    local = ROOT / ".dmb_windows_local.json"
    if local.is_file():
        data = json.loads(local.read_text(encoding="utf-8"))
        g = str(data.get("godot") or "")
        if g and Path(g).is_file():
            return g
    raise SystemExit("Godot not found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolutions", default="450x800,1280x720")
    ap.add_argument("--suite", default="all")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    godot = _godot()
    results = []
    for res in [r.strip() for r in args.resolutions.split(",") if r.strip()]:
        env = os.environ.copy()
        env["DMB_SHOT_DIR"] = str(OUT)
        env["DMB_VISUAL_REVIEW_SUITE"] = args.suite
        env["DMB_VISUAL_REVIEW"] = "1"
        cmd = [godot, "--path", str(ROOT / "godot_project"), "--resolution", res]
        if args.headless:
            cmd.insert(1, "--headless")
        cmd += ["--script", SCRIPT]
        print(json.dumps({"capture": res, "cmd": cmd}), flush=True)
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600)
        log = OUT / f"capture_{res.replace('x', '_')}.log"
        log.write_text(
            f"$ {' '.join(cmd)}\nexit={proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
            encoding="utf-8",
        )
        results.append({"resolution": res, "exit_code": proc.returncode, "log": str(log.relative_to(ROOT))})
        if proc.returncode != 0:
            print(proc.stdout[-1000:])
            print(proc.stderr[-1000:])
    shots = sorted(p.name for p in OUT.glob("*.png"))
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suite": args.suite,
        "results": results,
        "screenshots": shots,
        "human_acceptance": "PENDING — aesthetic judgement is owner-only",
        "notes": (
            "Real in-world Godot frames. Structural Ward Duel cleanliness is asserted in "
            "run_ward_duel_presentation.gd; this report does not invent visual PASS."
        ),
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# G11 / G12 in-world visual review",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "Human aesthetic PASS is **not** claimed.",
        "",
        "## Screenshots",
        "",
    ]
    for name in shots:
        lines.append(f"- `{name}`")
    lines.extend(["", "## Captures", ""])
    for r in results:
        lines.append(f"- {r['resolution']}: exit={r['exit_code']} (`{r['log']}`)")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": all(r["exit_code"] == 0 for r in results), "shots": len(shots)}))
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
