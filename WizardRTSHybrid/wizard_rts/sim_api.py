"""Headless training interface over the one authoritative HybridWorld. No Godot, no Gymnasium, no numpy required.

    env = HybridEnv(seed=507, map_size="standard", agent_factions=("Red", "Blue"))
    obs = env.reset()
    obs, reward, terminated, truncated, info = env.step({"Red": [{"op": "build", ...}], "Blue": []})

Design (engineering proposal, DECISIONS D6):
- The environment owns a HybridWorld and advances it in fixed game-time steps (`step_ms`).
- Factions in `agent_factions` act only through the actions passed to step(); every other faction is played by the
  built-in AI (`world.ai_factions`). Actions are the same commands God Mode and the AI use, so an illegal action is
  rejected by the simulation with a reason; `legal_actions()` gives the masks.
- Observations are plain dicts of numbers and short lists (JSON-serialisable); `flatten()` makes a fixed-order vector.
- Rewards are deltas of a score built from measurable state (wealth, territory, kills, survival); weights are a parameter.
- Determinism: the same seed and the same action sequence give the same `state_hash()` (tests/test_sim_api.py).
- save()/load() pickle the whole world (rng state included); replay() re-runs a recorded episode and checks the hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from typing import Any

from wizard_rts import construction as con
from wizard_rts import rules
from wizard_rts.coords import tile_to_hex  # noqa: F401  (kept importable for scripts)
from wizard_rts.world import FACTIONS, HybridWorld

TERRITORY_CELL = 8  # tiles per side of the coarse cell used to measure territory
WARE_VALUE = {  # wealth weights: raw goods count little, processed and military goods count more (engineering)
    "log": 1, "plank": 2, "granite": 2, "coal": 2, "iron_ore": 2, "iron": 4, "gold": 6, "ration": 2, "bread": 2,
    "fish": 2, "meat": 2, "wheat": 1, "water": 0, "ax": 6, "brick": 3, "marble": 4,
}
DEFAULT_WEIGHTS = {"wealth": 0.01, "territory": 0.5, "kill_value": 0.002, "loss_value": -0.002, "building_kill": 1.0, "building_loss": -1.0, "alive": 0.0, "eliminated": -50.0}
ACTION_OPS = ("build", "road", "queue", "cancel", "move", "order", "demolish", "rally", "stop")


class HybridEnv:
    def __init__(
        self,
        seed: int = 507,
        map_size: str = "standard",
        agent_factions: tuple[str, ...] = (),
        step_ms: int = 5_000,
        max_game_ms: int = 60 * 60_000,
        weights: dict[str, float] | None = None,
        aggressive: bool = True,
        terrain: bool = True,
    ) -> None:
        self.seed = int(seed)
        self.map_size = map_size
        self.agent_factions = tuple(agent_factions)
        self.step_ms = int(step_ms)
        self.max_game_ms = int(max_game_ms)
        self.weights = dict(DEFAULT_WEIGHTS, **(weights or {}))
        self.aggressive = aggressive
        self.use_terrain = terrain
        self.world: HybridWorld | None = None
        self.log: list[dict[str, Any]] = []
        self._seq = 0
        self._score: dict[str, float] = {}
        self._events_seen = 0

    # ---------------------------------------------------------------- lifecycle
    def reset(self, seed: int | None = None) -> dict[str, dict[str, Any]]:
        if seed is not None:
            self.seed = int(seed)
        os.environ.setdefault("HYBRID_AI", "1")
        self.world = HybridWorld(self.seed, terrain=self.use_terrain, map_size=self.map_size)
        w = self.world
        w.ai_enabled = True
        w.ai_aggressive = self.aggressive
        names = [f[0] for f in FACTIONS]
        for f in self.agent_factions:
            if f not in names:
                raise ValueError(f"unknown faction {f}")
        w.ai_factions = set(names) - set(self.agent_factions)
        self.log = []
        self._seq = 0
        self._events_seen = len(w.events)
        self._score = {n: self._score_of(n) for n in names}
        return {n: self.observe(n) for n in self.agent_factions}

    @property
    def game_ms(self) -> int:
        return int(self.world.dmb.clock.get("game_ms", 0))

    def state_hash(self) -> str:
        return self.world.state_hash()

    # ---------------------------------------------------------------- stepping
    def step(self, actions: dict[str, list[dict[str, Any]]] | None = None):
        """Apply each agent faction's actions (in faction order), advance `step_ms`, return
        (observations, rewards, terminated, truncated, info). Rewards are per agent faction."""
        w = self.world
        actions = actions or {}
        results: dict[str, list[dict[str, Any]]] = {}
        for faction in self.agent_factions:
            results[faction] = [self.apply(faction, a) for a in actions.get(faction, [])]
        self.log.append({"game_ms": self.game_ms, "actions": {f: [dict(a) for a in actions.get(f, [])] for f in self.agent_factions}})
        remaining = self.step_ms
        while remaining > 0:
            chunk = min(remaining, 1000)
            self._seq += 1
            w.advance(chunk, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)
            remaining -= chunk
        self._trim_events()
        names = [f[0] for f in FACTIONS]
        new = {n: self._score_of(n) for n in names}
        rewards = {f: round(new[f] - self._score[f] + self._alive_bonus(f), 6) for f in self.agent_factions}
        self._score = new
        alive = [n for n in names if self._alive(n)]
        terminated = {f: not self._alive(f) for f in self.agent_factions}
        done_all = len(alive) <= 1 or (self.agent_factions and all(terminated.values()))
        truncated = self.game_ms >= self.max_game_ms
        for f in self.agent_factions:
            if terminated[f] and f not in self.__dict__.setdefault("_dead_reported", set()):
                self._dead_reported.add(f)
                rewards[f] += self.weights["eliminated"]
        info = {"game_ms": self.game_ms, "results": results, "alive": alive, "episode_over": bool(done_all or truncated)}
        return {f: self.observe(f) for f in self.agent_factions}, rewards, terminated, truncated, info

    def _trim_events(self) -> None:
        ev = self.world.events
        if len(ev) > 50_000:
            del ev[:25_000]

    # ---------------------------------------------------------------- actions
    def apply(self, faction: str, action: dict[str, Any]) -> dict[str, Any]:
        """One action through the same commands God Mode uses. Returns the simulation's reply (status, reason)."""
        w = self.world
        op = action.get("op")
        if op not in ACTION_OPS:
            return {"status": "rejected", "reason": "unknown_op"}
        try:
            if op == "build":
                return _slim(w.build(faction, str(action["kind"]), int(action["tx"]), int(action["ty"])))
            if op == "road":
                if not (self._owns_building(faction, action["a"]) and self._owns_building(faction, action["b"])):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.road(faction, str(action["a"]), str(action["b"])))
            if op == "queue":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.queue(str(action["building"]), str(action["unit"])))
            if op == "cancel":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.cancel(str(action["building"]), int(action["index"])))
            if op == "demolish":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.demolish(str(action["building"])))
            if op == "rally":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.rally(str(action["building"]), int(action["tx"]), int(action["ty"])))
            units = [u for u in action.get("units", []) if self._owns_unit(faction, u)]
            if not units and op in ("move", "stop"):
                return {"status": "rejected", "reason": "no_units"}
            if op == "move":
                return _slim(w.move(units, int(action["tx"]), int(action["ty"]), bool(action.get("attack_move", False))))
            if op == "stop":
                return _slim(w.stop(units))
            if op == "order":
                if not self._owns_unit(faction, action["unit"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.order(str(action["unit"]), str(action["target"])))
        except (KeyError, TypeError, ValueError) as exc:
            return {"status": "rejected", "reason": f"malformed:{type(exc).__name__}"}
        return {"status": "rejected", "reason": "unhandled"}

    def _owns_building(self, faction: str, bid: Any) -> bool:
        b = self.world.buildings.get(str(bid))
        return b is not None and b["faction_name"] == faction

    def _owns_unit(self, faction: str, uid: Any) -> bool:
        u = self.world.units.get(str(uid))
        return u is not None and u["faction_name"] == faction and u.get("alive", True)

    # ---------------------------------------------------------------- masks
    def legal_actions(self, faction: str, site_samples: int = 6) -> dict[str, Any]:
        """Masks of what the faction may do now. Build sites are sampled near the warehouse (the simulation has the final word)."""
        w = self.world
        wh = con.faction_warehouse(w, faction)
        stocks = _stocks(w, faction)
        out: dict[str, Any] = {"build": [], "road": [], "queue": [], "move_units": [], "attack": [], "demolish": []}
        if wh is None:
            return out
        for kind, spec in con.BUILD_MENU.items():
            if all(stocks.get(g, 0) >= n for g, n in spec["cost"].items()):
                sites = self._sites(faction, kind, wh, site_samples)
                if sites:
                    out["build"].append({"kind": kind, "sites": sites})
        mine = [b for b in w.buildings.values() if b["faction_name"] == faction and int(b.get("hp", 1)) > 0]
        for b in mine:
            if b["kind"] != "warehouse" and not w.adjacency.get(b["id"]):
                out["road"].append({"a": b["id"], "b": wh["id"]})
            if b.get("operational") and b["kind"] in con.RECIPES and len(b.get("queue", [])) < 5:
                for unit in con.RECIPES[b["kind"]]:
                    out["queue"].append({"building": b["id"], "unit": unit})
            if b["kind"] != "warehouse":
                out["demolish"].append(b["id"])
        units = [u for u in w.units.values() if u["faction_name"] == faction and u.get("alive", True)]
        out["move_units"] = [{"id": u["id"], "loco": u.get("loco", "foot")} for u in units]
        armed = [u for u in units if u.get("weapon")]
        if armed:
            from wizard_rts.military import target_types

            for e in w.buildings.values():
                if e["faction_name"] != faction and "hp" in e and int(e["hp"]) > 0:
                    if any(rules.can_hit(rules.weapon(n), target_types(e)) for u in armed for n in u.get("weapons", [])):
                        out["attack"].append(e["id"])
        return out

    def _sites(self, faction: str, kind: str, wh: dict, k: int) -> list[list[int]]:
        w = self.world
        spec = con.BUILD_MENU[kind]
        out: list[list[int]] = []
        if spec.get("size") == "water3":
            from wizard_rts import ai

            site = ai._naval_site(w, faction, wh)
            return [list(site)] if site else []
        for r in range(4, 26, 2):
            for dy in range(-r, r + 1, 3):
                for dx in range(-r, r + 1, 3):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    t = (wh["tx"] + dx, wh["ty"] + dy)
                    why, _ctx = con.check_placement(w, faction, kind, t[0], t[1])
                    if why is None:
                        out.append(list(t))
                        if len(out) >= k:
                            return out
        return out

    # ---------------------------------------------------------------- observations
    def observe(self, faction: str) -> dict[str, Any]:
        w = self.world
        t = w.terrain
        mine_b = [b for b in w.buildings.values() if b["faction_name"] == faction and int(b.get("hp", 1)) > 0]
        wh = con.faction_warehouse(w, faction)
        units = [u for u in w.units.values() if u["faction_name"] == faction and u.get("alive", True)]
        counts: dict[str, int] = {}
        building_n: dict[str, int] = {}
        constructing: dict[str, int] = {}
        for b in mine_b:
            (constructing if b.get("constructing") else building_n)[b["kind"]] = (constructing if b.get("constructing") else building_n).get(b["kind"], 0) + 1
        for u in units:
            counts[u["kind"]] = counts.get(u["kind"], 0) + 1
        threats = self._threats(faction, wh)
        obs: dict[str, Any] = {
            "faction": faction,
            "game_ms": self.game_ms,
            "alive": wh is not None and int(wh["hp"]) > 0,
            "stocks": _stocks(w, faction),
            "buildings": building_n,
            "constructing": constructing,
            "units": counts,
            "territory_cells": self._territory(faction),
            "production": self._production(faction),
            "military_strength": sum(rules.actor(u["definition"])["cost"] * int(u["hp"]) // max(int(u["max_hp"]), 1) for u in units if rules.actor(u["definition"])),
            "threats": threats,
            "capital": [wh["tx"], wh["ty"]] if wh else None,
            "enemy_capitals": {n: [b["tx"], b["ty"]] for b in w.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] != faction for n in [b["faction_name"]]},
        }
        if t is not None and wh is not None:
            obs["local_map"] = self._local_map(wh["tx"], wh["ty"], 12)
            obs["deposits"] = {r: t.total(wh["tx"], wh["ty"], 30, r) for r in ("coal", "iron", "gold", "stones", "fish")}
        return obs

    def _local_map(self, cx: int, cy: int, r: int) -> list[list[int]]:
        t = self.world.terrain
        return [[t.cls[y * t.w + x] if t.in_bounds(x, y) else 5 for x in range(cx - r, cx + r + 1, 2)] for y in range(cy - r, cy + r + 1, 2)]

    def _territory(self, faction: str) -> int:
        cells = set()
        for b in self.world.buildings.values():
            if b["faction_name"] == faction and int(b.get("hp", 1)) > 0:
                cells.add((b["tx"] // TERRITORY_CELL, b["ty"] // TERRITORY_CELL))
        return len(cells)

    def _production(self, faction: str) -> dict[str, int]:
        from wizard_rts.logistics import io_for

        out: dict[str, int] = {}
        for b in self.world.buildings.values():
            if b["faction_name"] == faction and b.get("operational") and int(b.get("hp", 1)) > 0:
                for ware in io_for(self.world, b).get("outputs", []):
                    out[ware] = out.get(ware, 0) + 1
        return out

    def _threats(self, faction: str, wh: dict | None) -> dict[str, Any]:
        if wh is None:
            return {"enemy_units_near": 0, "enemy_strength_near": 0, "nearest": None}
        n = 0
        strength = 0
        nearest = None
        for u in self.world.units.values():
            if u["faction_name"] == faction or not u.get("alive", True):
                continue
            d = abs(u["tx"] - wh["tx"]) + abs(u["ty"] - wh["ty"])
            if d <= 40:
                n += 1
                r = rules.actor(u["definition"])
                strength += (r["cost"] if r else 0) * int(u["hp"]) // max(int(u["max_hp"]), 1)
                if nearest is None or d < nearest:
                    nearest = d
        return {"enemy_units_near": n, "enemy_strength_near": strength, "nearest": nearest}

    # ---------------------------------------------------------------- reward pieces
    def _alive(self, faction: str) -> bool:
        wh = con.faction_warehouse(self.world, faction)
        return wh is not None and int(wh["hp"]) > 0

    def _alive_bonus(self, faction: str) -> float:
        return self.weights["alive"] if self._alive(faction) else 0.0

    def _score_of(self, faction: str) -> float:
        w = self.world
        wealth = sum(WARE_VALUE.get(g, 1) * n for g, n in _stocks(w, faction).items())
        fs = w.fstats.get(faction, {})
        return (
            self.weights["wealth"] * wealth
            + self.weights["territory"] * self._territory(faction)
            + self.weights["kill_value"] * fs.get("kill_value", 0)
            + self.weights["loss_value"] * fs.get("loss_value", 0)
            + self.weights["building_kill"] * fs.get("building_kills", 0)
            + self.weights["building_loss"] * fs.get("building_losses", 0)
        )

    # ---------------------------------------------------------------- save / restore / replay
    def save(self) -> bytes:
        return pickle.dumps({"world": self.world, "log": self.log, "seq": self._seq, "score": self._score, "seen": self._events_seen, "seed": self.seed}, protocol=5)

    def load(self, blob: bytes) -> None:
        d = pickle.loads(blob)
        self.world, self.log, self._seq, self._score, self._events_seen, self.seed = d["world"], d["log"], d["seq"], d["score"], d["seen"], d["seed"]

    def replay(self, log: list[dict[str, Any]] | None = None) -> str:
        """Re-run a recorded episode from its seed and return the final state hash."""
        log = self.log if log is None else log
        twin = HybridEnv(self.seed, self.map_size, self.agent_factions, self.step_ms, self.max_game_ms, self.weights, self.aggressive, self.use_terrain)
        twin.reset()
        for entry in log:
            twin.step(entry["actions"])
        return twin.state_hash()

    def flatten(self, obs: dict[str, Any], wares: tuple[str, ...] = tuple(WARE_VALUE), kinds: tuple[str, ...] = tuple(con.BUILD_MENU)) -> list[float]:
        """A fixed-order numeric vector for a learner: stocks, buildings by kind, units, territory, strength, threats, deposits."""
        v = [float(obs["game_ms"]) / 60_000.0]
        v += [float(obs["stocks"].get(g, 0)) for g in wares]
        v += [float(obs["buildings"].get(k, 0)) for k in kinds]
        v += [float(sum(obs["units"].values())), float(obs["territory_cells"]), float(obs["military_strength"]) / 1000.0]
        th = obs["threats"]
        v += [float(th["enemy_units_near"]), float(th["enemy_strength_near"]) / 1000.0, float(th["nearest"] if th["nearest"] is not None else 99)]
        v += [float(obs.get("deposits", {}).get(r, 0)) for r in ("coal", "iron", "gold", "stones", "fish")]
        return v


def _stocks(world: HybridWorld, faction: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for b in world.buildings.values():
        if b["faction_name"] == faction and b["kind"] == "warehouse" and int(b.get("hp", 1)) > 0:
            for g, n in world.stocks.get(b["id"], {}).items():
                if n:
                    out[g] = out.get(g, 0) + int(n)
    return out


def _slim(reply: dict[str, Any]) -> dict[str, Any]:
    """Drop the snapshot the world commands attach: an agent step must not carry 300 KB per action."""
    return {k: v for k, v in reply.items() if k != "snapshot"}


def digest(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
