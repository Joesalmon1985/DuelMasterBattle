"""Imitation seeding (decision N02; execution plan T5.2; design 7.7): an optional, labelled starting lineage.

A shadow game is a game in which every seat is played by the heuristic `plus` AI while, for each seat, the neural interface (observer, candidates, the random-initialised
networks) runs at the neural decision times but issues nothing. What the heuristic then did in the next interval gives the label of each head:

    H1  `construction_started` of the seat                -> the candidate with the same kind whose tile is nearest (within 3 tiles)
    H2  a new road edge touching one of the seat's buildings -> the road candidate for that pair
    H3  `ai_expand_queue`                                  -> the candidate that queues that founder at that building
    H4  `ai_expand_site` / `ai_expand_deploy`              -> the move / deploy candidate nearest the event's tile (within 3 tiles)
    H5  `ai_attack` / `ai_defend` / `ai_recon`             -> the candidate aimed at that target / the nearest scouting waypoint
    H6  `card_drafted`                                     -> the candidate with that card
    H9  `construction_started` with `enhance_from`         -> the enhance candidate of that building
    H7, H8  never imitated (the heuristic does not trade or negotiate through these commands)

A head with no label in a tick contributes up to four of its candidates as "not now". For each head the hidden layer of the head network is computed for the chosen
candidate (+1) and a sample of the others (-1), and the head's output layer (W2, b2) is fitted by weighted ridge regression. The wait score is shifted (H0's bias) so that
its mean over the recorded ticks is -0.6 (`wait_margin`): a head acts when it has a candidate it believes the heuristic would choose. Every other weight keeps its random value.
The lineage is tagged `imitation` in all logs and can be switched off (`imitation_fraction` 0).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import numpy as np

HEADS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9")
NEGATIVE_ONLY = ("H7", "H8")
NEG_PER_POS = 20
NEG_NOT_NOW = 4
MATCH_TILES = 3


def _match_tile(cands: list, want_op: str | None, tile: tuple[int, int], kind: str | None = None) -> int:
    best, bd = -1, MATCH_TILES + 1
    for i, c in enumerate(cands):
        a = c.action
        if want_op and a.get("op") != want_op:
            continue
        if kind and a.get("kind") != kind:
            continue
        t = c.refs.get("tile")
        if t is None and "tx" in a:
            t = (a["tx"], a["ty"])
        if t is None:
            continue
        d = max(abs(int(t[0]) - int(tile[0])), abs(int(t[1]) - int(tile[1])))
        if d < bd:
            best, bd = i, d
    return best


def _label(rec: dict, e: dict, w: Any) -> None:
    k = e.get("kind")
    if k == "construction_started":
        if e.get("enhance_from"):
            for i, c in enumerate(rec.get("H9", {}).get("cands", [])):
                if c.action.get("op") in ("enhance", "upgrade") and c.action.get("building") == e.get("id"):
                    rec["H9"]["chosen"].add(i)
        elif "H1" in rec:
            b = w.buildings.get(e.get("id"))
            if b is not None:
                i = _match_tile(rec["H1"]["cands"], "build", (b["tx"], b["ty"]), b.get("kind"))
                if i >= 0:
                    rec["H1"]["chosen"].add(i)
    elif k == "ai_expand_queue" and "H3" in rec:
        for i, c in enumerate(rec["H3"]["cands"]):
            if c.action.get("building") == e.get("building") and (not e.get("founder") or c.action.get("unit") == e.get("founder")):
                rec["H3"]["chosen"].add(i)
                break
    elif k in ("ai_expand_site", "ai_expand_deploy") and "H4" in rec:
        i = _match_tile(rec["H4"]["cands"], "deploy" if k == "ai_expand_deploy" else "move", tuple(e["tile"]))
        if i >= 0:
            rec["H4"]["chosen"].add(i)
    elif k in ("ai_attack", "ai_defend") and "H5" in rec:
        target = e.get("target") if k == "ai_attack" else e.get("centre")
        for i, c in enumerate(rec["H5"]["cands"]):
            if len(c.key) > 2 and c.key[2] == target:
                rec["H5"]["chosen"].add(i)
    elif k == "ai_recon" and "H5" in rec:
        best, bd = -1, 9
        for i, c in enumerate(rec["H5"]["cands"]):
            if len(c.key) > 1 and c.key[1] == "scout":
                d = max(abs(c.refs["tile"][0] - e["to"][0]), abs(c.refs["tile"][1] - e["to"][1]))
                if d < bd:
                    best, bd = i, d
        if best >= 0:
            rec["H5"]["chosen"].add(best)
    elif k == "card_drafted" and "H6" in rec:
        for i, c in enumerate(rec["H6"]["cands"]):
            if c.action.get("card") == e.get("card"):
                rec["H6"]["chosen"].add(i)


def record_shadow(job_dir: Path, job: dict) -> dict:
    """Run one shadow game (inside a worker process); writes <job_dir>/shadow.npz and returns a small summary."""
    os.environ.setdefault("HYBRID_AI", "1")
    from neuro import nets
    from neuro.brain import Brain
    from neuro.candidates import CandidateGenerator
    from neuro.episode import EpisodeConfig
    from neuro.observer import FactionObserver
    from wizard_rts.sim_api import FACTIONS, HybridEnv

    cfg = EpisodeConfig(**job["episode"])
    theta = np.load(job["theta_path"]).astype(np.float32)
    nn = nets.Nets(theta)
    brain = Brain(nn)
    horizon = int(cfg.game_minutes) * 60
    env = HybridEnv(seed=cfg.seed, map_size=cfg.map_size, agent_factions=(), step_ms=1000, max_game_ms=horizon * 1000, profile=cfg.profile, rewards=False)
    env.reset()
    w = env.world
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, True
    w.nest_policy = {n: cfg.nest_policy for n in w.faction_info}
    w.outbreak_interval_scale = float(cfg.outbreak_interval_scale)
    w.ai_policy = {n: "plus" for n in w.faction_info}
    seats = [f[0] for f in FACTIONS]
    obs_ = {s: FactionObserver(w, s) for s in seats}
    gen = {s: CandidateGenerator(env, s, obs_[s]) for s in seats}
    memory = {s: np.zeros(16, dtype=np.float32) for s in seats}
    last = {s: -10 ** 9 for s in seats}
    pending: dict[str, dict] = {}
    rng = np.random.default_rng(int(cfg.seed))
    X: dict[str, list[np.ndarray]] = {h: [] for h in HEADS}
    Y: dict[str, list[np.ndarray]] = {h: [] for h in HEADS}
    waits: list[float] = []
    positives = {h: 0 for h in HEADS}
    cursor = env.event_cursor()
    edges = set(w.road_edges)
    t0 = time.time()
    for game_s in range(1, horizon + 1):
        env.step({}, observe=False)
        new_events, cursor = env.events_since(cursor)
        for s in seats:
            obs_[s].on_events(new_events)
        if len(w.road_edges) != len(edges):
            now = set(w.road_edges)
            for key in sorted(now - edges):
                a, c = w.road_edges[key]
                for s, rec in pending.items():
                    owner = (w.buildings.get(a) or {}).get("faction_name")
                    if owner == s and "H2" in rec:
                        for i, cand in enumerate(rec["H2"]["cands"]):
                            if cand.action.get("op") == "road" and {cand.action.get("a"), cand.action.get("b")} == {a, c}:
                                rec["H2"]["chosen"].add(i)
            edges = now
        for e in new_events:
            s = e.get("faction")
            if s in pending:
                _label(pending[s], e, w)
        gap = cfg.boot_decision_s if game_s < cfg.boot_minutes * 60 else cfg.decision_s
        for s in seats:
            if game_s - last[s] < gap:
                continue
            _flush(pending.pop(s, None), X, Y, positives, rng)
            last[s] = game_s
            try:
                obs = obs_[s].observe(game_s)
                cands = gen[s].all(obs)
                th = brain.think(obs, cands, memory[s], 0.0, keep_inputs=True)
            except Exception:  # noqa: BLE001 - a seat that cannot be observed (collapsed, split) is skipped
                continue
            memory[s] = th.memory
            waits.append(float(th.wait))
            rec = {}
            for h in HEADS:
                if cands.get(h):
                    hidden = np.tanh(th.inputs[h] @ nn.w[h]["W1"] + nn.w[h]["b1"])
                    rec[h] = {"cands": cands[h], "hidden": hidden.astype(np.float32), "chosen": set()}
            pending[s] = rec
    for s in list(pending):
        _flush(pending.pop(s), X, Y, positives, rng)
    out: dict[str, np.ndarray] = {"wait": np.asarray(waits, dtype=np.float32)}
    for h in HEADS:
        out[f"{h}_X"] = np.concatenate(X[h]) if X[h] else np.zeros((0, nn.w[h]["W1"].shape[1]), dtype=np.float32)
        out[f"{h}_y"] = np.concatenate(Y[h]) if Y[h] else np.zeros(0, dtype=np.float32)
    np.savez(job_dir / "shadow.npz", **out)
    return {"ok": True, "positives": positives, "rows": {h: int(len(out[f'{h}_y'])) for h in HEADS}, "wall_s": round(time.time() - t0, 1), "job_id": job["job_id"]}


def _flush(rec: dict | None, X: dict, Y: dict, positives: dict, rng: np.random.Generator) -> None:
    if not rec:
        return
    for h, r in rec.items():
        n = len(r["cands"])
        chosen = r["chosen"] if h not in NEGATIVE_ONLY else set()
        if not chosen:  # nothing chosen for this head: a few candidates are recorded as "not now"
            idx = sorted(rng.choice(n, size=min(n, NEG_NOT_NOW), replace=False).tolist())
            X[h].append(r["hidden"][idx])
            Y[h].append(np.full(len(idx), -1.0, dtype=np.float32))
            continue
        pos = sorted(chosen)
        neg_all = [i for i in range(n) if i not in chosen]
        k = min(len(neg_all), NEG_PER_POS * len(pos))
        neg = sorted(rng.choice(neg_all, size=k, replace=False).tolist()) if k else []
        idx = pos + neg
        X[h].append(r["hidden"][idx])
        Y[h].append(np.array([1.0] * len(pos) + [-1.0] * len(neg), dtype=np.float32))
        positives[h] += len(pos)


def fit_heads(theta: np.ndarray, shadow_files: list[Path], ridge: float = 1.0, wait_margin: float = 0.6) -> tuple[np.ndarray, dict]:
    """A copy of theta whose head output layers are the weighted ridge solution on the recorded rows, with H0's bias shifted so that the mean wait score over the recorded
    ticks is -wait_margin (measured on the 60-minute standard-map games: with 0 the policy hardly acts, with 0.6 it builds, scouts and sometimes founds a settlement)."""
    from neuro import nets

    g = theta.astype(np.float32).copy()
    n = nets.Nets(g)
    report: dict[str, Any] = {}
    data = [np.load(f) for f in shadow_files if Path(f).exists()]
    for h in HEADS:
        Xs = [d[f"{h}_X"] for d in data if len(d[f"{h}_y"])]
        ys = [d[f"{h}_y"] for d in data if len(d[f"{h}_y"])]
        if not Xs:
            report[h] = {"rows": 0, "positives": 0, "fitted": False}
            continue
        X, y = np.concatenate(Xs).astype(np.float64), np.concatenate(ys).astype(np.float64)
        pos, neg = y > 0, y <= 0
        w = np.where(pos, 0.5 / max(1, pos.sum()), 0.5 / max(1, neg.sum())) * len(y)
        A = np.hstack([X, np.ones((len(X), 1))])
        Aw = A * w[:, None]
        sol = np.linalg.solve(A.T @ Aw + ridge * np.eye(A.shape[1]), Aw.T @ y)
        n.w[h]["W2"][:, 0] = sol[:-1].astype(np.float32)
        n.w[h]["b2"][0] = np.float32(sol[-1])
        pred = A @ sol
        report[h] = {"rows": int(len(y)), "positives": int(pos.sum()), "fitted": True,
                     "separation": float(pred[pos].mean() - pred[neg].mean()) if pos.any() and neg.any() else None}
    waits = np.concatenate([d["wait"] for d in data if len(d["wait"])]) if data else np.zeros(0)
    if len(waits):
        shift = float(-waits.mean() - wait_margin)
        n.w["H0"]["b2"][0] = np.float32(n.w["H0"]["b2"][0] + shift)
        report["wait_shift"] = shift
    return g, report
