"""The game pool (execution plan T5.1): every game runs in its own Python process started from the run's code copy.

`GamePool(n, code_dir).run(jobs)` keeps up to n games running. A game that crashes writes `repro.json` and is run once more; a second failure voids it. A game whose
heartbeat (touched every 60 game seconds) goes stale for `stall_s`, or that runs past `kill_after_s` of wall time, is killed and run once more. The processes start
with below-normal priority so the PC stays usable. A STOP request lets the games in flight finish (STOP containing "now": kill them).

(The plan says a `multiprocessing` spawn pool; a plain subprocess per game does the same job and lets the worker import the run's frozen code copy rather than the
parent's modules, which a spawn pool cannot do because it unpickles the entry point from the parent's sys.path.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

HYB = Path(__file__).resolve().parents[1]
BELOW_NORMAL = 0x00004000
NO_WINDOW = 0x08000000


@dataclass
class Job:
    job_id: str
    dir: Path
    spec: dict[str, Any]  # {"episode": {...}, "seats": {...}, "log_decisions": bool, "tag": {...}}
    attempt: int = 1
    started: float = 0.0
    proc: Any = None
    notes: list[str] = field(default_factory=list)


def worker_env(code_dir: Path | None) -> tuple[dict[str, str], Path]:
    """(environment, working directory) of a worker: the run's code copy when given, else the live source tree."""
    if code_dir is None:
        top, hyb = HYB.parent, HYB
    else:
        top, hyb = Path(code_dir), Path(code_dir) / "WizardRTSHybrid"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(hyb) + os.pathsep + str(top)
    env["HYBRID_AI"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("DMB_UNFREEZE", None)
    return env, hyb


class GamePool:
    def __init__(self, n: int, code_dir: str | Path | None = None, stall_s: float = 1200.0, kill_after_s: float = 14400.0, poll_s: float = 0.5) -> None:
        self.n = max(1, int(n))
        self.code_dir = Path(code_dir) if code_dir else None
        self.stall_s, self.kill_after_s, self.poll_s = float(stall_s), float(kill_after_s), float(poll_s)
        self.events: list[dict] = []  # crashes, kills, voids (the session report prints them)

    # ------------------------------------------------------------------------------------------------------------------------ one process
    def _launch(self, job: Job) -> None:
        job.dir.mkdir(parents=True, exist_ok=True)
        for stale in ("result.json", "heartbeat"):
            (job.dir / stale).unlink(missing_ok=True)
        (job.dir / "job.json").write_text(json.dumps({"job_id": job.job_id, **job.spec}, indent=1, default=str), encoding="utf-8")
        env, cwd = worker_env(self.code_dir)
        flags = (BELOW_NORMAL | NO_WINDOW) if os.name == "nt" else 0
        log = open(job.dir / f"worker_{job.attempt}.log", "wb")
        job.proc = subprocess.Popen([sys.executable, "-m", "neuro.run_job", str(job.dir)], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        job.started = time.time()

    @staticmethod
    def _kill(job: Job) -> None:
        try:
            job.proc.kill()
            job.proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            pass

    def _failed(self, job: Job, reason: str, queue: list[Job], results: dict[str, dict]) -> None:
        self.events.append({"job": job.job_id, "attempt": job.attempt, "event": reason})
        repro = job.dir / "repro.json"
        if not repro.exists():
            repro.write_text(json.dumps({"job": {"job_id": job.job_id, **job.spec}, "reason": reason, "attempt": job.attempt}, indent=1, default=str), encoding="utf-8")
        if job.attempt == 1:
            repro.replace(job.dir / "repro_1.json")
            job.attempt, job.proc = 2, None
            queue.insert(0, job)
        else:
            results[job.job_id] = {"job_id": job.job_id, "tag": job.spec.get("tag", {}), "voided": True, "reason": reason, "ok": False}
            self.events.append({"job": job.job_id, "event": "voided"})

    # ------------------------------------------------------------------------------------------------------------------------ the loop
    def run(self, jobs: list[Job], stop: Callable[[], str] | None = None, on_result: Callable[[dict], None] | None = None) -> dict[str, dict]:
        """Run all jobs; returns job_id -> result dict (voided ones have voided=True). `stop()` returns "", "graceful" or "now"."""
        queue = list(jobs)
        running: list[Job] = []
        results: dict[str, dict] = {}
        while queue or running:
            mode = stop() if stop else ""
            if mode == "now":
                for j in running:
                    self._kill(j)
                    self.events.append({"job": j.job_id, "event": "killed_by_stop"})
                for j in queue + running:
                    results[j.job_id] = {"job_id": j.job_id, "tag": j.spec.get("tag", {}), "voided": True, "reason": "stopped", "ok": False}
                break
            if mode == "graceful":
                for j in queue:
                    results[j.job_id] = {"job_id": j.job_id, "tag": j.spec.get("tag", {}), "voided": True, "reason": "not_started", "ok": False}
                queue = []
            while queue and len(running) < self.n:
                j = queue.pop(0)
                self._launch(j)
                running.append(j)
            time.sleep(self.poll_s)
            for j in list(running):
                code = j.proc.poll()
                if code is None:
                    hb = j.dir / "heartbeat"
                    last = max(j.started, hb.stat().st_mtime if hb.exists() else 0.0)
                    if time.time() - last > self.stall_s:
                        self._kill(j)
                        running.remove(j)
                        self._failed(j, "stalled", queue, results)
                    elif time.time() - j.started > self.kill_after_s:
                        self._kill(j)
                        running.remove(j)
                        self._failed(j, "wall_cap", queue, results)
                    continue
                running.remove(j)
                res = j.dir / "result.json"
                if code == 0 and res.exists():
                    try:
                        results[j.job_id] = json.loads(res.read_text(encoding="utf-8"))
                        if on_result:
                            on_result(results[j.job_id])
                        continue
                    except Exception:  # noqa: BLE001
                        pass
                self._failed(j, f"crashed(exit {code})", queue, results)
        return results


def make_job(job_id: str, directory: str | Path, episode: dict, seats: dict[str, str], tag: dict | None = None, log_decisions: bool = False,
             log_seats: list[str] | None = None) -> Job:
    spec: dict[str, Any] = {"episode": episode, "seats": seats, "log_decisions": log_decisions, "tag": tag or {}}
    if log_seats is not None:
        spec["log_seats"] = log_seats
    return Job(job_id, Path(directory), spec)
