"""T5.1: the game pool runs games in separate processes, survives crashes and voids a job that fails twice."""
import json

import numpy as np

from neuro import nets
from neuro.workers import GamePool, make_job

EP = {"seed": 21, "game_minutes": 3, "map_size": "small", "checkpoint_game_minutes": 10 ** 6}


def test_a_two_job_pool_completes_and_a_failing_job_is_voided_with_a_repro_file(tmp_path):
    g = tmp_path / "g.npy"
    np.save(g, nets.random_genome(np.random.default_rng(1)))
    jobs = [make_job("ok1", tmp_path / "ok1", EP, {"Red": f"genome:{g}"}, {"k": 1}, log_decisions=True),
            make_job("ok2", tmp_path / "ok2", {**EP, "seed": 22}, {"Blue": f"genome:{g}", "Green": "baseline"}, {"k": 2}),
            make_job("bad", tmp_path / "bad", EP, {"Red": f"genome:{tmp_path / 'missing.npy'}"}, {"k": 3})]
    pool = GamePool(2, poll_s=0.2)
    res = pool.run(jobs)
    assert res["ok1"]["ok"] and res["ok1"]["result"]["end_reason"] == "horizon" and res["ok1"]["tag"] == {"k": 1}
    assert res["ok1"]["stats"]["Red"]["commands"] > 0 and (tmp_path / "ok1" / "decisions.jsonl.gz").exists()
    assert res["ok2"]["ok"] and [s["faction"] for s in res["ok2"]["result"]["seats"]] == ["Blue"]
    assert res["bad"]["voided"] and not res["bad"]["ok"]
    repro = json.loads((tmp_path / "bad" / "repro.json").read_text(encoding="utf-8"))
    assert "FileNotFoundError" in repro["traceback"] and repro["job"]["episode"]["seed"] == 21 and (tmp_path / "bad" / "repro_1.json").exists()
    assert [e["event"] for e in pool.events if e["job"] == "bad"].count("voided") == 1
    assert (tmp_path / "ok1" / "heartbeat").exists() and not (tmp_path / "ok1" / "ep").exists()


def test_stop_now_abandons_running_games_and_graceful_stop_starts_nothing_new(tmp_path):
    g = tmp_path / "g.npy"
    np.save(g, nets.random_genome(np.random.default_rng(1)))
    long_ep = {**EP, "game_minutes": 30}
    jobs = [make_job(f"j{i}", tmp_path / f"j{i}", long_ep, {"Red": f"genome:{g}"}) for i in range(3)]
    state = {"n": 0}

    def stop():
        state["n"] += 1
        return "now" if state["n"] > 12 else ""

    res = GamePool(1, poll_s=0.3).run(jobs, stop=stop)
    assert all(r.get("voided") for r in res.values()) and {r["reason"] for r in res.values()} <= {"stopped", "not_started"}
    jobs = [make_job(f"k{i}", tmp_path / f"k{i}", EP, {"Red": f"genome:{g}"}) for i in range(3)]
    started = {"n": 0}

    def graceful():
        started["n"] += 1
        return "graceful" if started["n"] > 6 else ""

    res = GamePool(1, poll_s=0.3).run(jobs, stop=graceful)
    assert any(r.get("ok") for r in res.values()) and any(r.get("reason") == "not_started" for r in res.values())
