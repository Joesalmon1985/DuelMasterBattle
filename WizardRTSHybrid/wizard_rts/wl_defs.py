"""Widelands definitions as hybrid building kinds, worker roles and programmes.

`data/widelands_defs.json` is produced by scripts/import_widelands_programs.py
from the pinned Widelands Lua. This module turns a runnable production site
into the commands that workers.py interprets, so a building does not have to
be hand-written to exist. Legacy hand-written kinds (lumberjack, sawmill, ...)
keep working and win when a name collides; tests compare both.

A generic building kind is the string "wl:<widelands name>".
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "data" / "widelands_defs.json"
PREFIX = "wl:"


@lru_cache(maxsize=1)
def defs() -> dict[str, Any]:
    if not DATA.is_file():
        return {"buildings": {}, "workers": {}, "wares": {}, "immovables": {}}
    return json.loads(DATA.read_text(encoding="utf-8"))


def _groups(wares: dict) -> list[tuple[list[str], int]]:
    """consume/produce ware dict from the importer -> [(alternatives, amount)]."""
    out: list[tuple[list[str], int]] = []
    for k, v in wares.items():
        if k == "|":
            out.append((list(v), 1))
        else:
            out.append(([k], int(v)))
    return out


def convert_actions(actions: list[dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for a in actions:
        cmd = a["cmd"]
        if cmd == "playsound":
            continue
        if cmd == "sleep":
            out.append(("sleep", {"ms": int(a["ms"])}))
        elif cmd == "animate":
            out.append(("animate", {"ms": int(a["ms"]), "name": a.get("name", "")}))
        elif cmd == "consume":
            groups = _groups(a["wares"])
            if all(len(alts) == 1 for alts, _n in groups):
                out.append(("consume", {alts[0]: n for alts, n in groups}))
            else:
                out.append(("consume_groups", {"groups": groups}))
        elif cmd == "produce":
            out.append(("produce", {k: int(v) for k, v in a["wares"].items() if k != "|"}))
        elif cmd == "callworker":
            out.append(("callworker", {"program": a["target"]}))
        elif cmd == "call":
            out.append(("call", {"target": a["target"]}))
        elif cmd == "mine":
            out.append(("mine", {"resource": a["resource"], "radius": int(a["radius"]), "yield": float(a["yield"]), "when_empty": float(a["when_empty"])}))
        elif cmd == "return":
            if a.get("unless_needs"):
                out.append(("return_unless_needs", {"good": a["unless_needs"]}))
            elif a.get("condition"):
                out.append(("return_cond", dict(a["condition"])))
            else:
                out.append(("return", {"skipped": bool(a.get("skipped"))}))
        elif cmd == "recruit":
            out.append(("recruit", {"unit": a.get("target", "")}))
        else:
            out.append(("unsupported", {"cmd": cmd}))
    return out


def is_soldier_site(b: dict) -> bool:
    return b["type"] == "productionsite" and any(a["cmd"] == "recruit" and "soldier" in a.get("target", "") for acts in b["programs"].values() for a in acts)


@lru_cache(maxsize=None)
def _soldier_wares(tribe: str) -> tuple:
    for name, b in defs()["buildings"].items():
        if b["tribe"] == tribe and is_soldier_site(b):
            for actions in b["programs"].values():
                for a in actions:
                    if a["cmd"] == "consume":
                        return tuple((g, int(n)) for g, n in a["wares"].items() if g not in ("recruit", "carrier", "|"))
    return ()


def soldier_wares(tribe: str) -> dict[str, int]:
    return dict(_soldier_wares(tribe))


def _soldier_wares_uncached(tribe: str) -> dict[str, int]:
    """The wares one soldier costs at a tribe's barracks (workers-as-wares excluded)."""
    for name, b in defs()["buildings"].items():
        if b["tribe"] == tribe and is_soldier_site(b):
            for actions in b["programs"].values():
                for a in actions:
                    if a["cmd"] == "consume":
                        return {g: int(n) for g, n in a["wares"].items() if g not in ("recruit", "carrier", "|")}
    return {}


def convert_worker_actions(actions: list[dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for a in actions:
        cmd = a["cmd"]
        if cmd == "playsound":
            continue
        if cmd == "findobject":
            out.append(("findobject", {"attrib": a["attrib"] or ("eatable" if "eatable" in a.get("args", "") else ""), "radius": int(a["radius"] or 6)}))
        elif cmd == "findspace":
            args = a.get("args", "")
            sapl = 5
            if "saplingsearches:" in args:
                sapl = int(args.split("saplingsearches:")[1].split()[0])
            step = {"radius": int(a["radius"] or 3), "avoid": "", "saplingsearches": sapl}
            if a.get("resource"):
                step["resource"] = a["resource"]
                step["breed"] = bool(a.get("breed"))
            out.append(("findspace", step))
        elif cmd == "mine":
            out.append(("mine", {"resource": a["resource"], "radius": int(a["radius"] or 1)}))
        elif cmd == "breed":
            out.append(("breed", {"resource": a["resource"], "radius": int(a["radius"] or 1)}))
        elif cmd == "walk":
            out.append(("walk", {"to": a.get("to", "")}))
        elif cmd in ("animate", "sleep"):
            out.append(("animate", {"name": a.get("name") or "idle", "ms": int(a["ms"])}))
        elif cmd == "callobject":
            out.append(("callobject", {"program": a["target"]}))
        elif cmd == "createware":
            out.append(("createware", {"ware": a["ware"]}))
        elif cmd == "plant":
            out.append(("plant", {"attrib": a["attrib"]}))
        elif cmd == "removeobject":
            out.append(("removeobject", {}))
        elif cmd == "return":
            out.append(("return", {}))
        else:
            out.append(("unsupported", {"cmd": cmd}))
    return out


@lru_cache(maxsize=None)
def worker_programs(role: str) -> dict[str, list[tuple[str, dict]]] | None:
    w = defs()["workers"].get(role)
    if w is None:
        return None
    return {name: convert_worker_actions(acts) for name, acts in w["programs"].items()}


@lru_cache(maxsize=None)
def building_spec(name: str) -> dict[str, Any] | None:
    b = defs()["buildings"].get(name)
    if b is None or not b.get("runnable"):
        return None
    programs = {k: convert_actions(v) for k, v in b["programs"].items()}
    outputs: list[str] = []
    for actions in programs.values():
        for cmd, args in actions:
            if cmd == "produce":
                outputs += [g for g in args if g not in outputs]
            if cmd == "recruit" and "soldier" not in args["unit"]:
                good = args["unit"].split("_", 1)[-1]
                if good not in outputs:
                    outputs.append(good)
    workers: dict[str, str] = {}  # worker program name -> role that runs it
    for actions in programs.values():
        for cmd, args in actions:
            if cmd == "callworker":
                for role in b["working_positions"]:
                    if role in defs()["workers"] and args["program"] in defs()["workers"][role]["programs"]:
                        workers[args["program"]] = role
    for role in set(workers.values()):
        for actions in defs()["workers"][role]["programs"].values():
            for a in actions:
                if a["cmd"] == "createware" and a["ware"] and a["ware"] not in outputs:
                    outputs.append(a["ware"])
    return {
        "kind": PREFIX + name, "name": name, "tribe": b["tribe"], "label": b.get("descname") or name,
        "programs": programs, "inputs": {g: int(n) for g, n in b["inputs"].items()}, "outputs": outputs,
        "cost": dict(b["buildcost"]), "worker_for_program": workers, "dir": b["dir"], "size": b.get("size", ""),
        "definition": f"widelands.{name}",
    }


def spec_for_kind(kind: str) -> dict[str, Any] | None:
    return building_spec(kind[len(PREFIX):]) if kind.startswith(PREFIX) else None


def runnable_names() -> list[str]:
    return sorted(n for n, b in defs()["buildings"].items() if b.get("runnable"))
