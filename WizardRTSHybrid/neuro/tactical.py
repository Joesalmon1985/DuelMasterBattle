"""The tactical controller N11 (milestone M8; design 4.3 and 5.3).

Every `tactical_s` (5) game seconds, for each squad of armed units within 24 tiles of a visible enemy (or whose hit points fell since the last tactical tick), N11 chooses
one of four orders from its 74-number input: hold, attack-move to the nearest visible enemy, focus the nearest known enemy building or nest, retreat to the nearest own
centre. It reads the networks' outputs cached at the last strategic tick (own and enemy unit encodings, the military coordinator N10 and the war summary N6), so it never
re-evaluates the economy; only geometry and strengths are recomputed from the world (own units, and enemies through neuro/vision.py). Deterministic: argmax, ties to the
lower index. An order is repeated only when it changes or after REPEAT_S seconds.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import schema as S
from neuro import vision
from neuro.brain import pool_rows, zeros
from neuro.cand_base import Candidate
from neuro.obs_world import sq
from neuro.schema import compose

ENGAGE_TILES = 24
SQUAD_LINK = 6
REPEAT_S = 30
HOLD, ATTACK, FOCUS, RETREAT = range(4)
ORDER_NAMES = ("hold", "attack", "focus", "retreat")
MAX_ORDERS = 3


class Tactical:
    def __init__(self, ctl: Any) -> None:
        self.ctl = ctl
        self.cache: dict[str, Any] = {}
        self.hp: dict[str, int] = {}
        self.last: dict[str, tuple[int, int]] = {}  # lead unit id -> (order, game second)
        self.orders_issued = [0, 0, 0, 0]

    def remember(self, obs: Any, enc: dict) -> None:
        """Called after every strategic tick: the encodings N11 reads."""
        self.cache = {"u_row": {uid: i for i, uid in enumerate(obs.u_ids)}, "n3": enc["n3"], "e_row": {uid: i for i, uid in enumerate(obs.e_ids)}, "n3e": enc["n3e"],
                      "n10": enc["n10"], "n6": enc["n6"]}

    # ------------------------------------------------------------------------------------------------------------------------ squads
    @staticmethod
    def _cluster(units: list[dict]) -> list[list[dict]]:
        left = sorted(units, key=lambda u: u["id"])
        out = []
        while left:
            group, frontier = [left.pop(0)], []
            frontier.append(group[0])
            while frontier:
                a = frontier.pop()
                near = [u for u in left if max(abs(u["tx"] - a["tx"]), abs(u["ty"] - a["ty"])) <= SQUAD_LINK]
                for u in near:
                    left.remove(u)
                    group.append(u)
                    frontier.append(u)
            out.append(group)
        return out

    def tick(self, game_s: int) -> list[tuple[dict, str]]:
        """[(command, label)] for this tactical tick."""
        ctl = self.ctl
        if not self.cache:
            return []
        w, me = ctl.env.world, ctl.faction
        own = sorted((u for u in w.units.values() if u["faction_name"] == me and u.get("alive", True) and not u.get("inside") and u.get("weapon")), key=lambda u: u["id"])
        seen = vision.seen_enemies(w, me)
        enemies = [w.units[r["id"]] for r in sorted(seen["units"], key=lambda r: r["id"]) if r["id"] in w.units]
        ebuild = [r for r in sorted(seen["buildings"], key=lambda r: r["id"])]
        hit = {u["id"] for u in own if u["id"] in self.hp and int(u.get("hp", 0)) < self.hp[u["id"]]}
        self.hp = {u["id"]: int(u.get("hp", 0)) for u in own}
        if not own:
            return []
        epos = np.array([[e["tx"], e["ty"]] for e in enemies], dtype=np.float64).reshape(-1, 2)
        engaged = []
        for u in own:
            near = len(epos) and float(np.abs(epos - (u["tx"], u["ty"])).max(axis=1).min()) <= ENGAGE_TILES
            if near or u["id"] in hit:
                engaged.append(u)
        ccs = [(c["tx"], c["ty"], c["id"]) for c in sorted((b for b in w.buildings.values() if b["faction_name"] == me and b["kind"] == "warehouse" and int(b.get("hp", 0)) > 0), key=lambda b: b["id"])]
        cmds: list[tuple[dict, str]] = []
        n3, urow = self.cache["n3"], self.cache["u_row"]
        n3e, erow = self.cache["n3e"], self.cache["e_row"]
        for squad in self._cluster(engaged):
            lead = squad[0]["id"]
            cx = sum(u["tx"] for u in squad) / len(squad)
            cy = sum(u["ty"] for u in squad) / len(squad)
            near_e = [e for e in enemies if max(abs(e["tx"] - cx), abs(e["ty"] - cy)) <= ENGAGE_TILES]
            own_str = sum(ctl.observer.strength(u) for u in squad)
            en_str = sum(ctl.observer.strength(e) for e in near_e)
            rows = [urow[u["id"]] for u in squad if u["id"] in urow]
            mean, mx = pool_rows(n3, rows, 12)
            erows = [erow[e["id"]] for e in near_e if e["id"] in erow]
            emean, _emx = pool_rows(n3e, erows, 12)
            dc = min((max(abs(cx - x), abs(cy - y)) for x, y, _i in ccs), default=100.0)
            blocked = 0.0
            if ccs and near_e:
                x, y, _i = min(ccs, key=lambda c: max(abs(cx - c[0]), abs(cy - c[1])))
                blocked = float(any(max(abs(e["tx"] - x), abs(e["ty"] - y)) < max(abs(cx - x), abs(cy - y)) for e in near_e))
            x = compose("N11", squad_mean=mean, squad_max=mx, enemy_mean=emean, enemy_count=np.array([len(near_e) / 10.0], dtype=np.float32),
                        enemy_strength=np.array([sq(en_str)], dtype=np.float32), force_ratio=np.array([own_str / (own_str + en_str + 1.0)], dtype=np.float32),
                        dist_centre=np.array([min(dc, 100.0) / 100.0], dtype=np.float32), retreat_blocked=np.array([blocked], dtype=np.float32), n10=self.cache["n10"],
                        n6=self.cache["n6"], pad=zeros(1))
            order = int(np.argmax(ctl.nets.forward("N11", x[None])[0]))
            prev = self.last.get(lead)
            if prev is not None and prev[0] == order and game_s - prev[1] < REPEAT_S and order != HOLD:
                continue
            if prev is not None and prev[0] == order == HOLD:
                continue
            cmd = self._command(order, squad, (cx, cy), near_e, ebuild, ccs)
            if cmd is None:
                continue
            self.last[lead] = (order, game_s)
            self.orders_issued[order] += 1
            cmds.append((cmd, ORDER_NAMES[order]))
            if len(cmds) >= MAX_ORDERS:
                break
        return cmds

    @staticmethod
    def _command(order: int, squad: list[dict], c: tuple[float, float], enemies: list[dict], buildings: list[dict], ccs: list[tuple]) -> dict | None:
        ids = [u["id"] for u in squad]
        if order == HOLD:
            return {"op": "stop", "units": ids}
        if order == ATTACK and enemies:
            e = min(enemies, key=lambda e: (math.hypot(e["tx"] - c[0], e["ty"] - c[1]), e["id"]))
            return {"op": "move", "units": ids, "tx": int(e["tx"]), "ty": int(e["ty"]), "attack_move": True}
        if order == FOCUS and buildings:
            b = min(buildings, key=lambda r: (math.hypot(r["tile"][0] - c[0], r["tile"][1] - c[1]), r["id"]))
            return {"op": "order", "unit": ids[0], "target": b["id"]}
        if order == RETREAT and ccs:
            x, y, _i = min(ccs, key=lambda cc: (math.hypot(cc[0] - c[0], cc[1] - c[1]), cc[2]))
            return {"op": "move", "units": ids, "tx": int(x), "ty": int(y) + 3, "attack_move": False}
        return None


def as_candidate(cmd: dict, label: str) -> Candidate:
    return Candidate("N11", cmd, np.zeros(0, dtype=np.float32), ("N11", label, str(cmd.get("units", cmd.get("unit")))[:40]), {})
