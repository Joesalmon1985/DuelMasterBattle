"""Strategy/economy environment over the real RTS world (`HybridEnv`, kept unchanged) with a macro-action vocabulary, legal masks, a
reward that cannot be earned by passive expansion, and scripted/random/no-op baselines.

Why a new reward (TRAINING_PROGRAMME.md): the old linear learner was paid 0.5 per coarse territory cell, so it learned to expand and
never fight. Here the score is a sum of NET quantities that cost something to hold, each weighted so that no single one dominates:
production that actually happened (made wares, not construction events), operational buildings, units alive (cost-valued), settlements
standing, military exchange (kills minus losses, buildings destroyed minus lost), tech cards, and survival. A change in score is the
reward, so building and demolishing in a loop earns nothing, and idling earns the small production the world makes anyway.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from wizard_rts import construction as con
from wizard_rts import settlements, tech
from wizard_rts.envs import Env
from wizard_rts.sim_api import HybridEnv

BUILD_KINDS = ["producer", "ranger", "processor", "quarry", "hunter", "well", "farm", "tavern", "bakery", "mine", "ironmine", "smelter", "smithy",
               "barracks", "vehicle_factory", "defense"]
UNITS = ["infantry", "tank", "mcv"]
VERBS = ["noop"] + ["build:" + k for k in BUILD_KINDS] + ["queue:" + u for u in UNITS] + ["draft:0", "draft:1", "draft:2", "expand", "attack", "road"]
N = len(VERBS)
V = {v: i for i, v in enumerate(VERBS)}
KEY_WARES = ("log", "plank", "granite", "coal", "iron_ore", "iron", "ration", "bread", "meat", "ax")

WEIGHTS = {"production": 0.01, "buildings": 0.15, "units": 0.002, "settlements": 1.0, "military": 0.003, "buildings_destroyed": 0.5, "tech": 0.4,
           "survive": 0.02, "territory": 0.02, "illegal": -0.05, "idle_streak": -0.02}
IDLE_AFTER = 6  # consecutive no-ops before the idle penalty starts


class StrategyEnv(Env):
    name = "strategy"

    def __init__(self, faction: str = "Red", map_size: str = "small", step_s: int = 20, horizon_min: int = 20, profile: str = "campaign",
                 aggressive: bool = True, weights: dict[str, float] | None = None, reference_ai: bool = False) -> None:
        super().__init__()
        self.reference_ai = reference_ai  # the built-in AI plays this faction too: the yardstick the agent is compared with
        self.faction, self.map_size, self.step_s, self.horizon_ms, self.profile, self.aggressive = faction, map_size, step_s, horizon_min * 60_000, profile, aggressive
        self.weights = dict(WEIGHTS, **(weights or {}))
        self.max_steps = horizon_min * 60 // step_s + 2
        self.env: HybridEnv | None = None
        self._prev = 0.0
        self._idle = 0
        self._mask_cache: tuple[int, dict[str, Any]] | None = None

    # ---- lifecycle
    def _reset(self, **scenario: Any) -> None:
        self.faction = scenario.get("faction", self.faction)
        self.env = HybridEnv(seed=self.seed, map_size=self.map_size, agent_factions=() if self.reference_ai else (self.faction,), step_ms=self.step_s * 1000,
                             max_game_ms=self.horizon_ms + 1000, aggressive=self.aggressive, profile=self.profile)
        self.env.reset()
        self.w = self.env.world
        self._prev = self.score()
        self._idle = 0
        self._mask_cache = None
        self.first = {"stats": dict(self.w.stats)}

    # ---- score
    def score(self) -> float:
        w, f, W = self.w, self.faction, self.weights
        made = sum(w.stats.get("made_" + g, 0) for g in KEY_WARES)  # global counters: the agent's colour is one of six, so use the faction's own below
        fs = w.fstats.get(f, {})
        mine = [b for b in w.buildings.values() if b["faction_name"] == f and b.get("operational") and int(b.get("hp", 1)) > 0 and b["kind"] != "warehouse"]
        units = [u for u in w.units.values() if u["faction_name"] == f and u.get("alive", True)]
        from wizard_rts import rules

        unit_value = sum((rules.actor(u["definition"]) or {}).get("cost", 0) * int(u["hp"]) // max(int(u["max_hp"]), 1) for u in units)
        prod = sum(w.fstats.get(f, {}).get("produced_" + g, 0) for g in KEY_WARES) or self._faction_production(f)
        s = (W["production"] * prod + W["buildings"] * len(mine) + W["units"] * unit_value + W["settlements"] * len(settlements.standing(w, f))
             + W["military"] * (fs.get("kill_value", 0) + fs.get("loss_value", 0) * -1) + W["buildings_destroyed"] * (fs.get("building_kills", 0) - fs.get("building_losses", 0))
             + W["tech"] * len(w.tech.get(f, {}).get("cards", [])) + W["territory"] * self.env._territory(f))
        return float(s)

    def _faction_production(self, f: str) -> int:
        """Wares made by the faction's buildings: the stock delta is not attributable per faction, so count productive operational buildings x time."""
        n = 0
        for b in self.w.buildings.values():
            if b["faction_name"] == f and b.get("working"):
                n += 1
        self._prod_acc = getattr(self, "_prod_acc", 0) + n
        return self._prod_acc

    # ---- masks
    def _legal(self) -> dict[str, Any]:
        if self._mask_cache and self._mask_cache[0] == self.t:
            return self._mask_cache[1]
        m = self.env.legal_actions(self.faction, site_samples=3)
        self._mask_cache = (self.t, m)
        return m

    def legal_mask(self) -> np.ndarray:
        m = self._legal()
        out = np.zeros(N)
        out[0] = 1
        stocks = self.env.observe(self.faction)["stocks"]
        for b in m["build"]:
            if b["kind"] in BUILD_KINDS:
                out[V["build:" + b["kind"]]] = 1
        for q in m["queue"]:
            if q["unit"] in UNITS:
                out[V["queue:" + q["unit"]]] = 1
        for k in range(min(3, len(m.get("draft", [])))):
            out[V["draft:%d" % k]] = 1
        out[V["expand"]] = 1 if (m["expansion_sites"] or any(d["ok"] for d in m["deploy"])) else 0
        out[V["attack"]] = 1 if m["attack"] and any(u.get("weapon") for u in self.w.units.values() if u["faction_name"] == self.faction and u.get("alive", True)) else 0
        out[V["road"]] = 1 if m["road"] else 0
        return out

    def is_legal(self, action: Any) -> bool:
        a = int(action)
        return 0 <= a < N and bool(self.legal_mask()[a]) and not self.done

    def legal_actions(self) -> list[Any]:
        return [i for i, m in enumerate(self.legal_mask()) if m > 0]

    # ---- dynamics
    def _apply(self, verb: str) -> dict[str, Any]:
        m, f, e = self._legal(), self.faction, self.env
        if verb == "noop":
            return {"status": "ok"}
        kind, _, arg = verb.partition(":")
        if kind == "build":
            site = next(b["sites"][0] for b in m["build"] if b["kind"] == arg)
            r = e.apply(f, {"op": "build", "kind": arg, "tx": site[0], "ty": site[1]})
            if r.get("status") == "ok" and r.get("id"):
                e.apply(f, {"op": "road", "a": r["id"], "b": con.faction_warehouse(self.w, f)["id"]})
            return r
        if kind == "queue":
            q = next(q for q in m["queue"] if q["unit"] == arg)
            return e.apply(f, {"op": "queue", "building": q["building"], "unit": arg})
        if kind == "draft":
            return e.apply(f, {"op": "draft", "card": m["draft"][int(arg)]})
        if verb == "road":
            r = m["road"][0]
            return e.apply(f, {"op": "road", "a": r["a"], "b": r["b"]})
        if verb == "expand":
            for d in m["deploy"]:
                if d["ok"]:
                    return e.apply(f, {"op": "deploy", "unit": d["unit"]})
            s = m["expansion_sites"][0]
            return e.apply(f, {"op": "move", "units": [s["unit"]], "tx": s["tile"][0], "ty": s["tile"][1]})
        if verb == "attack":
            armed = [u["id"] for u in self.w.units.values() if u["faction_name"] == f and u.get("alive", True) and u.get("weapon") and not u.get("order")]
            if not armed:
                return {"status": "rejected", "reason": "no_idle_army"}
            tgt = m["attack"][0]
            return e.apply(f, {"op": "order", "unit": armed[0], "target": tgt}) if len(armed) == 1 else e.apply(f, {"op": "move", "units": armed[:12], "tx": self.w.buildings[tgt]["tx"], "ty": self.w.buildings[tgt]["ty"], "attack_move": True})
        return {"status": "rejected", "reason": "unknown"}

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        verb = VERBS[int(action)]
        res = self._apply(verb)
        self._idle = self._idle + 1 if verb == "noop" else 0
        self._mask_cache = None
        _obs, _rew, terminated, truncated, info = self.env.step({})
        s = self.score()
        r = s - self._prev + self.weights["survive"]
        self._prev = s
        if self._idle > IDLE_AFTER:
            r += self.weights["idle_streak"]
        alive = self.env._alive(self.faction)
        if not alive:
            self.done, self.reason = True, "eliminated"
            r -= 5.0
        elif self.env.game_ms >= self.horizon_ms:
            self.done, self.reason = True, "horizon"
        return r, {"verb": verb, "status": res.get("status"), "score": round(s, 3)}

    def _illegal(self, action: Any) -> tuple[float, dict[str, Any]]:
        self.env.step({})  # an illegal action still costs the time that passed
        self._mask_cache = None
        s = self.score()
        r = s - self._prev + self.weights["illegal"]
        self._prev = s
        if self.env.game_ms >= self.horizon_ms:
            self.done, self.reason = True, "horizon"
        return r, {"illegal": True}

    # ---- observation
    def observe(self) -> dict[str, Any]:
        o = self.env.observe(self.faction)
        o["cards"] = list(self.w.tech.get(self.faction, {}).get("cards", []))
        o["offers"] = list(self.w.tech.get(self.faction, {}).get("offers", []))
        return o

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        obs = obs or self.observe()
        v = self.env.flatten(obs)
        v += [len(obs["cards"]) / 6.0, len(obs["offers"]) / 3.0, len(obs["mcvs"]), len(obs["command_centers"]) / 3.0, self.env.game_ms / self.horizon_ms]
        return np.array(v, float)

    def state(self) -> Any:
        return {"seed": self.seed, "faction": self.faction, "hash": self.env.state_hash(), "t": self.t, "done": self.done}

    def save(self) -> bytes:
        return self.env.save()

    # ---- baselines
    def expert_action(self) -> int:
        """A scripted builder-soldier: draft by the AI planner, grow the economy to its plan, recruit, expand with an MCV, attack when strong."""
        mask = self.legal_mask()
        obs = self.observe()
        counts = obs["buildings"]
        plan = {"producer": 3, "ranger": 3, "quarry": 2, "processor": 1, "hunter": 1, "farm": 2, "well": 1, "mine": 2, "ironmine": 1, "smelter": 1, "tavern": 1,
                "bakery": 1, "smithy": 1, "barracks": 1, "vehicle_factory": 1, "defense": 1}
        if obs["offers"]:
            pick = tech.ai_pick(self.w, self.faction)
            k = obs["offers"].index(pick) if pick in obs["offers"] else 0
            if mask[V["draft:%d" % k]]:
                return V["draft:%d" % k]
        if mask[V["road"]]:
            return V["road"]
        minutes = self.env.game_ms / 60_000
        army = sum(obs["units"].get(k, 0) for k in ("infantry", "tank"))
        if mask[V["expand"]]:
            return V["expand"]
        if minutes > 6 and not obs["mcvs"] and len(obs["command_centers"]) < 2 and mask[V["queue:mcv"]] and obs["buildings"].get("vehicle_factory", 0):
            return V["queue:mcv"]
        if army >= 5 and minutes > 10 and mask[V["attack"]]:
            return V["attack"]
        for kind in BUILD_KINDS:
            if counts.get(kind, 0) < plan[kind] and mask[V["build:" + kind]] and not obs["constructing"].get(kind, 0):
                return V["build:" + kind]
        for u in ("tank", "infantry"):
            if army < 12 and mask[V["queue:" + u]]:
                return V["queue:" + u]
        return V["noop"]


def policy_noop(env: StrategyEnv, obs: dict[str, Any]) -> int:
    return V["noop"]


def policy_random(rng: np.random.RandomState):
    def p(env: StrategyEnv, obs: dict[str, Any]) -> int:
        legal = env.legal_actions()
        return int(rng.choice(legal))
    return p


def policy_scripted(env: StrategyEnv, obs: dict[str, Any]) -> int:
    return env.expert_action()


def policy_expansion_only(env: StrategyEnv, obs: dict[str, Any]) -> int:
    """The old learner's exploit: expand whenever possible, never fight."""
    m = env.legal_mask()
    for v in ("expand", "queue:mcv"):
        if m[V[v]]:
            return V[v]
    for kind in ("producer", "ranger", "quarry", "processor", "vehicle_factory", "barracks"):
        if m[V["build:" + kind]] and obs["buildings"].get(kind, 0) < 2:
            return V["build:" + kind]
    return V["noop"]


def run_episode(env: StrategyEnv, policy, seed: int, **scenario: Any) -> dict[str, Any]:
    obs = env.reset(seed, **scenario)
    while not env.done:
        obs, _r, _t, _tr, _i = env.step(policy(env, obs))
    f = env.faction
    fs = env.w.fstats.get(f, {})
    return {"return": round(env.return_, 3), "score": round(env.score(), 3), "reason": env.reason, "steps": env.t, "buildings": sum(1 for b in env.w.buildings.values() if b["faction_name"] == f and "hp" in b and b["kind"] != "warehouse"),
            "settlements": len(settlements.standing(env.w, f)), "cards": len(env.w.tech[f]["cards"]), "kills": fs.get("unit_kills", 0), "building_kills": fs.get("building_kills", 0),
            "army": sum(1 for u in env.w.units.values() if u["faction_name"] == f and u.get("alive", True) and u.get("weapon"))}
