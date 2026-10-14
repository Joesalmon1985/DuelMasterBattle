"""The manifest of a run or a model (execution plan T4.2; design 10.4): everything that decides whether a result can be reused.

`build(config)` records the code and rules versions, the content roster, the architecture and schema versions, the catastrophe level and scale, the machine
and the configuration. `compatible(a, b)` applies the rule of design 10.4:

    "incompatible"  different roster, architecture, observation schema, action schema or fitness schema (no weight surgery: refused)
    "reevaluate"    same architecture but different rules version, catastrophe level or outbreak scale (usable as a starting point, must be re-evaluated)
    "same"          nothing that matters differs (code SHA and dirty flag are recorded, not compared)
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from neuro import nets
from neuro import schema as S
from neuro.curriculum import Curriculum
from neuro.features import obs_schema_hash
from wizard_rts import RULES_VERSION, freeze

ACT_SCHEMA_VERSION = "act-1.0.0"
FIT_SCHEMA_VERSION = "fit-1.0.0"
SEED_STREAMS = ("train", "heldout", "control", "evolution", "imitation")
HYB = Path(__file__).resolve().parents[1]
REPO = HYB.parent

_cache: dict[str, Any] = {}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30).stdout.rstrip(chr(13) + chr(10))
    except Exception:  # noqa: BLE001 - no git is data, not an error
        return ""


def git_state() -> dict:
    sha = _git("rev-parse", "HEAD")
    dirty = [ln[3:] for ln in _git("status", "--porcelain", "--", "WizardRTSHybrid", "sim", "train_ai.py").splitlines()]
    return {"sha": sha, "dirty": bool(dirty), "dirty_files": sorted(dirty)[:20]}


def tree_hash(root: Path) -> str:
    """sha256 over the sorted relative file names and contents of a code tree (caches and compiled files excluded)."""
    key = f"tree:{root}"
    if key in _cache:
        return _cache[key]
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyd", ".so", ".dll"):
            h.update(p.relative_to(root).as_posix().encode())
            h.update(b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
    _cache[key] = h.hexdigest()
    return _cache[key]


def hardware() -> dict:
    out: dict[str, Any] = {"machine": platform.node(), "platform": platform.platform(), "cpu_count": os.cpu_count()}
    try:
        import psutil

        out["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        out["physical_cores"] = psutil.cpu_count(logical=False)
    except Exception:  # noqa: BLE001
        pass
    return out


def build(config: dict | None = None) -> dict:
    config = dict(config or {})
    cur = Curriculum.from_json(config.get("curriculum"))
    level = str(config.get("catastrophe_level", cur.current))
    return {
        "git": git_state(),
        "roster_version": freeze.ROSTER_VERSION,
        "roster_hash": freeze.roster_hash(),
        "rules_version": RULES_VERSION,
        "wizard_rts_sha256": tree_hash(HYB / "wizard_rts"),
        "architecture": {"version": nets.ARCH_VERSION, "genome_size": nets.genome_size()},
        "obs_schema": {"version": S.OBS_SCHEMA_VERSION, "hash": obs_schema_hash()},
        "act_schema_version": ACT_SCHEMA_VERSION,
        "fit_schema_version": FIT_SCHEMA_VERSION,
        "catastrophe_level": level,
        "outbreak_interval_scale": cur.scale_of(level),
        "curriculum": cur.to_json(),
        "config": config,
        "hardware": hardware(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "seed_streams": list(SEED_STREAMS),
    }


def differences(a: dict, b: dict) -> dict[str, list[str]]:
    """{'incompatible': [...], 'reevaluate': [...]} - what differs, by the rule of design 10.4."""
    hard, soft = [], []
    for name, get in (("roster_version", lambda m: m.get("roster_version")), ("architecture", lambda m: m.get("architecture", {}).get("version")),
                      ("obs_schema", lambda m: m.get("obs_schema", {}).get("version")), ("obs_schema_hash", lambda m: m.get("obs_schema", {}).get("hash")),
                      ("act_schema", lambda m: m.get("act_schema_version")), ("fit_schema", lambda m: m.get("fit_schema_version")),
                      ("roster_hash", lambda m: m.get("roster_hash"))):
        if get(a) != get(b):
            hard.append(f"{name}: {get(a)!r} != {get(b)!r}")
    for name in ("rules_version", "catastrophe_level", "outbreak_interval_scale"):
        if a.get(name) != b.get(name):
            soft.append(f"{name}: {a.get(name)!r} != {b.get(name)!r}")
    return {"incompatible": hard, "reevaluate": soft}


def compatible(a: dict, b: dict) -> str:
    d = differences(a, b)
    if d["incompatible"]:
        return "incompatible"
    return "reevaluate" if d["reevaluate"] else "same"
