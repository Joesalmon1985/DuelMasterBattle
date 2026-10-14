"""The evolution loop (execution plan T5.2; design 7).

A mirrored evolution strategy with module-wise noise masks, centred-rank shaping, Adam on the parent mean and a per-module step size adapted by the 1/5 success rule.
There are one or two LINEAGES (each with its own parent mean theta, Adam state and step sizes): the random-initialised one and, when `imitation_fraction` > 0, one whose
action-head output layers were fitted to the heuristic AI's recorded choices (neuro/imitation.py; every child is tagged with its lineage). A lineage that stays well
ahead of the other for three generations is adopted by the other (logged).

Per generation: seeds from the "train" stream; one all-`plus` control game per seed; every entry (each child and each lineage's unperturbed parent) plays two games on two
seeds on opposite legs against opponents drawn by the league mixer; an entry's advantage is the mean over its (seed, seat) samples of F - F_control(seed, seat).
Mirrored children share their games, so a pair differs only by the sign of the noise. The best entry with a positive advantage is held out-evaluated
(neuro/heldout.py) and promoted by league.promotion_decision. Everything is checkpointed after each generation.
"""
from __future__ import annotations

import json
import time
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from neuro import heldout, league as L, nets, persist
from neuro.curriculum import Curriculum
from neuro.workers import GamePool, Job, make_job

STREAM_TRAIN, STREAM_HELDOUT, STREAM_NOISE, STREAM_INIT, STREAM_IMIT = 1, 2, 3, 4, 5
SEED_RANGE = {STREAM_TRAIN: (10_000, 4_000_000), STREAM_HELDOUT: (4_000_000, 5_000_000), STREAM_IMIT: (5_000_000, 6_000_000)}


def stream_seed(run_seed: int, stream: int, *idx: int) -> int:
    """A game seed from a named stream; the train, held-out and imitation ranges are disjoint, so a training seed is never a held-out seed."""
    lo, hi = SEED_RANGE[stream]
    return lo + int(np.random.SeedSequence([run_seed, stream, *idx]).generate_state(1)[0]) % (hi - lo)


@dataclass
class EvolutionConfig:
    name: str = "full240"
    population: int = 24
    mirrored: bool = True
    sigma0: float = 0.1
    sigma_min: float = 0.01
    sigma_max: float = 0.2
    module_mask_probs: tuple = (0.5, 0.35, 0.15)
    full_mask_prob: float = 0.1
    adam_lr: float = 0.02
    seeds_per_generation: int = 4
    seats_per_game: int = 3
    imitation_fraction: float = 0.25
    imitation_games: int = 20
    game_minutes: int = 240
    map_size: str = "standard"
    wall_cap_s: int = 7200
    stall_s: int = 1200
    workers: int = 14
    hours: float = 8.0
    max_run_gb: float = 20.0
    run_seed: int = 1
    promote: bool = True
    promotion_min_games: int = 6
    promotion_full_games: int = 12
    decision_log_every: int = 1
    tactical: bool = False
    adopt_margin: float = 30.0
    curriculum: dict = field(default_factory=lambda: Curriculum().to_json())

    @staticmethod
    def from_dict(d: dict) -> "EvolutionConfig":
        names = set(EvolutionConfig.__dataclass_fields__)
        kw = {k: v for k, v in d.items() if k in names}
        if "module_mask_probs" in kw:
            kw["module_mask_probs"] = tuple(kw["module_mask_probs"])
        return EvolutionConfig(**kw)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lineage:
    name: str  # "random" | "imitation"
    theta: np.ndarray
    m: np.ndarray
    v: np.ndarray
    t: int
    sigma: dict[str, float]
    parent_adv: list[float] = field(default_factory=list)

    @staticmethod
    def fresh(name: str, theta: np.ndarray, sigma0: float) -> "Lineage":
        z = np.zeros_like(theta, dtype=np.float64)
        return Lineage(name, theta.astype(np.float32).copy(), z, z.copy(), 0, {k: float(sigma0) for k in nets.MODULES})


@dataclass
class Entry:
    id: str
    lineage: str
    kind: str  # "parent" | "child"
    pair: int
    sign: int
    genome: np.ndarray
    eps: np.ndarray | None
    mask: list[str]
    ordinal: int
    games: list[tuple[int, str]] = field(default_factory=list)  # (seed index, leg)
    samples: list[float] = field(default_factory=list)  # advantages over the control, one per (game, seat)
    raw: list[float] = field(default_factory=list)
    tiers: list[str] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)
    stats: list[dict] = field(default_factory=list)
    levels: list[str] = field(default_factory=list)

    @property
    def adv(self) -> float:
        return float(np.mean(self.samples)) if self.samples else float("nan")


class Evolution:
    def __init__(self, run_dir: str | Path, config: EvolutionConfig, manifest: dict, seed_from: str | None = None, code_dir: str | Path | None = None,
                 neural_seed_path: str | Path | None = None) -> None:
        self.dir = Path(run_dir)
        self.cfg = config
        self.manifest = manifest
        self.curriculum = Curriculum.from_json(config.curriculum)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.archive = L.ChampionArchive(self.dir / "champions")
        self.mixer_cfg = L.MixerConfig()
        self.grid = L.BehaviourGrid()
        self.history: list[dict] = []
        self.champion: dict | None = None  # {"id", "path", "evaluation"}
        self.heldout_n = 0
        self.generation_index = 0
        self.imitation_done = False
        self.lineages: dict[str, Lineage] = {}
        self.pending_reeval: dict | None = None
        self.progress: Callable[[int, int, int], None] | None = None
        state = persist.load_checkpoint(self.dir)
        if state is not None:
            self._restore(state)
        else:
            self._initialise(seed_from, neural_seed_path)

    # ------------------------------------------------------------------------------------------------------------------------ state
    def _initialise(self, seed_from: str | None, seed_path: str | Path | None) -> None:
        rng = np.random.default_rng(np.random.SeedSequence([self.cfg.run_seed, STREAM_INIT]))
        base = nets.random_genome(rng)
        if seed_from and seed_path and Path(seed_path).exists():
            theta, meta = persist.load_model(seed_path, self.manifest)
            lin = Lineage.fresh("random", theta, self.cfg.sigma0 / 2)
            self.lineages["random"] = lin
            cid = self.archive.add(theta, meta["manifest"], {**meta.get("evaluation", {}), "seeded_from": str(seed_path), "compatibility": meta["compatibility"]})
            if meta["compatibility"] == "same":
                self.champion = {"id": cid, "path": str(self.archive.dir / f"{cid}.npy"), "evaluation": meta.get("evaluation", {})}
            else:
                self.pending_reeval = {"id": cid, "path": str(self.archive.dir / f"{cid}.npy")}
            self.imitation_done = True  # a seeded run does not start an imitation lineage
        else:
            self.lineages["random"] = Lineage.fresh("random", base, self.cfg.sigma0)
        self.base_genome = base
        np.save(self.dir / "theta0.npy", base)

    def _restore(self, s: dict) -> None:
        self.generation_index = int(s["generation"])
        self.lineages = {k: Lineage(**v) for k, v in s["lineages"].items()}
        self.grid = L.BehaviourGrid.from_json(s["grid"])
        self.history = s["history"]
        self.champion = s["champion"]
        self.heldout_n = int(s["heldout_n"])
        self.imitation_done = bool(s["imitation_done"])
        self.pending_reeval = s.get("pending_reeval")
        self.base_genome = np.load(self.dir / "theta0.npy")

    def state(self) -> dict:
        return {"generation": self.generation_index, "lineages": {k: {"name": v.name, "theta": v.theta, "m": v.m, "v": v.v, "t": v.t, "sigma": v.sigma,
                                                                      "parent_adv": v.parent_adv} for k, v in self.lineages.items()},
                "grid": self.grid.to_json(), "history": self.history, "champion": self.champion, "heldout_n": self.heldout_n, "imitation_done": self.imitation_done,
                "pending_reeval": self.pending_reeval, "config": self.cfg.to_dict(), "manifest": self.manifest}

    def checkpoint(self) -> None:
        persist.save_checkpoint(self.dir, self.state(), self.generation_index)

    # ------------------------------------------------------------------------------------------------------------------------ imitation
    def setup_imitation(self, pool: GamePool, stop: Callable[[], str] | None = None) -> dict | None:
        """Generation 0 only: record shadow games, fit the output layers of H1 and H6 and add the imitation lineage (a labelled arm; flag imitation_fraction)."""
        from neuro import imitation

        c = self.cfg
        if self.imitation_done or c.imitation_fraction <= 0 or self.generation_index > 0:
            return None
        theta0 = self.dir / "theta0.npy"
        minutes = min(60, int(c.game_minutes))
        jobs = []
        for k in range(c.imitation_games):
            s = stream_seed(c.run_seed, STREAM_IMIT, k)
            ep = heldout.episode_dict(s, minutes, c.map_size, "C0", 1.0, c.wall_cap_s, False)
            j = make_job(f"shadow_{k}", self.dir / "imitation" / f"shadow_{k}", ep, {}, {"kind": "shadow", "seed": s})
            j.spec["kind"] = "shadow"
            j.spec["theta_path"] = str(theta0)
            jobs.append(j)
        res = pool.run(jobs, stop=stop)
        files = [self.dir / "imitation" / f"shadow_{k}" / "shadow.npz" for k in range(c.imitation_games) if res.get(f"shadow_{k}", {}).get("ok")]
        genome, report = imitation.fit_heads(self.base_genome, files)
        report["games"] = len(files)
        if not any(r.get("fitted") for r in report.values() if isinstance(r, dict)):
            self.imitation_done = True
            report["note"] = "no usable recordings: the imitation lineage was not created"
            return report
        self.add_imitation_lineage(genome)
        np.save(self.dir / "theta0_imitation.npy", genome)
        (self.dir / "imitation" / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        return report

    # ------------------------------------------------------------------------------------------------------------------------ pieces
    def add_imitation_lineage(self, theta: np.ndarray) -> None:
        self.lineages["imitation"] = Lineage.fresh("imitation", theta, self.cfg.sigma0)
        self.imitation_done = True

    def _noise(self, lin: Lineage, g: int, idx: int, n_pairs: int) -> list[tuple[np.ndarray, list[str]]]:
        rng = np.random.default_rng(np.random.SeedSequence([self.cfg.run_seed, STREAM_NOISE, g, idx]))
        sl = nets.slices()
        out = []
        for _ in range(n_pairs):
            if rng.random() < self.cfg.full_mask_prob:
                mods = list(nets.MODULES)
            else:
                k = 1 + int(rng.choice(len(self.cfg.module_mask_probs), p=np.asarray(self.cfg.module_mask_probs) / sum(self.cfg.module_mask_probs)))
                mods = sorted(rng.choice(nets.MODULES, size=min(k, len(nets.MODULES)), replace=False).tolist())
            eps = np.zeros(nets.genome_size(), dtype=np.float32)
            for m in mods:
                a, b = sl[m]
                eps[a:b] = rng.standard_normal(b - a).astype(np.float32)
            out.append((eps, mods))
        return out

    def _perturb(self, lin: Lineage, eps: np.ndarray, sign: int) -> np.ndarray:
        sl = nets.slices()
        delta = np.zeros_like(eps)
        for m, (a, b) in sl.items():
            if np.any(eps[a:b]):
                delta[a:b] = eps[a:b] * lin.sigma[m]
        child = lin.theta + sign * delta
        t = sl["TEMP"]
        child[t[0]:t[1]] = np.clip(child[t[0]:t[1]], 0.05, 20.0)
        return child.astype(np.float32)

    def _plan(self, g: int) -> list[Entry]:
        c = self.cfg
        lins = list(self.lineages.values())
        entries: list[Entry] = []
        ordinal = 0
        for li, lin in enumerate(lins):
            share = c.population if len(lins) == 1 else (max(2, int(round(c.population * (c.imitation_fraction if lin.name == "imitation" else 1 - c.imitation_fraction)))))
            n_pairs = max(1, share // 2) if c.mirrored else max(1, share)
            entries.append(Entry(f"g{g}-{lin.name[:3]}-parent", lin.name, "parent", -1, 0, lin.theta.copy(), None, [], ordinal))
            ordinal += 1
            for j, (eps, mods) in enumerate(self._noise(lin, g, li, n_pairs)):
                signs = (1, -1) if c.mirrored else (1,)
                for s in signs:
                    entries.append(Entry(f"g{g}-{lin.name[:3]}-{j}{'p' if s > 0 else 'm'}", lin.name, "child", j, s, self._perturb(lin, eps, s), eps, mods, ordinal))
                ordinal += 1
        S = c.seeds_per_generation
        for e in entries:
            # entries of one mirrored pair share an ordinal and therefore their games
            e.games = [(e.ordinal % S, "A" if (e.ordinal + g) % 2 == 0 else "B"), ((e.ordinal + 1) % S, "B" if (e.ordinal + g) % 2 == 0 else "A")]
        return entries

    # ------------------------------------------------------------------------------------------------------------------------ one generation
    def _path(self, gen_dir: Path, e: Entry) -> Path:
        p = gen_dir / "genomes" / f"{e.id}.npy"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            np.save(p, e.genome)
        return p

    def generation(self, pool: GamePool, stop: Callable[[], str] | None = None) -> dict:
        t0 = time.time()
        g, c = self.generation_index, self.cfg
        gen_dir = self.dir / "games" / f"gen_{g:06d}"
        entries = self._plan(g)
        seeds = [stream_seed(c.run_seed, STREAM_TRAIN, g, k) for k in range(c.seeds_per_generation)]
        lvl_rng = np.random.default_rng(np.random.SeedSequence([c.run_seed, STREAM_NOISE, g, 99]))
        levels = [self.curriculum.draw(lvl_rng) for _ in seeds]
        mixer = L.OpponentMixer(self.mixer_cfg, c.run_seed, self.archive)
        jobs: list[Job] = []
        for k, s in enumerate(seeds):
            ep = heldout.episode_dict(s, c.game_minutes, c.map_size, levels[k], self.curriculum.scale_of(levels[k]), c.wall_cap_s, c.tactical)
            jobs.append(make_job(f"ctl_{k}", gen_dir / f"ctl_{k}", ep, {}, {"kind": "control", "k": k, "seed": s, "level": levels[k]}))
        log_entry = (g // max(1, c.decision_log_every)) % len(entries) if c.decision_log_every else -1
        for e in entries:
            path = self._path(gen_dir, e)
            for gi, (k, leg) in enumerate(e.games):
                s = seeds[k]
                ep = heldout.episode_dict(s, c.game_minutes, c.map_size, levels[k], self.curriculum.scale_of(levels[k]), c.wall_cap_s, c.tactical)
                mine, _ = L.seats_for(leg)
                seats = {x: f"genome:{path}" for x in mine}
                for seat, spec in mixer.draw(s, leg).items():
                    if spec == "champion" and self.champion:
                        seats[seat] = f"genome:{self.champion['path']}"
                    elif spec.startswith("archive:"):
                        seats[seat] = f"genome:{self.archive.dir / (spec.split(':', 1)[1] + '.npy')}"
                    else:
                        seats[seat] = "plus" if spec in ("champion",) or spec.startswith("archive") else spec
                jobs.append(make_job(f"{e.id}__{gi}", gen_dir / f"{e.id}__{gi}", ep, seats,
                                     {"kind": "candidate", "entry": e.id, "k": k, "leg": leg, "level": levels[k], "seat_set": list(mine)},
                                     log_decisions=(e.ordinal == log_entry and gi == 0), log_seats=list(mine)))
        counter = [0]

        def tick(_r: dict) -> None:
            counter[0] += 1
            if self.progress:
                self.progress(g, counter[0], len(jobs))

        results = pool.run(jobs, stop=stop, on_result=tick)
        # control fitness per (seed index, seat)
        ctrl: dict[tuple[int, str], float] = {}
        ctrl_lost: list[bool] = []
        for k in range(len(seeds)):
            r = results.get(f"ctl_{k}")
            if r and not r.get("voided"):
                ctrl_lost.append(r["result"]["end_reason"] == "collective_loss")
                for s in r["result"]["control_seats"]:
                    if s["tier"] != "V":
                        ctrl[(k, s["faction"])] = float(s["fitness"])
        valid_games = 0
        for e in entries:
            for gi, (k, leg) in enumerate(e.games):
                r = results.get(f"{e.id}__{gi}")
                if not r or r.get("voided"):
                    continue
                valid_games += 1
                mine, _ = L.seats_for(leg)
                for s in r["result"]["seats"]:
                    if s["faction"] in mine and s["tier"] != "V" and (k, s["faction"]) in ctrl:
                        e.samples.append(float(s["fitness"]) - ctrl[(k, s["faction"])])
                        e.raw.append(float(s["fitness"]))
                        e.tiers.append(s["tier"])
                        e.levels.append(levels[k])
                        e.metrics.append(s.get("metrics", {}))
                for st in r.get("stats", {}).values():
                    e.stats.append(st)
        done = sum(1 for e in entries if e.kind == "child" and e.samples)
        if done < 4:
            return {"generation": g, "aborted": True, "reason": f"only {done} children finished (stopped early or too many voided games)", "games": len(jobs), "events": list(pool.events[-20:])}
        summary = self._update(entries, g)
        promo = self._maybe_promote(pool, entries, g, stop) if c.promote else None
        self._record_grid(entries, g)
        summary.update({"generation": g, "games": len(jobs), "valid_games": valid_games, "seeds": seeds, "levels": levels, "wall_s": round(time.time() - t0, 1),
                        "control_loss_rate": float(np.mean(ctrl_lost)) if ctrl_lost else None, "promotion": promo, "voided": sum(1 for r in results.values() if r.get("voided")),
                        "sim_minutes": sum(r["result"]["t_end_min"] for r in results.values() if r.get("ok")),
                        "worker_wall_s": sum(r.get("wall_s", 0) for r in results.values() if r.get("ok")),
                        "imitation_lineage": "imitation" in self.lineages, "events": list(pool.events[-20:])})
        self.history.append(summary)
        with open(self.dir / "generations.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, default=str) + "\n")
        self.generation_index += 1
        self.checkpoint()
        return summary

    # ------------------------------------------------------------------------------------------------------------------------ the update
    def _update(self, entries: list[Entry], g: int) -> dict:
        c = self.cfg
        out: dict[str, Any] = {"lineages": {}}
        best_all: Entry | None = None
        for name, lin in list(self.lineages.items()):
            mine = [e for e in entries if e.lineage == name]
            parent = next(e for e in mine if e.kind == "parent")
            kids = [e for e in mine if e.kind == "child" and e.samples]
            lin.parent_adv.append(parent.adv if parent.samples else float("nan"))
            info: dict[str, Any] = {"parent_adv": parent.adv, "children": len(kids)}
            if len(kids) >= 2:
                adv = np.array([e.adv for e in kids])
                order = adv.argsort().argsort().astype(np.float64)
                w = order / (len(kids) - 1) - 0.5
                grad = np.zeros(nets.genome_size(), dtype=np.float64)
                sl = nets.slices()
                for m, (a, b) in sl.items():
                    act = [i for i, e in enumerate(kids) if m in e.mask]
                    if not act:
                        continue
                    acc = np.zeros(b - a, dtype=np.float64)
                    for i in act:
                        acc += w[i] * kids[i].eps[a:b] * (kids[i].sign if c.mirrored else 1)
                    grad[a:b] = acc / (len(act) * lin.sigma[m])
                    if parent.samples and len(act) >= 2:
                        rate = float(np.mean([kids[i].adv > parent.adv for i in act]))
                        lin.sigma[m] = float(np.clip(lin.sigma[m] * (1.1 if rate > 0.2 else 0.95), c.sigma_min, c.sigma_max))
                lin.t += 1
                lin.m = 0.9 * lin.m + 0.1 * grad
                lin.v = 0.999 * lin.v + 0.001 * grad * grad
                mhat, vhat = lin.m / (1 - 0.9 ** lin.t), lin.v / (1 - 0.999 ** lin.t)
                step = c.adam_lr * mhat / (np.sqrt(vhat) + 1e-8)
                lin.theta = (lin.theta + step.astype(np.float32)).astype(np.float32)
                t = sl["TEMP"]
                lin.theta[t[0]:t[1]] = np.clip(lin.theta[t[0]:t[1]], 0.05, 20.0)
                info.update(best_child_adv=float(adv.max()), mean_child_adv=float(adv.mean()), step_norm=float(np.linalg.norm(step)))
            info["sigma_mean"] = float(np.mean(list(lin.sigma.values())))
            out["lineages"][name] = info
            cand = [e for e in mine if e.samples]
            if cand:
                top = max(cand, key=lambda e: e.adv)
                if best_all is None or top.adv > best_all.adv:
                    best_all = top
            (self.dir / "theta").mkdir(exist_ok=True)
            np.save(self.dir / "theta" / f"gen_{g:06d}_{name[:3]}.npy", lin.theta)
        # adoption: a lineage well ahead for three generations replaces the other's mean
        if len(self.lineages) == 2:
            a, b = self.lineages["random"], self.lineages["imitation"]
            last = lambda lin: np.nanmean(lin.parent_adv[-3:]) if len(lin.parent_adv) >= 3 and not np.all(np.isnan(lin.parent_adv[-3:])) else np.nan  # noqa: E731
            la, lb = last(a), last(b)
            if not (np.isnan(la) or np.isnan(lb)):
                if lb > la + c.adopt_margin:
                    a.theta = b.theta.copy()
                    out["adopted"] = "random adopted imitation"
                elif la > lb + c.adopt_margin:
                    b.theta = a.theta.copy()
                    out["adopted"] = "imitation adopted random"
        valid = [e for e in entries if e.samples]
        out["best_entry"] = {"id": best_all.id, "lineage": best_all.lineage, "adv": best_all.adv, "raw": float(np.mean(best_all.raw))} if best_all else None
        out["mean_advantage"] = float(np.mean([e.adv for e in valid])) if valid else None
        out["best_advantage"] = best_all.adv if best_all else None
        out["best_raw_fitness"] = float(max((np.mean(e.raw) for e in valid), default=float("nan")))
        cmds = sum(s["commands"] for e in valid for s in e.stats)
        ticks = sum(s["ticks"] for e in valid for s in e.stats)
        rej = sum(s["rejected"] for e in valid for s in e.stats)
        heads: dict[str, int] = {}
        for e in valid:
            for s in e.stats:
                for h, (n, _r) in s["by_head"].items():
                    heads[h] = heads.get(h, 0) + n
        out["commands_per_tick"] = cmds / ticks if ticks else 0.0
        out["rejected_fraction"] = rej / cmds if cmds else 0.0
        out["heads_used"] = {h: round(n / cmds, 3) for h, n in sorted(heads.items())} if cmds else {}
        per_level: dict[str, list[float]] = {}
        for e in valid:
            for lv, a in zip(e.levels, e.samples):
                per_level.setdefault(lv, []).append(a)
        out["advantage_by_level"] = {lv: float(np.mean(v)) for lv, v in sorted(per_level.items())}
        out["entries"] = [{"id": e.id, "lineage": e.lineage, "kind": e.kind, "adv": e.adv, "raw": float(np.mean(e.raw)), "mask": e.mask, "n": len(e.samples), "sd": float(np.std(e.samples))} for e in valid]
        if best_all is not None:
            (self.dir / "best_by_gen").mkdir(exist_ok=True)
            np.save(self.dir / "best_by_gen" / f"gen_{g:06d}.npy", best_all.genome)
        self._best_entry = best_all
        return out

    # ------------------------------------------------------------------------------------------------------------------------ promotion
    def heldout_seeds(self, n: int) -> list[int]:
        seeds = [stream_seed(self.cfg.run_seed, STREAM_HELDOUT, self.heldout_n, k) for k in range(n)]
        self.heldout_n += 1
        return seeds

    def _maybe_promote(self, pool: GamePool, entries: list[Entry], g: int, stop: Any) -> dict | None:
        c = self.cfg
        if self.pending_reeval is not None:
            return self._reevaluate_seed(pool, g, stop)
        top = getattr(self, "_best_entry", None)
        if top is None or not (top.adv > 0):
            return None
        cand_path = self._path(self.dir / "games" / f"gen_{g:06d}", top)
        ref = Path(self.champion["path"]) if self.champion else None
        out_dir = self.dir / "games" / "promotion" / f"gen_{g:06d}"
        pairs: list[dict] = []
        decision: dict = {}
        for batch in range(2):
            seeds = self.heldout_seeds(c.promotion_full_games // 4)
            pairs += heldout.paired_heldout(pool, out_dir / f"b{batch}", cand_path, ref, seeds, c.game_minutes, c.map_size, self.curriculum.current,
                                            self.curriculum.scale_of(self.curriculum.current), c.wall_cap_s, c.tactical, stop)
            decision = L.promotion_decision(pairs, None, self.curriculum.retention_tolerance, c.promotion_min_games, c.promotion_full_games, seed=g)
            if decision["decided"]:
                break
        rec = {"candidate": top.id, "lineage": top.lineage, "training_advantage": top.adv, "reference": "champion" if ref else "plus-control", **decision,
               "summary": heldout.summarize(pairs) if pairs else {}}
        if decision.get("promote"):
            cid = self.archive.add(top.genome, {**self.manifest, "generation": g}, {"heldout": rec["summary"], "decision": {k: decision[k] for k in ("mean_advantage", "lower", "n")},
                                                                                     "generation": g, "lineage": top.lineage})
            self.champion = {"id": cid, "path": str(self.archive.dir / f"{cid}.npy"), "evaluation": rec["summary"], "generation": g}
            rec["champion"] = cid
        return rec

    def _reevaluate_seed(self, pool: GamePool, g: int, stop: Any) -> dict:
        c, pr = self.cfg, self.pending_reeval
        seeds = self.heldout_seeds(c.promotion_full_games // 2)
        pairs = heldout.paired_heldout(pool, self.dir / "games" / "promotion" / f"reeval_{g:06d}", Path(pr["path"]), None, seeds, c.game_minutes, c.map_size,
                                       self.curriculum.current, self.curriculum.scale_of(self.curriculum.current), c.wall_cap_s, c.tactical, stop)
        d = L.promotion_decision(pairs, None, self.curriculum.retention_tolerance, c.promotion_min_games, c.promotion_full_games, seed=g)
        rec = {"reevaluated": pr["id"], **d, "summary": heldout.summarize(pairs) if pairs else {}}
        if d.get("promote"):
            self.champion = {"id": pr["id"], "path": pr["path"], "evaluation": rec["summary"], "generation": g}
        self.pending_reeval = None
        return rec

    # ------------------------------------------------------------------------------------------------------------------------ behaviour grid
    def _record_grid(self, entries: list[Entry], g: int) -> None:
        gdir = self.dir / "grid"
        gdir.mkdir(exist_ok=True)
        for e in entries:
            if not e.samples or not e.metrics:
                continue
            tot = sum(m.get("total_vp", 0) for m in e.metrics)
            cell = L.descriptor(sum(m.get("conquest_vp", 0) for m in e.metrics), tot, int(np.mean([m.get("founded", 0) for m in e.metrics])),
                                float(np.mean([m.get("cured", 0) + m.get("aid", 0) for m in e.metrics])))
            if self.grid.offer(cell, float(np.mean(e.raw)), e.id, {"generation": g, "lineage": e.lineage, "advantage": e.adv}):
                np.save(gdir / ("cell_%d_%d_%d.npy" % cell), e.genome)
