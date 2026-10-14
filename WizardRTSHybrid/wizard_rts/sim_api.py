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
from wizard_rts import wl_defs
from wizard_rts import rules, tech
from wizard_rts import diagnostics, territory, visibility
from wizard_rts.coords import tile_to_hex  # noqa: F401  (kept importable for scripts)
from wizard_rts.world import FACTIONS, HybridWorld

TERRITORY_CELL = 8  # tiles per side of the coarse cell used to measure territory
WARE_VALUE = {  # wealth weights: raw goods count little, processed and military goods count more (engineering)
    "log": 1, "plank": 2, "granite": 2, "coal": 2, "iron_ore": 2, "iron": 4, "gold": 6, "ration": 2, "bread": 2,
    "fish": 2, "meat": 2, "wheat": 1, "water": 0, "ax": 6, "brick": 3, "marble": 4,
}
DEFAULT_WEIGHTS = {"wealth": 0.01, "territory": 0.5, "kill_value": 0.002, "loss_value": -0.002, "building_kill": 1.0, "building_loss": -1.0, "alive": 0.0, "eliminated": -50.0}
ACTION_OPS = ("build", "road", "queue", "cancel", "move", "order", "demolish", "rally", "stop", "deploy", "draft", "enhance", "ability", "dismantle", "convert", "waterway",
              "belt", "upgrade", "configure", "link_power", "trade", "propose", "respond", "break_treaty")


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
        profile: str = "test_showcase",
        era_max_ms: int | None = None,
        era_vp: int | None = None,
    ) -> None:
        # training pacing: a shorter stall guard and/or a lower world-VP threshold per era (None keeps the rules: 75 minutes, VP 6/8/8)
        self.era_max_ms = era_max_ms
        self.era_vp = era_vp
        self.profile = profile
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
        self.world = HybridWorld(self.seed, terrain=self.use_terrain, map_size=self.map_size, profile=self.profile)
        w = self.world
        if self.era_max_ms is not None:
            w.era_max_ms = max(10_000, int(self.era_max_ms))
        if self.era_vp is not None:
            w.era_vp_threshold = max(1, int(self.era_vp))
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

    def seats_of(self, faction: str) -> list[str]:
        """The faction and every split successor it has been given, recursively (N07: the same controller plays them all)."""
        out = [faction]
        for s in self.world.__dict__.get("agent_successors", {}).get(faction, []):
            out += self.seats_of(s)
        return out

    def seats(self) -> list[str]:
        """Every faction an agent plays now: the agent factions in order, each followed by its successors."""
        return [s for f in self.agent_factions for s in self.seats_of(f)]

    @property
    def game_ms(self) -> int:
        return int(self.world.dmb.clock.get("game_ms", 0))

    def state_hash(self) -> str:
        return self.world.state_hash()

    # ---------------------------------------------------------------- stepping
    def step(self, actions: dict[str, list[dict[str, Any]]] | None = None, observe: bool = True):
        """Apply each seat's actions (the agent factions and their successors, in order), advance `step_ms`, return
        (observations, rewards, terminated, truncated, info). Rewards are per agent faction. With observe=False the observations
        are `{}` (a controller that builds its own features skips the 1-4 ms per seat that observe() costs)."""
        w = self.world
        actions = actions or {}
        results: dict[str, list[dict[str, Any]]] = {}
        seats = self.seats()
        for faction in seats:
            results[faction] = [self.apply(faction, a) for a in actions.get(faction, [])]
        self.log.append({"game_ms": self.game_ms, "actions": {f: [dict(a) for a in actions.get(f, [])] for f in seats}})
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
        for f in self.seats():
            rewards.setdefault(f, 0.0)  # a successor seat has no reward stream of its own
        self._score = new
        alive = [n for n in names if self._alive(n)]
        terminated = {f: not self._alive(f) for f in self.agent_factions}
        extra = {f: not self._alive(f) for f in self.seats() if f not in terminated}
        done_all = len(alive) <= 1 or (self.agent_factions and all(terminated.values()))
        truncated = self.game_ms >= self.max_game_ms
        from wizard_rts import history

        lost_together = bool(getattr(w, "collective_loss", False))
        if lost_together:  # catastrophe limit reached: every faction lost, whatever its VP (plan v2 7.2); reported once as a terminal loss for each agent
            terminated = {f: True for f in self.agent_factions}
            done_all = True
        for f in self.agent_factions:
            if terminated[f] and f not in self.__dict__.setdefault("_dead_reported", set()):
                self._dead_reported.add(f)
                rewards[f] += self.weights["eliminated"]
        info = {"game_ms": self.game_ms, "results": results, "alive": alive, "episode_over": bool(done_all or truncated), "outcome": history.outcome(w), "seats": self.seats(),
                "faction_states": {n: history.state(w)["faction"].get(n, {}).get("state", "active") for n in sorted(w.faction_info)}}
        return ({f: self.observe(f) for f in self.seats()} if observe else {}), rewards, {**terminated, **extra}, truncated, info

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
            if op == "draft":
                return _slim(w.draft(faction, str(action["card"])))
            if op == "road":
                if not (self._owns_building(faction, action["a"]) and self._owns_building(faction, action["b"])):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.road(faction, str(action["a"]), str(action["b"])))
            if op == "queue":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.queue(str(action["building"]), str(action["unit"]), faction=faction))
            if op == "cancel":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.cancel(str(action["building"]), int(action["index"]), faction=faction))
            if op == "demolish":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.demolish(str(action["building"]), faction=faction))
            if op == "enhance":  # Widelands in-place upgrade (additive to the action space)
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.enhance(faction, str(action["building"]), str(action.get("to", ""))))
            if op in ("dismantle", "convert"):
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.dismantle(faction, str(action["building"])) if op == "dismantle" else w.convert(faction, str(action["building"]), str(action.get("to", ""))))
            if op == "waterway":
                if not (self._owns_building(faction, action["a"]) and self._owns_building(faction, action["b"])):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.waterway(faction, str(action["a"]), str(action["b"])))
            if op == "ability":  # board / unload / capture / infiltrate / lay_mine / power (additive to the action space)
                kw = {k: v for k, v in action.items() if k not in ("op", "what")}
                for key in ("unit", "transport"):
                    if key in kw and not self._owns_unit(faction, kw[key]):
                        return {"status": "rejected", "reason": "not_yours"}
                if "building" in kw and str(action.get("what")) == "power" and not self._owns_building(faction, kw["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.ability(faction, str(action.get("what", "")), **kw))
            if op == "belt":  # one run of belt, duct, conduit or payload conveyor as a construction site (Modern era)
                tiles = [[int(t[0]), int(t[1])] for t in action["tiles"]]
                end_dir = action.get("end_dir")
                return _slim(w.belt(faction, tiles, None if end_dir is None else int(end_dir), str(action.get("kind", "mdy:conveyor"))))
            if op == "upgrade":  # a mine or drill becomes advanced equipment on the same site
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.upgrade(faction, str(action["building"]), str(action["to"])))
            if op == "configure":  # a machine's setting: drill target, factory plan, sorter item, bridge link, rotation, ...
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.configure(faction, str(action["building"]), str(action["key"]), action["value"]))
            if op == "link_power":
                a_id, b_id = str(action["a"]), str(action["b"])
                if not (self._owns_building(faction, a_id) and self._owns_building(faction, b_id)):
                    return {"status": "rejected", "reason": "not_yours"}
                from wizard_rts.industry import commands as ind_commands

                return _slim(ind_commands.link_power(w, faction, a_id, b_id))
            if op == "trade":  # a caravan from an own warehouse to a partner's warehouse the faction knows (remembered, in sight, or an ally's)
                from wizard_rts import trade

                wh_id, partner = str(action["building"]), str(action["partner"])
                give = {str(g): int(n) for g, n in dict(action["give"]).items()}
                want = {str(g): int(n) for g, n in dict(action["want"]).items()}
                if not self._owns_building(faction, wh_id):
                    return {"status": "rejected", "reason": "not_yours"}
                if not self._may_trade_with(faction, partner):
                    return {"status": "rejected", "reason": "unknown_partner"}
                return _slim(trade.send_caravan(w, faction, wh_id, partner, give, want))
            if op == "propose":  # a truce, peace or alliance offer from this faction
                from wizard_rts import diplomacy

                other = str(action["to"])
                if other not in w.faction_info or other == faction:
                    return {"status": "rejected", "reason": "bad_offer"}
                return _slim(diplomacy.propose(w, faction, other, str(action.get("state", "truce")), int(action.get("duration_ms", diplomacy.TRUCE_MS))))
            if op == "respond":  # accept or refuse an offer addressed to this faction
                from wizard_rts import diplomacy

                offer = w.__dict__.get("offers", {}).get(str(action["offer"]))
                if offer is not None and offer["to"] != faction:
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(diplomacy.respond(w, str(action["offer"]), bool(action["accept"])))
            if op == "break_treaty":
                from wizard_rts import diplomacy

                other = str(action["with"])
                if other not in w.faction_info or other == faction:
                    return {"status": "rejected", "reason": "bad_relation"}
                return _slim(diplomacy.break_treaty(w, faction, other, why="agent"))
            if op == "rally":
                if not self._owns_building(faction, action["building"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.rally(str(action["building"]), int(action["tx"]), int(action["ty"]), faction=faction))
            units = [u for u in action.get("units", []) if self._owns_unit(faction, u)]
            if not units and op in ("move", "stop"):
                return {"status": "rejected", "reason": "no_units"}
            if op == "move":
                return _slim(w.move(units, int(action["tx"]), int(action["ty"]), bool(action.get("attack_move", False)), faction=faction))
            if op == "stop":
                return _slim(w.stop(units, faction=faction))
            if op == "deploy":  # an MCV becomes a command centre where it stands (same command as God Mode's Deploy button)
                if not self._owns_unit(faction, action["unit"]):
                    return {"status": "rejected", "reason": "not_yours"}
                return _slim(w.deploy(str(action["unit"]), faction=faction))
            if op == "order":
                if not self._owns_unit(faction, action["unit"]):
                    return {"status": "rejected", "reason": "not_yours"}
                if not self._may_target(faction, str(action["target"])):
                    return {"status": "rejected", "reason": "not_visible"}  # an agent can only attack what it can see or remembers seeing
                return _slim(w.order(str(action["unit"]), str(action["target"]), faction=faction))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            return {"status": "rejected", "reason": f"malformed:{type(exc).__name__}"}
        return {"status": "rejected", "reason": "unhandled"}

    def _owns_building(self, faction: str, bid: Any) -> bool:
        b = self.world.buildings.get(str(bid))
        return b is not None and b["faction_name"] == faction

    def _may_target(self, faction: str, target_id: str) -> bool:
        """May this faction name this entity as a target? Its own things, anything in its memory of enemy buildings, anything in sight now."""
        w = self.world
        e = w.buildings.get(target_id) or w.units.get(target_id)
        if e is not None and e.get("faction_name") == faction:
            return True
        if target_id in visibility.memory_of(w, faction):
            return True
        return e is not None and visibility.visible(w, faction, e["tx"], e["ty"])

    def _may_trade_with(self, faction: str, partner_id: str) -> bool:
        """A partner warehouse the faction has seen (memory or sight) or that belongs to an ally."""
        from wizard_rts import diplomacy

        w = self.world
        pw = w.buildings.get(partner_id)
        if pw is None:
            return False
        if diplomacy.state_of(w, faction, pw["faction_name"]) == "alliance":
            return True
        return partner_id in visibility.memory_of(w, faction) or visibility.visible(w, faction, pw["tx"], pw["ty"])

    def _owns_unit(self, faction: str, uid: Any) -> bool:
        u = self.world.units.get(str(uid))
        return u is not None and u["faction_name"] == faction and u.get("alive", True)

    # ---------------------------------------------------------------- masks
    def legal_actions(self, faction: str, site_samples: int = 6) -> dict[str, Any]:
        """Masks of what the faction may do now. Build sites are sampled near the warehouse (the simulation has the final word)."""
        w = self.world
        wh = con.faction_warehouse(w, faction)
        stocks = _stocks(w, faction)
        out: dict[str, Any] = {"build": [], "road": [], "queue": [], "move_units": [], "attack": [], "demolish": [], "deploy": [], "expansion_sites": [], "draft": list(w.tech.get(faction, {}).get("offers", []))}
        if wh is None:
            return out
        for kind, spec in con.BUILD_MENU.items():
            if all(stocks.get(g, 0) >= n for g, n in spec["cost"].items()):
                sites = self._sites(faction, kind, wh, site_samples)
                if sites:
                    out["build"].append({"kind": kind, "sites": sites})
        listed = {e["kind"] for e in out["build"]}
        for kind, spec in self._generated_menu(faction).items():  # the faction's own Widelands buildings and the Mindustry machines it has unlocked
            if kind in listed or not tech.kind_allowed(w, faction, kind):
                continue
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
                    if not tech.unit_allowed(w, faction, unit):
                        continue
                    out["queue"].append({"building": b["id"], "unit": unit})
            if b["kind"] != "warehouse":
                out["demolish"].append(b["id"])
            if b.get("operational") and b["kind"].startswith("wl:"):
                up = (wl_defs.spec_for_kind(b["kind"]) or {}).get("enhances_to")
                if up and tech.kind_allowed(w, faction, up):
                    out.setdefault("enhance", []).append({"building": b["id"], "to": up})
        units = [u for u in w.units.values() if u["faction_name"] == faction and u.get("alive", True)]
        out["move_units"] = [{"id": u["id"], "loco": u.get("loco", "foot")} for u in units]
        for u in units:
            if territory.is_founder(u):
                why = territory.deploy_check(w, u)
                out["deploy"].append({"unit": u["id"], "ok": why is None, "reason": why or ""})
                if why is not None:
                    from wizard_rts import ai

                    site = ai._find_expansion_site(w, faction, u)
                    if site is not None:
                        out["expansion_sites"].append({"unit": u["id"], "tile": list(site)})
        self._mechanics_masks(faction, out)
        armed = [u for u in units if u.get("weapon")]
        if armed:
            from wizard_rts.military import target_types

            # an agent can attack what it can see now (units, nests) and the enemy buildings it remembers seeing (the memory may be stale)
            seen = visibility.seen_enemies(w, faction)
            cands = [w.units[r["id"]] for r in seen["units"] if r["id"] in w.units]
            cands += [w.buildings[r["id"]] for r in seen["buildings"] if not r["faction"] and r["id"] in w.buildings]  # blight nests belong to nobody
            for r in visibility.known_enemy_buildings(w, faction):
                b = w.buildings.get(r["id"])
                if b is None:
                    out["attack"].append(r["id"])  # remembered, but it may be gone: nobody has looked
                else:
                    cands.append(b)
            for e in cands:
                if e["id"] in out["attack"] or e.get("inside"):
                    continue
                if any(rules.can_hit(rules.weapon(n), target_types(e)) for u in armed for n in u.get("weapons", [])):
                    out["attack"].append(e["id"])
            out["attack"].sort()
        return out

    def _mechanics_masks(self, faction: str, out: dict[str, Any]) -> None:
        """What the faction may attempt with the industry, trade and diplomacy commands now (the simulation still has the final word)."""
        from wizard_rts import diplomacy, history, tech, trade
        from wizard_rts.industry import registry as ind_registry

        w = self.world
        mine = sorted((b for b in w.buildings.values() if b["faction_name"] == faction and int(b.get("hp", 0)) > 0 and not b.get("constructing")), key=lambda b: b["id"])
        out["upgrade"], out["configure"], out["link_power"] = [], [], []
        drills = [(k, ind_registry.block(k)) for k in ind_registry.kinds()]
        drills = [(k, s) for k, s in drills if s and s["role"] == "drill" and tech.kind_allowed(w, faction, k)]
        for b in mine:
            for kind, spec in drills:
                if b["kind"] in spec["upgrade_from"]:
                    out["upgrade"].append({"building": b["id"], "to": kind})
            if b.get("mdy") is not None:
                out["configure"].append({"building": b["id"], "role": b["mdy"]["role"]})
                if b["mdy"]["role"] == "node":
                    out["link_power"].append(b["id"])
        live = [n for n in sorted(w.faction_info) if n != faction and history.state(w)["faction"].get(n, {}).get("state") != "collapsed"]
        out["propose"] = [{"to": n, "states": [s for s in diplomacy.STATES[1:] if s != diplomacy.state_of(w, faction, n)]} for n in live]
        out["break_treaty"] = [n for n in live if diplomacy.state_of(w, faction, n) != "war"]
        out["respond"] = [{"offer": o["id"], "from": o["from"], "state": o["state"]} for o in sorted(w.__dict__.get("offers", {}).values(), key=lambda o: o["id"]) if o["to"] == faction]
        posts = [b for b in mine if trade.is_post(b)]
        partners = sorted((p for p in (w.buildings.get(r["id"]) for r in visibility.known_enemy_buildings(w, faction)) if p is not None and trade.is_post(p) and int(p.get("hp", 0)) > 0
                           and not trade.hostile(w, faction, p["faction_name"])), key=lambda p: p["id"])
        allied = sorted((b for b in w.buildings.values() if b["faction_name"] != faction and b.get("faction_name") and trade.is_post(b) and int(b.get("hp", 0)) > 0
                         and diplomacy.state_of(w, faction, b["faction_name"]) == "alliance"), key=lambda p: p["id"])
        out["trade"] = [{"building": b["id"], "partner": p["id"], "partner_faction": p["faction_name"]} for b in posts for p in {x["id"]: x for x in partners + allied}.values()][:64]

    def _generated_menu(self, faction: str) -> dict[str, dict[str, Any]]:
        """Buildable kinds beyond BUILD_MENU for this faction: its tribe's runnable wl: buildings (not enhancement-only) and every mdy: machine."""
        tribe = self.world.faction_info[faction].get("tribe", "")
        cache = self.__dict__.setdefault("_gen_menu", {})
        if tribe not in cache:
            menu = {}
            for kind, spec in con.full_menu().items():
                if kind in con.BUILD_MENU or spec.get("enhancement_of"):
                    continue
                if spec.get("game") == "widelands" and spec.get("tribe") != tribe:
                    continue
                menu[kind] = spec
            from wizard_rts.industry import registry as ind_registry

            for kind in ind_registry.kinds():
                spec = con.build_spec(kind)
                if spec is not None and kind not in menu:
                    menu[kind] = spec
            cache[tribe] = menu
        return cache[tribe]

    def _sites(self, faction: str, kind: str, wh: dict, k: int) -> list[list[int]]:
        w = self.world
        spec = con.build_spec(kind)
        out: list[list[int]] = []
        if not tech.kind_allowed(w, faction, kind):
            return out
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
            "alive": self._alive(faction),
            "stocks": _stocks(w, faction),
            "buildings": building_n,
            "constructing": constructing,
            "units": counts,
            "territory_cells": self._territory(faction),
            "production": self._production(faction),
            "military_strength": sum(rules.actor(u["definition"])["cost"] * int(u["hp"]) // max(int(u["max_hp"]), 1) for u in units if rules.actor(u["definition"])),
            "threats": threats,
            "capital": [wh["tx"], wh["ty"]] if wh else None,
            "command_centers": [
                {"id": c["id"], "tile": [c["tx"], c["ty"]], "radius": territory.radius_of(c), "outpost": bool(c.get("outpost")), "stock": dict(w.stocks.get(c["id"], {}))}
                for c in territory.command_centers(w, faction)
            ],
            "mcvs": [{"id": u["id"], "tile": [u["tx"], u["ty"]], "cargo": dict(u.get("cargo") or {})} for u in units if territory.is_founder(u)],
            "known_enemy_buildings": len(visibility.memory_of(w, faction)),
            "stuck_entities": sum(1 for r in diagnostics.stuck_report(w) if r["faction"] == faction),
            # only capitals this faction has seen and remembers (owner decision D, T1.1): the rest of the world is not in its observation
            "enemy_capitals": {e["faction_name"]: list(e["tile"]) for e in visibility.known_enemy_buildings(w, faction) if e["kind"] == "warehouse"},
            "visible": visibility.seen_enemies(w, faction),
            "explored_cells": len(visibility.explored_of(w, faction)),
        }
        if t is not None and wh is not None:
            obs["local_map"] = self._local_map(wh["tx"], wh["ty"], 12)
            obs["deposits"] = {r: t.total(wh["tx"], wh["ty"], 30, r) for r in ("coal", "iron", "gold", "stones", "fish")}
        return obs

    def _local_map(self, cx: int, cy: int, r: int) -> list[list[int]]:
        t = self.world.terrain
        return [[t.cls[y * t.w + x] if t.in_bounds(x, y) else 5 for x in range(cx - r, cx + r + 1, 2)] for y in range(cy - r, cy + r + 1, 2)]

    def _territory(self, faction: str) -> int:
        """Coarse cells (TERRITORY_CELL tiles a side) covered by the build squares of the faction's command centres: growing it means
        deploying MCVs, not building more houses beside the capital."""
        cells = set()
        for c in territory.command_centers(self.world, faction):
            r = territory.radius_of(c)
            for cy in range((c["ty"] - r) // TERRITORY_CELL, (c["ty"] + r) // TERRITORY_CELL + 1):
                for cx in range((c["tx"] - r) // TERRITORY_CELL, (c["tx"] + r) // TERRITORY_CELL + 1):
                    cells.add((cx, cy))
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
        for row in visibility.visible_units(self.world, faction):  # a threat is an enemy the faction can see
            u = self.world.units[row["id"]]
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
        """A faction lives until history collapses it (no standing settlement and no founder unit). Losing the capital building alone does not
        end it: the faction may hold other settlements and can recover (V4 history rules)."""
        from wizard_rts import history

        return history.state(self.world)["faction"].get(faction, {}).get("state") != "collapsed"

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
    SAVE_FORMAT = 2  # V4: saves carry a format number and the state hash; a save from another format is refused instead of half-loading

    def save(self) -> bytes:
        return pickle.dumps({"format": self.SAVE_FORMAT, "hash": self.world.state_hash(), "world": self.world, "log": self.log, "seq": self._seq, "score": self._score, "seen": self._events_seen, "seed": self.seed}, protocol=5)

    def load(self, blob: bytes) -> None:
        d = pickle.loads(blob)
        if d.get("format") != self.SAVE_FORMAT:
            raise ValueError(f"save format {d.get('format')!r} is not {self.SAVE_FORMAT}: re-record it with this version")
        self.world, self.log, self._seq, self._score, self._events_seen, self.seed = d["world"], d["log"], d["seq"], d["score"], d["seen"], d["seed"]
        if self.world.state_hash() != d["hash"]:
            raise ValueError("the loaded world does not match the hash recorded in the save")

    def replay(self, log: list[dict[str, Any]] | None = None) -> str:
        """Re-run a recorded episode from its seed and return the final state hash."""
        log = self.log if log is None else log
        twin = HybridEnv(self.seed, self.map_size, self.agent_factions, self.step_ms, self.max_game_ms, self.weights, self.aggressive, self.use_terrain, self.profile, self.era_max_ms, self.era_vp)
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
        v += [float(len(obs.get("command_centers", []))), float(len(obs.get("mcvs", []))), float(obs.get("known_enemy_buildings", 0)), float(obs.get("stuck_entities", 0))]
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
