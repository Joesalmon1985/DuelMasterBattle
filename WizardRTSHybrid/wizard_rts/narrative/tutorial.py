"""The opening, the teacher's lessons and the first quest, all inside the live world (execution plan B.4, plus a narrative-only quest).

`start` (campaign profile, from `server.py`) casts a teacher beside the wizard's starting place. The teacher gives the three colours, a duel
against a Ward that is told aloud and one against a hidden Ward (each on the real board, verified in `duel_lease`). When the stories unlock
(`graph.unlocked`: every essential lesson done, or 20 game minutes) three villagers appear in the village with a quarrel (`gossip.json`):
a quest that is pure story. It records a journal note and changes nothing in the simulation. Residents cannot die yet (D.3), so there is no
backup route for the teacher; that arrives with D.5.
"""

from __future__ import annotations

import random
import zlib
from typing import Any

from wizard_rts import settlements
from wizard_rts.narrative import characters, config, duel_lease, events, graph, residents, wizard

TEACHER = "tutorial"
QUEST = "gossip"
LESSON_TITLES = {"meet": "Meet your teacher", "colours": "Learn the three colours", "told_ward": "Break a Ward you were told",
                 "hidden_ward": "Duel a hidden Ward", "world": "Ask what the village needs"}
CAST_RADIUS = 4  # tiles from the wizard's starting place


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("tutorial", {"started": False, "teacher": "", "story_cast": {}})


def start(world: Any) -> None:
    """Campaign only, once per world: cast the teacher beside the wizard."""
    st = state(world)
    if st["started"] or world.profile != "campaign":
        return
    st["started"] = True
    px, py = int(world.player["tx"]), int(world.player["ty"])
    near = min((r for r in settlements.standing(world)), key=lambda r: abs(r["tile"][0] - px) + abs(r["tile"][1] - py), default=None)
    tile = residents.free_tile(world, px, py, CAST_RADIUS)
    if near is None or tile is None:
        events.log(world, "tutorial_not_cast", why="no_settlement_or_tile")
        return
    tribe = world.faction_info.get(near["faction"], {}).get("tribe", "barbarians")
    st["teacher"] = residents.create(world, settlement=near["id"], role="teacher", graph=TEACHER, speaker="teacher", tile=tile, tribe=tribe,
                                     faction=near["faction"], key="teacher")
    st["settlement"] = near["id"]


def _story_tile(world: Any, base: tuple[int, int], rng: random.Random, avoid: set[tuple[int, int]]) -> tuple[int, int] | None:
    return residents.free_tile(world, base[0], base[1], 3, rng, avoid)


def cast_story(world: Any) -> None:
    """When the stories unlock: the three villagers of the quarrel appear, a little way from the centre, away from where the teacher stands."""
    st = state(world)
    if st["story_cast"] or not st["started"] or not st["teacher"]:
        return
    rec = settlements.record(world, st["settlement"])
    centre = world.buildings.get(rec["centre"]) if rec else None
    if rec is None or centre is None:
        return
    rng = random.Random(zlib.crc32(f"{world.seed}|{QUEST}|cast".encode()))
    px, py = int(world.player["tx"]), int(world.player["ty"])
    template = graph.load(QUEST)
    tribe = world.faction_info.get(rec["faction"], {}).get("tribe", "barbarians")
    avoid: set[tuple[int, int]] = set()
    base = None
    for dx, dy in [(9, -3), (-9, 3), (3, 9), (-3, -9), (8, 6), (-8, -6)]:
        t = _story_tile(world, (centre["tx"] + dx, centre["ty"] + dy), rng, avoid)
        if t is not None and abs(t[0] - px) + abs(t[1] - py) >= 6:
            base = t
            break
    if base is None:
        return
    offsets = {"aggrieved": (0, 0), "accused": (5, 1), "neighbour": (2, 4)}
    for speaker in ("aggrieved", "accused", "neighbour"):
        tile = _story_tile(world, (base[0] + offsets[speaker][0], base[1] + offsets[speaker][1]), rng, avoid) or base
        avoid.add(tile)
        pid = residents.create(world, settlement=rec["id"], role=template["roles"][speaker], graph=QUEST, speaker=speaker, tile=tile, tribe=tribe,
                               faction=rec["faction"], key=f"{QUEST}:{speaker}")
        world.dmb.people[pid]["name"] = world.dmb.people[pid]["display_name"] = template["names"][speaker]  # authored names: the lines refer to them
        world.dmb.people[pid]["identity"]["name"] = template["names"][speaker]
        st["story_cast"][speaker] = pid
    events.log(world, "story_cast", story=QUEST, settlement=rec["id"])


def tick(world: Any) -> None:
    residents.quantum(world)
    if graph.unlocked(world):
        cast_story(world)


# ------------------------------------------------------------------ talking (called by story.talk / story.choose for residents)

def _ctx(world: Any, pid: str) -> dict[str, Any]:
    r = residents.table(world)[pid]
    return {"template": r["graph"], "speaker": r["speaker"], "speaker_pid": pid, "name": world.dmb.people[pid]["name"]}


def _reply(world: Any, pid: str, out: dict[str, Any]) -> dict[str, Any]:
    reply = {"status": "ok", "npc": pid, "name": world.dmb.people[pid]["name"], "quest_status": "", "lines": out["lines"], "choices": out["choices"]}
    for k, v in out.get("extras", {}).items():
        reply[k] = v
    if "text" in out:
        reply["text"] = out["text"]
    return reply


def _near(world: Any, pid: str) -> bool:
    t = residents.table(world)[pid]["tile"]
    return abs(int(world.player["tx"]) - t[0]) + abs(int(world.player["ty"]) - t[1]) <= characters.TALK_RANGE


def talk(world: Any, pid: str) -> dict[str, Any]:
    if not _near(world, pid):
        return {"status": "rejected", "reason": "too_far"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    residents.start_conversation(world, pid)
    return _reply(world, pid, graph.talk(world, _ctx(world, pid)))


def choose(world: Any, pid: str, choice: str) -> dict[str, Any]:
    if not _near(world, pid):
        return {"status": "rejected", "reason": "too_far"}
    out = graph.choose(world, _ctx(world, pid), choice)
    if out is None:
        return {"status": "rejected", "reason": "choice_unavailable"}
    reply = _reply(world, pid, out)
    lease = reply.get("duel_lease")
    if lease:
        lease["payload"]["duel"]["speaker"] = pid
    return reply


PURPOSE_FLAGS = {"told_ward": ("told_won", "told_fresh"), "hidden_ward": ("hidden_won", "hidden_fresh")}


def on_duel_resolved(world: Any, lease: dict[str, Any], out: dict[str, Any]) -> dict[str, Any] | None:
    """A verified lesson duel finished: the lesson is done (it counts to have fought), and the teacher answers. Returns the follow-up dialogue."""
    purpose = lease["purpose"]
    if purpose not in PURPOSE_FLAGS:
        return None
    won_flag, fresh_flag = PURPOSE_FLAGS[purpose]
    f = graph.flags(world, TEACHER)
    f.pop(won_flag, None)
    graph.set_flag(world, TEACHER, fresh_flag)
    if out["outcome"] == "won":
        graph.set_flag(world, TEACHER, won_flag)
    if wizard.complete_lesson(world, purpose):
        events.log(world, "lesson_done", lesson=purpose)
    pid = lease.get("speaker") or state(world)["teacher"]
    if pid not in residents.table(world):
        return None
    residents.start_conversation(world, pid)
    return _reply(world, pid, graph.talk(world, _ctx(world, pid)))


# ------------------------------------------------------------------ what the client shows

def quest_status(world: Any) -> str:
    st = state(world)
    if not st["story_cast"]:
        return "none"
    f = graph.flags(world, QUEST)
    if "done" in f:
        return "done"
    return "active" if any(x in f for x in ("heard_a", "heard_b", "gossip_heard")) else "offered"


def _quest_objective(world: Any) -> str:
    f = graph.flags(world, QUEST)
    s = quest_status(world)
    if s == "offered":
        return "Find the hen-keeper and the carter (figures with a golden mark) and hear what happened."
    if s == "active":
        if not ("heard_a" in f and "heard_b" in f):
            return "Hear both sides: Brenna the hen-keeper and Orrik the carter. Ilda the weaver has opinions too."
        if not any(x in f for x in ("outcome_fence", "outcome_coins", "outcome_none")):
            return "You have heard both. Ask Ilda the weaver what you should do about it."
        return "Tell Brenna and Orrik how it ended, and let Ilda know."
    return ""


def next_lesson_hint(world: Any) -> str:
    if not wizard.lesson_done(world, "meet"):
        return "Talk to your teacher (the figure with a golden mark near where you arrived)."
    if not wizard.lesson_done(world, "colours"):
        return "Ask your teacher to teach you magic."
    if not wizard.lesson_done(world, "told_ward"):
        return "Ask your teacher to let you try breaking a Ward you were told."
    if not wizard.lesson_done(world, "hidden_ward"):
        return "Duel your teacher with hidden Wards."
    if not wizard.lesson_done(world, "world") and graph.unlocked(world):
        return "Ask your teacher whether anyone in the village needs help."
    return ""


def row_info(world: Any):
    st = state(world)

    def info(pid: str, rec: dict[str, Any]) -> dict[str, Any]:
        if pid == st["teacher"]:
            hint = next_lesson_hint(world)
            return {"has_quest": bool(hint), "hint": ("Lesson: " + hint) if hint else ""}
        if rec["graph"] == QUEST:
            s = quest_status(world)
            return {"has_quest": s in ("offered", "active"), "hint": ("Quest: " + _quest_objective(world)) if s in ("offered", "active") else ""}
        return {}
    return info


def snapshot(world: Any) -> dict[str, Any]:
    w = wizard.wiz(world)
    notes = [dict(n) for n in w["journal_notes"]]
    out = {"opening": [] if w.get("opening_seen") or not state(world)["started"] else list(graph.load(TEACHER)["opening"]),
           "lessons": [{"id": k, "title": v, "done": k in w["lessons"]} for k, v in LESSON_TITLES.items()],
           "next_lesson": next_lesson_hint(world), "spells": [wizard.SPELL_NAMES.get(s, str(s)) for s in w["spells"]], "weave_size": int(w["weave_size"]),
           "unlocked": graph.unlocked(world), "duel": ({"lease": duel_lease.active(world)["id"], "purpose": duel_lease.active(world)["purpose"]} if duel_lease.active(world) else {}),
           "quest": {"id": QUEST, "title": graph.load(QUEST)["title"], "status": quest_status(world), "objective": _quest_objective(world)}, "notes": notes}
    return out
