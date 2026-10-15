"""Narrative-only quests played by the settlement's own people (the first is "The Forest Dispute").

A quest template (`data/narrative/dialogue/<id>.json`) names its cast by *role selectors*, not by ids: "a worker whose role is lumberjack", "a soldier, or
else a stonemason or hunter, or else a carrier". At casting time the selectors are matched against the simulation's workers, carriers and soldiers
near the wizard's settlement and each match is bound to its existing Person (`characters.person_for`, one Person per body). **Nobody is created for a
quest**: the woodcutter you talk to is the woodcutter whose work is simulated, and he keeps doing it. If no settlement body fits a required role the
quest is `unavailable` (retried later) rather than forced. If a bound person dies, is displaced or is otherwise gone, another body with the same
selector takes the role (a different person, with a different name and a note in the journal); if nobody can, the quest is `interrupted`, and
the journal says so. Nobody is resurrected and nothing is teleported. Quests change no simulation state: their consequences are flags, lines and
journal notes. State lives in `world.narrative["quests"][id]`: status, settlement, bindings, history.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import settlements
from wizard_rts.narrative import characters, events, graph, occupations, wizard

TEMPLATES = ("forest_dispute",)
RETRY_MS = 30_000
GRACE_MS = 60_000  # a participant who is gone is replaced if someone fitting turns up within this long (a hut sends a new worker after 30 s), else the quest is interrupted
RADIUS = 40  # a candidate is within this many tiles (Chebyshev) of the settlement's centre
PRESENT = ("present", "inside", "working_away")
COMPASS = ("east", "south-east", "south", "south-west", "west", "north-west", "north", "north-east")


def table(world: Any) -> dict[str, Any]:
    return world.narrative["quests"]


def rec(world: Any, qid: str) -> dict[str, Any] | None:
    return table(world).get(qid)


def status(world: Any, qid: str) -> str:
    r = rec(world, qid)
    if r is None:
        return "none"
    if r["status"] in ("unavailable", "interrupted"):
        return r["status"]
    f = graph.flags(world, qid)
    if "done" in f:
        return "done"
    return "active" if any(x in f for x in ("heard_cutter", "heard_planter", "witness_saw", "witness_gossip")) else "offered"


# ------------------------------------------------------------------ casting

def _tile(row: dict[str, Any]) -> tuple[int, int]:
    return int(row["tx"]), int(row["ty"])


def _matches(spec: dict[str, Any], kind: str, row: dict[str, Any]) -> bool:
    if spec["kind"] != kind:
        return False
    if kind == "worker":
        return row["role"] in spec.get("roles", [row["role"]])
    if kind == "unit":
        return row.get("kind", "soldier") in spec.get("unit_kinds", ["soldier"]) and row.get("alive", True)
    return True


def candidates(world: Any, picks: list[dict[str, Any]], centre: tuple[int, int], faction: str, taken: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Bodies (kind, id) matching a role's selectors, preferred selector first, nearest to the settlement's centre first, ids as the tie-break."""
    out: list[tuple[str, str]] = []
    for spec in picks:
        table_ = {"worker": world.workers, "carrier": world.carriers, "unit": world.units}[spec["kind"]]
        found = []
        for eid, row in table_.items():
            if row.get("faction_name") != faction or (spec["kind"], eid) in taken or not _matches(spec, spec["kind"], row):
                continue
            d = max(abs(_tile(row)[0] - centre[0]), abs(_tile(row)[1] - centre[1]))
            if d <= RADIUS:
                found.append((d, eid))
        out.extend((spec["kind"], eid) for _d, eid in sorted(found))
    return out


def _centre(world: Any, sid: str) -> tuple[tuple[int, int], str] | None:
    r = settlements.record(world, sid)
    b = world.buildings.get(r["centre"]) if r else None
    return (_tile(b), r["faction"]) if b is not None else None


def cast(world: Any, qid: str, sid: str) -> bool:
    """Bind every role to an existing body of the settlement. All or nothing."""
    where = _centre(world, sid)
    if where is None:
        return False
    centre, faction = where
    template = graph.load(qid)
    taken: set[tuple[str, str]] = set()
    bindings: dict[str, dict[str, Any]] = {}
    for role, spec in template["cast"].items():
        found = candidates(world, spec["pick"], centre, faction, taken)
        if not found:
            table(world)[qid] = {"status": "unavailable", "settlement": sid, "why": role, "retry_ms": int(world.dmb.clock.get("game_ms", 0)) + RETRY_MS,
                                 "bindings": {}, "history": []}
            return False
        kind, eid = found[0]
        taken.add((kind, eid))
        bindings[role] = {"kind": kind, "id": eid}
    for role, b in bindings.items():
        b["pid"] = characters.person_for(world, b["kind"], b["id"])
    table(world)[qid] = {"status": "cast", "settlement": sid, "bindings": bindings, "history": []}
    events.log(world, "quest_cast", quest=qid, settlement=sid, cast={r: b["pid"] for r, b in bindings.items()})
    return True


# ------------------------------------------------------------------ speakers and names

def binding_of(world: Any, pid: str) -> tuple[str, str] | None:
    for qid in TEMPLATES:
        r = rec(world, qid)
        if r is None:
            continue
        for role, b in sorted(r["bindings"].items()):
            if b["pid"] == pid:
                return qid, role
    return None


def _speaker_of(world: Any, b: dict[str, Any]) -> dict[str, Any] | None:
    row = getattr(world, characters.TABLES[b["kind"]]).get(b["id"])
    return {"key": b["id"], "kind": b["kind"], "pid": b["pid"], "row": row} if row is not None else None


def where_text(world: Any, b: dict[str, Any]) -> str:
    sp = _speaker_of(world, b)
    if sp is None:
        return "no longer to be found"
    row = sp["row"]
    dx, dy = _tile(row)[0] - int(world.player["tx"]), _tile(row)[1] - int(world.player["ty"])
    dist = max(abs(dx), abs(dy))
    import math

    heading = COMPASS[int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8] if dist else "here"
    loc = ""
    if b["kind"] == "worker":
        loc = "works at " + occupations.facts_for(world, sp)["workplace"] + ", "
    elif b["kind"] == "unit":
        loc = "keeps watch nearby, "
    elif b["kind"] == "carrier":
        loc = "carries along the roads, "
    return f"{loc}about {dist} tiles {heading} of you" if dist > 1 else f"{loc}right beside you"


def cast_names(world: Any, qid: str) -> dict[str, str]:
    """Placeholders for the lines: each role's name, its occupation, and where to find them now."""
    r = rec(world, qid)
    if r is None or not r["bindings"]:
        return {}
    out: dict[str, str] = {}
    for role, b in r["bindings"].items():
        person = world.dmb.people.get(b["pid"], {})
        sp = _speaker_of(world, b)
        out[role] = person.get("name", "someone")
        out[role + "_role"] = occupations.label(sp).lower() if sp else "villager"
        out[role + "_where"] = f"{out[role]} {where_text(world, b)}" if sp else f"{out[role]} is gone"
    return out


def ctx_for(world: Any, sp: dict[str, Any]) -> dict[str, Any] | None:
    """The dialogue context of a speaker who plays a role in a live quest, else None (they are an ordinary person)."""
    hit = binding_of(world, sp["pid"])
    if hit is None or status(world, hit[0]) in ("none", "unavailable", "interrupted"):
        return None
    qid, role = hit
    return {"template": qid, "speaker": role, "speaker_pid": sp["pid"], "name": world.dmb.people[sp["pid"]]["name"], "cast": cast_names(world, qid),
            "facts": occupations.facts_for(world, sp)}


# ------------------------------------------------------------------ the quest through time

def available(world: Any, b: dict[str, Any]) -> bool:
    pid = b["pid"]
    return characters.lifecycle(world, pid) in PRESENT


def _note(world: Any, text: str, qid: str) -> None:
    wizard.wiz(world)["journal_notes"].append({"game_ms": int(world.dmb.clock.get("game_ms", 0)), "text": text, "source": qid})


def _replacement(world: Any, qid: str, role: str) -> tuple[str, str] | None:
    r = rec(world, qid)
    old = r["bindings"][role]
    where = _centre(world, r["settlement"])
    taken = {(b["kind"], b["id"]) for rr, b in r["bindings"].items() if rr != role}
    found = candidates(world, graph.load(qid)["cast"][role]["pick"], where[0], where[1], taken) if where else []
    found = [c for c in found if c != (old["kind"], old["id"])]
    return found[0] if found else None


def _substitute(world: Any, qid: str, role: str, found: tuple[str, str]) -> None:
    r = rec(world, qid)
    old = r["bindings"][role]
    old_name = world.dmb.people[old["pid"]]["name"]
    title = graph.load(qid)["title"]
    kind, eid = found
    new_pid = characters.person_for(world, kind, eid)
    r["bindings"][role] = {"kind": kind, "id": eid, "pid": new_pid}
    r["history"].append({"ms": int(world.dmb.clock.get("game_ms", 0)), "role": role, "from": old["pid"], "to": new_pid})
    _note(world, f"The {title}: {old_name} is gone. {world.dmb.people[new_pid]['name']} has taken their side of the dispute.", qid)
    graph.set_flag(world, qid, "sub_" + role)
    events.log(world, "quest_rebound", quest=qid, role=role, to=new_pid)


def _interrupt(world: Any, qid: str, role: str) -> None:
    r = rec(world, qid)
    old = r["bindings"][role]
    r["status"], r["why"] = "interrupted", role
    r["history"].append({"ms": int(world.dmb.clock.get("game_ms", 0)), "role": role, "from": old["pid"], "to": None})
    _note(world, f"The {graph.load(qid)['title']}: {world.dmb.people[old['pid']]['name']} is gone and nobody else can take their place. It cannot be settled now.", qid)
    events.log(world, "quest_interrupted", quest=qid, role=role)


def tick(world: Any, settlement: str) -> None:
    """Once a game second: cast the quest when the stories unlock, and keep every role filled by someone who is really there."""
    if not graph.unlocked(world):
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    for qid in TEMPLATES:
        r = rec(world, qid)
        if r is None or (r["status"] == "unavailable" and now >= r["retry_ms"]):
            if settlement:
                cast(world, qid, settlement)
            continue
        if r["status"] in ("unavailable", "interrupted") or "done" in graph.flags(world, qid):
            continue
        for role in sorted(r["bindings"]):
            b = r["bindings"][role]
            if available(world, b):
                b.pop("lost_ms", None)
                continue
            b.setdefault("lost_ms", now)
            found = _replacement(world, qid, role)
            if found is not None:
                _substitute(world, qid, role, found)
            elif now - int(b["lost_ms"]) >= GRACE_MS:
                _interrupt(world, qid, role)
                break


# ------------------------------------------------------------------ what the Journal shows

def objective(world: Any, qid: str) -> str:
    s = status(world, qid)
    names = cast_names(world, qid)
    f = graph.flags(world, qid)
    if s == "interrupted":
        return "The people of this dispute are gone; it cannot be settled."
    if s not in ("offered", "active"):
        return ""
    if not ("heard_cutter" in f and "heard_planter" in f):
        todo = []
        if "heard_cutter" not in f:
            todo.append(f"{names['cutter']} (woodcutter)")
        if "heard_planter" not in f:
            todo.append(f"{names['planter']} (forester)")
        return f"Hear both sides: {' and '.join(todo)}. {names['witness']} saw part of it."
    if not any(x in f for x in ("outcome_compromise", "outcome_cutter", "outcome_planter", "outcome_none")):
        return f"You have heard both. Tell {names['witness']} how you would settle it."
    return f"Let {names['cutter']} and {names['planter']} know how it ended, then tell {names['witness']}."


def snapshot(world: Any) -> list[dict[str, Any]]:
    out = []
    for qid in TEMPLATES:
        s = status(world, qid)
        if s in ("none", "unavailable"):
            continue
        r = rec(world, qid)
        people = []
        for role, b in sorted(r["bindings"].items()):
            sp = _speaker_of(world, b)
            people.append({"role": role, "name": world.dmb.people[b["pid"]]["name"], "occupation": occupations.label(sp).lower() if sp else "gone",
                           "where": where_text(world, b)})
        out.append({"id": qid, "title": graph.load(qid)["title"], "status": s, "objective": objective(world, qid), "people": people})
    return out
