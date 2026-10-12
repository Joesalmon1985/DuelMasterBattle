"""Outbreak environment: choose where and when to treat under limited attention (D12, S09).

The dynamics are the game's own `wizard_rts/regions.py` (cadence, spread, outbreaks, treatment channel and cooldown, terminal loss),
stepped on a lightweight world object that carries the same attributes the module reads (a copy of a real world's settlement and
building layout, no economy). That keeps a 90-minute episode in milliseconds so a policy can be trained; `evaluate_on_real_world`
replays a policy's decisions on a full `HybridWorld` (economy and AI running) to confirm the transfer.

Action: a region index to travel to and treat, or `R` to wait 30 s. Travelling takes game time (distance / walking speed), then the
8 s channel and the 20 s cooldown, so every decision costs real attention. Observation modes: `full` (all cubes) and `partial`
(only the region the wizard stands in, its neighbours, and regions that report themselves: a standing settlement with two or more cubes).
"""

from __future__ import annotations

import math
import pickle
from typing import Any

import numpy as np

from wizard_rts import regions
from wizard_rts.envs import Env

WALK_TILES_PER_S = 1.4
WAIT_S = 30


class _Clock(dict):
    pass


class StubWorld:
    """Just what regions.py reads. Built from a real world's layout so regions contain real settlements and buildings."""

    def __init__(self, layout: dict[str, Any], seed: int, era: int = 0) -> None:
        class DMB:
            pass

        self.dmb = DMB()
        self.dmb.clock = {"game_ms": 0}
        self.dmb.settlements = {sid: dict(rec, chronicle=[]) for sid, rec in layout["settlements"].items()}
        self.buildings = {bid: dict(b) for bid, b in layout["buildings"].items()}

        class T:
            pass

        self.terrain = T()
        self.terrain.w, self.terrain.h = layout["w"], layout["h"]
        self.events: list[dict[str, Any]] = []
        self.stats: dict[str, int] = {}
        self.seed = seed
        self.era_index = era
        self.player = {"tx": layout["start"][0], "ty": layout["start"][1], "facing": "down"}
        self.economy_quanta = 0
        self.cycle_pending = False
        self.outbreaks_enabled = True


_LAYOUTS: dict[int, dict[str, Any]] = {}


def layout_for(seed: int) -> dict[str, Any]:
    """The settlement/building layout of the real world for this seed (built once per process, ~3 s)."""
    if seed not in _LAYOUTS:
        from wizard_rts.world import HybridWorld

        w = HybridWorld(seed, profile="campaign")
        _LAYOUTS[seed] = {"w": w.terrain.w, "h": w.terrain.h, "start": (w.player["tx"], w.player["ty"]),
                          "settlements": {sid: {k: rec[k] for k in ("id", "faction", "name", "tile", "state", "home", "centre")} for sid, rec in w.dmb.settlements.items()},
                          "buildings": {bid: {"id": bid, "tx": b["tx"], "ty": b["ty"], "kind": b["kind"], "hp": b.get("hp", 1), "faction_name": b["faction_name"]}
                                        for bid, b in w.buildings.items() if "hp" in b}}
    return _LAYOUTS[seed]


class OutbreakEnv(Env):
    name = "outbreak"

    def __init__(self, layout_seed: int = 507, horizon_min: int = 90, era: int = 0, interval_scale: float = 1.0, mode: str = "partial") -> None:
        super().__init__()
        self.layout_seed, self.horizon_ms, self.era, self.scale, self.mode = layout_seed, horizon_min * 60_000, era, interval_scale, mode
        self.max_steps = 400
        self.w: StubWorld | None = None
        self.rg: regions.Regions | None = None
        self.R = 0
        self.known: set[int] = set()

    def _reset(self, **scenario: Any) -> None:
        self.layout_seed = int(scenario.get("layout_seed", self.layout_seed))
        self.w = StubWorld(layout_for(self.layout_seed), self.seed, self.era)
        self.w.outbreak_interval_scale = float(scenario.get("interval_scale", self.scale))
        self.rg = regions.state(self.w)
        self.R = len(self.rg.axials)
        self.known = set()
        self._prev_out = 0
        self._prev_treated = 0

    # ---- helpers
    def region_centre(self, i: int) -> tuple[int, int]:
        """The wizard stands at the busiest settlement of the region if it has one, else near the geometric centre (clamped to the map)."""
        for rec in sorted(self.w.dmb.settlements.values(), key=lambda r: r["id"]):
            if self.rg.region_at(rec["tile"][0], rec["tile"][1]) == i and rec["state"] == "standing":
                return int(rec["tile"][0]), int(rec["tile"][1])
        q, r = self.rg.axials[i]
        cx = self.w.terrain.w / 2 + 1.5 * self.rg.size * q
        cy = self.w.terrain.h / 2 + math.sqrt(3) * self.rg.size * (r + q / 2)
        x, y = int(max(0, min(self.w.terrain.w - 1, cx))), int(max(0, min(self.w.terrain.h - 1, cy)))
        for rad in range(0, 60):  # nearest tile that is actually inside region i
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    tx, ty = x + dx, y + dy
                    if 0 <= tx < self.w.terrain.w and 0 <= ty < self.w.terrain.h and self.rg.region_at(tx, ty) == i:
                        return tx, ty
        return x, y

    def _advance(self, seconds: float) -> None:
        for _ in range(int(math.ceil(seconds))):
            self.w.dmb.clock["game_ms"] += 1000
            self.w.economy_quanta += 10
            regions.regions_quantum(self.w)

    def legal_actions(self) -> list[Any]:
        return list(range(self.R + 1)) if not self.done else []

    def is_legal(self, action: Any) -> bool:
        return isinstance(action, (int, np.integer)) and 0 <= int(action) <= self.R and not self.done

    def legal_mask(self) -> np.ndarray:
        m = np.ones(self.R + 1)
        return m

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        a = int(action)
        rg, w = self.rg, self.w
        if a == self.R:
            self._advance(WAIT_S)
        else:
            here = rg.region_at(w.player["tx"], w.player["ty"])
            dest = self.region_centre(a)
            if a != here:
                dist = max(abs(dest[0] - w.player["tx"]), abs(dest[1] - w.player["ty"]))
                self._advance(dist / WALK_TILES_PER_S)
                w.player["tx"], w.player["ty"] = dest
            res = regions.begin_treatment(w)
            if res["status"] == "started":
                self._advance(regions.const("treat_ms") / 1000.0 + 1)
            elif res["status"] == "rejected" and res["reason"] == "recovering":
                self._advance(res["ready_in_ms"] / 1000.0 + 0.0)
                res = regions.begin_treatment(w)
                if res["status"] == "started":
                    self._advance(regions.const("treat_ms") / 1000.0 + 1)
            else:
                self._advance(2)  # a wasted trip: nothing to treat there
        self._update_known()
        d_out = rg.outbreaks - self._prev_out
        d_treated = rg.treated - self._prev_treated
        self._prev_out, self._prev_treated = rg.outbreaks, rg.treated
        r = -2.0 * d_out - 0.0005 * sum(rg.cubes) + 0.2 * d_treated
        if rg.lost:
            self.done, self.reason = True, "terminal_loss"
            r -= 5.0
        elif self.w.dmb.clock["game_ms"] >= self.horizon_ms:
            self.done, self.reason = True, "horizon"
            r += 1.0
        return r, {"outbreaks": rg.outbreaks, "treated": rg.treated, "cubes": int(sum(rg.cubes))}

    def _update_known(self) -> None:
        rg, w = self.rg, self.w
        here = rg.region_at(w.player["tx"], w.player["ty"])
        self.known = {here} | set(rg.neighbours[here])
        for rec in w.dmb.settlements.values():
            i = rg.region_at(rec["tile"][0], rec["tile"][1])
            if rec["state"] == "standing" and rg.cubes[i] >= 2:
                self.known.add(i)  # the settlement's healer reports it

    def observe(self) -> dict[str, Any]:
        rg, w = self.rg, self.w
        if not self.known:
            self._update_known()
        cubes = [(-1 if (self.mode == "partial" and i not in self.known) else rg.cubes[i]) for i in range(self.R)]
        here = rg.region_at(w.player["tx"], w.player["ty"])
        return {"cubes": cubes, "here": here, "outbreaks": rg.outbreaks, "minutes_left": max(0, (self.horizon_ms - w.dmb.clock["game_ms"]) // 60_000),
                "treated": rg.treated, "inhabited": sorted({rg.region_at(r["tile"][0], r["tile"][1]) for r in w.dmb.settlements.values() if r["state"] == "standing"})}

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        obs = obs or self.observe()
        cubes = np.array(obs["cubes"], float)
        known = (cubes >= 0).astype(float)
        inh = np.zeros(self.R)
        inh[obs["inhabited"]] = 1.0
        here = np.zeros(self.R)
        here[obs["here"]] = 1.0
        dist = np.array([self._dist(obs["here"], i) for i in range(self.R)])
        return np.concatenate([np.maximum(cubes, 0) / 3.0, known, inh, here, dist / 400.0, [obs["outbreaks"] / 8.0, obs["minutes_left"] / 90.0]])

    def _dist(self, a: int, b: int) -> float:
        ca, cb = self.region_centre(a), self.region_centre(b)
        return float(max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1])))

    def state(self) -> Any:
        rg = self.rg
        return {"seed": self.seed, "cubes": list(rg.cubes), "kinds": list(rg.kind), "outbreaks": rg.outbreaks, "treated": rg.treated, "ms": self.w.dmb.clock["game_ms"],
                "player": [self.w.player["tx"], self.w.player["ty"]], "done": self.done}

    def save(self) -> bytes:
        return pickle.dumps(self)


# ---------------------------------------------------------------- baselines

def policy_noop(env: OutbreakEnv, obs: dict[str, Any]) -> int:
    return env.R


def policy_random(rng: np.random.RandomState):
    def p(env: OutbreakEnv, obs: dict[str, Any]) -> int:
        return int(rng.randint(0, env.R + 1))
    return p


def policy_greedy(env: OutbreakEnv, obs: dict[str, Any]) -> int:
    """Treat the region with the most cubes among those it knows about; ties go to the nearest. Waits when it knows of none."""
    best, key = env.R, None
    for i, c in enumerate(obs["cubes"]):
        if c > 0:
            k = (-c, env._dist(obs["here"], i), i)
            if key is None or k < key:
                best, key = i, k
    return best


def run_episode(env: OutbreakEnv, policy, seed: int, **scenario: Any) -> dict[str, Any]:
    obs = env.reset(seed, **scenario)
    while not env.done:
        obs, _r, _t, _tr, _i = env.step(policy(env, obs))
    return {"return": round(env.return_, 3), "outbreaks": env.rg.outbreaks, "treated": env.rg.treated, "lost": env.rg.lost, "reason": env.reason,
            "cubes_left": int(sum(env.rg.cubes)), "steps": env.t}
