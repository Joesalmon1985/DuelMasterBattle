"""Generic immovables (fields, bushes, other trees) run from the imported Lua programmes.

An object is a dict in world.trees with "imm" set to the Widelands immovable
name. Its `main` programme is a list of animate / remove / transform / grow /
seed actions; `harvest` and `fall` style programmes run on demand
(callobject). The beech and wheat objects in workers.py keep their hand-written
tables; everything else lives here.
"""

from __future__ import annotations

import re
from typing import Any

from wizard_rts import wl_defs

LONG_MS = 10**9


def spec(name: str) -> dict[str, Any] | None:
    return wl_defs.defs()["immovables"].get(name)


def attributes(obj: dict) -> list[str]:
    s = spec(obj["imm"])
    return s["attributes"] if s else []


def candidates(attrib: str) -> list[str]:
    return sorted(n for n, i in wl_defs.defs()["immovables"].items() if attrib in i["attributes"])


def _chance(a: dict) -> float:
    m = re.search(r"chance:([\d.]+)%", a.get("raw", ""))
    return float(m.group(1)) if m else 100.0


def make(world: Any, tile: tuple[int, int], name: str) -> str:
    from wizard_rts.workers import new_id

    oid = new_id(world, "tree")
    world.trees[oid] = {
        "id": oid, "kind": "tree", "definition": f"widelands.imm.{name}", "species": name.split("_")[0], "imm": name,
        "stage": "", "tx": tile[0], "ty": tile[1], "timer_ms": 0, "pc": 0, "reserved_by": "",
    }
    world.tree_tiles[tile] = oid
    _advance(world, world.trees[oid], "main")
    return oid


def _remove(world: Any, obj: dict, reason: str) -> None:
    from wizard_rts.workers import remove_tree

    remove_tree(world, obj["id"], reason)


def _advance(world: Any, obj: dict, program: str) -> None:
    """Run actions until one waits (animate) or the programme ends."""
    s = spec(obj["imm"])
    actions = (s or {}).get("programs", {}).get(program, [])
    while obj["pc"] < len(actions):
        a = actions[obj["pc"]]
        obj["pc"] += 1
        cmd = a["cmd"]
        if cmd == "animate":
            obj["timer_ms"] = int(a.get("ms", 1000))
            return
        if cmd == "remove":
            if world.rng.random() * 100 < _chance(a):
                _remove(world, obj, "removed")
                return
        elif cmd in ("transform", "grow"):
            target = a.get("args", "").split()[0] if a.get("args") else ""
            if target and world.rng.random() * 100 < _chance(a) and spec(target):
                obj["imm"], obj["definition"], obj["pc"] = target, f"widelands.imm.{target}", 0
                obj["species"] = target.split("_")[0]
                s = spec(target)
                actions = s["programs"].get("main", [])
                program = "main"
                continue
        elif cmd == "seed":
            pass
    obj["timer_ms"] = LONG_MS  # nothing left to do


def tick(world: Any, obj: dict, step: int = 100) -> None:
    obj["timer_ms"] -= step
    if obj["timer_ms"] <= 0 and not obj["reserved_by"]:
        _advance(world, obj, "main")


def call(world: Any, obj: dict, program: str) -> None:
    """callobject=<program>: run the object's named programme now."""
    obj["pc"] = 0
    s = spec(obj["imm"])
    actions = (s or {}).get("programs", {}).get(program, [])
    for a in actions:
        if a["cmd"] == "remove":
            _remove(world, obj, program)
            return
        if a["cmd"] in ("transform", "grow") and a.get("args"):
            target = a["args"].split()[0]
            if spec(target):
                obj["imm"], obj["definition"], obj["pc"] = target, f"widelands.imm.{target}", 0
                obj["species"] = target.split("_")[0]
                obj["reserved_by"] = ""
                _advance(world, obj, "main")
                return
