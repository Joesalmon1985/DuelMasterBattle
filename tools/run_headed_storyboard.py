#!/usr/bin/env python3
"""Run headed Godot storyboard capture for one gate with timeouts + orphan cleanup.

Usage:
  python tools/run_headed_storyboard.py --gate G06
  python tools/run_headed_storyboard.py --gate G06 --resolution 450x800 --timeout 240
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_godot() -> str:
    env = os.environ.get("GODOT")
    if env and Path(env).is_file() and os.access(env, os.X_OK):
        return env
    candidates = [
        Path.home() / "Documents/Godot/Godot_v4.4.1-stable_linux.x86_64",
        Path.home() / "Documents/Godot/Godot_v4.5.2-stable_linux.x86_64",
        Path("/usr/local/bin/godot"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    raise SystemExit("Godot binary not found; set GODOT=")


def _cleanup() -> None:
    for pat in ("Godot.*godot_project", "Godot.*DuelMasterBattle"):
        subprocess.run(["pkill", "-f", pat], check=False, capture_output=True)
    time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True)
    ap.add_argument("--resolution", default="450x800")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--headed", action="store_true", default=True)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    gate = args.gate.upper()
    godot = _find_godot()
    out_dir = (
        ROOT
        / "Pack"
        / "DuelMasterBattle_Build_Pack"
        / "tracking"
        / "gates"
        / gate
        / "auto"
        / "screenshots"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"storyboard_{gate.lower()}.log"

    _cleanup()
    cmd = [
        godot,
        "--path",
        str(ROOT / "godot_project"),
        "--resolution",
        args.resolution,
    ]
    if args.headless:
        cmd.insert(1, "--headless")
    cmd += [
        "--script",
        "res://client/tests/run_auto_gate_storyboard.gd",
        "--",
        f"--gate={gate}",
    ]
    env = os.environ.copy()
    env["DMB_AUTO_GATE"] = gate
    env["DMB_RESOLUTION"] = args.resolution
    env.setdefault("GODOT_USER_DATA_DIR", str(ROOT / "godot_project" / ".godot_user"))

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            start_new_session=True,
        )
        log_path.write_text(
            f"$ {' '.join(cmd)}\nexit={proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
            encoding="utf-8",
        )
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(exc.pid, signal.SIGKILL)  # type: ignore[arg-type]
        except (ProcessLookupError, AttributeError, OSError):
            pass
        _cleanup()
        out = (exc.stdout or b"")
        err = (exc.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        log_path.write_text(
            f"$ {' '.join(cmd)}\nTIMEOUT after {args.timeout}s\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}\n",
            encoding="utf-8",
        )
        print(f"BLOCKER: headed storyboard timed out after {args.timeout}s; see {log_path}")
        return 124
    finally:
        _cleanup()

    shots = list(out_dir.glob("*.png"))
    print(
        {
            "gate": gate,
            "exit": code,
            "duration_s": round(time.time() - started, 2),
            "shots": len(shots),
            "log": str(log_path.relative_to(ROOT)),
        }
    )
    return 0 if code == 0 and shots else (code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
