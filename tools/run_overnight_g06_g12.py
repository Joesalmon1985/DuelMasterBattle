#!/usr/bin/env python3
"""Resumable overnight G06→G12 orchestration.

Records stage state under tracking/overnight/ so a crashed Cursor/terminal can
resume without redoing verified expensive stages. Fail-closed: never infers a
gate PASS from a stale report when source inputs changed.

Usage:
  .\\.venv\\Scripts\\python.exe tools\\run_overnight_g06_g12.py --resume
  .\\.venv\\Scripts\\python.exe tools\\run_overnight_g06_g12.py --from-stage g06
  .\\.venv\\Scripts\\python.exe tools\\run_overnight_g06_g12.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "overnight"
STATE_PATH = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"

STAGES: list[dict] = [
    {
        "id": "ward_duel_regression",
        "title": "Ward Duel presentation regression",
        "inputs": [
            "godot_project/client/core/presentation_mode.gd",
            "godot_project/client/scenes/g05_shell.gd",
            "godot_project/client/tests/run_ward_duel_presentation.gd",
        ],
        "cmd": [
            "{godot}",
            "--headless",
            "--path",
            "godot_project",
            "--script",
            "res://client/tests/run_ward_duel_presentation.gd",
        ],
        "timeout_s": 300,
    },
    {
        "id": "auto_gate_portability",
        "title": "Auto-gate python portability unit tests",
        "inputs": ["tools/run_auto_gate.py", "tests/tools/test_run_auto_gate_portability.py"],
        "cmd": ["{python}", "-m", "pytest", "-q", "tests/tools/test_run_auto_gate_portability.py"],
        "timeout_s": 120,
    },
    {
        "id": "g06",
        "title": "G06 gate (fresh evidence)",
        "inputs": ["qa/auto_gates/G06.json", "tools/run_auto_gate.py", "tools/evaluate_mvp.py"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G06"],
        "timeout_s": 3600,
    },
    {
        "id": "g07",
        "title": "G07 gate (fresh evidence)",
        "inputs": ["qa/auto_gates/G07.json", "tools/evaluate_full_world.py"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G07"],
        "timeout_s": 7200,
    },
    {
        "id": "g08",
        "title": "G08 gate (fresh evidence)",
        "inputs": ["qa/auto_gates/G08.json", "tools/content/validate_corpus.py"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G08"],
        "timeout_s": 7200,
    },
    {
        "id": "g09_pipeline",
        "title": "G09 honest training/selection pipeline",
        "inputs": [
            "tools/run_g09_pipeline.py",
            "training/select_library.py",
            "training/train_imitation.py",
            "training/evaluate.py",
        ],
        "cmd": ["{python}", "tools/run_g09_pipeline.py"],
        "timeout_s": 86400,
        "expensive": True,
    },
    {
        "id": "g09_gate",
        "title": "G09 gate check after pipeline",
        "inputs": ["qa/auto_gates/G09.json", "godot_project/content/policies/manifest.json"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G09"],
        "timeout_s": 1800,
        "depends_on": ["g09_pipeline"],
    },
    {
        "id": "g10",
        "title": "G10 release candidate",
        "inputs": ["qa/auto_gates/G10.json"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G10"],
        "timeout_s": 7200,
        "depends_on": ["g09_gate"],
    },
    {
        "id": "g11",
        "title": "G11 semantic + visual evidence",
        "inputs": ["qa/auto_gates/G11.json", "tools/validate_semantic_catalogue.py"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G11"],
        "timeout_s": 3600,
        "depends_on": ["g10"],
    },
    {
        "id": "g12",
        "title": "G12 aggregate",
        "inputs": ["qa/auto_gates/G12.json", "tools/run_g12_aggregate.py"],
        "cmd": ["{python}", "tools/check.py", "--gate", "G12"],
        "timeout_s": 3600,
        "depends_on": ["g11"],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_python() -> str:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return str(venv)
    venv2 = ROOT / ".venv" / "bin" / "python"
    if venv2.is_file():
        return str(venv2)
    return sys.executable


def _resolve_godot() -> str:
    env = os.environ.get("GODOT", "").strip().strip('"')
    if env and Path(env).is_file():
        return env
    local = ROOT / ".dmb_windows_local.json"
    if local.is_file():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
            g = str(data.get("godot") or "")
            if g and Path(g).is_file():
                return g
        except (OSError, json.JSONDecodeError):
            pass
    return os.environ.get("GODOT", "godot")


def _hash_inputs(paths: list[str]) -> str:
    h = hashlib.sha256()
    for rel in paths:
        path = ROOT / rel
        h.update(rel.encode())
        if path.is_file():
            h.update(path.read_bytes())
        else:
            h.update(b"MISSING")
    return h.hexdigest()[:16]


def _load_state() -> dict:
    if not STATE_PATH.is_file():
        return {"version": 1, "stages": {}, "updated_at": None}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "stages": {}, "updated_at": None, "corrupt": True}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _expand_cmd(cmd: list[str], *, python: str, godot: str) -> list[str]:
    return [c.replace("{python}", python).replace("{godot}", godot) for c in cmd]


def _stage_verified(state: dict, stage: dict) -> bool:
    rec = (state.get("stages") or {}).get(stage["id"]) or {}
    if rec.get("status") != "VERIFIED":
        return False
    expected = _hash_inputs(stage.get("inputs") or [])
    return rec.get("input_hash") == expected and rec.get("exit_code") == 0


def run_stage(stage: dict, *, force: bool = False) -> dict:
    state = _load_state()
    stage_id = stage["id"]
    input_hash = _hash_inputs(stage.get("inputs") or [])
    if not force and _stage_verified(state, stage):
        print(json.dumps({"stage": stage_id, "action": "skip_verified", "input_hash": input_hash}))
        return {"status": "SKIPPED_VERIFIED", "input_hash": input_hash}

    for dep in stage.get("depends_on") or []:
        dep_stage = next((s for s in STAGES if s["id"] == dep), None)
        if dep_stage is None:
            continue
        if not _stage_verified(state, dep_stage):
            msg = f"dependency {dep} not verified — fail closed"
            print(json.dumps({"stage": stage_id, "action": "blocked", "reason": msg}))
            rec = {
                "status": "BLOCKED",
                "reason": msg,
                "input_hash": input_hash,
                "finished_at": _now(),
            }
            state.setdefault("stages", {})[stage_id] = rec
            _save_state(state)
            return rec

    python = _resolve_python()
    godot = _resolve_godot()
    cmd = _expand_cmd(stage["cmd"], python=python, godot=godot)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"{stamp}_{stage_id}.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["GODOT"] = godot
    env["DMB_PYTHON"] = python
    print(json.dumps({"stage": stage_id, "action": "start", "cmd": cmd, "log": str(log_path)}), flush=True)
    started = time.time()
    state.setdefault("stages", {})[stage_id] = {
        "status": "RUNNING",
        "cmd": cmd,
        "input_hash": input_hash,
        "started_at": _now(),
        "log": str(log_path.relative_to(ROOT)),
    }
    _save_state(state)
    try:
        with log_path.open("w", encoding="utf-8") as log_fh:
            log_fh.write(f"$ {' '.join(cmd)}\n")
            log_fh.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log_fh.write(line)
                log_fh.flush()
                # Mirror progress for overnight monitoring.
                sys.stdout.write(line)
                sys.stdout.flush()
            code = proc.wait(timeout=int(stage.get("timeout_s") or 3600))
        ok = code == 0
        rec = {
            "status": "VERIFIED" if ok else "FAILED",
            "exit_code": code,
            "duration_s": round(time.time() - started, 3),
            "input_hash": input_hash,
            "cmd": cmd,
            "log": str(log_path.relative_to(ROOT)),
            "finished_at": _now(),
        }
    except subprocess.TimeoutExpired:
        try:
            proc.kill()  # type: ignore[name-defined]
        except Exception:
            pass
        with log_path.open("a", encoding="utf-8") as log_fh:
            log_fh.write("\nTIMEOUT\n")
        rec = {
            "status": "TIMEOUT",
            "exit_code": 124,
            "duration_s": round(time.time() - started, 3),
            "input_hash": input_hash,
            "cmd": cmd,
            "log": str(log_path.relative_to(ROOT)),
            "finished_at": _now(),
        }
    state.setdefault("stages", {})[stage_id] = rec
    _save_state(state)
    print(json.dumps({"stage": stage_id, "action": "done", **{k: rec[k] for k in ("status", "exit_code", "duration_s")}}), flush=True)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resume", action="store_true", help="Skip VERIFIED stages whose inputs match")
    ap.add_argument("--from-stage", default="", help="Start from this stage id")
    ap.add_argument("--only", default="", help="Run only this stage id")
    ap.add_argument("--force", action="store_true", help="Re-run even if verified")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--continue-on-fail", action="store_true", help="Keep going after non-expensive failures")
    args = ap.parse_args(argv)

    if args.list:
        state = _load_state()
        for s in STAGES:
            rec = (state.get("stages") or {}).get(s["id"]) or {}
            print(f"{s['id']:24} {rec.get('status', 'PENDING'):16} {s['title']}")
        return 0

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    start_idx = 0
    if args.from_stage:
        ids = [s["id"] for s in STAGES]
        if args.from_stage not in ids:
            raise SystemExit(f"unknown stage: {args.from_stage}")
        start_idx = ids.index(args.from_stage)

    stages = STAGES[start_idx:]
    if args.only:
        stages = [s for s in STAGES if s["id"] == args.only]
        if not stages:
            raise SystemExit(f"unknown stage: {args.only}")

    # Ensure resume is the default behaviour when --resume is passed (skip verified).
    force = bool(args.force)
    failures = 0
    for stage in stages:
        if args.resume and not force and _stage_verified(_load_state(), stage):
            print(json.dumps({"stage": stage["id"], "action": "skip_verified"}))
            continue
        rec = run_stage(stage, force=force)
        if rec.get("status") not in {"VERIFIED", "SKIPPED_VERIFIED"}:
            failures += 1
            if stage.get("expensive") or not args.continue_on_fail:
                print(json.dumps({"overnight": "stopped", "failed_stage": stage["id"], "status": rec.get("status")}))
                return 1
    print(json.dumps({"overnight": "complete", "failures": failures, "state": str(STATE_PATH.relative_to(ROOT))}))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
