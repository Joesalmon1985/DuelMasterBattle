"""One game in its own process (execution plan T5.1): `python -m neuro.run_job <job_dir>`.

Reads <job_dir>/job.json, plays the game, writes <job_dir>/result.json atomically (heartbeat file touched every 60 game seconds). On any exception writes
<job_dir>/repro.json (seed, seats, genome files, config, code SHA, traceback) and exits with status 3, so the parent can requeue or void the job.
Seat specs: "plus" | "baseline" (heuristic AIs) | "genome:<path to .npy>" (a neural controller).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path


def _atomic_json(path: Path, obj: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def run(job_dir: Path) -> dict:
    os.environ.setdefault("HYBRID_AI", "1")
    import numpy as np

    from neuro import nets
    from neuro.controller import Controller, DecisionLog
    from neuro.episode import EpisodeConfig, run_episode

    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    if job.get("kind") == "shadow":
        from neuro import imitation

        out = imitation.record_shadow(job_dir, job)
        _atomic_json(job_dir / "result.json", out)
        return out
    seats: dict[str, str] = job["seats"]
    genome_seats = {s: v[len("genome:"):] for s, v in seats.items() if v.startswith("genome:")}
    opponents = {s: v for s, v in seats.items() if not v.startswith("genome:")}
    ep = dict(job["episode"])
    ep.pop("agent_seats", None)
    ep.pop("opponents", None)
    cfg = EpisodeConfig(**ep, agent_seats=tuple(sorted(genome_seats)), opponents=opponents)
    log = DecisionLog(job_dir / "decisions.jsonl.gz") if job.get("log_decisions") else None
    cache: dict[str, object] = {}
    ctls = {}
    for seat, path in sorted(genome_seats.items()):
        if path not in cache:
            cache[path] = nets.Nets(np.load(path).astype(np.float32))
        ctls[seat] = Controller(None, seat, cache[path], cfg, int(cfg.seed), log if seat in job.get("log_seats", sorted(genome_seats)) else None)
    t0 = time.time()
    ep_dir = job_dir / "ep"
    res = run_episode(cfg, ctls, log_dir=ep_dir, heartbeat=job_dir / "heartbeat")
    if log is not None:
        log.close()
    out = {"job_id": job["job_id"], "tag": job.get("tag", {}), "seats": seats, "config": asdict(cfg), "result": asdict(res), "wall_s": round(time.time() - t0, 1),
           "stats": {s: c.stats() for s, c in ctls.items()}, "ok": True}
    _atomic_json(job_dir / "result.json", out)
    for f in ("ep",):
        d = job_dir / f
        if d.exists():
            import shutil

            shutil.rmtree(d, ignore_errors=True)
    return out


def main(argv: list[str]) -> int:
    job_dir = Path(argv[0])
    try:
        run(job_dir)
        return 0
    except BaseException:  # noqa: BLE001 - everything goes into the repro file
        tb = traceback.format_exc()
        try:
            job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            job = {}
        sha = ""
        try:
            from neuro import manifest

            sha = manifest.git_state().get("sha", "")
        except Exception:  # noqa: BLE001
            pass
        _atomic_json(job_dir / "repro.json", {"job": job, "sha": sha, "traceback": tb})
        sys.stderr.write(tb)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
