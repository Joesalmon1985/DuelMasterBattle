#!/usr/bin/env python3
"""Run an automated visual/semantic gate for G06–G12.

Usage:
  python tools/run_auto_gate.py --gate G06
  python tools/run_auto_gate.py --gate G06 --dry-run

Returns non-zero on failure. Preserves logs under tracking/gates/<GATE>/auto/.
Does NOT invent human PASS — records AUTO_READY_FOR_OWNER_REVIEW candidates.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA_GATES = ROOT / "qa" / "auto_gates"
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_gate(gate: str) -> dict:
    path = QA_GATES / f"{gate}.json"
    if not path.is_file():
        raise SystemExit(f"missing gate definition: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _run(cmd: list[str], *, cwd: Path, timeout: int, log_path: Path) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log_path.write_text(
            f"$ {' '.join(cmd)}\nexit={proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
            encoding="utf-8",
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "duration_s": round(time.time() - started, 3),
            "log": str(log_path.relative_to(ROOT)),
            "status": "PASS" if proc.returncode == 0 else "FAIL",
        }
    except subprocess.TimeoutExpired as exc:
        # Best-effort kill of hung Godot/sidecar trees
        try:
            subprocess.run(["pkill", "-f", "Godot.*godot_project"], check=False)
        except OSError:
            pass
        out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log_path.write_text(
            f"$ {' '.join(cmd)}\nTIMEOUT after {timeout}s\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}\n",
            encoding="utf-8",
        )
        return {
            "cmd": cmd,
            "exit_code": 124,
            "duration_s": round(time.time() - started, 3),
            "log": str(log_path.relative_to(ROOT)),
            "status": "TIMEOUT",
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True, help="G06 … G12")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    gate = args.gate.upper()
    spec = _load_gate(gate)
    out_dir = TRACKING / gate / "auto"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    if args.dry_run:
        print(json.dumps({"gate": gate, "steps": spec.get("steps"), "dry_run": True}, indent=2))
        return 0
    for i, step in enumerate(spec.get("steps") or []):
        name = str(step.get("name") or f"step_{i}")
        kind = str(step.get("kind") or "shell")
        timeout = int(step.get("timeout_s") or 180)
        log_path = out_dir / "logs" / f"{i:02d}_{name}.log"
        if kind == "pytest":
            paths = step.get("paths") or []
            cmd = [sys.executable, "-m", "pytest", "-q", *[str(p) for p in paths]]
            results.append(_run(cmd, cwd=ROOT, timeout=timeout, log_path=log_path))
        elif kind == "check_task":
            task = str(step["task"])
            cmd = [sys.executable, "tools/check.py", "--task", task]
            results.append(_run(cmd, cwd=ROOT, timeout=timeout, log_path=log_path))
        elif kind == "godot_script":
            script = str(step["script"])
            godot = os.environ.get("GODOT") or str(
                Path.home() / "Documents/Godot/Godot_v4.4.1-stable_linux.x86_64"
            )
            res = str(step.get("resolution") or "450x800")
            headed = bool(step.get("headed", False))
            cmd = [godot, "--path", str(ROOT / "godot_project"), "--resolution", res]
            if not headed:
                cmd.insert(1, "--headless")
            cmd += ["--script", script]
            results.append(_run(cmd, cwd=ROOT, timeout=timeout, log_path=log_path))
        elif kind == "shell":
            cmd = list(step.get("cmd") or [])
            results.append(_run(cmd, cwd=ROOT, timeout=timeout, log_path=log_path))
        else:
            results.append({"name": name, "status": "FAIL", "exit_code": 2, "detail": f"unknown kind {kind}"})
        results[-1]["name"] = name
        results[-1]["kind"] = kind

    failed = [r for r in results if r.get("status") not in {"PASS"}]
    status = "AUTO_READY_FOR_OWNER_REVIEW" if not failed else "AUTO_FAILED"
    report = {
        "gate": gate,
        "generated_at": _now(),
        "status": status,
        "human_acceptance": "PENDING — never invent PASS",
        "results": results,
        "spec": spec.get("id") or gate,
        "seed": spec.get("seed"),
        "fixture": spec.get("fixture"),
    }
    (out_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = out_dir / "summary.md"
    lines = [
        f"# {gate} automated gate",
        "",
        f"**Status:** `{status}`",
        "",
        "Human acceptance remains PENDING. Automation does not equal PASS.",
        "",
        "| Step | Kind | Status | Exit | Duration |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.get('name')} | {r.get('kind')} | {r.get('status')} | {r.get('exit_code')} | {r.get('duration_s', '')} |"
        )
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "status": status, "failed": len(failed)}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    # Avoid leaving orphans if parent dies mid-run.
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    raise SystemExit(main())
