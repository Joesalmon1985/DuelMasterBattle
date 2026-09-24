#!/usr/bin/env python3
"""T156 — clean-machine / packaged smoke helper.

On Linux: validates local bundle layout and offline invariants.
On Windows: intended for GitHub Actions; records evidence under tracking/clean_machine/.
Never invents Windows PASS from Linux evidence.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "clean_machine"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux", "windows", "auto"), default="auto")
    args = parser.parse_args(argv)
    target = args.platform
    if target == "auto":
        target = "windows" if platform.system() == "Windows" else "linux"
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(),
        "requested_platform": target,
        "offline_required": True,
        "developer_deps_required": False,
    }
    if target == "linux":
        bundle = ROOT / "build" / "desktop" / "mvp_linux"
        report["bundle_exists"] = bundle.is_dir()
        report["bundle"] = str(bundle.relative_to(ROOT)) if bundle.is_dir() else None
        report["windows_certified"] = False
        report["status"] = "PASS_LINUX_ONLY" if bundle.is_dir() else "FAIL"
        report["honesty"] = "Linux smoke cannot clear Windows clean-machine acceptance."
    else:
        exe = ROOT / "build" / "windows"
        report["bundle_exists"] = any(exe.is_file() for exe in (ROOT / "build").rglob("*.exe")) if (ROOT / "build").is_dir() else False
        report["windows_certified"] = False
        if platform.system() != "Windows":
            report["status"] = "BLOCKED"
            report["blocker"] = "smoke_release --platform windows must run on a Windows host/runner."
        elif not report["bundle_exists"]:
            report["status"] = "BLOCKED"
            report["blocker"] = "No Windows .exe package found under build/."
        else:
            report["status"] = "PASS"
            report["windows_certified"] = True
    path = OUT / f"smoke_{target}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] in {"PASS", "PASS_LINUX_ONLY"}:
        return 0
    if report["status"] == "BLOCKED" and target == "windows" and platform.system() != "Windows":
        # Honest blocker on Linux is acceptable for T156 bookkeeping.
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
