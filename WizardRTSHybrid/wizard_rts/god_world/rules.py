"""The declared rules of `god_catan_v1`: five stable roles, costs, odds, timings and the four ages' display identities.

Everything here is read from `data/god_world/god_catan_v1.json` once and validated; code elsewhere asks this module rather than hard-coding a
number. `pips(n)` is the number of dice pairs (out of 36) that sum to `n`, the Catan production odds."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROLES: tuple[str, ...] = ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")
DESERT = "DESERT"
PROFILE = "god_catan_v1"

_DATA = Path(__file__).resolve().parents[1] / "data" / "god_world" / "god_catan_v1.json"


class RulesError(ValueError):
    pass


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    with open(_DATA, encoding="utf-8") as fh:
        raw = json.load(fh)
    validate(raw)
    return raw


def validate(raw: dict[str, Any]) -> None:
    """Schema checks: the five roles, four ages with every role mapped, costs on known roles, token inventory of 28, role counts summing to 30."""
    if raw.get("ruleset") != PROFILE:
        raise RulesError(f"ruleset {raw.get('ruleset')!r} is not {PROFILE}")
    if tuple(raw.get("roles", ())) != ROLES:
        raise RulesError("roles must be exactly WOOD, BRICK, SHEEP, WHEAT, ORE in that order")
    board = raw["board"]
    counts = board["role_counts"]
    if set(counts) != set(ROLES) | {DESERT}:
        raise RulesError("role_counts must name the five roles and DESERT")
    if sum(int(v) for v in counts.values()) != 30:
        raise RulesError("role_counts must sum to 30 hexes")
    tokens = [int(t) for t in board["tokens"]]
    if len(tokens) != 30 - int(counts[DESERT]):
        raise RulesError("one token per productive hex")
    if any(t == 7 or t < 2 or t > 12 for t in tokens):
        raise RulesError("tokens are 2..12 without 7")
    for kind, cost in raw["costs"].items():
        for role, n in cost.items():
            if role not in ROLES or int(n) <= 0:
                raise RulesError(f"cost {kind}: bad entry {role}={n}")
    ages = raw["ages"]
    if len(ages) != 4 or [a["index"] for a in ages] != [1, 2, 3, 4]:
        raise RulesError("exactly four ages indexed 1..4")
    for age in ages:
        for role in ROLES:
            spec = age["roles"].get(role)
            if not spec or not spec.get("name") or not spec.get("buildings"):
                raise RulesError(f"age {age['index']} role {role} needs a name and buildings")
        if not age["military"].get("facility") or not age["military"].get("unit"):
            raise RulesError(f"age {age['index']} needs a military facility and unit")
    if len(raw["factions"]) != 6 or len({f["id"] for f in raw["factions"]}) != 6:
        raise RulesError("six factions with distinct ids")
    for key in ("roll_interval", "road_build", "city_build", "warehouse_stage", "edge_travel_road", "edge_travel_trail", "military_interval", "transition_build", "ai_pass"):
        if int(raw["timings_ms"][key]) <= 0:
            raise RulesError(f"timing {key} must be positive")


def pips(token: int) -> int:
    """Dice pairs out of 36 that produce on this token (0 for a desert or 7)."""
    if token is None or token == 7 or token < 2 or token > 12:
        return 0
    return 6 - abs(7 - int(token))


def odds_text(token: int) -> str:
    p = pips(token)
    return f"{p}/36 ({100.0 * p / 36.0:.2f}%)" if p else "never"


def cost(kind: str) -> dict[str, int]:
    return {k: int(v) for k, v in data()["costs"][kind].items()}


def timing(key: str) -> int:
    return int(data()["timings_ms"][key])


def limit(key: str) -> int:
    return int(data()["limits"][key])


def vp_target() -> int:
    return int(data()["vp"]["target"])


def vp_for_level(level: int) -> int:
    v = data()["vp"]
    return int(v["city"]) if int(level) >= 2 else (int(v["settlement"]) if int(level) == 1 else 0)


def age_spec(age: int) -> dict[str, Any]:
    for a in data()["ages"]:
        if int(a["index"]) == int(age):
            return a
    raise RulesError(f"no age {age}")


def age_name(age: int) -> str:
    return str(age_spec(age)["name"])


def role_name(age: int, role: str) -> str:
    return str(age_spec(age)["roles"][role]["name"])


def hex_name(age: int, role: str) -> str:
    if role == DESERT:
        return "Desert"
    return str(age_spec(age)["roles"][role]["hex"])


def role_buildings(age: int, role: str) -> list[str]:
    return list(age_spec(age)["roles"][role]["buildings"])


def role_worker(age: int, role: str) -> str:
    return str(age_spec(age)["roles"][role].get("worker", ""))


def military_spec(age: int) -> dict[str, Any]:
    return dict(age_spec(age)["military"])


def factions() -> list[dict[str, str]]:
    return [dict(f) for f in data()["factions"]]


def board_spec() -> dict[str, Any]:
    return dict(data()["board"])


def last_age() -> int:
    return max(int(a["index"]) for a in data()["ages"])


def describe_cost(kind: str, age: int) -> str:
    return " + ".join(f"{n} {role_name(age, role).lower()}" for role, n in cost(kind).items())
