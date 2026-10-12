"""Run supervisor for unattended jobs (plan v2 section 11.3). Standard library only, no POSIX-only calls.

    python3 scripts/autorun/supervisor.py --name tourney1 -- python3 scripts/run_civilisation_tournament.py ...

Creates $DMB_RUNS/<name>/ (default ~/dmb_runs) holding manifest.json, supervisor.log, job.log, STATUS.json and heartbeat.
The job is restarted with exponential back-off when it exits non-zero or its heartbeat file stops changing for --stall-s
seconds. The same fatal error repeated --max-same times (identical last log line) stops the run instead of looping.
Stop cleanly by creating the file <run dir>/STOP. Refuses to start below --min-free-gb of free disk and stops if disk
drops below half of it. A job can show liveness by touching the path in env DMB_HEARTBEAT; if it never does, output growth
in job.log is the heartbeat.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def last_line(p: Path) -> str:
    try:
        data = p.read_bytes()[-2000:].decode(errors="replace").strip().splitlines()
        return data[-1] if data else ""
    except OSError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--stall-s", type=float, default=900)
    ap.add_argument("--max-restarts", type=int, default=8)
    ap.add_argument("--max-same", type=int, default=3)
    ap.add_argument("--min-free-gb", type=float, default=5.0)
    ap.add_argument("--poll-s", type=float, default=5.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("no command")
    root = Path(os.environ.get("DMB_RUNS", Path.home() / "dmb_runs")) / a.name
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free / 2**30
    if free < a.min_free_gb:
        print(f"refusing to start: {free:.1f} GB free < {a.min_free_gb}", file=sys.stderr)
        return 2
    stop = root / "STOP"
    stop.unlink(missing_ok=True)
    hb = root / "heartbeat"
    job_log = root / "job.log"
    log = (root / "supervisor.log").open("a", buffering=1)

    def say(msg: str) -> None:
        log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")

    manifest = {"name": a.name, "cmd": cmd, "git_sha": sha(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "python": sys.version.split()[0],
                "host": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    restarts, same, prev_err = 0, 0, ""
    active_s = 0.0
    state = "running"
    while True:
        env = dict(os.environ, DMB_HEARTBEAT=str(hb), DMB_RUN_DIR=str(root), PYTHONUNBUFFERED="1")
        hb.write_text(str(time.time()))
        with job_log.open("ab") as out:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, env=env)
        say(f"started pid {proc.pid} (restart {restarts})")
        t_start = last_change = time.time()
        sig = (hb.stat().st_mtime, job_log.stat().st_size)
        reason = ""
        while proc.poll() is None:
            time.sleep(a.poll_s)
            if stop.exists():
                reason = "stop file"
                break
            if shutil.disk_usage(root).free / 2**30 < a.min_free_gb / 2:
                reason = "disk space low"
                break
            cur = (hb.stat().st_mtime if hb.exists() else 0, job_log.stat().st_size)
            if cur != sig:
                sig, last_change = cur, time.time()
            elif time.time() - last_change > a.stall_s:
                reason = f"stalled {a.stall_s:.0f}s"
                break
            (root / "STATUS.json").write_text(json.dumps({"state": state, "pid": proc.pid, "restarts": restarts, "uptime_s": round(time.time() - t_start),
                                                          "last_output": last_line(job_log)[:300], "free_gb": round(shutil.disk_usage(root).free / 2**30, 1)}))
        active_s += time.time() - t_start
        if reason:
            proc.terminate()
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                proc.kill()
            say(f"killed job: {reason}")
            if reason in ("stop file", "disk space low"):
                state = "stopped: " + reason
                break
        elif proc.returncode == 0:
            state = "finished"
            say("job finished cleanly")
            break
        err = last_line(job_log)
        same = same + 1 if err == prev_err else 1
        prev_err = err
        restarts += 1
        say(f"job ended rc={proc.returncode} reason={reason or 'exit'} last={err[:200]!r}")
        if restarts > a.max_restarts or same >= a.max_same:
            state = "failed: too many restarts" if restarts > a.max_restarts else "failed: same error repeated"
            break
        time.sleep(min(300, 5 * 2 ** restarts))
    (root / "STATUS.json").write_text(json.dumps({"state": state, "restarts": restarts, "active_s": round(active_s)}))
    say(f"supervisor exit: {state}")
    return 0 if state in ("finished",) or state.startswith("stopped") else 1


if __name__ == "__main__":
    sys.exit(main())
