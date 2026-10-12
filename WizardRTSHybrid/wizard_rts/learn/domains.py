"""Training and evaluation of one policy per domain over the real environments, with disjoint train / validation / test seeds,
scripted expert, random-masked and no-op baselines, paired statistics, saved curves and checkpoints.

Budgets (`BUDGETS`): `smoke` (seconds, used by the test suite), `standard` (minutes, the reported run) and `long` (opt-in).
No domain needs trained weights to run the game; these policies are discovery and robustness tools (owner section E).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from wizard_rts.learn import nn
from wizard_rts.learn.policy import Policy, behaviour_clone, paired_stats, reinforce, rollout
from wizard_rts.learn.runs import Run

BUDGETS = {
    "smoke": {"duel_train": 120, "duel_test": 20, "dungeon_train": 16, "dungeon_test": 8, "dagger": 1, "bc_epochs": 8, "outbreak_train": 10, "outbreak_test": 4, "pg_iters": 2,
              "quest_train": 6, "quest_test": 4, "full_train": 3, "full_test": 3, "rts_train": 0, "rts_test": 0, "rts_min": 6},
    "standard": {"duel_train": 1500, "duel_test": 150, "dungeon_train": 160, "dungeon_test": 40, "dagger": 2, "bc_epochs": 25, "outbreak_train": 120, "outbreak_test": 30, "pg_iters": 30,
                 "quest_train": 24, "quest_test": 12, "full_train": 30, "full_test": 12, "rts_train": 12, "rts_test": 6, "rts_min": 15},
    "long": {"duel_train": 6000, "duel_test": 400, "dungeon_train": 400, "dungeon_test": 100, "dagger": 4, "bc_epochs": 40, "outbreak_train": 400, "outbreak_test": 80, "pg_iters": 120,
             "quest_train": 60, "quest_test": 30, "full_train": 120, "full_test": 30, "rts_train": 40, "rts_test": 12, "rts_min": 25},
}


def _split(lo: int, n: int) -> list[int]:
    return list(range(lo, lo + n))


# ---------------------------------------------------------------- duels

def train_duel(budget: str = "standard", slots: int = 4, colours: int = 6, casts: int = 10, seed: int = 0) -> dict[str, Any]:
    from wizard_rts.envs.duel_env import MastermindEnv
    from wizard_rts.mastermind_solvers import ConsistentSolver

    b = BUDGETS[budget]
    run = Run("duel", {"slots": slots, "colours": colours, "casts": casts, "budget": budget, "seed": seed})
    env = MastermindEnv(slots, colours, casts, "random")
    train_seeds = _split(0, b["duel_train"])          # training
    val_seeds = _split(10_000, max(20, b["duel_test"] // 3))   # validation (model choice)
    test_seeds = _split(20_000, b["duel_test"])      # held-out test, never trained or tuned on
    X, Y = [], []
    for s in train_seeds:
        env.reset(s)
        solver, hist = ConsistentSolver(slots, colours), []
        while not env.done:
            X.append(env.encode())
            g = solver.next_guess(hist)
            Y.append(g)
            env.step(g)
            hist.append((g, env.history[-1]["exact"], env.history[-1]["colour_only"]))
    X, Y = np.array(X), np.array(Y)
    pol = Policy(X.shape[1], slots * colours, (192, 96), seed=seed)
    curve = []
    rng = np.random.RandomState(seed)
    for ep in range(b["bc_epochs"]):
        order = rng.permutation(len(X))
        tot = 0.0
        for i in range(0, len(X), 128):
            idx = order[i:i + 128]
            out, acts = pol.net.forward(X[idx])
            g_all = np.zeros_like(out)
            loss = 0.0
            for s_ in range(slots):
                sl = slice(s_ * colours, (s_ + 1) * colours)
                l, g = nn.xent_grad(out[:, sl], None, Y[idx, s_])
                g_all[:, sl] = g
                loss += l
            pol.net.step(*pol.net.backward(g_all, acts), lr=2e-3)
            tot += loss * len(idx)
        curve.append(tot / len(X))
        run.log(epoch=ep, bc_loss=tot / len(X))

    def act(env_, greedy=True):
        out = pol.net.predict(env_.encode())[0]
        return [int(np.argmax(out[s_ * colours:(s_ + 1) * colours])) for s_ in range(slots)]

    def play(opponent: str, seeds: list[int], who: str) -> list[dict[str, float]]:
        res = []
        for s in seeds:
            e = MastermindEnv(slots, colours, casts, opponent)
            e.reset(s)
            solver, hist = ConsistentSolver(slots, colours), []
            r2 = np.random.RandomState(s)
            while not e.done:
                if who == "net":
                    g = act(e)
                elif who == "solver":
                    g = solver.next_guess(hist)
                else:
                    g = [int(r2.randint(0, colours)) for _ in range(slots)]
                e.step(g)
                if e.history:
                    hist.append((g, e.history[-1]["exact"], e.history[-1]["colour_only"]))
            res.append({"solved": float(e.reason == "solved"), "casts": float(len(e.history)), "invalid": float(any(h is None for h in e.history))})
        return res

    out: dict[str, Any] = {"curve": curve, "samples": int(len(X)), "eval": {}}
    for opp in ("random", "rule_based", "adversarial"):
        seeds = test_seeds if opp != "adversarial" else test_seeds[: max(10, len(test_seeds) // 5)]
        r = {w: play(opp, seeds, w) for w in ("net", "solver", "random")}
        out["eval"][opp] = {w: {"solve_rate": float(np.mean([x["solved"] for x in v])), "mean_casts_when_solved": float(np.mean([x["casts"] for x in v if x["solved"]] or [float("nan")]))}
                            for w, v in r.items()}
        out["eval"][opp]["net_vs_random_solved"] = paired_stats([x["solved"] for x in r["net"]], [x["solved"] for x in r["random"]])
        out["eval"][opp]["net_vs_solver_solved"] = paired_stats([x["solved"] for x in r["net"]], [x["solved"] for x in r["solver"]])
    out["seeds"] = {"train": [train_seeds[0], train_seeds[-1]], "val": [val_seeds[0], val_seeds[-1]], "test": [test_seeds[0], test_seeds[-1]]}
    pol.save(str(run.dir / "policy.json"))
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


# ---------------------------------------------------------------- dungeons

def _expert_or_noop(env) -> int:
    a = env.expert_action()  # one call per step: each call consumes a verb of the plan
    return 0 if a is None else a


def train_dungeon(budget: str = "standard", seed: int = 0) -> dict[str, Any]:
    from wizard_rts.envs.dungeon_env import N_VERBS, DungeonEnv, split_seeds

    b = BUDGETS[budget]
    run = Run("dungeon", {"budget": budget, "seed": seed})
    env = DungeonEnv()
    train = list(split_seeds("train"))[: b["dungeon_train"]]
    test = list(split_seeds("test"))[: b["dungeon_test"]]
    X, Y, M = [], [], []

    def add_expert(seeds: list[int], policy: Policy | None = None, mix: float = 0.0) -> None:
        rng = np.random.RandomState(seed + len(X))
        for s in seeds:
            env.reset(s)
            for _ in range(env.max_steps):
                a_exp = env.expert_action()
                if a_exp is None:
                    break
                X.append(env.encode())
                M.append(env.legal_mask())
                Y.append(a_exp)
                a = a_exp
                if policy is not None and rng.rand() > mix:
                    a = policy.act(X[-1], M[-1], greedy=False)
                env.step(a)
                env._plan = [] if a != a_exp else env._plan  # off the expert's path: replan from the new state
                if env.done:
                    break

    add_expert(train)
    pol = Policy(len(X[0]), N_VERBS, (192, 96), seed=seed)
    for rnd in range(b["dagger"] + 1):
        Xa, Ya, Ma = np.array(X), np.array(Y), np.array(M)
        curve = behaviour_clone(pol, Xa, Ya, Ma, epochs=b["bc_epochs"], seed=seed + rnd)
        run.log(round=rnd, samples=len(X), bc_loss=curve[-1])
        if rnd < b["dagger"]:
            add_expert(train[: max(8, len(train) // 2)], policy=pol, mix=0.3)  # DAgger: states the policy visits, labelled by the expert

    def solve(policy_fn, seeds: list[int]) -> dict[str, float]:
        solved, steps, illegal = 0, [], 0
        for s in seeds:
            env.reset(s)
            for _ in range(env.max_steps):
                _o, _r, _t, _tr, info = env.step(policy_fn(env))
                illegal += bool(info.get("illegal"))
                if env.done:
                    break
            solved += env.reason == "solved"
            steps.append(env.t)
        return {"solve_rate": solved / len(seeds), "mean_steps": float(np.mean(steps)), "illegal": illegal}

    rng = np.random.RandomState(5)
    res = {"net_greedy": solve(lambda e: pol.act(e.encode(), e.legal_mask(), greedy=True), test),
           "net_sampled": solve(lambda e: pol.act(e.encode(), e.legal_mask(), greedy=False), test),
           "expert": solve(lambda e: _expert_or_noop(e), test),
           "random": solve(lambda e: int(rng.choice(e.legal_actions())), test)}
    # unique failure paths: where the greedy net gets stuck, by puzzle type of the first unsolved room
    fails: dict[str, int] = {}
    for s in test:
        env.reset(s)
        for _ in range(env.max_steps):
            env.step(pol.act(env.encode(), env.legal_mask(), greedy=True))
            if env.done:
                break
        if env.reason != "solved":
            first = next(i for i, ok in enumerate(env.run.view()["solved"]) if not ok)
            t = env.d["puzzles"][first]["type"]
            fails[t] = fails.get(t, 0) + 1
    out = {"eval": res, "failures_by_first_unsolved_puzzle": fails, "samples": len(X), "seeds": {"train": [train[0], train[-1]], "test": [test[0], test[-1]]}}
    pol.save(str(run.dir / "policy.json"))
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


# ---------------------------------------------------------------- outbreaks

def train_outbreak(budget: str = "standard", seed: int = 0) -> dict[str, Any]:
    from wizard_rts.envs.outbreak_env import OutbreakEnv, policy_greedy, policy_noop, policy_random, run_episode

    b = BUDGETS[budget]
    run = Run("outbreak", {"budget": budget, "seed": seed})
    env = OutbreakEnv(mode="partial", horizon_min=90, interval_scale=0.5)
    train_seeds = _split(0, b["outbreak_train"])
    test_seeds = _split(50_000, b["outbreak_test"])
    # imitation of the greedy prioritiser (it sees what the wizard sees), then policy gradient
    X, Y, M = [], [], []
    for s in train_seeds[: max(6, len(train_seeds) // 2)]:
        env.reset(s)
        while not env.done:
            X.append(env.encode())
            M.append(env.legal_mask())
            a = policy_greedy(env, env.observe())
            Y.append(a)
            env.step(a)
    X, Y, M = np.array(X), np.array(Y), np.array(M)
    pol = Policy(X.shape[1], env.R + 1, (128, 64), seed=seed)
    bc = behaviour_clone(pol, X, Y, M, epochs=b["bc_epochs"], seed=seed)
    run.log(stage="bc", loss=bc[-1], samples=len(X))
    pg = reinforce(pol, env, train_seeds, b["pg_iters"], episodes_per_iter=6, lr=5e-4, entropy=0.02,
                   on_iter=lambda i, row: run.log(stage="pg", **row))
    pol_fn = lambda e, x, m: pol.act(x, m, greedy=True)  # noqa: E731
    rows = {}
    for name, scale in (("default", 1.0), ("hard", 0.5), ("brutal", 0.25)):
        e2 = OutbreakEnv(mode="partial", horizon_min=90, interval_scale=scale)
        per = {"net": [], "greedy": [], "random": [], "noop": []}
        for s in test_seeds:
            per["net"].append(run_episode(e2, lambda E, o: pol.act(E.encode(o), E.legal_mask(), greedy=True), s))
            per["greedy"].append(run_episode(e2, policy_greedy, s))
            per["random"].append(run_episode(e2, policy_random(np.random.RandomState(s)), s))
            per["noop"].append(run_episode(e2, policy_noop, s))
        rows[name] = {k: {"return": float(np.mean([r["return"] for r in v])), "outbreaks": float(np.mean([r["outbreaks"] for r in v])),
                          "loss_rate": float(np.mean([r["lost"] for r in v])), "treated": float(np.mean([r["treated"] for r in v]))} for k, v in per.items()}
        rows[name]["net_vs_noop_return"] = paired_stats([r["return"] for r in per["net"]], [r["return"] for r in per["noop"]])
        rows[name]["net_vs_greedy_return"] = paired_stats([r["return"] for r in per["net"]], [r["return"] for r in per["greedy"]])
    out = {"eval": rows, "seeds": {"train": [train_seeds[0], train_seeds[-1]], "test": [test_seeds[0], test_seeds[-1]]}, "bc_final_loss": bc[-1], "pg_last": pg[-1] if pg else None}
    pol.save(str(run.dir / "policy.json"))
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


# ---------------------------------------------------------------- quests

def train_quest(budget: str = "standard", seed: int = 0) -> dict[str, Any]:
    from wizard_rts.envs.quest_env import N, QuestEnv

    b = BUDGETS[budget]
    run = Run("quest", {"budget": budget, "seed": seed})
    env = QuestEnv()
    train_seeds, test_seeds = _split(0, b["quest_train"]), _split(100, b["quest_test"])
    X, Y, M = [], [], []
    for s in train_seeds:
        env.reset(s)
        while not env.done:
            X.append(env.encode())
            M.append(env.legal_mask())
            a = env.expert_action()
            Y.append(a)
            env.step(a)
    pol = Policy(len(X[0]), N, (64, 32), seed=seed)
    curve = behaviour_clone(pol, np.array(X), np.array(Y), np.array(M), epochs=b["bc_epochs"] * 2, seed=seed)
    rows: dict[str, Any] = {}
    for kind in ("base", "world_fix_first", "mine_destroyed", "npc_dead", "reload"):
        per = {"net": [], "expert": []}
        for s in test_seeds:
            for who in ("net", "expert"):
                env.reset(s, kind=kind, at_step=3)
                for _ in range(env.max_steps):
                    a = pol.act(env.encode(), env.legal_mask(), greedy=True) if who == "net" else env.expert_action()
                    env.step(a)
                    if env.done:
                        break
                per[who].append({"reason": env.reason, "return": env.return_})
        rows[kind] = {w: {"success": float(np.mean([r["reason"] == "reached_dungeon_with_the_sigil" for r in v])), "return": float(np.mean([r["return"] for r in v])),
                          "reasons": sorted({r["reason"] for r in v})} for w, v in per.items()}
    out = {"eval": rows, "bc_final_loss": curve[-1], "samples": len(X), "seeds": {"train": [train_seeds[0], train_seeds[-1]], "test": [test_seeds[0], test_seeds[-1]]}}
    pol.save(str(run.dir / "policy.json"))
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


# ---------------------------------------------------------------- cross-system wizard agent

def train_fullgame(budget: str = "standard", seed: int = 0) -> dict[str, Any]:
    from wizard_rts.envs.fullgame_env import N, FullGameEnv, policy_interleaved, policy_story_first, policy_treat_first, policy_wait, run_episode

    b = BUDGETS[budget]
    run = Run("fullgame", {"budget": budget, "seed": seed})
    env = FullGameEnv(interval_scale=0.25, horizon_min=45)
    train_seeds, test_seeds = _split(0, 18), _split(60, b["full_test"])  # seeds 0..5 reuse the six prepared maps; 6+ change the outbreak sequence
    env.reset(0)
    pol = Policy(len(env.encode()), N, (64, 32), seed=seed)
    iters = max(2, b["full_train"] // 6)
    pg = reinforce(pol, env, train_seeds, iters, episodes_per_iter=6, lr=1e-3, entropy=0.03, on_iter=lambda i, row: run.log(stage="pg", **row))
    rows = {"net": [], "story_first": [], "treat_first": [], "interleaved": [], "wait": []}
    for s in test_seeds:
        rows["net"].append(run_episode(env, lambda E, o: pol.act(E.encode(o), E.legal_mask(), greedy=True), s))
        rows["story_first"].append(run_episode(env, policy_story_first, s))
        rows["treat_first"].append(run_episode(env, policy_treat_first, s))
        rows["interleaved"].append(run_episode(env, policy_interleaved(2), s))
        rows["wait"].append(run_episode(env, policy_wait, s))
    summary = {k: {"return": float(np.mean([r["return"] for r in v])), "story_completed": float(np.mean([r["quest"] == "completed" for r in v])),
                   "loss_rate": float(np.mean([r["reason"] == "terminal_loss" for r in v])), "outbreaks": float(np.mean([r["outbreaks"] for r in v]))} for k, v in rows.items()}
    summary["net_vs_story_first_return"] = paired_stats([r["return"] for r in rows["net"]], [r["return"] for r in rows["story_first"]])
    summary["net_vs_interleaved_return"] = paired_stats([r["return"] for r in rows["net"]], [r["return"] for r in rows["interleaved"]])
    out = {"eval": summary, "pg_curve": pg, "seeds": {"train": [train_seeds[0], train_seeds[-1]], "test": [test_seeds[0], test_seeds[-1]]}}
    pol.save(str(run.dir / "policy.json"))
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


# ---------------------------------------------------------------- RTS

def _rts_episode(args: tuple) -> dict[str, Any]:
    kind, seed, faction, minutes, weights_path = args
    from wizard_rts.envs.strategy_env import StrategyEnv, policy_noop, policy_random, policy_scripted, run_episode

    env = StrategyEnv(faction=faction, horizon_min=minutes)
    if kind == "net":
        pol = Policy.load(weights_path)
        return run_episode(env, lambda E, o: pol.act(E.encode(o), E.legal_mask(), greedy=True), seed) | {"seed": seed, "faction": faction, "kind": kind}
    if kind == "reference_ai":
        env = StrategyEnv(faction=faction, horizon_min=minutes, reference_ai=True)
        return run_episode(env, policy_noop, seed) | {"seed": seed, "faction": faction, "kind": kind}
    fn = {"noop": policy_noop, "scripted": policy_scripted, "random": policy_random(np.random.RandomState(seed))}[kind]
    return run_episode(env, fn, seed) | {"seed": seed, "faction": faction, "kind": kind}


def _rts_collect(args: tuple) -> dict[str, Any]:
    seed, faction, minutes = args
    from wizard_rts.envs.strategy_env import StrategyEnv

    env = StrategyEnv(faction=faction, horizon_min=minutes)
    env.reset(seed)
    X, Y, M = [], [], []
    while not env.done:
        X.append(env.encode())
        M.append(env.legal_mask())
        a = env.expert_action()
        Y.append(a)
        env.step(a)
    return {"X": np.array(X), "Y": np.array(Y), "M": np.array(M)}


FACTIONS = ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")


def train_rts(budget: str = "standard", seed: int = 0, workers: int = 3) -> dict[str, Any]:
    """Imitation of the scripted builder-soldier across all six factions (five tribes), then evaluation on held-out seeds and tribes against the
    scripted expert, a masked-random policy, a no-op policy and the built-in AI. REINFORCE fine-tuning is available through `rts_pg_iters`."""
    from multiprocessing import Pool

    from wizard_rts.envs.strategy_env import N

    b = BUDGETS[budget]
    run = Run("rts", {"budget": budget, "seed": seed, "minutes": b["rts_min"]})
    train = [(s, FACTIONS[s % 6], b["rts_min"]) for s in range(b["rts_train"])]
    test = [(1000 + s, FACTIONS[s % 6], b["rts_min"]) for s in range(b["rts_test"])]
    with Pool(workers) as pool:
        data = pool.map(_rts_collect, train) if train else []
    if not data:
        return {"skipped": "rts_train is 0 for this budget"}
    X = np.concatenate([d["X"] for d in data])
    Y = np.concatenate([d["Y"] for d in data])
    M = np.concatenate([d["M"] for d in data])
    pol = Policy(X.shape[1], N, (128, 64), seed=seed)
    curve = behaviour_clone(pol, X, Y, M, epochs=b["bc_epochs"], seed=seed)
    wp = str(run.dir / "policy.json")
    pol.save(wp)
    jobs = [(k, s, f, m, wp) for (s, f, m) in test for k in ("net", "scripted", "noop", "random", "reference_ai")]
    with Pool(workers) as pool:
        rows = pool.map(_rts_episode, jobs)
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(r["kind"], []).append(r)
    summary = {k: {"score": float(np.mean([r["score"] for r in v])), "return": float(np.mean([r["return"] for r in v])), "buildings": float(np.mean([r["buildings"] for r in v])),
                   "cards": float(np.mean([r["cards"] for r in v])), "settlements": float(np.mean([r["settlements"] for r in v])), "eliminated": float(np.mean([r["reason"] == "eliminated" for r in v]))}
               for k, v in by.items()}
    order = {k: sorted(v, key=lambda r: r["seed"]) for k, v in by.items()}
    summary["net_vs_noop_score"] = paired_stats([r["score"] for r in order["net"]], [r["score"] for r in order["noop"]])
    summary["net_vs_scripted_score"] = paired_stats([r["score"] for r in order["net"]], [r["score"] for r in order["scripted"]])
    out = {"eval": summary, "bc_final_loss": curve[-1], "samples": int(len(X)), "per_episode": rows, "seeds": {"train": [train[0][0], train[-1][0]], "test": [test[0][0], test[-1][0]]},
           "factions_test": sorted({t[1] for t in test})}
    run.save_json("result.json", out)
    run.flush()
    out["run_dir"] = str(run.dir)
    return out


DOMAINS = {"duel": train_duel, "dungeon": train_dungeon, "outbreak": train_outbreak, "quest": train_quest, "fullgame": train_fullgame, "rts": train_rts}
