"""Reproducible run records: seeds, config, code SHA, curves and checkpoints in a run directory outside git (default ~/dmb_runs)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def code_sha() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "WizardRTSHybrid/wizard_rts"], capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def runs_dir() -> Path:
    return Path(os.environ.get("DMB_RUNS_DIR", str(Path.home() / "dmb_runs")))


class Run:
    def __init__(self, domain: str, config: dict[str, Any], name: str | None = None) -> None:
        self.dir = runs_dir() / domain / (name or time.strftime("%Y%m%d-%H%M%S"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta = {"domain": domain, "config": config, "code_sha": code_sha(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "python": os.sys.version.split()[0]}
        self.curves: list[dict[str, Any]] = []
        self.flush()

    def log(self, **kw: Any) -> None:
        self.curves.append(kw)

    def flush(self) -> None:
        (self.dir / "run.json").write_text(json.dumps({**self.meta, "curves": self.curves}, indent=1, default=str))

    def save_json(self, name: str, obj: Any) -> Path:
        p = self.dir / name
        p.write_text(json.dumps(obj, indent=1, default=str))
        return p
