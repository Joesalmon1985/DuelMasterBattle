"""One-on-one (or n-on-n) engagements of two unit definitions in the shared combat model, for balance checks and tests.

`fight("mindustry.dagger", "openra.e1")` puts the two groups on open ground far from every building and lets them fight under the ordinary
military quantum (AI off). Returns who won, the winner's remaining health fraction and the game seconds it took."""
from __future__ import annotations

import math
from typing import Any

from wizard_rts import rules
from wizard_rts.world import HybridWorld


def _open_field(world: Any, w: int = 24, h: int = 6) -> tuple[int, int]:
    t = world.terrain
    far = [(b["tx"], b["ty"]) for b in world.buildings.values()]
    best = None
    for y in range(8, t.h - 8, 3):
        for x in range(8, t.w - 8 - w, 3):
            if any(math.hypot(x - bx, y - by) < 22 for bx, by in far):
                continue
            if all(t.ground(x + a, y + b) and (x + a, y + b) not in world.tree_tiles for a in range(0, w, 2) for b in range(h)):
                return x, y
    return best or (40, 40)


def _loco_ok(world: Any, definition: str, x: int, y: int) -> bool:
    r = rules.actor(definition)
    return world.tile_speed(r.get("locomotor"), x, y) > 0


def fight(a: str, b: str, na: int = 1, nb: int = 1, seconds: int = 180, distance: int = 8, seed: int = 507) -> dict[str, Any]:
    w = HybridWorld(seed, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    x, y = _open_field(w)
    ids: dict[str, list[str]] = {"A": [], "B": []}
    for side, (definition, n, fx, faction) in {"A": (a, na, x + 2, "Red"), "B": (b, nb, x + 2 + distance, "Blue")}.items():
        r = rules.actor(definition)
        for k in range(n):
            tile = (fx, y + 1 + k * 2 % 5 + (k // 3))
            uid = w._unit(w.faction_info[faction]["id"], faction, definition.split(".")[-1], r["name"], definition, tile)
            ids[side].append(uid)
    for side in ids:
        for uid in ids[side]:
            u = w.units[uid]
            u["order"] = {"kind": "attack_move", "tile": [x + 2 + (distance if side == "A" else 0), u["ty"]]}
    base = int(w.dmb.clock.get("clock_sequence", 0))
    t = 0
    for i in range(seconds * 10):
        w.advance(100, base + i + 1, snapshot=False)
        t += 1
        alive = {s: [u for u in (w.units.get(i_) for i_ in ids[s]) if u and u.get("alive", True)] for s in ids}
        if not alive["A"] or not alive["B"]:
            break
    alive = {s: [w.units[i_] for i_ in ids[s] if w.units[i_].get("alive", True)] for s in ids}
    hp = {s: sum(int(u["hp"]) for u in alive[s]) / max(1, sum(int(w.units[i_]["max_hp"]) for i_ in ids[s])) for s in ids}
    winner = "A" if alive["A"] and not alive["B"] else ("B" if alive["B"] and not alive["A"] else ("draw" if not alive["A"] else ("A" if hp["A"] > hp["B"] else "B")))
    return {"winner": winner, "hp_a": round(hp["A"], 3), "hp_b": round(hp["B"], 3), "seconds": t / 10.0, "a": a, "b": b, "na": na, "nb": nb}
