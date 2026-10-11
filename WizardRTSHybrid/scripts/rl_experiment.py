"""Small, honest learning experiment on the real game (numpy only; no ML framework is installed or needed).

    python3 scripts/rl_experiment.py baseline --seeds 101 102 103 104 105 106     # scripted AI, no-op and random-macro policies
    python3 scripts/rl_experiment.py train --generations 3 --population 8 --workers 3
    python3 scripts/rl_experiment.py eval --params docs/evidence/rl/policy.json --seeds 101 102 103 104 105 106

What it is: one faction is controlled by an agent through `HybridEnv.apply` (the same validated commands God Mode and the scripted AI
use: build, road, queue, move, order, deploy); the other five are the scripted AI. Every 30 game seconds the agent chooses one MACRO
from a masked set (build economy, build military, recruit, expand with an MCV, attack, defend, wait). A "foreman" routine only connects
new buildings by road (the agent decides what to build, not which tiles a road crosses). The policy is linear + softmax over the flat
observation; it is trained with the cross-entropy method on training seeds and judged on HELD-OUT seeds (different seeds and different
agent factions) against the same faction played by the scripted AI under the same seeds and the same score.

What it is not: a claim that a neural network plays well. The experiment exists to prove that the interface, masks, rewards, resets,
determinism and evaluation are sound enough to train against, and to give a measured baseline. `docs/TRAINING_PROGRAMME.md` records
what a real programme needs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts import territory  # noqa: E402
from wizard_rts.sim_api import HybridEnv  # noqa: E402
from wizard_rts.world import FACTIONS  # noqa: E402

OUT = HYB / "docs" / "evidence" / "rl"
FACTION_NAMES = [f[0] for f in FACTIONS]
MACROS = ("wait", "build_economy", "build_military", "recruit", "expand", "attack", "defend")
ECONOMY_TARGETS = {"producer": 3, "ranger": 3, "quarry": 2, "processor": 1, "farm": 1, "well": 1, "hunter": 1, "tavern": 1, "bakery": 1, "mine": 1, "ironmine": 1, "smelter": 1, "smithy": 1}
MILITARY_TARGETS = {"barracks": 1, "vehicle_factory": 1, "defense": 2}
DECISION_STEPS = 6  # env steps (5 s each) per decision: 30 game seconds
SCALE = None  # fixed feature scales, set from a reference observation


# ------------------------------------------------------------------ features and macros

def features(env: HybridEnv, obs: dict) -> np.ndarray:
    v = np.array(env.flatten(obs), dtype=np.float64)
    return np.log1p(np.abs(v)) * np.sign(v)  # a compact scale for counts that span 0 to hundreds


def _count(obs: dict, kind: str) -> int:
    return int(obs["buildings"].get(kind, 0)) + int(obs["constructing"].get(kind, 0))


def macro_mask(env: HybridEnv, faction: str, obs: dict, mask: dict) -> np.ndarray:
    ok = np.zeros(len(MACROS), dtype=bool)
    ok[0] = True
    buildable = {b["kind"] for b in mask["build"]}
    ok[1] = any(k in buildable and _count(obs, k) < n for k, n in ECONOMY_TARGETS.items())
    ok[2] = any(k in buildable and _count(obs, k) < n for k, n in MILITARY_TARGETS.items())
    ok[3] = any(q["unit"] in ("infantry", "tank") and len(env.world.buildings[q["building"]].get("queue", [])) < 2 for q in mask["queue"])
    mcvs = obs["mcvs"]
    queued_mcv = any(i["unit"] == "mcv" for b in env.world.buildings.values() if b["faction_name"] == faction for i in b.get("queue", []))
    ok[4] = bool(mcvs) or (not queued_mcv and any(q["unit"] == "mcv" for q in mask["queue"]) and len(obs["command_centers"]) < 3)
    idle = _idle_army(env, faction)
    ok[5] = bool(idle) and bool(mask["attack"])
    ok[6] = bool(idle)
    return ok


def _idle_army(env: HybridEnv, faction: str) -> list[dict]:
    return [u for u in env.world.units.values() if u["faction_name"] == faction and u.get("alive", True) and u.get("weapon")
            and u.get("loco") not in ("naval", "lcraft") and not u.get("order")]


def macro_actions(env: HybridEnv, faction: str, macro: str, obs: dict, mask: dict) -> list[dict]:
    w = env.world
    out: list[dict] = []
    if macro in ("build_economy", "build_military"):
        targets = ECONOMY_TARGETS if macro == "build_economy" else MILITARY_TARGETS
        for b in mask["build"]:
            if b["kind"] in targets and _count(obs, b["kind"]) < targets[b["kind"]] and b["sites"]:
                out.append({"op": "build", "kind": b["kind"], "tx": b["sites"][0][0], "ty": b["sites"][0][1]})
                break
    elif macro == "recruit":
        seen = set()
        for q in mask["queue"]:
            if q["unit"] in ("infantry", "tank") and q["building"] not in seen and len(w.buildings[q["building"]].get("queue", [])) < 2:
                seen.add(q["building"])
                out.append({"op": "queue", "building": q["building"], "unit": q["unit"]})
    elif macro == "expand":
        if obs["mcvs"]:
            for m in obs["mcvs"]:
                d = next((d for d in mask["deploy"] if d["unit"] == m["id"]), None)
                if d and d["ok"]:
                    out.append({"op": "deploy", "unit": m["id"]})
                else:
                    site = next((s["tile"] for s in mask["expansion_sites"] if s["unit"] == m["id"]), None)
                    if site and not w.units[m["id"]].get("order"):
                        out.append({"op": "move", "units": [m["id"]], "tx": site[0], "ty": site[1]})
        else:
            for q in mask["queue"]:
                if q["unit"] == "mcv":
                    out.append({"op": "queue", "building": q["building"], "unit": "mcv"})
                    break
    elif macro in ("attack", "defend"):
        idle = _idle_army(env, faction)
        if idle:
            ids = [u["id"] for u in idle]
            cx = sum(u["tx"] for u in idle) / len(idle)
            cy = sum(u["ty"] for u in idle) / len(idle)
            if macro == "attack":
                target = min((w.buildings[i] for i in mask["attack"]), key=lambda b: abs(b["tx"] - cx) + abs(b["ty"] - cy), default=None)
                if target is not None:
                    out.append({"op": "move", "units": ids, "tx": target["tx"], "ty": target["ty"], "attack_move": True})
            else:
                cap = obs["capital"]
                if cap:
                    out.append({"op": "move", "units": ids, "tx": cap[0] + 6, "ty": cap[1] + 6, "attack_move": True})
    return out


def foreman(env: HybridEnv, faction: str, mask: dict) -> list[dict]:
    """Connect every unconnected building to its warehouse. Roads are bookkeeping for the agent, not a strategic choice."""
    return [{"op": "road", "a": r["a"], "b": r["b"]} for r in mask["road"][:3]]


# ------------------------------------------------------------------ policies

class Linear:
    def __init__(self, w: np.ndarray | None = None, dim: int = 1) -> None:
        self.w = w if w is not None else np.zeros((len(MACROS), dim + 1))

    def act(self, x: np.ndarray, ok: np.ndarray, rng: np.random.Generator, greedy: bool) -> int:
        z = self.w @ np.append(x, 1.0)
        z = np.where(ok, z, -1e9)
        if greedy:
            return int(np.argmax(z))
        p = np.exp(z - z.max())
        p /= p.sum()
        return int(rng.choice(len(MACROS), p=p))


def run_episode(kind: str, params: list | None, seed: int, faction: str, minutes: int, map_size: str = "small") -> dict:
    """One episode. kind: scripted (the built-in AI plays `faction`), wait, random, linear."""
    agents = () if kind == "scripted" else (faction,)
    env = HybridEnv(seed, map_size=map_size, agent_factions=agents, step_ms=5000, max_game_ms=minutes * 60_000)
    obs = env.reset()
    rng = np.random.default_rng(seed * 7 + 1)
    pol = Linear(np.array(params), 0) if kind == "linear" and params is not None else None
    t0 = time.perf_counter()
    total = 0.0
    macros_used = {m: 0 for m in MACROS}
    rejected = 0
    attempted = 0
    steps = minutes * 12
    for step in range(steps):
        acts: dict = {}
        if agents:
            if step % DECISION_STEPS == 0:
                o = obs[faction] if step else env.observe(faction)
                mask = env.legal_actions(faction)
                ok = macro_mask(env, faction, o, mask)
                if kind == "wait":
                    m = 0
                elif kind == "random":
                    m = int(rng.choice(np.flatnonzero(ok)))
                else:
                    m = pol.act(features(env, o), ok, rng, greedy=False)
                macros_used[MACROS[m]] += 1
                acts = {faction: macro_actions(env, faction, MACROS[m], o, mask) + foreman(env, faction, mask)}
        obs, rew, term, trunc, info = env.step(acts)
        if agents:
            total += rew[faction]
            for a in acts.get(faction, []):
                attempted += 1
            if term[faction]:
                break
    w = env.world
    fs = w.fstats.get(faction, {})
    return {
        "kind": kind, "seed": seed, "faction": faction, "minutes": minutes, "score": round(env._score_of(faction) - 0.0, 4), "return": round(total, 4),
        "territory_cells": env._territory(faction), "command_centers": len(territory.command_centers(w, faction)),
        "buildings": sum(1 for b in w.buildings.values() if b["faction_name"] == faction and int(b.get("hp", 1)) > 0),
        "units": sum(1 for u in w.units.values() if u["faction_name"] == faction and u.get("alive", True)),
        "unit_kills": int(fs.get("unit_kills", 0)), "building_kills": int(fs.get("building_kills", 0)), "alive": env._alive(faction),
        "macros": macros_used, "wall_s": round(time.perf_counter() - t0, 1), "hash": env.state_hash()[:12],
    }


def _job(args: tuple) -> dict:
    return run_episode(*args)


def pairs(seeds: list[int]) -> list[tuple[int, str]]:
    """(seed, faction): the faction varies with the seed so held-out evaluation covers homelands the policy was not trained on."""
    return [(s, FACTION_NAMES[s % 6]) for s in seeds]


def summarize(rows: list[dict]) -> dict:
    sc = np.array([r["score"] for r in rows])
    return {"n": len(rows), "mean": round(float(sc.mean()), 3), "std": round(float(sc.std()), 3), "min": round(float(sc.min()), 3), "max": round(float(sc.max()), 3),
            "alive": sum(1 for r in rows if r["alive"]), "territory": round(float(np.mean([r["territory_cells"] for r in rows])), 1),
            "kills": round(float(np.mean([r["unit_kills"] + r["building_kills"] for r in rows])), 1), "command_centers": round(float(np.mean([r["command_centers"] for r in rows])), 2)}


# ------------------------------------------------------------------ commands

def cmd_baseline(a: argparse.Namespace) -> None:
    jobs = [(k, None, s, f, a.minutes) for k in ("scripted", "wait", "random") for s, f in pairs(a.seeds)]
    with Pool(a.workers) as pool:
        rows = pool.map(_job, jobs)
    by = {k: [r for r in rows if r["kind"] == k] for k in ("scripted", "wait", "random")}
    out = {"minutes": a.minutes, "seeds": a.seeds, "summary": {k: summarize(v) for k, v in by.items()}, "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "baseline.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, s in out["summary"].items():
        print(f"{k:9s} {s}")


def cmd_train(a: argparse.Namespace) -> None:
    dim = len(features(*_ref()))
    rng = np.random.default_rng(a.seed)
    mean = np.zeros((len(MACROS), dim + 1))
    mean[:, -1] = 0.0
    std = np.full_like(mean, 0.7)
    train_pairs = pairs(a.train_seeds)
    history = []
    t0 = time.perf_counter()
    with Pool(a.workers) as pool:
        for gen in range(a.generations):
            pop = [mean + std * rng.standard_normal(mean.shape) for _ in range(a.population)]
            jobs = [("linear", p.tolist(), s, f, a.minutes) for p in pop for s, f in train_pairs]
            rows = pool.map(_job, jobs)
            fit = np.array([np.mean([r["score"] for r in rows[i * len(train_pairs):(i + 1) * len(train_pairs)]]) for i in range(a.population)])
            elite = np.argsort(fit)[-max(2, a.population // 3):]
            mean = np.mean([pop[i] for i in elite], axis=0)
            std = np.maximum(np.std([pop[i] for i in elite], axis=0), 0.15)
            history.append({"generation": gen, "best": round(float(fit.max()), 3), "mean": round(float(fit.mean()), 3), "elapsed_s": round(time.perf_counter() - t0)})
            print(history[-1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "policy.json").write_text(json.dumps({"macros": MACROS, "params": mean.tolist(), "history": history, "train_seeds": a.train_seeds, "minutes": a.minutes}), encoding="utf-8")
    print("wrote", OUT / "policy.json")


def _ref():
    env = HybridEnv(1, map_size="small", agent_factions=("Red",))
    obs = env.reset()
    return env, obs["Red"]


def cmd_eval(a: argparse.Namespace) -> None:
    blob = json.loads(Path(a.params).read_text(encoding="utf-8"))
    ps = pairs(a.seeds)
    jobs = [("linear", blob["params"], s, f, a.minutes) for s, f in ps] + [("scripted", None, s, f, a.minutes) for s, f in ps]
    with Pool(a.workers) as pool:
        rows = pool.map(_job, jobs)
    lin = [r for r in rows if r["kind"] == "linear"]
    scr = [r for r in rows if r["kind"] == "scripted"]
    diff = np.array([l["score"] - s["score"] for l, s in zip(lin, scr)])
    out = {"minutes": a.minutes, "seeds": a.seeds, "learned": summarize(lin), "scripted": summarize(scr),
           "paired_difference_mean": round(float(diff.mean()), 3), "paired_wins": int((diff > 0).sum()), "paired_n": len(diff),
           "verdict": "learned policy does NOT beat the scripted baseline" if (diff > 0).sum() * 2 <= len(diff) or diff.mean() <= 0 else "learned policy scores higher on these held-out seeds (not evidence of general strength)",
           "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "eval_heldout.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--seeds", type=int, nargs="+", default=[101, 102, 103, 104, 105, 106])
    b.add_argument("--minutes", type=int, default=14)
    b.add_argument("--workers", type=int, default=3)
    t = sub.add_parser("train")
    t.add_argument("--generations", type=int, default=3)
    t.add_argument("--population", type=int, default=8)
    t.add_argument("--train-seeds", type=int, nargs="+", default=[1, 2])
    t.add_argument("--minutes", type=int, default=14)
    t.add_argument("--workers", type=int, default=3)
    t.add_argument("--seed", type=int, default=0)
    e = sub.add_parser("eval")
    e.add_argument("--params", default=str(OUT / "policy.json"))
    e.add_argument("--seeds", type=int, nargs="+", default=[101, 102, 103, 104, 105, 106])
    e.add_argument("--minutes", type=int, default=14)
    e.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    {"baseline": cmd_baseline, "train": cmd_train, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
