"""Import Widelands tribe definitions (Lua) into wizard_rts/data/widelands_defs.json.

A small Lua table parser reads every `new_*_type { ... }` call under
data/tribes (buildings, workers, wares) and data/world/immovables (trees and
others). For each definition it keeps what the hybrid needs: buildcost, inputs,
working positions, programmes (parsed into commands with durations in ms),
spritesheet metadata, size. Programmes are then checked against the commands
the hybrid interpreter can execute; `executable` says whether the whole
definition could run on it, not that it does yet.

Source: Widelands 47c5cae8 (pinned in sources/manifest.json). GPL-2.0-or-later,
Widelands Development Team.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HYBRID = Path(__file__).resolve().parents[1]
DATA = HYBRID / "external" / "widelands" / "data"
OUT = HYBRID / "wizard_rts" / "data" / "widelands_defs.json"

# ------------------------------------------------------------------ Lua subset parser

TOKEN = re.compile(
    r"""
    (?P<ws>\s+)|
    (?P<comment>--\[\[.*?\]\]|--[^\n]*)|
    (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|
    (?P<number>-?\d+\.?\d*)|
    (?P<concat>\.\.)|
    (?P<name>[A-Za-z_][A-Za-z_0-9]*)|
    (?P<punct>[{}()\[\],=.:;+\-*/%#])
    """,
    re.X | re.S,
)


def tokenize(text: str) -> list[tuple[str, str]]:
    out = []
    pos = 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        if kind in ("ws", "comment"):
            continue
        out.append((kind, m.group()))
    return out


class Parser:
    def __init__(self, tokens: list[tuple[str, str]], pos: int = 0) -> None:
        self.t = tokens
        self.i = pos

    def peek(self) -> tuple[str, str]:
        return self.t[self.i] if self.i < len(self.t) else ("eof", "")

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, value: str) -> None:
        kind, v = self.take()
        if v != value:
            raise ValueError(f"expected {value!r}, got {v!r}")

    def value(self):
        left = self.simple()
        while self.peek()[1] == "..":
            self.take()
            right = self.simple()
            left = (str(left) if isinstance(left, (str, int, float)) else "?") + (str(right) if isinstance(right, (str, int, float)) else "?")
        while self.peek()[1] in ("+", "-", "*", "/") and self.peek()[0] == "punct":
            op = self.take()[1]
            right = self.simple()
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                left = {"+": left + right, "-": left - right, "*": left * right, "/": left / right if right else 0}[op]
        return left

    def simple(self):
        kind, v = self.peek()
        if v == "{":
            return self.table()
        if kind == "string":
            self.take()
            return bytes(v[1:-1], "utf-8").decode("unicode_escape", errors="ignore") if "\\" in v else v[1:-1]
        if kind == "number":
            self.take()
            return float(v) if "." in v else int(v)
        if v == "-" and self.t[self.i + 1][0] == "number":
            self.take()
            n = self.take()[1]
            return -(float(n) if "." in n else int(n))
        if v == "(":
            self.take()
            inner = self.value()
            self.expect(")")
            return inner
        if kind == "name":
            self.take()
            if v in ("true", "false", "nil"):
                return {"true": True, "false": False, "nil": None}[v]
            name = v
            while self.peek()[1] in (".", ":") and self.i + 1 < len(self.t) and self.t[self.i + 1][0] == "name":
                self.take()
                name += "." + self.take()[1]
            if self.peek()[1] == "(":
                self.take()
                args = []
                while self.peek()[1] != ")":
                    args.append(self.value())
                    if self.peek()[1] == ",":
                        self.take()
                self.expect(")")
                if name in ("_", "pgettext", "ngettext", "npgettext"):
                    strings = [a for a in args if isinstance(a, str)]
                    return strings[-1] if strings else ""
                if name == "path.dirname":
                    return "<dir>"
                return {"$call": name, "args": args}
            if self.peek()[0] == "string":  # f"str"
                return {"$call": name, "args": [self.value()]}
            return {"$var": name}
        raise ValueError(f"unexpected {kind} {v!r}")

    def table(self):
        self.expect("{")
        positional = []
        keyed: dict = {}
        while self.peek()[1] != "}":
            kind, v = self.peek()
            nxt = self.t[self.i + 1][1] if self.i + 1 < len(self.t) else ""
            if kind == "name" and nxt == "=":
                self.take()
                self.take()
                keyed[v] = self.value()
            elif v == "[":
                self.take()
                key = self.value()
                self.expect("]")
                self.expect("=")
                keyed[str(key)] = self.value()
            else:
                positional.append(self.value())
            if self.peek()[1] in (",", ";"):
                self.take()
        self.expect("}")
        if keyed and positional:
            keyed["$list"] = positional
            return keyed
        return keyed if keyed else positional


def register_attributes(directory: Path) -> dict[str, list[str]]:
    """register.lua is `return { immovable_name = { "attr", ... } }`."""
    path = directory / "register.lua"
    if not path.is_file():
        return {}
    tokens = tokenize(path.read_text(encoding="utf-8", errors="replace"))
    for i, (kind, v) in enumerate(tokens):
        if v == "return" and i + 1 < len(tokens) and tokens[i + 1][1] == "{":
            try:
                table = Parser(tokens, i + 1).table()
            except Exception:  # noqa: BLE001
                return {}
            return {k: [x for x in vals if isinstance(x, str)] for k, vals in table.items() if isinstance(vals, list)} if isinstance(table, dict) else {}
    return {}


NEW_TYPE = re.compile(r"new_(\w+?)_type\s*\{")


def extract(path: Path) -> list[tuple[str, dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens = tokenize(text)
    out = []
    for i, (kind, v) in enumerate(tokens):
        if kind == "name" and v.startswith("new_") and v.endswith("_type") and i + 1 < len(tokens) and tokens[i + 1][1] == "{":
            try:
                out.append((v[4:-5], Parser(tokens, i + 1).table()))
            except Exception:  # noqa: BLE001 - a definition we cannot parse is reported, not hidden
                out.append((v[4:-5], {"$parse_error": str(path)}))
    return out


# ------------------------------------------------------------------ programme actions

DUR = re.compile(r"(\d+)(ms|m|s)")


def duration_ms(text: str) -> int:
    total = 0
    for n, unit in DUR.findall(text):
        total += int(n) * {"m": 60_000, "s": 1_000, "ms": 1}[unit]
    return total


# Ware names in programmes that differ from the hybrid's: tribe prefix is dropped, "planks" is "plank".
def ware(name: str) -> str:
    name = name.strip()
    for prefix in ("barbarians_", "empire_", "atlanteans_", "frisians_", "amazons_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return {"planks": "plank"}.get(name, name)


def wares(text: str) -> dict[str, int]:
    """'log:2 plank' -> {'log': 2, 'plank': 1}; alternatives 'a,b' are returned under the '|' key."""
    out: dict[str, int] = {}
    for tok in text.split():
        if tok.startswith(("radius", "yield", "when_", "experience", "duration", "priority", "allow_")):
            continue
        name, _, n = tok.partition(":")
        if "," in name:
            out.setdefault("|", [])  # type: ignore[assignment]
            out["|"] = [ware(x) for x in name.split(",")]  # type: ignore[assignment]
        else:
            out[ware(name)] = int(n) if n.isdigit() else 1
    return out


def parse_action(line: str) -> dict:
    cmd, _, rest = line.partition("=")
    cmd, rest = cmd.strip(), rest.strip()
    a: dict = {"cmd": cmd, "raw": line}
    if cmd in ("sleep", "animate"):
        m = re.search(r"duration:(\S+)", rest)
        a["ms"] = duration_ms(m.group(1)) if m else 0
        if cmd == "animate":
            a["name"] = rest.split()[0] if rest else ""
    elif cmd in ("consume", "produce"):
        a["wares"] = wares(rest)
    elif cmd == "return":
        a["skipped"] = rest.startswith("skipped")
        m = re.search(r"unless economy needs (\S+)", rest)
        a["unless_needs"] = ware(m.group(1)) if m else ""
        a["other_condition"] = bool(rest) and not m and rest.strip() != "skipped"
    elif cmd in ("call", "callworker", "callobject"):
        a["target"] = rest.split()[0] if rest else ""
    elif cmd == "mine":
        a["resource"] = rest.split()[0].replace("resource_", "")
        for key in ("radius", "yield", "when_empty"):
            m = re.search(key + r":([\d.]+)", rest)
            a[key] = float(m.group(1)) if m else 0.0
    elif cmd in ("findobject", "findspace"):
        a["args"] = rest
        m = re.search(r"attrib:(\w+)", rest)
        a["attrib"] = m.group(1) if m else ""
        m = re.search(r"radius:(\d+)", rest)
        a["radius"] = int(m.group(1)) if m else 0
    elif cmd == "createware":
        a["ware"] = ware(rest.split()[0]) if rest else ""
    elif cmd == "plant":
        m = re.search(r"attrib:(\w+)", rest)
        a["attrib"] = m.group(1) if m else ""
    elif cmd == "walk":
        a["to"] = rest
    else:
        a["args"] = rest
    return a


def parse_program(entry) -> list[dict]:
    actions = entry.get("actions") if isinstance(entry, dict) else entry
    if isinstance(entry, dict) and "$list" in entry and not actions:
        actions = entry["$list"]
    return [parse_action(x) for x in (actions or []) if isinstance(x, str)]


BUILDING_COMMANDS = {"consume", "produce", "sleep", "animate", "callworker", "mine", "return", "call", "playsound"}
WORKER_COMMANDS = {"findobject", "findspace", "walk", "animate", "callobject", "createware", "plant", "removeobject", "return", "playsound", "sleep"}
OBJECT_ATTRIBS = {"tree", "rocks", "ripe_wheat", "eatable"}
SPACE_OK = {"", "tree_sapling", "seed_wheat"}


def executable_building(programs: dict[str, list[dict]]) -> tuple[bool, list[str]]:
    problems = []
    for name, actions in programs.items():
        for a in actions:
            if a["cmd"] not in BUILDING_COMMANDS:
                problems.append(f"{name}: {a['cmd']}")
            elif a["cmd"] == "return" and a.get("other_condition"):
                problems.append(f"{name}: return condition {a['raw']}")
            elif a["cmd"] == "call" and a["target"] not in programs:
                problems.append(f"{name}: call {a['target']}")
    return not problems, problems


def executable_worker(programs: dict[str, list[dict]]) -> tuple[bool, list[str]]:
    problems = []
    for name, actions in programs.items():
        for a in actions:
            if a["cmd"] not in WORKER_COMMANDS:
                problems.append(f"{name}: {a['cmd']}")
            elif a["cmd"] == "findobject" and a["attrib"] not in OBJECT_ATTRIBS and "eatable" not in a["args"]:
                problems.append(f"{name}: findobject {a['args']}")
            elif a["cmd"] == "plant" and a["attrib"] not in SPACE_OK:
                problems.append(f"{name}: plant {a['attrib']}")
            elif a["cmd"] == "findspace" and any(k in a["args"] for k in ("swim", "resource:", "terraform", "ferry", "breed")):
                problems.append(f"{name}: findspace {a['args']}")
    return not problems, problems


# ------------------------------------------------------------------ main

def sheets(entry: dict) -> dict:
    out = {}
    for name, sheet in (entry.get("spritesheets") or {}).items():
        if isinstance(sheet, dict):
            out[name] = {k: v for k, v in sheet.items() if k in ("fps", "frames", "rows", "columns", "hotspot", "directional", "basename")}
    return out


def inputs(entry: dict) -> dict[str, int]:
    out = {}
    for item in entry.get("inputs") or []:
        if isinstance(item, dict) and "name" in item:
            out[ware(item["name"])] = int(item.get("amount", 1))
    return out


def mark_runnable(defs: dict) -> None:
    """A building is runnable when its programmes, its workers' programmes and every ware it names are known."""
    B, W, WA = defs["buildings"], defs["workers"], defs["wares"]
    for name, b in B.items():
        if b["type"] != "productionsite":
            b["runnable"], b["blocked_by"] = False, f"{b['type']} not implemented"
            continue
        reason = ""
        if not b["executable"]:
            reason = "building_programs: " + "; ".join(b["problems"][:2])
        for wp in b["working_positions"]:
            if wp not in W:
                reason = reason or f"worker_missing: {wp}"
        for prog in b["programs"].values():
            for a in prog:
                if a["cmd"] == "callworker" and not reason:
                    ok = any(a["target"] in W[wp]["programs"] and W[wp]["executable"] for wp in b["working_positions"] if wp in W)
                    if not ok:
                        reason = f"worker_program: {a['target']}"
                if a["cmd"] in ("consume", "produce") and not reason:
                    for k, v in a["wares"].items():
                        for g in (v if k == "|" else [k]):
                            if g not in WA:
                                reason = f"unknown_ware: {g}"
        b["runnable"], b["blocked_by"] = not reason, reason


def main() -> None:
    defs: dict[str, dict] = {"buildings": {}, "workers": {}, "wares": {}, "immovables": {}, "errors": []}
    for path in sorted((DATA / "tribes").rglob("init.lua")):
        tribe = next((p for p in path.parts if p in ("barbarians", "empire", "atlanteans", "frisians", "amazons")), "")
        for kind, entry in extract(path):
            if "$parse_error" in entry:
                defs["errors"].append(entry["$parse_error"])
                continue
            name = str(entry.get("name", ""))
            if not name:
                continue
            rel = path.relative_to(DATA).as_posix()
            if kind in ("productionsite", "warehouse", "militarysite", "trainingsite"):
                progs = {k: parse_program(v) for k, v in (entry.get("programs") or {}).items() if isinstance(v, (dict, list))}
                ok, problems = executable_building(progs) if kind == "productionsite" else (False, [f"{kind} not implemented"])
                defs["buildings"][name] = {
                    "tribe": tribe, "type": kind, "source": rel, "size": entry.get("size", ""),
                    "descname": entry.get("descname", ""), "dir": path.parent.relative_to(DATA).as_posix(),
                    "animations": {k: {"hotspot": v.get("hotspot")} for k, v in (entry.get("animations") or {}).items() if isinstance(v, dict)},
                    "buildcost": {ware(k): int(v) for k, v in (entry.get("buildcost") or {}).items() if isinstance(v, (int, float))},
                    "inputs": inputs(entry), "working_positions": {k: v for k, v in (entry.get("working_positions") or {}).items()},
                    "programs": progs, "spritesheets": sheets(entry), "executable": ok, "problems": problems[:6],
                }
            elif kind in ("worker", "carrier", "soldier"):
                progs = {k: parse_program(v) for k, v in (entry.get("programs") or {}).items() if isinstance(v, (dict, list))}
                ok, problems = executable_worker(progs) if progs else (kind == "carrier", [])
                defs["workers"][name] = {
                    "tribe": tribe, "type": kind, "source": rel, "descname": entry.get("descname", ""),
                    "dir": path.parent.relative_to(DATA).as_posix(),
                    "animations": {k: {"hotspot": v.get("hotspot")} for k, v in (entry.get("animations") or {}).items() if isinstance(v, dict)},
                    "buildcost": {ware(k): int(v) for k, v in (entry.get("buildcost") or {}).items() if isinstance(v, (int, float))},
                    "programs": progs, "spritesheets": sheets(entry), "executable": ok, "problems": problems[:6],
                }
            elif kind == "ware":
                defs["wares"][ware(name)] = {"tribe": tribe, "source": rel, "descname": entry.get("descname", "")}
    for root in (DATA / "world" / "immovables", DATA / "tribes" / "immovables"):
        for path in sorted(root.rglob("init.lua")):
            attrs = register_attributes(path.parent)
            for kind, entry in extract(path):
                name = str(entry.get("name", "")) if isinstance(entry, dict) else ""
                if kind == "immovable" and name:
                    progs = {k: [parse_action(x) for x in v if isinstance(x, str)] for k, v in (entry.get("programs") or {}).items() if isinstance(v, list)}
                    defs["immovables"][name] = {
                        "source": path.relative_to(DATA).as_posix(), "dir": path.parent.relative_to(DATA).as_posix(), "size": entry.get("size", ""),
                        "attributes": attrs.get(name, []), "programs": progs, "spritesheets": sheets(entry),
                        "animations": {k: {"hotspot": v.get("hotspot")} for k, v in (entry.get("animations") or {}).items() if isinstance(v, dict)},
                    }
    for path in sorted((DATA / "world" / "critters").rglob("init.lua")):
        attrs = register_attributes(path.parent)
        for kind, entry in extract(path):
            name = str(entry.get("name", "")) if isinstance(entry, dict) else ""
            if kind == "critter" and name:
                defs.setdefault("critters", {})[name] = {
                    "dir": path.parent.relative_to(DATA).as_posix(), "size": entry.get("size"), "reproduction_rate": entry.get("reproduction_rate"),
                    "appetite": entry.get("appetite"), "attributes": attrs.get(name, []), "spritesheets": sheets(entry),
                    "animations": {k: {"hotspot": v.get("hotspot")} for k, v in (entry.get("animations") or {}).items() if isinstance(v, dict)},
                }
    mark_runnable(defs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(defs, indent=1), encoding="utf-8")
    b, w = defs["buildings"], defs["workers"]
    prod = [x for x in b.values() if x["type"] == "productionsite"]
    print(
        f"WL_DEFS buildings={len(b)} productionsites={len(prod)} executable={sum(1 for x in prod if x['executable'])} "
        f"workers={len(w)} executable={sum(1 for x in w.values() if x['executable'])} wares={len(defs['wares'])} "
        f"immovables={len(defs['immovables'])} critters={len(defs.get('critters', {}))} parse_errors={len(defs['errors'])} "
        f"runnable={sum(1 for x in b.values() if x.get('runnable'))}"
    )


if __name__ == "__main__":
    main()
