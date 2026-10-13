"""Logic blocks: processors that run a small mlog program, memory cells, displays, switches and message blocks (owner programme 13 Oct 2026).

A processor executes `instructionsPerTick` instructions per game tick (6 ticks per quantum, at most 200 per quantum) of the program text in `m["code"]`
(Mindustry's mlog, one instruction per line). Supported: set, op, jump, end, wait, stop, read, write, print, printflush, sensor, control, getlink,
draw, drawflush. A processor links every logic, memory, display, message, switch or turret block of its faction inside its range; links are named
by the block id with an ascending number (`cell1`, `display1`, `switch1`, `message1`, `duo1`...) exactly as in the game. Programs are set by
`configure(code=...)`; execution is deterministic (no wall clock, no randomness except `rand` seeded by building id and step count).
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts.industry import registry as R

MAX_PER_QUANTUM = 200
OPS = {
    "add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b, "div": lambda a, b: a / b if b else 0.0, "idiv": lambda a, b: float(math.floor(a / b)) if b else 0.0,
    "mod": lambda a, b: a % b if b else 0.0, "pow": lambda a, b: a ** b, "equal": lambda a, b: float(abs(a - b) < 1e-6), "notEqual": lambda a, b: float(abs(a - b) >= 1e-6),
    "lessThan": lambda a, b: float(a < b), "lessThanEq": lambda a, b: float(a <= b), "greaterThan": lambda a, b: float(a > b), "greaterThanEq": lambda a, b: float(a >= b),
    "strictEqual": lambda a, b: float(a == b), "land": lambda a, b: float(bool(a) and bool(b)), "max": max, "min": min,
    "and": lambda a, b: float(int(a) & int(b)), "or": lambda a, b: float(int(a) | int(b)), "xor": lambda a, b: float(int(a) ^ int(b)),
    "shl": lambda a, b: float(int(a) << int(b)), "shr": lambda a, b: float(int(a) >> int(b)),
}
OPS1 = {"abs": abs, "floor": math.floor, "ceil": math.ceil, "sqrt": lambda a: math.sqrt(a) if a >= 0 else 0.0, "not": lambda a: float(~int(a)), "log": lambda a: math.log(a) if a > 0 else 0.0,
        "sin": lambda a: math.sin(math.radians(a)), "cos": lambda a: math.cos(math.radians(a)), "tan": lambda a: math.tan(math.radians(a))}


def init_logic(world: Any, b: dict, m: dict, spec: dict) -> None:
    f = spec["fields"]
    cls = spec["class"]
    m.update(code=[], pc=0, vars={}, links={}, text="", enabled=True, wait=0, steps=0, ipt=int(f.get("instructionsPerTick", 2)),
             cells=[0.0] * int(f.get("memoryCapacity", 64)), display=[], buffer=[], printbuf="", linked_at=-1, error="")
    if cls == "MemoryBlock":
        m["cells"] = [0.0] * int(f.get("memoryCapacity", 64))
    code = b.pop("mdy_code", None)
    if code:
        set_code(m, code)


def set_code(m: dict, code: str) -> None:
    m["code"] = [ln.strip() for ln in code.replace(";", "\n").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    m["pc"], m["vars"], m["wait"], m["error"] = 0, {}, 0, ""


def relink(world: Any, b: dict, m: dict, spec: dict) -> None:
    rng = float(spec["fields"].get("range", 176)) / 8.0
    counters: dict[str, int] = {}
    links: dict[str, str] = {}
    for o in sorted(world.buildings.values(), key=lambda x: x["id"]):
        if o["id"] == b["id"] or o["faction_name"] != b["faction_name"] or o.get("mdy") is None or o.get("constructing") or int(o.get("hp", 1)) <= 0:
            continue
        osp = R.block(o["kind"])
        if osp["role"] not in ("logic", "turret", "store", "core", "mender", "overdrive", "shield", "door", "wall", "bridge", "unloader", "crafter", "generator", "battery", "drill", "pump"):
            continue
        if math.hypot(o["tx"] - b["tx"], o["ty"] - b["ty"]) > rng:
            continue
        name = osp["id"].split("-")[1] if "-" in osp["id"] else osp["id"]  # LogicBuilder: "memory-cell" is linked as cell1
        counters[name] = counters.get(name, 0) + 1
        links[f"{name}{counters[name]}"] = o["id"]
    m["links"] = links


def _val(world: Any, m: dict, tok: str):
    if tok in m["vars"]:
        return m["vars"][tok]
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1]
    if tok in ("true", "false"):
        return 1.0 if tok == "true" else 0.0
    if tok == "null":
        return 0.0
    if tok.startswith("@"):
        return {"@time": float(world.dmb.clock.get("game_ms", 0)), "@tick": float(world.economy_quanta * 6), "@counter": float(m["pc"]), "@links": float(len(m["links"]))}.get(tok, tok)
    try:
        return float(tok)
    except ValueError:
        return tok


def _num(v) -> float:
    return v if isinstance(v, (int, float)) else 0.0


def step(world: Any, st: Any, b: dict, m: dict, spec: dict, satisfaction: float) -> None:
    cls = spec["class"]
    if cls != "LogicBlock":
        m["state"] = "idle"
        return
    if spec["power_use_per_s"] > 0 and satisfaction <= 0:
        m["state"] = "no power"
        return
    if not m["code"]:
        m["state"] = "no program"
        return
    if m["linked_at"] < 0 or world.economy_quanta - m["linked_at"] > 100:
        relink(world, b, m, spec)
        m["linked_at"] = world.economy_quanta
    m["state"] = "running"
    budget = min(MAX_PER_QUANTUM, m["ipt"] * 6)
    if m["wait"] > 0:
        m["wait"] = max(0, m["wait"] - 100)
        if m["wait"] > 0:
            return
    for _ in range(budget):
        if m["pc"] >= len(m["code"]):
            m["pc"] = 0
            return  # the program wrapped: the rest of the update is skipped (LogicBuilder.updateTile)
        line = m["code"][m["pc"]]
        m["pc"] += 1
        m["steps"] += 1
        if not _exec(world, b, m, line):
            return


def _exec(world: Any, b: dict, m: dict, line: str) -> bool:
    """One instruction. False ends this quantum's run (end, wait, stop, error)."""
    parts = line.split()
    op = parts[0]
    a = parts[1:]
    try:
        if op == "set":
            m["vars"][a[0]] = _val(world, m, a[1])
        elif op == "op":
            fn, dst = a[0], a[1]
            x = _num(_val(world, m, a[2]))
            if fn in OPS1:
                m["vars"][dst] = float(OPS1[fn](x))
            elif fn == "rand":
                import random

                m["vars"][dst] = random.Random(f"{b['id']}:{m['steps']}").random() * x
            else:
                m["vars"][dst] = float(OPS[fn](x, _num(_val(world, m, a[3]))))
        elif op == "jump":
            dest, cond = int(a[0]), a[1]
            if cond == "always":
                m["pc"] = dest
            else:
                x, y = _num(_val(world, m, a[2])), _num(_val(world, m, a[3]))
                tbl = {"equal": x == y, "notEqual": x != y, "lessThan": x < y, "lessThanEq": x <= y, "greaterThan": x > y, "greaterThanEq": x >= y, "strictEqual": x == y}
                if tbl.get(cond):
                    m["pc"] = dest
        elif op == "end":
            m["pc"] = 0
            return False
        elif op in ("stop",):
            m["pc"] -= 1
            return False
        elif op == "wait":
            m["wait"] = int(_num(_val(world, m, a[0])) * 1000)
            return False
        elif op == "read":
            cell = world.buildings.get(m["links"].get(a[1], ""))
            idx = int(_num(_val(world, m, a[2])))
            cells = cell["mdy"]["cells"] if cell and cell.get("mdy") and "cells" in cell["mdy"] else []
            m["vars"][a[0]] = cells[idx] if 0 <= idx < len(cells) else 0.0
        elif op == "write":
            cell = world.buildings.get(m["links"].get(a[1], ""))
            idx = int(_num(_val(world, m, a[2])))
            if cell and cell.get("mdy") and "cells" in cell["mdy"] and 0 <= idx < len(cell["mdy"]["cells"]):
                cell["mdy"]["cells"][idx] = _num(_val(world, m, a[0]))
        elif op == "print":
            v = _val(world, m, " ".join(a))
            m["printbuf"] += (str(int(v)) if isinstance(v, float) and v == int(v) else str(v)).replace("\\n", "\n")
        elif op == "printflush":
            target = world.buildings.get(m["links"].get(a[0], ""))
            if target and target.get("mdy") is not None:
                target["mdy"]["text"] = m["printbuf"][:400]
            m["printbuf"] = ""
        elif op == "draw":
            m["buffer"].append(a)
            m["buffer"] = m["buffer"][-256:]
        elif op == "drawflush":
            target = world.buildings.get(m["links"].get(a[0], ""))
            if target and target.get("mdy") is not None and "display" in target["mdy"]:
                target["mdy"]["display"] = list(m["buffer"])
            m["buffer"] = []
        elif op == "getlink":
            idx = int(_num(_val(world, m, a[1])))
            names = sorted(m["links"])
            m["vars"][a[0]] = names[idx] if 0 <= idx < len(names) else 0.0
        elif op == "sensor":
            tgt = world.buildings.get(m["links"].get(a[1], ""))
            m["vars"][a[0]] = sense(world, tgt, a[2]) if tgt else 0.0
        elif op == "control":
            what, name = a[0], a[1]
            tgt = world.buildings.get(m["links"].get(name, ""))
            if tgt and tgt.get("mdy") is not None:
                val = _val(world, m, a[2]) if len(a) > 2 else 0.0
                if what == "enabled":
                    tgt["mdy"]["enabled"] = bool(_num(val))
                    tgt["unpowered"] = not bool(_num(val))
                elif what == "config":
                    tgt["mdy"]["config"] = val
                    if "item" in tgt["mdy"] or tgt["mdy"]["role"] in ("sorter", "unloader"):
                        tgt["mdy"]["item"] = str(val)
                elif what == "shoot":
                    tgt["mdy"]["force_shoot"] = bool(_num(val))
    except (IndexError, KeyError, ValueError, ZeroDivisionError, OverflowError) as exc:
        m["error"] = f"{type(exc).__name__} in '{line}'"
        m["state"] = "error"
        return False
    return True


def sense(world: Any, tgt: dict, prop: str) -> float:
    m = tgt.get("mdy") or {}
    p = prop.lstrip("@")
    if p == "health":
        return float(tgt.get("hp", 0))
    if p == "maxHealth":
        return float(tgt.get("max_hp", 0))
    if p == "x":
        return float(tgt["tx"])
    if p == "y":
        return float(tgt["ty"])
    if p == "enabled":
        return 1.0 if m.get("enabled", True) and not tgt.get("unpowered") else 0.0
    if p == "totalItems":
        return float(sum(world.stocks.get(tgt["id"], {}).values()) + sum(m.get("buf", {}).values()))
    if p == "ammo" or p == "totalAmmo":
        return float(sum(n for _w, n in m.get("ammo", [])))
    if p == "shooting":
        return 1.0 if m.get("state") == "shooting" else 0.0
    if p in ("powerNetStored", "powerNetIn", "powerNetOut"):
        from wizard_rts.industry import sim as S

        st = S.ind(world)
        g = st.power.get(st.graph_of.get(tgt["id"], -1), {})
        return float({"powerNetIn": g.get("supply", 0), "powerNetOut": g.get("demand", 0), "powerNetStored": g.get("stored", 0)}[p])
    ware = "coal" if p == "coal" else "mdy." + p.replace("-", "_")
    return float(world.stocks.get(tgt["id"], {}).get(ware, 0) + m.get("buf", {}).get(ware, 0))
