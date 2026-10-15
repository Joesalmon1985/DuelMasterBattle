"""A stand-in controller that issues random legal commands (execution plan T1.5, until the real controller exists in M3).

It is deliberately dumb: its job is to exercise the episode runner, the action surface and the validation with a seat that is not the heuristic
AI. All randomness comes from a numpy Generator seeded from (seed, faction), so two runs with the same seed issue the same commands.
"""
from __future__ import annotations

import zlib
from typing import Any

import numpy as np


class RandomController:
    kind = "random"

    def __init__(self, faction: str, cfg: Any, seed: int = 0, env: Any = None) -> None:
        self.env, self.faction, self.cfg, self.seed = env, faction, cfg, int(seed)
        self.rng = np.random.default_rng(np.random.SeedSequence([self.seed, zlib.crc32(faction.encode())]))
        self.last_tick = -10 ** 9
        self.decisions_logged = 0

    def attach(self, env: Any) -> None:
        """Called by the episode runner once the environment exists."""
        self.env = env

    def spawn_for(self, faction: str) -> "RandomController":
        """The controller of a split successor: the same kind of player, its own random stream."""
        return RandomController(faction, self.cfg, int(self.rng.integers(0, 2 ** 31 - 1)), self.env)

    def _due(self, game_s: int) -> bool:
        gap = self.cfg.boot_decision_s if game_s < self.cfg.boot_minutes * 60 else self.cfg.decision_s
        return game_s - self.last_tick >= gap

    def _pick(self, items: list) -> Any:
        return items[int(self.rng.integers(0, len(items)))]

    def on_step(self, game_s: int, events: list[dict]) -> list[dict]:
        if not self._due(game_s):
            return []
        self.last_tick = game_s
        acts = self.env.legal_actions(self.faction)
        w = self.env.world
        cmds: list[dict[str, Any]] = []
        if acts.get("draft"):
            cmds.append({"op": "draft", "card": self._pick(acts["draft"])})
        kinds = ["build", "queue", "road", "move", "attack", "deploy", "propose", "respond", "demolish"]
        usable = [k for k in kinds if (acts.get(k) if k != "build" else [o for o in acts.get("build", []) if o.get("sites")]) and (k != "demolish" or self.rng.random() < 0.1)]
        for _ in range(int(self.rng.integers(1, 4))):
            if not usable:
                break
            kind = self._pick(usable)
            if kind == "build":
                opt = self._pick([o for o in acts["build"] if o.get("sites")])
                tx, ty = self._pick(opt["sites"])
                cmds.append({"op": "build", "kind": opt["kind"], "tx": tx, "ty": ty})
            elif kind == "queue":
                cmds.append({"op": "queue", **self._pick(acts["queue"])})
            elif kind == "road":
                cmds.append({"op": "road", **self._pick(acts["road"])})
            elif kind == "move":
                u = w.units[self._pick(acts["move_units"])["id"]]
                dx, dy = (int(v) for v in self.rng.integers(-12, 13, size=2))
                cmds.append({"op": "move", "units": [u["id"]], "tx": int(u["tx"]) + dx, "ty": int(u["ty"]) + dy, "attack_move": bool(self.rng.random() < 0.5)})
            elif kind == "attack":
                armed = [m["id"] for m in acts["move_units"] if w.units[m["id"]].get("weapon")]
                if armed:
                    cmds.append({"op": "order", "unit": self._pick(armed), "target": self._pick(acts["attack"])})
            elif kind == "deploy":
                ok = [d["unit"] for d in acts["deploy"] if d["ok"]]
                if ok:
                    cmds.append({"op": "deploy", "unit": self._pick(ok)})
            elif kind == "propose":
                p = self._pick(acts["propose"])
                cmds.append({"op": "propose", "to": p["to"], "state": self._pick(p["states"])})
            elif kind == "respond":
                o = self._pick(acts["respond"])
                cmds.append({"op": "respond", "offer": o["offer"], "accept": bool(self.rng.random() < 0.5)})
            elif kind == "demolish":
                cmds.append({"op": "demolish", "building": self._pick(acts["demolish"])})
        self.decisions_logged += 1
        return cmds
