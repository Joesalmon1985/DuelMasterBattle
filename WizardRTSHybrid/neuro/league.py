"""Opponents, champion archive, behaviour grid and promotion (execution plan T4.3; design 7.4, 7.5, 7.8 rule 4, 7.1).

    OpponentMixer     who plays the three seats a candidate does not (heuristic plus / baseline, the champion, a random archive member), mirrored legs A and B
    ChampionArchive   the hall of fame: every champion ever promoted, never deleted
    BehaviourGrid     3 x 3 x 2 cells over (conquest share of VP, settlements founded, cubes cured + aid delivered), best fitness per cell: preserved strategies
    promotion_decision(paired_results, retention=None)   the held-out rule of design 7.5 and the optional retention rule of 7.8
"""
from __future__ import annotations

import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

LEG_A = ("Red", "Green", "Purple")
LEG_B = ("Blue", "Yellow", "Orange")


def seats_for(leg: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(candidate seats, opponent seats) for leg 'A' or 'B'."""
    return (LEG_A, LEG_B) if leg == "A" else (LEG_B, LEG_A)


# ---------------------------------------------------------------------------------------------------------------------------- opponents
@dataclass
class MixerConfig:
    plus: float = 0.40
    baseline: float = 0.10
    champion: float = 0.25
    archive: float = 0.25


class OpponentMixer:
    """Deterministic per (seed, leg): the same call gives the same opponents. Specs are 'plus', 'baseline', 'champion' or 'archive:<id>'. Without a champion or
    archive the neural shares fall back to the heuristic `plus`."""

    def __init__(self, cfg: MixerConfig | None = None, base_seed: int = 0, archive: "ChampionArchive | None" = None) -> None:
        self.cfg, self.base_seed, self.archive = cfg or MixerConfig(), int(base_seed), archive

    def draw(self, seed: int, leg: str) -> dict[str, str]:
        rng = np.random.default_rng(np.random.SeedSequence([self.base_seed, int(seed), zlib.crc32(leg.encode())]))
        p = np.array([self.cfg.plus, self.cfg.baseline, self.cfg.champion, self.cfg.archive], dtype=np.float64)
        p = p / p.sum()
        ids = self.archive.ids() if self.archive is not None else []
        out: dict[str, str] = {}
        for seat in seats_for(leg)[1]:
            k = int(rng.choice(4, p=p))
            if k == 0:
                out[seat] = "plus"
            elif k == 1:
                out[seat] = "baseline"
            elif k == 2:
                out[seat] = "champion" if ids else "plus"
            else:
                out[seat] = f"archive:{ids[int(rng.integers(0, len(ids)))]}" if ids else "plus"
        return out


# ---------------------------------------------------------------------------------------------------------------------------- archive
class ChampionArchive:
    """Directory of champions: <id>.npy (the genome) and <id>.json (manifest and evaluation). `current.txt` names the latest. Nothing is ever deleted."""

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def ids(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("c*.json"))

    def add(self, genome: np.ndarray, manifest: dict, evaluation: dict) -> str:
        n = len(self.ids()) + 1
        cid = f"c{n:04d}"
        np.save(self.dir / f"{cid}.npy", np.asarray(genome, dtype=np.float32))
        (self.dir / f"{cid}.json").write_text(json.dumps({"id": cid, "level": manifest.get("catastrophe_level", "C0"), "manifest": manifest, "evaluation": evaluation},
                                                         indent=1, default=str), encoding="utf-8")
        tmp = self.dir / "current.txt.tmp"
        tmp.write_text(cid, encoding="utf-8")
        tmp.replace(self.dir / "current.txt")
        return cid

    def current(self) -> str | None:
        p = self.dir / "current.txt"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None

    def genome(self, cid: str) -> np.ndarray:
        return np.load(self.dir / f"{cid}.npy").astype(np.float32)

    def record(self, cid: str) -> dict:
        return json.loads((self.dir / f"{cid}.json").read_text(encoding="utf-8"))

    def champion_of_level(self, level: str) -> str | None:
        """The latest champion promoted at a curriculum level (champions of every level are kept forever)."""
        best = None
        for cid in self.ids():
            if self.record(cid).get("level") == level:
                best = cid
        return best

    def __len__(self) -> int:
        return len(self.ids())


# ---------------------------------------------------------------------------------------------------------------------------- behaviour grid
SHARE_EDGES = (0.15, 0.5)  # conquest share of VP: low / medium / high
FOUNDED_EDGES = (2, 4)  # settlements founded (beyond the start): 0-1 / 2-3 / 4+
CO_EDGES = (1,)  # cubes cured + aid delivered: none / some


def descriptor(conquest_vp: float, total_vp: float, founded: int, cured_and_aid: float) -> tuple[int, int, int]:
    share = conquest_vp / total_vp if total_vp > 0 else 0.0
    return (int(sum(share >= e for e in SHARE_EDGES)), int(sum(founded >= e for e in FOUNDED_EDGES)), int(sum(cured_and_aid >= e for e in CO_EDGES)))


@dataclass
class BehaviourGrid:
    cells: dict[tuple[int, int, int], dict[str, Any]] = field(default_factory=dict)
    shape: tuple[int, int, int] = (3, 3, 2)

    def offer(self, cell: tuple[int, int, int], fitness: float, genome_id: str, extra: dict | None = None) -> bool:
        """Keep the best fitness per cell; True when this candidate took the cell."""
        cur = self.cells.get(tuple(cell))
        if cur is None or fitness > cur["fitness"]:
            self.cells[tuple(cell)] = {"fitness": float(fitness), "id": genome_id, **(extra or {})}
            return True
        return False

    def filled(self) -> int:
        return len(self.cells)

    def total(self) -> int:
        return self.shape[0] * self.shape[1] * self.shape[2]

    def to_json(self) -> dict:
        return {"shape": list(self.shape), "cells": {",".join(map(str, k)): v for k, v in sorted(self.cells.items())}}

    @staticmethod
    def from_json(d: dict) -> "BehaviourGrid":
        g = BehaviourGrid(shape=tuple(d.get("shape", (3, 3, 2))))  # type: ignore[arg-type]
        g.cells = {tuple(int(x) for x in k.split(",")): v for k, v in d.get("cells", {}).items()}
        return g


# ---------------------------------------------------------------------------------------------------------------------------- promotion
def bootstrap_mean_interval(values: list[float] | np.ndarray, level: float = 0.90, n: int = 4000, seed: int = 0) -> tuple[float, float, float]:
    """(mean, lower, upper) of the one-sided `level` bounds of the mean: lower = the (1-level) quantile, upper = the `level` quantile of bootstrap means."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return float(v.mean()), float(np.quantile(means, 1.0 - level)), float(np.quantile(means, level))


def promotion_decision(paired_results: list[dict], retention: dict[str, list[dict]] | None = None, tolerance: float = 50.0, min_games: int = 6,
                       full_games: int = 12, level: float = 0.90, seed: int = 0) -> dict:
    """Design 7.5. `paired_results`: one dict per held-out game with `adv` (candidate fitness minus champion fitness on the same seed and seats, averaged over the
    seats), `cand_lost` and `champ_lost` (collective loss in that game). Promote when the mean advantage is above 0 with a bootstrap `level` lower bound above 0 and the
    candidate's collective-loss rate is not higher than the champion's. Sequential: below `min_games` nothing is decided; between `min_games` and `full_games` the
    decision is made early only when decisive (lower bound above 0 and the loss rule holds: promote; upper bound below 0: reject); at `full_games` it is final.
    `retention` (design 7.8 rule 4): earlier level -> its paired results; the candidate must not be worse than the champion there by more than `tolerance` (the upper
    bound of champion minus candidate is at most the tolerance), otherwise it is not promoted."""
    n = len(paired_results)
    advs = [float(r["adv"]) for r in paired_results]
    mean, lo, hi = bootstrap_mean_interval(advs, level, seed=seed)
    lc = sum(1 for r in paired_results if r.get("cand_lost")) / n if n else 0.0
    lh = sum(1 for r in paired_results if r.get("champ_lost")) / n if n else 0.0
    out: dict[str, Any] = {"n": n, "mean_advantage": mean, "lower": lo, "upper": hi, "loss_rate_candidate": lc, "loss_rate_champion": lh, "promote": False, "decided": False,
                           "reason": ""}
    ret_ok, ret_report = True, {}
    for lvl, res in (retention or {}).items():
        m, rl, _ru = bootstrap_mean_interval([float(r["adv"]) for r in res], level, seed=seed + 1)
        ok = (not res) or (-rl <= tolerance)  # champion minus candidate has upper bound -rl
        ret_report[lvl] = {"n": len(res), "mean_advantage": m, "lower": rl, "champion_minus_candidate_upper": -rl, "ok": ok}
        ret_ok = ret_ok and ok
    out["retention"] = ret_report
    if n < min_games:
        out["reason"] = f"{n} of at least {min_games} games"
        return out
    good = mean > 0 and lo > 0 and lc <= lh
    if not ret_ok:
        out.update(decided=True, reason="forgetting: worse than the champion at an earlier level by more than the tolerance")
        return out
    if n >= full_games:
        out.update(decided=True, promote=bool(good), reason="promoted" if good else ("loss rate higher than the champion's" if (mean > 0 and lo > 0) else "no significant advantage"))
        return out
    if good:
        out.update(decided=True, promote=True, reason="promoted early (decisive)")
    elif hi < 0:
        out.update(decided=True, reason="rejected early (decisive)")
    else:
        out["reason"] = "undecided: more games"
    return out
