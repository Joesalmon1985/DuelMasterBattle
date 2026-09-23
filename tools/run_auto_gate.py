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

# Shell executables that mean "run with the repository Python interpreter".
_REPO_PYTHON_NAMES = frozenset({"python", "python3", "py"})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rewrite_shell_cmd(cmd: list[str], *, python_executable: str | None = None) -> list[str]:
    """Rewrite python/python3/py shell steps to the active interpreter.

    Gate JSON files historically start with literal ``python3``. On Windows the
    project may only expose ``.venv\\Scripts\\python.exe``. Substitute when the
    first token is a known Python launcher; leave arbitrary external commands
    (godot, bash, etc.) untouched.
    """
    if not cmd:
        return list(cmd)
    rewritten = [str(x) for x in cmd]
    head = Path(rewritten[0]).name.lower()
    # Windows may pass ``python3.exe``; strip suffix for comparison.
    if head.endswith(".exe"):
        head = head[:-4]
    if head in _REPO_PYTHON_NAMES:
        rewritten[0] = python_executable or sys.executable
    return rewritten


def _kill_process_tree(proc: subprocess.Popen[str] | None) -> None:
    """Best-effort cross-platform cleanup after timeout."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            if os.name == "nt":
                # Kill the whole child tree without touching unrelated processes.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    check=False,
                    capture_output=True,
                    timeout=10,
                )
            else:
                proc.kill()
            proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass
    if os.name != "nt":
        try:
            subprocess.run(["pkill", "-f", "Godot.*godot_project"], check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _load_gate(gate: str) -> dict:
    path = QA_GATES / f"{gate}.json"
    if not path.is_file():
        raise SystemExit(f"missing gate definition: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _run(cmd: list[str], *, cwd: Path, timeout: int, log_path: Path) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    env = os.environ.copy()
    cmd = rewrite_shell_cmd(cmd)
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, ValueError):
                stdout, stderr = "", ""
            log_path.write_text(
                f"$ {' '.join(cmd)}\nTIMEOUT after {timeout}s\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n",
                encoding="utf-8",
            )
            return {
                "cmd": cmd,
                "exit_code": 124,
                "duration_s": round(time.time() - started, 3),
                "log": str(log_path.relative_to(ROOT)),
                "status": "TIMEOUT",
            }
        log_path.write_text(
            f"$ {' '.join(cmd)}\nexit={proc.returncode}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n",
            encoding="utf-8",
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "duration_s": round(time.time() - started, 3),
            "log": str(log_path.relative_to(ROOT)),
            "status": "PASS" if proc.returncode == 0 else "FAIL",
        }
    except OSError as exc:
        log_path.write_text(
            f"$ {' '.join(cmd)}\nOSError: {exc}\n",
            encoding="utf-8",
        )
        return {
            "cmd": cmd,
            "exit_code": 127,
            "duration_s": round(time.time() - started, 3),
            "log": str(log_path.relative_to(ROOT)),
            "status": "FAIL",
            "error": str(exc),
        }
    finally:
        if proc is not None and proc.poll() is None:
            _kill_process_tree(proc)


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
        steps = []
        for step in spec.get("steps") or []:
            kind = str(step.get("kind") or "shell")
            entry = {"name": step.get("name"), "kind": kind}
            if kind == "shell":
                entry["cmd"] = rewrite_shell_cmd(list(step.get("cmd") or []))
            steps.append(entry)
        print(json.dumps({"gate": gate, "steps": steps, "dry_run": True}, indent=2))
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
            cmd = rewrite_shell_cmd(list(step.get("cmd") or []))
            results.append(_run(cmd, cwd=ROOT, timeout=timeout, log_path=log_path))
        else:
            results.append(
                {"name": name, "status": "FAIL", "exit_code": 2, "detail": f"unknown kind {kind}"}
            )
        results[-1]["name"] = name
        results[-1]["kind"] = kind

    failed = [r for r in results if r.get("status") not in {"PASS"}]
    status = "AUTO_READY_FOR_OWNER_REVIEW" if not failed else "AUTO_FAILED"
    # G12 aggregate may declare PARTIAL — BLOCKED BY G09 via GATE_STATUS= probe below.
    # G09: prefer honest pipeline status when present (PARTIAL / blockers).
    prior_path = out_dir / "result.json"
    if gate == "G09" and prior_path.is_file():
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            prior_status = str(prior.get("status") or "")
            if prior_status in {
                "PARTIAL_BLOCKED",
                "PARTIAL",
                "AUTO_FAILED",
                "AUTO_READY_FOR_OWNER_REVIEW",
            }:
                if not failed:
                    # Keep PARTIAL when infrastructure passes but qualification incomplete.
                    if prior_status.startswith("PARTIAL"):
                        status = prior_status
                    elif (
                        prior.get("qualified_policies", 3) < 3
                        and prior_status != "AUTO_READY_FOR_OWNER_REVIEW"
                    ):
                        status = prior_status
                else:
                    status = "AUTO_FAILED"
        except json.JSONDecodeError:
            pass
    # Optional gate-declared status probe from last successful step stdout.
    for r in results:
        log = r.get("log")
        if log:
            try:
                text = (ROOT / log).read_text(encoding="utf-8") if (ROOT / log).is_file() else ""
            except OSError:
                text = ""
            if "GATE_STATUS=" in text:
                for line in text.splitlines():
                    if line.startswith("GATE_STATUS="):
                        status = line.split("=", 1)[1].strip()
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
    # Preserve G09 pipeline fields when merging.
    if gate == "G09" and prior_path.is_file():
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            for key in ("qualified_policies", "blockers", "owner_review_status", "honesty", "evidence"):
                if key in prior and key not in report:
                    report[key] = prior[key]
            if prior.get("owner_review_status"):
                report["owner_review_status"] = prior["owner_review_status"]
        except json.JSONDecodeError:
            pass
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
            f"| {r.get('name')} | {r.get('kind')} | {r.get('status')} | "
            f"{r.get('exit_code')} | {r.get('duration_s', '')} |"
        )
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "status": status, "failed": len(failed)}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    # Avoid leaving orphans if parent dies mid-run.
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    raise SystemExit(main())
