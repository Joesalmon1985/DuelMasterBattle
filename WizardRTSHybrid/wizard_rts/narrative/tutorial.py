"""The opening and the mentor's lessons, inside the live world (execution plan B.4; the apprentice opening of the campaign milestone).

`start` (campaign profile, from `server.py`) casts the apprentice's mentor beside the wizard: the one dedicated resident, because a teacher of magic has no
counterpart among the simulation's occupations. The mentor has an authored persona (`data/narrative/characters.json`) and a warm relationship with
the apprentice, gives the three colours, a duel against a Ward that is told aloud and one against a hidden Ward (each on the real board, verified in
`duel_lease`), and sends the apprentice out into the settlement. Everyone else the wizard meets, including the people of the optional quest
(`quests.py`), is an ordinary simulation character. What happens after the lessons is `campaign.py`. (Internally the mentor is still `state["teacher"]`.)
"""

from __future__ import annotations

from typing import Any

from wizard_rts import settlements
from wizard_rts.narrative import campaign, config, conversation, duel_lease, events, graph, party, personas, quests, residents, wizard

TEACHER = "tutorial"
LESSON_TITLES = {"meet": "Speak with your mentor", "colours": "Learn the three colours", "told_ward": "Break a Ward you were told",
                 "hidden_ward": "Duel a hidden Ward", "flame_world": "Use Flame in the world (optional)", "world": "Hear what the village needs (optional)"}
CAST_RADIUS = 4  # tiles from the wizard's starting place


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("tutorial", {"started": False, "teacher": "", "settlement": ""})


def start(world: Any) -> None:
    """Campaign only, once per world: cast the teacher beside the wizard."""
    st = state(world)
    if st["started"] or world.profile != "campaign" or wizard.wiz(world).get("campaign_finished") or wizard.wiz(world).get("mentor_dead"):
        return  # a new cycle after the mentor's death or the introduction has no second mentor (nobody is resurrected)
    st["started"] = True
    px, py = int(world.player["tx"]), int(world.player["ty"])
    near = min((r for r in settlements.standing(world)), key=lambda r: abs(r["tile"][0] - px) + abs(r["tile"][1] - py), default=None)
    tile = residents.free_tile(world, px, py, CAST_RADIUS)
    if near is None or tile is None:
        events.log(world, "tutorial_not_cast", why="no_settlement_or_tile")
        return
    tribe = world.faction_info.get(near["faction"], {}).get("tribe", "barbarians")
    st["teacher"] = residents.create(world, settlement=near["id"], role="mentor", graph=TEACHER, speaker="teacher", tile=tile, tribe=tribe,
                                     faction=near["faction"], key="teacher")
    st["settlement"] = near["id"]
    personas.set_authored(world, st["teacher"], "mentor")
    from sim.dmb.people.registry import PeopleService

    PeopleService(world.dmb).set_relationship(st["teacher"], "player", int(config.get("campaign", "mentor_relationship", 40)))
    campaign.state(world)
    campaign.grant_basics(world)  # an apprentice of a season: the colours and the weave from the first moment; the lessons teach the method


def refresh(world: Any) -> None:
    """Bring the quests up to date now (casting happens once a second in the tick; a teacher who has just unlocked the stories must not answer first)."""
    quests.tick(world, state(world)["settlement"])


def tick(world: Any) -> None:
    residents.quantum(world)
    for _seat in party.players(world):  # each wizard's own conversations: ended when they walk away or leave them idle
        conversation.tick(world)
    campaign.tick(world)
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
    f.pop("quick", None)
    graph.set_flag(world, TEACHER, fresh_flag)
    if out["outcome"] == "won":
        graph.set_flag(world, TEACHER, won_flag)
        if int(wizard.wiz(world)["duels"]["attempts"][-1]["casts"]) <= 3:
            graph.set_flag(world, TEACHER, "quick")  # won in three casts or fewer: the mentor remarks on it
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
    if not state(world)["started"] or campaign.stage(world) not in ("training",):
        return ""  # no mentor in this world, or the lessons are over
    if not wizard.lesson_done(world, "meet"):
        return "Talk to your mentor: click them and choose Talk."
    if not wizard.lesson_done(world, "colours"):
        return "Ask your mentor to teach you magic."
    if not wizard.lesson_done(world, "told_ward"):
        return "Ask your mentor to let you try breaking a Ward you were told."
    if not wizard.lesson_done(world, "hidden_ward"):
        return "Duel your mentor with hidden Wards."
    return ""


def row_info(world: Any):
    st = state(world)

    def info(pid: str, rec: dict[str, Any]) -> dict[str, Any]:
        # only the teacher has a (subtle) tutorial affordance; everyone else looks like everyone else
        return {"has_quest": bool(next_lesson_hint(world))} if pid == st["teacher"] and rec["status"] == "present" else {}
    return info


def objective(world: Any) -> str:
    """The one current objective for the HUD: the next lesson, else the campaign's (explore, the stranger, the aftermath, the final objective), else
    the optional quest, else nothing."""
    hint = next_lesson_hint(world) or (campaign.objective(world) if state(world)["started"] else "")
    if not hint and wizard.wiz(world).get("campaign_finished"):
        hint = "Seek greater magical power."  # the introduction was finished in an earlier cycle: the objective stands
    if hint:
        if hint == "Seek greater magical power.":
            from wizard_rts.trial import run as trial

            gate = trial.gate_text(world)
            if gate:
                hint = hint + " " + gate  # the one place the valley offers it: the gate, and where it is from here
        return hint
    for q in quests.snapshot(world):
        if q["objective"]:
            return q["objective"]
    return ""


def _rats_journal(world: Any) -> list[dict[str, Any]]:
    from wizard_rts.narrative import pests

    try:
        return pests.journal(world)
    except Exception:  # noqa: BLE001 - the journal must never fail for the rats' sake
        return []


def snapshot(world: Any) -> dict[str, Any]:
    w = wizard.wiz(world)
    lease = duel_lease.active(world)
    names = campaign.names(world) if state(world)["started"] else {}
    return {"opening": [] if w.get("opening_seen") or not state(world)["started"] else [l.format_map(names) for l in graph.load(TEACHER)["opening"]],
            "campaign": campaign.snapshot(world) if state(world)["started"] else {},
            "lessons": [{"id": k, "title": v, "done": k in w["lessons"]} for k, v in LESSON_TITLES.items()],
            "next_lesson": next_lesson_hint(world), "objective": objective(world), "spells": [wizard.SPELL_NAMES.get(s, str(s)) for s in w["spells"]],
            "weave_size": int(w["weave_size"]), "magic_gated": world.profile == "campaign", "unlocked": graph.unlocked(world),
            "duel": {"lease": lease["id"], "purpose": lease["purpose"]} if lease else {}, "quests": _rats_journal(world) + quests.snapshot(world),
            "notes": [dict(n) for n in w["journal_notes"]], "talking": sorted(conversation.table(world)), "magic": _magic(world), "trial_gate": _gate(world),
            "games": _games(world)}


def _games(world: Any) -> dict[str, Any]:
    from wizard_rts.minigames import table as game_table

    try:
        return game_table.journal(world)
    except Exception:  # noqa: BLE001
        return {}


def _gate(world: Any) -> str:
    from wizard_rts.trial import run as trial

    try:
        return trial.gate_text(world)
    except Exception:  # noqa: BLE001
        return ""


def _magic(world: Any) -> dict[str, Any]:
    from wizard_rts.narrative import progression

    try:
        return progression.view(world)
    except Exception:  # noqa: BLE001
        return {}
