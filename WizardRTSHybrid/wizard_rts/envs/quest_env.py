"""Quest / social environment on a real settlement (roadmap M3; owner section D.2).

The wizard stands in a prepared HybridWorld whose dry coal mine has already opened a quest for a real person. He only knows what he has
seen and been told: the visible people and places (with their quest markers), the dialogue lines and choices he has opened, his inventory,
and what he has asked. Actions are the wizard's own: go to someone, talk, choose a dialogue option, wait, enter the gallery. The
episode ends when the story leaves this environment's scope (he enters the gallery with the sigil), the quest closes, or time runs out.

Scenario knobs change the world under him: `world_fix_first`, `mine_destroyed`, `npc_dead`, `reload` (a save and load in the middle).
"""

from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from wizard_rts import story, story_agent as A
from wizard_rts.envs import Env
from wizard_rts.envs._world_cache import attention_advance, prepared

CHOICES = ["ask_cause", "ask_gallery", "accept_help", "persuade", "give_up", "accept_treat"]
VERBS = ["wait", "go_npc0", "go_npc1", "go_entrance", "talk", "leave_dialogue", "enter_gallery"] + ["choose_" + c for c in CHOICES]
N = len(VERBS)
V = {v: i for i, v in enumerate(VERBS)}
WALK = 1.4  # tiles per second


class QuestEnv(Env):
    name = "quest"
    max_steps = 60

    def __init__(self, economy: bool = False, horizon_min: int = 20) -> None:
        super().__init__()
        self.economy, self.horizon_ms = economy, horizon_min * 60_000
        self.w: Any = None
        self.ids: dict[str, Any] = {}
        self.dialog: dict[str, Any] | None = None
        self.learned: set[str] = set()
        self.scenario = "base"

    # ---- lifecycle
    def _reset(self, **scenario: Any) -> None:
        self.scenario = str(scenario.get("kind", "base"))
        self.w, self.ids = prepared(self.seed % 6, "story")  # six distinct maps/mines; the rest of the seed varies the task parameters
        self.w._env_t0 = int(self.w.dmb.clock["game_ms"])
        self.dialog = None
        self.learned = set()
        self.at: str | None = None  # "npc0" / "entrance"
        self._injected = False
        self._inject_at = int(scenario.get("at_step", 3))

    def _npcs(self) -> list[str]:
        return sorted(story.state(self.w)["npcs"])

    def _q(self) -> tuple[str, dict] | None:
        qs = story.state(self.w)["quests"]
        return next(iter(sorted(qs.items())), None)

    # ---- legality
    def legal_mask(self) -> np.ndarray:
        m = np.zeros(N)
        m[V["wait"]] = 1
        npcs = self._npcs()
        for i in range(min(2, len(npcs))):
            m[V["go_npc%d" % i]] = 1
        if story.state(self.w)["dungeons"]:
            m[V["go_entrance"]] = 1
        m[V["talk"]] = 1.0 if self._near_npc() else 0.0
        m[V["leave_dialogue"]] = 1.0 if self.dialog else 0.0
        m[V["enter_gallery"]] = 1.0 if self.at == "entrance" else 0.0
        if self.dialog:
            for c in self.dialog.get("choices", []):
                if c["available"] and ("choose_" + c["id"]) in V:
                    m[V["choose_" + c["id"]]] = 1
        return m

    def _near_npc(self) -> bool:
        return bool(self.at and self.at.startswith("npc"))

    def is_legal(self, action: Any) -> bool:
        a = int(action)
        return 0 <= a < N and bool(self.legal_mask()[a]) and not self.done

    def legal_actions(self) -> list[Any]:
        return [i for i, m in enumerate(self.legal_mask()) if m > 0]

    # ---- dynamics
    def _time(self) -> int:
        return int(self.w.dmb.clock["game_ms"]) - self.w._env_t0

    def _walk_to(self, tile: list[int]) -> None:
        p = self.w.player
        dist = abs(p["tx"] - tile[0]) + abs(p["ty"] - tile[1])
        attention_advance(self.w, dist / WALK, self.economy)
        A.place_wizard_near(self.w, tile)

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        v = VERBS[int(action)]
        w = self.w
        r = -0.01
        info: dict[str, Any] = {"verb": v}
        if self.scenario != "base" and not self._injected and self.t + 1 >= self._inject_at:
            self._apply_scenario()
        if v == "wait":
            attention_advance(w, 30, self.economy)
        elif v.startswith("go_npc"):
            npcs = self._npcs()
            i = int(v[-1])
            if i < len(npcs):
                self._walk_to(story.state(w)["npcs"][npcs[i]]["tile"])
                self.at = "npc%d" % i
                self.dialog = None
        elif v == "go_entrance":
            d = next(iter(story.state(w)["dungeons"].values()))
            self._walk_to(d["entrance"]["tile"])
            self.at, self.dialog = "entrance", None
        elif v == "talk":
            npc = self._npcs()[int(self.at[-1])]
            res = A.op(w, "talk", npc=npc)
            self.dialog = res if res["status"] == "ok" else None
            attention_advance(w, 2, self.economy)
        elif v == "leave_dialogue":
            self.dialog = None
        elif v == "enter_gallery":
            did = next(iter(story.state(w)["dungeons"]))
            res = A.op(w, "enter", dungeon=did)
            if res["status"] == "ok":
                qs = self._q()
                if qs and qs[1]["sigil_given"]:
                    self.done, self.reason = True, "reached_dungeon_with_the_sigil"
                    r += 1.0
                else:
                    self.done, self.reason = True, "entered_without_the_sigil"
                    r -= 0.2
        else:
            c = v[len("choose_"):]
            npc = self._npcs()[int(self.at[-1])]
            res = A.op(w, "choose", npc=npc, choice=c)
            self.dialog = {"status": "ok", "lines": res.get("lines", []), "choices": res.get("choices", []), "quest_status": ""}
            if res.get("status") == "ok":
                self.learned.add(c)
                if c == "give_up":
                    r -= 0.5
                if c == "persuade" and res.get("check", {}).get("passed"):
                    r += 0.2
                if c in ("ask_cause", "ask_gallery"):
                    r += 0.05
                if c == "accept_help":
                    r += 0.2
            attention_advance(w, 2, self.economy)
        qs = self._q()
        if qs and not self.done:
            status = w.dmb.quests[qs[0]]["status"]
            if status in ("completed", "resolved_by_world", "failed_with_consequence", "suspended"):
                self.done, self.reason = True, status
                r += {"completed": 1.0, "resolved_by_world": 0.0, "failed_with_consequence": -0.3, "suspended": -0.1}[status]
        if not self.done and self._time() >= self.horizon_ms:
            self.done, self.reason = True, "timeout"
            r -= 0.1
        return r, info

    def _apply_scenario(self) -> None:
        """Change the world under the wizard, once, through the same paths the game uses."""
        w, k = self.w, self.scenario
        self._injected = True
        qs = self._q()
        if qs is None:
            return
        q = qs[1]
        mine = w.buildings.get(q["mine"])
        if k == "world_fix_first" and mine is not None:
            from wizard_rts.economy import produce

            for (x, y, a, i) in w.terrain.cells(mine["tx"], mine["ty"], 2, q["resource"])[:6]:
                w.terrain.add(x, y, q["resource"], 20)
            mine.pop("deposit_exhausted", None)
        elif k == "mine_destroyed" and mine is not None:
            w.damage_building(mine["id"], 10 ** 9, ["structure"], {})
        elif k == "npc_dead":
            from sim.dmb.people.registry import PeopleService

            PeopleService(w.dmb).record_death(q["npc"])
            from sim.dmb.quests.runtime import QuestService

            QuestService(w.dmb).evaluate(qs[0], world_signals={"stakeholder_dead": True})
        elif k == "reload":
            blob = pickle.dumps(w)
            self.w = pickle.loads(blob)
        attention_advance(self.w, 2, self.economy)

    # ---- observation: only what the wizard could know
    def observe(self) -> dict[str, Any]:
        w = self.w
        s = story.state(w)
        p = w.player
        seen = []
        for e in story.entity_rows(w):
            dist = abs(p["tx"] - e["tx"]) + abs(p["ty"] - e["ty"])
            if dist <= 30:
                seen.append({"id": e["id"], "kind": e["kind"], "role": e.get("role", ""), "distance": dist, "marker": bool(e.get("has_quest", False))})
        d = self.dialog
        return {"seen": seen, "at": self.at, "dialogue": None if d is None else {"lines": list(d.get("lines", [])), "choices": [{"id": c["id"], "available": c["available"]} for c in d.get("choices", [])]},
                "inventory": list(s["inventory"]), "learned": sorted(self.learned), "minutes": self._time() // 60_000, "steps": self.t}

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        obs = obs or self.observe()
        f = [1.0 if any(e["kind"] == "npc" and e["marker"] for e in obs["seen"]) else 0.0,
             1.0 if any(e["kind"] == "dungeon_entrance" for e in obs["seen"]) else 0.0,
             1.0 if obs["at"] and obs["at"].startswith("npc") else 0.0, 1.0 if obs["at"] == "entrance" else 0.0,
             1.0 if obs["dialogue"] else 0.0, len(obs["inventory"]) / 8.0, obs["minutes"] / 20.0, obs["steps"] / 60.0]
        f += [1.0 if c in obs["learned"] else 0.0 for c in CHOICES]
        avail = {c["id"]: c["available"] for c in (obs["dialogue"] or {}).get("choices", [])}
        f += [1.0 if avail.get(c, False) else 0.0 for c in CHOICES]
        f += [1.0 if any(i.startswith("sigil_") for i in obs["inventory"]) else 0.0]
        return np.array(f)

    def state(self) -> Any:
        qs = self._q()
        return {"seed": self.seed, "scenario": self.scenario, "t": self.t, "ms": self._time(), "at": self.at,
                "quest": None if qs is None else [qs[0], self.w.dmb.quests[qs[0]]["status"], qs[1]["stage"], sorted(qs[1]["learned"]), qs[1]["sigil_given"], qs[1]["persuaded"]],
                "inv": list(story.state(self.w)["inventory"]), "done": self.done, "reason": self.reason}

    def expert_action(self) -> int:
        """The scripted social player: find the marked person, learn what happened and where, take the sigil, persuade, go to the gallery."""
        o = self.observe()
        if o["dialogue"] is None:
            if self.at == "entrance":
                return V["enter_gallery"]
            if self.at is None:
                return V["go_npc0"]
            if "accept_help" in self.learned and any(i.startswith("sigil_") for i in o["inventory"]):
                return V["go_entrance"]
            return V["talk"]
        avail = {c["id"]: c["available"] for c in o["dialogue"]["choices"]}
        for c in ("ask_cause", "ask_gallery", "accept_help", "persuade"):
            if avail.get(c):
                return V["choose_" + c]
        return V["leave_dialogue"]
