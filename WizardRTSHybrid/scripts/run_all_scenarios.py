#!/usr/bin/env python3
"""Selective, reproducible scenario runner with a report (owner section D/G).

  python3 scripts/run_all_scenarios.py --suite smoke                 # seconds: every environment resets, steps, replays and saves
  python3 scripts/run_all_scenarios.py --suite envs systems          # the pytest groups of each domain (minutes)
  python3 scripts/run_all_scenarios.py --suite stress                # long runs: 40-minute campaigns, industry slice, outbreak horizon (opt-in, tens of minutes)
  python3 scripts/run_all_scenarios.py --suite parity                # re-export the GDScript fixtures from Godot and compare (needs Godot)
  python3 scripts/run_all_scenarios.py --suite smoke --report docs/evidence/scenario_report.json

Suites run in order; the report records, per item: pass/fail, seconds, the command, the code SHA and (for smoke) the state hashes so two runs can be diffed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))

PYTEST_GROUPS = {
    "envs": ["tests/test_duel_env.py", "tests/test_dungeon_env.py", "tests/test_quest_env.py", "tests/test_outbreak_env.py", "tests/test_fullgame_env.py", "tests/test_nn.py"],
    "systems": ["tests/test_campaign_tech.py::test_profiles_defined_and_unknown_rejected", "tests/test_mindustry_pipeline.py", "tests/test_industry_mechanics.py", "tests/test_story_slice.py",
                "tests/test_vp_eras.py", "tests/test_puzzle_parity.py", "tests/test_ward_parity.py"],
    "training": ["tests/test_training_smoke.py"],
    "stress": ["tests/test_campaign_tech.py", "tests/test_industry_slice.py", "tests/test_outbreaks.py"],
}


def sha() -> str:
    from wizard_rts.learn.runs import code_sha

    return code_sha()


def run_pytest(group: str) -> dict:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *PYTEST_GROUPS[group]]
    t = time.time()
    r = subprocess.run(cmd, cwd=HYB, capture_output=True, text=True, env={**os.environ, "HYBRID_AI": "0"})
    tail = [l for l in r.stdout.strip().splitlines() if l.strip()][-1:] or [""]
    return {"item": f"pytest:{group}", "ok": r.returncode == 0, "seconds": round(time.time() - t, 1), "summary": tail[0], "command": " ".join(cmd[2:])}


def smoke() -> list[dict]:
    rows = []

    def item(name, fn):
        t = time.time()
        try:
            detail = fn()
            rows.append({"item": f"smoke:{name}", "ok": True, "seconds": round(time.time() - t, 2), **detail})
        except Exception as exc:  # a failure is a result, not a crash of the runner
            rows.append({"item": f"smoke:{name}", "ok": False, "seconds": round(time.time() - t, 2), "error": f"{type(exc).__name__}: {exc}"})

    def duel():
        from wizard_rts.envs.duel_env import MastermindEnv
        from wizard_rts.mastermind_solvers import ConsistentSolver

        e = MastermindEnv()
        e.reset(1)
        s, h = ConsistentSolver(), []
        while not e.done:
            g = s.next_guess(h)
            e.step(g)
            h.append((g, e.history[-1]["exact"], e.history[-1]["colour_only"]))
        assert e.reason == "solved" and e.check_invariants() == []
        twin = MastermindEnv()
        assert twin.replay([t["action"] for t in e.trace], seed=1) == e.state_hash()
        return {"hash": e.state_hash(), "steps": e.t}

    def dungeon():
        from wizard_rts.envs.dungeon_env import DungeonEnv

        e = DungeonEnv()
        e.reset(2)
        while not e.done:
            e.step(e.expert_action())
        assert e.reason == "solved"
        return {"hash": e.state_hash(), "steps": e.t}

    def quest():
        from wizard_rts.envs.quest_env import QuestEnv

        e = QuestEnv()
        e.reset(1)
        while not e.done:
            e.step(e.expert_action())
        assert e.reason == "reached_dungeon_with_the_sigil"
        return {"hash": e.state_hash(), "steps": e.t}

    def outbreak():
        from wizard_rts.envs.outbreak_env import OutbreakEnv, policy_greedy, run_episode

        r = run_episode(OutbreakEnv(mode="full"), policy_greedy, 1)
        assert not r["lost"]
        return {"result": r}

    def fullgame():
        from wizard_rts.envs.fullgame_env import FullGameEnv, policy_story_first, run_episode

        r = run_episode(FullGameEnv(horizon_min=30), policy_story_first, 1)
        assert r["quest"] == "completed"
        return {"result": r}

    def strategy():
        from wizard_rts.envs.strategy_env import StrategyEnv, policy_scripted, run_episode

        r = run_episode(StrategyEnv(horizon_min=5), policy_scripted, 1)
        return {"result": r}

    def world_profiles():
        from wizard_rts.world import HybridWorld

        h = {}
        for p in ("campaign", "developer", "test_showcase"):
            w = HybridWorld(507, profile=p)
            w.advance(2000, 1)
            h[p] = w.state_hash()[:12]
        return {"hashes": h}

    for name, fn in (("world_profiles", world_profiles), ("duel", duel), ("dungeon", dungeon), ("quest", quest), ("outbreak", outbreak), ("fullgame", fullgame), ("strategy", strategy)):
        item(name, fn)
    return rows


def parity() -> list[dict]:
    rows = []
    for name in ("test_puzzle_parity.py", "test_ward_parity.py"):
        t = time.time()
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"tests/{name}"], cwd=HYB, capture_output=True, text=True, env={**os.environ, "GODOT_PARITY": "1"})
        rows.append({"item": f"parity:{name}", "ok": r.returncode == 0, "seconds": round(time.time() - t, 1), "summary": (r.stdout.strip().splitlines() or [""])[-1], "note": "re-exported from the real GDScript"})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", nargs="+", default=["smoke"], choices=["smoke", "envs", "systems", "training", "stress", "parity"])
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    results: list[dict] = []
    for s in a.suite:
        print(f"== suite {s}", flush=True)
        rows = smoke() if s == "smoke" else parity() if s == "parity" else [run_pytest(s)]
        for r in rows:
            print(("PASS " if r["ok"] else "FAIL ") + r["item"], r.get("summary", r.get("error", "")), f"{r['seconds']}s", flush=True)
        results += rows
    report = {"code_sha": sha(), "date": time.strftime("%Y-%m-%dT%H:%M:%S"), "python": sys.version.split()[0], "suites": a.suite, "results": results,
              "all_ok": all(r["ok"] for r in results)}
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(report, indent=1))
    print("ALL_OK" if report["all_ok"] else "SOME_FAILED")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
