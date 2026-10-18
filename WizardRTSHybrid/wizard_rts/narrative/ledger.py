"""The behaviour ledger: what the apprentices have actually done, counted, so that people can react to it (plan amendment 9).

Counts live in `world.narrative["ledger"]`: world-wide (`world`) and per seat (`seats[seat]`), plus a short list of recent notes. Nothing here decides
anything; dialogue data reads the counts as `facts` (`graph.holds`: `{"facts": [{"name": "kills", "gte": 2}]}`) and the mother, the mentor, the
warehouse keeper and the Trial official choose their lines from them. Keys in use: `pvp_duels`, `kills`, `deaths`, `resurrections`, `draws`,
`protests`, `challenges_declined`, `provocations`, `lessons_skipped`, `trial_entered_unprepared`, `attacked_during_scene`, `upset_wins`.
Saved with the world; game time only; no wall clock; sorted iteration.
"""

from __future__ import annotations

from typing import Any

RECENT_CAP = 60
KNOWN = ("pvp_duels", "pvp_wins", "pvp_losses", "kills", "deaths", "resurrections", "draws", "protests", "provocations", "refused_steps", "accosted",
         "fourth_wall", "talks", "pests_killed", "pests_burned", "pest_escapes", "burned_trees", "burned_rocks", "burned_buildings", "burned_people", "burned_soldiers")  # fourth_wall: the rare lines that notice they are lines (capped by the banks' own conditions)  # always present as facts (0 when nothing happened)


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("ledger", {"world": {}, "seats": {}, "recent": []})


def _seat_counts(world: Any, seat: str) -> dict[str, int]:
    return state(world)["seats"].setdefault(str(seat), {})


def bump(world: Any, key: str, seat: str | None = None, n: int = 1) -> int:
    """Count one more `key` for the world and, when given, for `seat`. Returns the world count."""
    st = state(world)
    st["world"][key] = int(st["world"].get(key, 0)) + int(n)
    if seat is not None:
        counts = _seat_counts(world, seat)
        counts[key] = int(counts.get(key, 0)) + int(n)
    return int(st["world"][key])


def count(world: Any, key: str, seat: str | None = None) -> int:
    if "narrative" not in world.__dict__:
        return 0
    st = state(world)
    if seat is None:
        return int(st["world"].get(key, 0))
    return int(st["seats"].get(str(seat), {}).get(key, 0))


def note(world: Any, kind: str, **data: Any) -> None:
    st = state(world)
    st["recent"].append({"kind": kind, "game_ms": int(world.dmb.clock.get("game_ms", 0)), **data})
    del st["recent"][:-RECENT_CAP]


def rename_seat(world: Any, old: str, new: str) -> None:
    st = state(world)
    if str(old) in st["seats"]:
        st["seats"][str(new)] = st["seats"].pop(str(old))


def facts(world: Any, seat: str | None = None) -> dict[str, int]:
    """The counts as dialogue facts: the world's under their own names, the seat's as `my_<key>`."""
    if "narrative" not in world.__dict__:
        return {}
    st = state(world)
    out = {k: 0 for k in KNOWN}
    out.update({k: int(v) for k, v in sorted(st["world"].items())})
    if seat is not None:
        for k in KNOWN:
            out["my_" + k] = 0
        for k, v in sorted(st["seats"].get(str(seat), {}).items()):
            out["my_" + k] = int(v)
    return out
