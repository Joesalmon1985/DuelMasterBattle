"""The opening and the teacher's lessons, inside the live world (execution plan B.4).

`start` (campaign profile, from `server.py`) casts a teacher beside the wizard: the one dedicated resident, because a teacher of magic has no
counterpart among the simulation's occupations. The teacher gives the three colours, a duel against a Ward that is told aloud and one against a hidden
Ward (each on the real board, verified in `duel_lease`). Everyone else the wizard meets, including the people of the first quest
(`quests.py`), is an ordinary simulation character. Residents cannot die yet (D.3), so there is no backup route for the teacher; that is D.5.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import settlements
from wizard_rts.narrative import conversation, duel_lease, events, graph, quests, residents, wizard

TEACHER = "tutorial"
LESSON_TITLES = {"meet": "Meet your teacher", "colours": "Learn the three colours", "told_ward": "Break a Ward you were told",
                 "hidden_ward": "Duel a hidden Ward", "world": "Ask what the village needs"}
CAST_RADIUS = 4  # tiles from the wizard's starting place


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("tutorial", {"started": False, "teacher": "", "settlement": ""})


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


def refresh(world: Any) -> None:
    """Bring the quests up to date now (casting happens once a second in the tick; a teacher who has just unlocked the stories must not answer first)."""
    quests.tick(world, state(world)["settlement"])


def tick(world: Any) -> None:
    residents.quantum(world)
    conversation.tick(world)
    quests.tick(world, state(world)["settlement"])


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
    conversation.end(world, pid, "duel")
    if pid not in residents.table(world):
        return None
    reply = conversation.talk(world, pid)
    return reply if reply["status"] == "ok" else None


# ------------------------------------------------------------------ what the client shows

def next_lesson_hint(world: Any) -> str:
    if not state(world)["started"]:
        return ""  # no teacher in this world (a profile other than the campaign): there is no lesson to point at
    if not wizard.lesson_done(world, "meet"):
        return "Talk to your teacher: click them and choose Talk."
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
        # only the teacher has a (subtle) tutorial affordance; everyone else looks like everyone else
        return {"has_quest": bool(next_lesson_hint(world))} if pid == st["teacher"] else {}
    return info


def objective(world: Any) -> str:
    """The one current objective for the HUD: the next lesson, else the open quest, else nothing."""
    hint = next_lesson_hint(world)
    if hint:
        return hint
    for q in quests.snapshot(world):
        if q["objective"]:
            return q["objective"]
    return ""


def snapshot(world: Any) -> dict[str, Any]:
    w = wizard.wiz(world)
    lease = duel_lease.active(world)
    return {"opening": [] if w.get("opening_seen") or not state(world)["started"] else list(graph.load(TEACHER)["opening"]),
            "lessons": [{"id": k, "title": v, "done": k in w["lessons"]} for k, v in LESSON_TITLES.items()],
            "next_lesson": next_lesson_hint(world), "objective": objective(world), "spells": [wizard.SPELL_NAMES.get(s, str(s)) for s in w["spells"]],
            "weave_size": int(w["weave_size"]), "magic_gated": world.profile == "campaign", "unlocked": graph.unlocked(world),
            "duel": {"lease": lease["id"], "purpose": lease["purpose"]} if lease else {}, "quests": quests.snapshot(world),
            "notes": [dict(n) for n in w["journal_notes"]], "talking": sorted(conversation.table(world))}
