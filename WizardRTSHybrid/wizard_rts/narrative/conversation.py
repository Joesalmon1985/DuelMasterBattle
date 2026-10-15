"""The conversation lifecycle: one owner for talking to anybody (the teacher, a villager of a quest, any worker, carrier or soldier).

States of a conversation (`world.narrative["conversations"][speaker key]`): **begun** (`talk`: range, no duel open, the person is held in place by
`hold.py`, the world goes on), **speaking** (the reply carries what they say and the choices that are open), **responding** (`choose`: the person answers;
the reply has `ends` and, when it ends, no choices), **ended**. Whether a choice continues or ends the conversation is declared by the data
(`"ends": true` on a choice, or a duel beginning), never inferred from a label. When a reply has `ends`, the client shows the final response and one
acknowledge button; acknowledging, pressing Escape or the Leave button, walking away, a duel starting, a saved game being loaded, the person's removal,
and a conversation left idle for too long all end the conversation (`end`), release the person and let them resume what they were doing. Quest state
changed by a choice is already applied when the reply is sent, so closing early never loses it.

Ordinary people are not special-cased: a person with a part in a quest (`quests.ctx_for`) simply has the quest's lines and choices in addition to what
their occupation says (`occupations.view`).
"""

from __future__ import annotations

from typing import Any

from wizard_rts import hold, workers
from wizard_rts.narrative import campaign, characters, duel_lease, events, graph, occupations, quests, residents

IDLE_MS = 120_000  # a conversation nobody has touched for this long (game time) ends by itself
LEAVE_RANGE = characters.TALK_RANGE + 3  # walking this far (Manhattan) from the person ends the conversation
CALLOUT_RANGE = 6  # the wizard has to be this close (Chebyshev) to a building to ask someone out of it
FAREWELL = {"id": "farewell", "text": "Goodbye.", "available": True}


def table(world: Any) -> dict[str, Any]:
    return world.narrative["conversations"]


def now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def resolve(world: Any, key: str) -> dict[str, Any] | None:
    """Who is `key`: a resident (the teacher) or a simulation body. Bodies get their one Person here if they have none yet."""
    r = residents.table(world).get(key)
    if r is not None:
        return {"key": key, "kind": "resident", "pid": key, "row": None, "tile": (int(r["tile"][0]), int(r["tile"][1])), "res": r}
    found = characters.locate(world, key)
    if found is None:
        return None
    kind, row = found
    pid = characters.person_for(world, kind, key)
    return {"key": key, "kind": kind, "pid": pid, "row": row, "tile": (int(row["tx"]), int(row["ty"]))} if pid else None


def _distance(world: Any, sp: dict[str, Any]) -> int:
    return abs(int(world.player["tx"]) - sp["tile"][0]) + abs(int(world.player["ty"]) - sp["tile"][1])


def subtitle(world: Any, sp: dict[str, Any]) -> str:
    if sp["kind"] == "resident":
        role = "Mentor" if sp["res"]["role"] == "teacher" else sp["res"]["role"].capitalize()
        return f"{role} (dead)" if sp["res"]["status"] == "dead" else role
    faction = sp["row"].get("faction_name", "")
    return f"{occupations.label(sp)} of the {faction} settlement" if faction else occupations.label(sp)


def _reply(world: Any, sp: dict[str, Any], lines: list[str], choices: list[dict[str, Any]], ends: bool = False, text: str = "", extras: dict | None = None) -> dict[str, Any]:
    person = world.dmb.people[sp["pid"]]
    out = {"status": "ok", "npc": sp["key"], "person": sp["pid"], "name": person["name"], "subtitle": subtitle(world, sp), "quest_status": "",
           "lines": lines, "choices": choices, "ends": ends}
    if text:
        out["text"] = text
    out.update(extras or {})
    return out


def _ctx(world: Any, sp: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """(the quest or lesson context if this person has a graph, the context for their everyday talk)."""
    name = world.dmb.people[sp["pid"]]["name"]
    if sp["kind"] == "resident":
        from wizard_rts.narrative import tutorial

        tutorial.refresh(world)  # the stories may have unlocked a moment ago: cast them before the teacher answers
        r = sp["res"]
        return {"template": r["graph"], "speaker": r["speaker"], "speaker_pid": sp["pid"], "name": name,
                "cast": {**campaign.names_for(world, sp["pid"]), **quests.cast_names(world, "forest_dispute")}, "facts": {}}, {}
    facts = occupations.facts_for(world, sp)
    octx = {"template": "occupation", "speaker": "occupation", "speaker_pid": sp["pid"], "name": name, "facts": facts, "cast": campaign.names_for(world, sp["pid"])}
    gctx = quests.ctx_for(world, sp)
    if gctx is not None:
        gctx["cast"] = {**campaign.names_for(world, sp["pid"]), **gctx["cast"]}
    return gctx, octx


def _compose(world: Any, sp: dict[str, Any], asked: set[str], fresh: bool) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Lines and choices at this point of the conversation: the person's graph (a lesson or a quest) first, then what their occupation lets you ask."""
    gctx, octx = _ctx(world, sp)
    lines: list[str] = []
    choices: list[dict[str, Any]] = []
    extras: dict[str, Any] = {}
    if gctx is not None:
        gv = graph.talk(world, gctx) if fresh else graph.view(world, gctx)
        lines, choices, extras = list(gv["lines"]), list(gv["choices"]), dict(gv["extras"])
        if fresh and sp["kind"] != "resident":  # a person with a part in a quest still has something to say about the stranger first
            react = occupations.reaction_lines(world, sp, octx)
            if react:
                lines = react + lines
    if sp["kind"] != "resident":
        ov = occupations.view(world, sp, octx, intro=fresh and not lines, asked=asked)
        lines += ov["lines"]
        choices += ov["choices"]
        if not any(c["id"] in ("leave", "farewell") for c in choices):
            choices.append(dict(FAREWELL))
    return lines, choices, extras


def _pending_responses(world: Any, sp: dict[str, Any], octx: dict[str, Any], conv: dict[str, Any]) -> list[dict[str, Any]]:
    """The apprentice's possible replies to the last thing this person said, if it invited one (a topic with `responses`), until one is given."""
    out: list[dict[str, Any]] = []
    for tid in conv.get("asked", []):
        t = occupations.topic_def(world, sp, tid)
        if t is not None and t.get("responses"):
            out += graph.response_choices(world, octx, "topic:" + tid, t["responses"])
    return out


def begin(world: Any, sp: dict[str, Any]) -> None:
    for other in [k for k in table(world) if k != sp["key"]]:
        end(world, other, "another")
    campaign.note_contact(world, sp["pid"])
    table(world)[sp["key"]] = {"kind": sp["kind"], "pid": sp["pid"], "since_ms": now(world), "last_ms": now(world), "asked": []}
    if sp["row"] is not None:
        hold.hold(world, sp["row"])
    if sp["kind"] != "resident":
        occupations.note_talk(world, sp["pid"])


def talk(world: Any, key: str) -> dict[str, Any]:
    sp = resolve(world, key)
    if sp is None:
        return {"status": "rejected", "reason": "no_such_person"}
    if sp["kind"] == "unit" and not sp["row"].get("alive", True):
        return {"status": "rejected", "reason": "dead"}
    if sp["kind"] == "resident" and sp["res"]["status"] != "present":
        return {"status": "rejected", "reason": "dead" if sp["res"]["status"] == "dead" else "gone"}
    if campaign.over(world):
        return {"status": "rejected", "reason": "game_over"}
    if campaign.active_scene(world) is not None:
        return {"status": "rejected", "reason": "scene"}
    if _distance(world, sp) > characters.TALK_RANGE:
        return {"status": "rejected", "reason": "too_far"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    if sp["kind"] == "resident" and sp["res"].get("hostile"):  # the stranger speaks only in the scenes of the story
        return _reply(world, sp, ["The stranger's eyes pass over you as if you were furniture."], [], ends=True)
    if sp["kind"] == "unit" and sp["row"].get("target") is not None:  # fighting: no conversation, and nothing is held
        return _reply(world, sp, ["Not now. Can't you see I am busy?"], [], ends=True)
    begin(world, sp)
    lines, choices, extras = _compose(world, sp, set(), True)
    return _reply(world, sp, lines, choices, extras=extras)


def choose(world: Any, key: str, choice: str) -> dict[str, Any]:
    sp = resolve(world, key)
    if sp is None:
        return {"status": "rejected", "reason": "no_such_person"}
    if _distance(world, sp) > characters.TALK_RANGE:
        return {"status": "rejected", "reason": "too_far"}
    if key not in table(world):
        begin(world, sp)
    conv = table(world)[key]
    conv["last_ms"] = now(world)
    if sp["row"] is not None:
        hold.hold(world, sp["row"])
    asked = set(conv["asked"])
    gctx, octx = _ctx(world, sp)
    if choice.startswith("topic:") and sp["kind"] != "resident":
        res = occupations.topic(world, sp, octx, choice[len("topic:"):])
        if res is None:
            return {"status": "rejected", "reason": "choice_unavailable"}
        conv["asked"].append(choice[len("topic:"):])
        _l, choices, extras = _compose(world, sp, set(conv["asked"]), False)
        choices = _pending_responses(world, sp, octx, conv) + choices
        extras = {**extras, **res["extras"], "check": res["check"]}
        return _reply(world, sp, [], choices, text="\n".join(res["lines"]), extras=extras)
    if choice.startswith("resp:") and sp["kind"] != "resident":
        _r, _k, tid, rid = choice.split(":", 3)
        t = occupations.topic_def(world, sp, tid)
        out = graph.respond(world, octx, "topic:" + tid, t["responses"], rid) if t is not None else None
        if out is None:
            return {"status": "rejected", "reason": "choice_unavailable"}
        _l, choices, extras = _compose(world, sp, set(conv["asked"]), False)
        choices = _pending_responses(world, sp, octx, conv) + choices
        return _reply(world, sp, [], choices, text="\n".join(out["lines"] + out["reply"]), extras={**extras, **out["extras"], "check": out["check"], "reaction": out["reaction"]})
    if choice == "farewell" and sp["kind"] != "resident":
        return _reply(world, sp, [], [], ends=True, text=occupations.data()["farewell"])
    if gctx is None:
        return {"status": "rejected", "reason": "choice_unavailable"}
    out = graph.choose(world, gctx, choice)
    if out is None:
        return {"status": "rejected", "reason": "choice_unavailable"}
    ends = bool(out["ends"])
    lease = out["extras"].get("duel_lease")
    if lease:
        lease["payload"]["duel"]["speaker"] = key  # who answers when the duel is over (tutorial.on_duel_resolved)
    choices = list(out["choices"])
    if sp["kind"] != "resident" and not ends:
        ov = occupations.view(world, sp, octx, intro=False, asked=asked)
        choices += ov["choices"]
        if not any(c["id"] in ("leave", "farewell") for c in choices):
            choices.append(dict(FAREWELL))
    extras = dict(out["extras"])
    if out.get("check"):
        extras["check"] = out["check"]
    return _reply(world, sp, [] if ends else out["lines"], [] if ends else choices, ends=ends, text=out.get("text", ""), extras=extras)


def end(world: Any, key: str | None = None, reason: str = "closed") -> int:
    """End one conversation (or all of them): the person is released and goes back to what they were doing. Returns how many ended."""
    n = 0
    for k in ([key] if key else list(table(world))):
        conv = table(world).pop(k, None)
        if conv is None:
            continue
        found = characters.locate(world, k)
        if found is not None:
            hold.release(found[1])
        world.narrative.get("callouts", {}).pop(k, None)
        events.log(world, "conversation_ended", speaker=conv["pid"], reason=reason)
        n += 1
    return n


def close_all(world: Any, reason: str) -> None:
    end(world, None, reason)
    for coll in (world.workers, world.carriers, world.units):  # a save can carry a hold: nobody stays held after a load
        for row in coll.values():
            hold.release(row)
    world.narrative.get("callouts", {}).clear()


# ------------------------------------------------------------------ asking someone out of their building

def inspect_person(world: Any, key: str) -> dict[str, Any]:
    """Who this person is (name, occupation, settlement) for an inspect panel; a body gets its one Person here if it has none yet."""
    sp = resolve(world, key)
    if sp is None:
        return {"status": "rejected", "reason": "no_such_person"}
    campaign.note_inspect(world, key)
    dead = sp["kind"] == "resident" and sp["res"]["status"] == "dead"
    return {"status": "ok", "npc": key, "person": sp["pid"], "name": world.dmb.people[sp["pid"]]["name"], "subtitle": subtitle(world, sp), "dead": dead,
            "hostile": bool(sp["kind"] == "resident" and sp["res"].get("hostile"))}


def inspect_building(world: Any, building_id: str) -> dict[str, Any]:
    """Who works in a building and whether they are inside (they are not drawn then), for the building's information panel."""
    b = world.buildings.get(building_id)
    if b is None:
        return {"status": "rejected", "reason": "no_such_building"}
    campaign.note_inspect(world, building_id)
    people = []
    for role, wid in sorted((b.get("worker_ids") or {}).items()):
        row = world.workers.get(wid)
        if row is None:
            continue
        pid = characters.person_for(world, "worker", wid)
        people.append({"id": wid, "person": pid, "name": world.dmb.people[pid]["name"], "role": role, "inside": characters.lifecycle(world, pid) == "inside"})
    return {"status": "ok", "building": building_id, "people": people}


def _door(world: Any, b: dict[str, Any]) -> tuple[int, int] | None:
    """The free tile near the building closest to the wizard (the worker steps out there)."""
    px, py = int(world.player["tx"]), int(world.player["ty"])
    best = None
    for radius in (1, 2, 3):
        t = residents.free_tile(world, b["tx"], b["ty"], radius)
        if t is not None:
            d = abs(t[0] - px) + abs(t[1] - py)
            best = (d, t) if best is None or d < best[0] else best
    return best[1] if best else None


def call_out(world: Any, key: str) -> dict[str, Any]:
    """Ask a worker who is inside their building to come out and talk. They are held, then step to a free tile near the door (one tile a game
    second, `tick`); production waits for them and resumes when the conversation ends. Nothing is teleported further than the door."""
    sp = resolve(world, key)
    if sp is None or sp["kind"] != "worker":
        return {"status": "rejected", "reason": "no_such_person"}
    b = world.buildings.get(sp["row"]["building"])
    if b is None or characters.lifecycle(world, sp["pid"]) != "inside":
        return {"status": "rejected", "reason": "not_inside"}
    if max(abs(int(world.player["tx"]) - b["tx"]), abs(int(world.player["ty"]) - b["ty"])) > CALLOUT_RANGE:
        return {"status": "rejected", "reason": "too_far"}
    door = _door(world, b)
    if door is None:
        return {"status": "rejected", "reason": "no_room"}
    path = workers.find_path(world, sp["tile"], door)
    if path is None:
        return {"status": "rejected", "reason": "no_path"}
    end(world, None, "another")
    table(world)[key] = {"kind": "worker", "pid": sp["pid"], "since_ms": now(world), "last_ms": now(world), "asked": []}
    hold.hold(world, sp["row"])
    world.narrative.setdefault("callouts", {})[key] = {"path": [list(t) for t in path], "door": list(door)}
    events.log(world, "called_out", speaker=sp["pid"], building=b["id"])
    return {"status": "coming", "npc": key, "name": world.dmb.people[sp["pid"]]["name"], "door": list(door), "steps": len(path)}


def _step_callouts(world: Any) -> None:
    for key, c in sorted(world.narrative.get("callouts", {}).items()):
        row = world.workers.get(key)
        if row is None or not c["path"]:
            world.narrative["callouts"].pop(key, None)
            continue
        nxt = c["path"].pop(0)
        row["facing"] = workers.facing(nxt[0] - row["tx"], nxt[1] - row["ty"])
        row["tx"], row["ty"] = nxt[0], nxt[1]
        if not c["path"]:
            world.narrative["callouts"].pop(key)


def tick(world: Any) -> None:
    """Once a game second: keep held people held, step called-out workers, and end conversations that were abandoned."""
    _step_callouts(world)
    for key, conv in sorted(table(world).items()):
        sp = resolve(world, key) if key in table(world) else None
        if sp is None:
            end(world, key, "gone")  # the person died, left or was removed: nothing to release, the conversation just closes
            continue
        if sp["kind"] == "unit" and not sp["row"].get("alive", True):
            end(world, key, "gone")
        elif _distance(world, sp) > LEAVE_RANGE and key not in world.narrative.get("callouts", {}):
            end(world, key, "walked_away")
        elif now(world) - int(conv["last_ms"]) > IDLE_MS:
            end(world, key, "idle")
        elif sp["row"] is not None:
            hold.hold(world, sp["row"])
