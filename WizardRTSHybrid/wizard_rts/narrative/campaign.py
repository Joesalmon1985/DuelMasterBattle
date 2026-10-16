"""The opening campaign: an apprentice, free exploration, a stranger who kills the mentor, a lethal Ward Duel, the aftermath, and one objective.

One state machine in `world.narrative["campaign"]`, advanced once per game second by `tick` and by the player's acknowledgements (`scene_next`):

    training -> explore -> arrival -> confrontation -> duel -> victory -> aftermath -> complete        (or -> game_over from the duel)

* **training**: the mentor's lessons (`tutorial.py`, `data/narrative/dialogue/tutorial.json`). The essential lessons are in `config.json`.
* **explore**: a configurable stretch of ordinary play (`campaign.explore_min_ms` of *game* time, so a paused or backgrounded client does not advance it).
  The attack comes when that time has passed and the player has made enough contact with the settlement (people spoken to, things inspected), or when
  `explore_fallback_ms` has passed whatever the player did, and only when nothing else owns the player (no conversation, no duel, no dungeon).
* **arrival**: the stranger, a resident with a name, a persona and a body in the world, walks in over a real path; the mentor stands to meet him.
* **confrontation**: a scripted scene (`data/narrative/dialogue/campaign_scenes.json`) of pages the player acknowledges, with the camera guided by `focus`.
  Its pages carry effects that happen exactly once: the mentor is killed (a real Person death, `kill_mentor`), the apprentice may answer (worldview
  responses, Aspect checks), and the last page begins the duel.
* **duel**: a genuine Ward Duel lease (`duel_lease`), verified by Python. Only a verified victory wins. A defeat, a draw, a stalemate, leaving the board, a
  report that does not verify, and a save that is loaded with the duel open all end the game: `game_over`, a terminal state (pause token held, every
  op but starting again refused, saves refused).
* **victory / aftermath / complete**: the stranger retreats (he is alive and will be able to return; nothing is started now), the villagers react
  according to who they are and what they saw (`aftermath.json`), and after a few conversations (or a fallback time) the journal records
  *Seek greater magical power.*

Nothing here touches the simulation's rules: the stranger and the mentor are residents (narrative-owned bodies), the world keeps running during
exploration and the walk-in, and the clock is paused only by the client during scenes and by the duel and game-over pause tokens.
"""

from __future__ import annotations

import json
import random
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from sim.dmb.people.registry import PeopleService
from sim.dmb.time.clock import ClockService

from wizard_rts import settlements
from wizard_rts.narrative import characters, checks, config, conversation, duel_lease, events, graph, ledger, party, personas, residents, wizard

SCENES = Path(__file__).resolve().parents[1] / "data" / "narrative" / "dialogue" / "campaign_scenes.json"
STAGES = ("training", "explore", "arrival", "confrontation", "duel", "victory", "aftermath", "complete", "game_over")
DUEL_PURPOSE = duel_lease.LETHAL
OPPONENT = "opponent.stranger"
NOTE_SOURCE = "campaign"


@lru_cache(maxsize=1)
def _file() -> dict[str, Any]:
    return json.loads(SCENES.read_text())


def scenes() -> dict[str, Any]:
    return _file()["scenes"]


def page_responses(page: dict[str, Any]) -> list[dict[str, Any]]:
    """A page's possible answers: inline, or a named set shared by several scenes (`"$stranger_answers"`)."""
    r = page.get("responses", [])
    return _file()["response_sets"][r[1:]] if isinstance(r, str) else r


def now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _fresh() -> dict[str, Any]:
    return {"stage": "training", "stage_ms": 0, "explore_start_ms": None, "contacts": [], "inspected": [], "scene": None, "attacker": "", "witnesses": [],
            "mentor_fate": "", "events_seen": 0, "aftermath_talks": [], "aftermath_start_ms": None, "outcome": "", "attack_log": [], "stranger_gone_to": None,
            "training_ended_by": ""}


def state(world: Any) -> dict[str, Any]:
    st = world.narrative.get("campaign")
    if st is None:
        st = world.narrative["campaign"] = _fresh()
        if all(wizard.lesson_done(world, l) for l in config.get("tutorial", "essential", [])):  # a world that is already past the lessons (an older save)
            st["stage"], st["explore_start_ms"], st["stage_ms"] = "explore", now(world), now(world)
        m = world.narrative.get("tutorial", {}).get("teacher", "")
        if m in world.dmb.people and "persona" not in world.dmb.people[m]:  # a mentor cast by an earlier build has no persona or relationship yet
            personas.set_authored(world, m, "mentor")
            if "player" not in world.dmb.people[m].setdefault("relationship_map", {}):
                PeopleService(world.dmb).set_relationship(m, checks.ACTOR, int(config.get("campaign", "mentor_relationship", 40)))
    return st


def stage(world: Any) -> str:
    return state(world)["stage"] if "narrative" in world.__dict__ else ""


def over(world: Any) -> bool:
    """The campaign is over for the wizard acting now: the stage is `game_over` (nobody is left), or this wizard has died (in company the others go on)."""
    if "narrative" not in world.__dict__:
        return False
    fate = world.narrative["wizard"].get("fate")
    return bool(fate) and not fate.get("alive", True)


def over_for_all(world: Any) -> bool:
    """Nobody human is left alive in this world (the stage itself never records a defeat: a new wizard may still arrive)."""
    return "narrative" in world.__dict__ and "campaign" in world.narrative and not _someone_alive(world)


def _guest_seat(world: Any) -> str:
    """The seat whose scene cursor is acting, or "" for the host / a world without company (whose cursor is `state["scene"]`, as ever)."""
    seat = party.current(world)
    return seat if seat and not party.is_host_seat(world, seat) and seat in party.guests(world) else ""


def _scene(world: Any) -> dict[str, Any] | None:
    g = _guest_seat(world)
    return party.guests(world)[g].get("scene") if g else state(world)["scene"]


def _set_scene(world: Any, value: dict[str, Any] | None) -> None:
    g = _guest_seat(world)
    if g:
        party.guests(world)[g]["scene"] = value
    else:
        state(world)["scene"] = value


def any_scene_open(world: Any) -> bool:
    """Is a present human still reading a scene? (Nothing else about the stranger advances over somebody's head, but nobody waits for ever.)"""
    for _seat in party.players(world, humans_only=True, present_only=True):
        if _scene(world) is not None:
            return True
    return False


def _set_stage(world: Any, name: str) -> None:
    st = state(world)
    events.log(world, "campaign_stage", stage=name, previous=st["stage"])
    st["stage"], st["stage_ms"] = name, now(world)


def mentor(world: Any) -> str:
    from wizard_rts.narrative import tutorial

    return tutorial.state(world)["teacher"]


def mentor_present(world: Any) -> bool:
    pid = mentor(world)
    r = residents.table(world).get(pid)
    return bool(pid and r is not None and r["status"] == "present" and world.dmb.people.get(pid, {}).get("alive", True))


def names(world: Any) -> dict[str, str]:
    """The names the scenes and the villagers use: the mentor, the stranger (only to those who saw him), the settlement."""
    from wizard_rts.narrative import tutorial

    st = state(world)
    people = world.dmb.people
    return {"mentor": people[mentor(world)]["name"] if mentor(world) in people else "the mentor",
            "attacker": people[st["attacker"]]["name"] if st["attacker"] in people else "the stranger",
            "settlement": village(world)}


SUFFIXES = ("Hold", "Wick", "Ford", "Rest", "Stead")


def village(world: Any) -> str:
    """The settlement's name in the story (the simulation calls it 'Red home 1'): generated once from the tribe's syllables and kept."""
    from wizard_rts.narrative import tutorial

    st = state(world)
    if st.get("village"):
        return st["village"]
    mentor_rec = residents.table(world).get(mentor(world))
    if mentor_rec is None:
        return "the settlement"
    tribe = mentor_rec["tribe"]
    ident = characters.identity_for(world, tribe, "settlement:" + str(mentor_rec["settlement"]))
    rng = random.Random(zlib.crc32(f"{world.seed}|{mentor_rec['settlement']}|village".encode()))
    st["village"] = f"{ident['given']} {rng.choice(SUFFIXES)}"
    return st["village"]


def names_for(world: Any, pid: str | None) -> dict[str, str]:
    """The placeholders a person may use: the stranger is named only by those who saw him; the others speak of 'the stranger'."""
    n = names(world)
    if knowledge(world, pid) != "witnessed":
        n["attacker"] = "the stranger"
    return n


# ------------------------------------------------------------------ knowledge: who knows what about the attack

def knowledge(world: Any, pid: str | None) -> str:
    """none (before the attack), witnessed (the speaker was near), or rumour (they have heard)."""
    st = state(world)
    if not st["mentor_fate"] or st["stage"] in ("training", "explore", "arrival"):
        return "none"
    if pid == st["attacker"] or pid == mentor(world):
        return "witnessed"
    link = (world.dmb.people.get(pid or "", {}).get("link") or {})
    key = characters.link_key(link.get("kind", ""), link.get("id", ""))
    return "witnessed" if key in st["witnesses"] else "rumour"


# ------------------------------------------------------------------ contact and the exploration phase

def note_contact(world: Any, pid: str) -> None:
    """The apprentice spoke to `pid` (called when a conversation begins)."""
    if "narrative" not in world.__dict__ or pid == mentor(world):
        return
    st = state(world)
    if st["stage"] == "explore" and pid not in st["contacts"]:
        st["contacts"].append(pid)
    elif st["stage"] in ("aftermath", "victory") and pid not in st["aftermath_talks"] and pid != st["attacker"]:
        st["aftermath_talks"].append(pid)


def note_inspect(world: Any, key: str) -> None:
    st = state(world)
    if st["stage"] == "explore" and key not in st["inspected"] and key != mentor(world):
        st["inspected"].append(key)


def explore_due(world: Any) -> dict[str, Any]:
    """Whether the attack is due, and why (the same answer the tests and the HUD read). Contact with the settlement is people spoken to and things
    inspected; duels fought, deaths and resurrections count as well (an apprentice who spent the morning killing their friend has made contact)."""
    st = state(world)
    elapsed = now(world) - int(st["explore_start_ms"] or now(world))
    contact = len(st["contacts"]) + len(st["inspected"]) + min(3, ledger.count(world, "pvp_duels") + ledger.count(world, "deaths") + ledger.count(world, "resurrections"))
    need = int(config.get("campaign", "explore_min_contacts", 3))
    by_play = elapsed >= int(config.get("campaign", "explore_min_ms", 180000)) and contact >= need
    by_fallback = elapsed >= int(config.get("campaign", "explore_fallback_ms", 420000))
    return {"elapsed_ms": elapsed, "contacts": contact, "needed": need, "due": by_play or by_fallback, "by": "play" if by_play else ("fallback" if by_fallback else "")}


def _quiet(world: Any) -> bool:
    """Nothing else owns the player: no conversation, no duel, no dungeon, and no open story duel."""
    if party.multi(world):  # in company it is enough that one present wizard is free: nobody can hold the story back by standing in a dungeon
        for _seat in party.players(world, humans_only=True, present_only=True):
            if not conversation.table(world) and duel_lease.active(world) is None and not over(world):
                return True
        return not party.present_humans(world)
    story = world.__dict__.get("story") or {}
    return (not conversation.table(world) and duel_lease.active(world) is None and not story.get("in_dungeon") and not story.get("duel"))


# ------------------------------------------------------------------ the tick

def tick(world: Any) -> None:
    from wizard_rts.narrative import tutorial

    if not tutorial.state(world)["started"]:
        return
    st = state(world)
    _watch_fire(world, st)
    s = st["stage"]
    if s == "training" and _training_over(world, st):
        for _seat in party.players(world):  # every wizard has the magic when the lessons are over: the progression is applied, never just the flag
            if party.multi(world) and not all(wizard.lesson_done(world, l) for l in config.get("tutorial", "essential", [])):
                catch_up(world)  # a wizard who has not finished the lessons by now is caught up (they stay free to ask the mentor again)
            elif not all(wizard.knows(world, sp) for sp in wizard.palette()) or int(wizard.wiz(world)["weave_size"]) < 3:
                wizard.learn(world, wizard.palette(), 3)  # (a wizard who has not finished the lessons is caught up; so is an inconsistent save)
                events.log(world, "spells_repaired", spells=wizard.spells(world))
        st["explore_start_ms"] = now(world)
        _set_stage(world, "explore")
    elif s == "explore":
        if explore_due(world)["due"] and _quiet(world) and not any_scene_open(world):
            start_arrival(world)
    elif s == "arrival" and _arrival_ready(world, st):
        _arrival_step(world, st)
    elif s == "duel":
        _duel_watch(world, st)
        _depart_check(world, st)
    elif s == "confrontation":
        _depart_check(world, st)
    elif s == "aftermath":
        _aftermath_step(world, st)
    if s in ("victory", "aftermath", "complete"):
        _stranger_leaves(world, st)


def _training_over(world: Any, st: dict[str, Any]) -> bool:
    """Training is an activity, not a gate (plan amendment 2): it is over when the lessons are done, when the apprentices have proved they can duel
    (a duel between them, a death), or after `training_fallback_ms` of game time, whichever comes first."""
    if _training_done(world, st):
        st["training_ended_by"] = "lessons"
        return True
    if ledger.count(world, "pvp_duels") >= 1 or ledger.count(world, "deaths") >= 1:
        st["training_ended_by"] = "play"
        return True
    if now(world) >= int(config.get("campaign", "training_fallback_ms", 300000)):
        st["training_ended_by"] = "time"
        return True
    return False


def grant_basics(world: Any) -> bool:
    """An apprentice of a season knows the three colours and the weave of three from the first moment (the lessons teach the method, and remain open).
    Acts for the wizard acting now; True when anything was granted."""
    if not bool(config.get("campaign", "start_with_colours", True)):
        return False
    w = wizard.wiz(world)
    if all(wizard.knows(world, sp) for sp in wizard.palette()) and int(w["weave_size"]) >= 3:
        return False
    wizard.learn(world, wizard.palette(), 3)
    return True


def _lethal_open(world: Any) -> bool:
    """Is any human still to settle with the stranger: a challenge answered but not yet fought, or a duel under way?"""
    for _seat in party.players(world, humans_only=True):
        if wizard.wiz(world).get("lethal") in ("challenged", "active") and not over(world):
            return True
    return False


def _depart_check(world: Any, st: dict[str, Any]) -> None:
    """The stranger leaves once everybody present has had their say (and anybody who challenged him has fought): nobody is forced into anything,
    nobody waits for ever (`departure_grace_ms` after the confrontation began)."""
    if st["stage"] not in ("confrontation", "duel") or not st["attacker"]:
        return
    grace = int(config.get("campaign", "departure_grace_ms", 90000)) + int(config.get("party", "scene_grace_ms", 90000))
    if _lethal_open(world):
        return
    if any_scene_open(world) and now(world) - int(st["stage_ms"]) < grace:
        return
    _begin_aftermath(world)


def _begin_aftermath(world: Any) -> None:
    st = state(world)
    if st["stage"] in ("aftermath", "complete", "victory"):
        return
    if not st["outcome"]:
        st["outcome"] = "spared"
    world_effects(world)  # whoever walked away from the square: the mentor is dead all the same
    st["aftermath_start_ms"] = now(world)
    _set_stage(world, "aftermath")
    _retreat(world, scene_ctx(world), {})


def _training_done(world: Any, st: dict[str, Any]) -> bool:
    """One wizard: the essential lessons are done. Company: every present human has finished them, or the first to finish has waited
    `party.training_grace_ms` for the others (nobody is held back by a friend who is elsewhere, asleep or slow)."""
    essential = config.get("tutorial", "essential", [])
    if not party.multi(world):
        return all(wizard.lesson_done(world, l) for l in essential)
    done = {seat: all(wizard.lesson_done(world, l) for l in essential) for seat in party.players(world, humans_only=True)}
    present = party.present_humans(world)
    waiting = [s for s in (present or list(done)) if not done.get(s, False)]
    if not waiting:
        return any(done.values()) or not done
    if any(done.values()):
        first = st.setdefault("first_done_ms", now(world))
        return now(world) - int(first) >= party.training_grace_ms()
    return False


def _arrival_ready(world: Any, st: dict[str, Any]) -> bool:
    """The walk-in waits for the notice to be read, but not for ever."""
    if not party.multi(world):
        return not st["scene"]
    return not any_scene_open(world) or now(world) - int(st.get("arrival_ms") or 0) > int(config.get("campaign", "arrival_walk_cap_ms", 60000)) + int(config.get("party", "scene_grace_ms", 90000))


def _duel_watch(world: Any, st: dict[str, Any]) -> None:
    if not party.multi(world):
        if duel_lease.active(world) is None and not st["scene"]:
            _lost_duel(world, "no_duel")  # the stage says a duel is under way but there is none: a lethal duel is never skipped
        return
    for _seat in party.players(world, humans_only=True):
        w = wizard.wiz(world)
        if w.get("lethal") == "active" and duel_lease.active(world) is None and _scene(world) is None and not over(world):
            _lost_duel(world, "no_duel")


def _watch_fire(world: Any, st: dict[str, Any]) -> None:
    """The first time the apprentice burns anything with Flame, the lesson of using it in the world is done (optional; nothing waits for it)."""
    total = int(world.events.total)
    fresh = total - int(st["events_seen"])
    st["events_seen"] = total
    if fresh <= 0 or wizard.lesson_done(world, "flame_world"):
        return
    window = list(world.events)
    recent = window[-fresh:] if fresh <= len(window) else window
    if any(e["kind"] == "fire_magic" for e in recent) and wizard.complete_lesson(world, "flame_world"):
        events.log(world, "lesson_done", lesson="flame_world")


# ------------------------------------------------------------------ arrival of the stranger

def _spawn(world: Any, goal: tuple[int, int]) -> tuple[tuple[int, int], int] | None:
    """A walkable tile far from `goal` with a real path to it, so the stranger visibly walks in: rings of decreasing distance, seeded order."""
    rng = random.Random(zlib.crc32(f"{world.seed}|stranger|spawn".encode()))
    base = int(config.get("campaign", "arrival_distance", 14))
    for radius in (base, base - 3, base - 6, 5):
        offsets = [(dx, dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1) if max(abs(dx), abs(dy)) == radius]
        rng.shuffle(offsets)
        for dx, dy in offsets[:24]:
            t = residents.free_tile(world, goal[0] + dx, goal[1] + dy, 1)
            if t is None:
                continue
            from wizard_rts import workers

            path = workers.find_path(world, t, goal, limit=radius + 24)
            if path is not None and len(path) <= radius * 4:
                return t, len(path)
    return None


def start_arrival(world: Any) -> bool:
    """The exploration is over: the stranger enters the settlement. Exactly once (the attacker's presence is the latch)."""
    st = state(world)
    if st["attacker"] or st["stage"] != "explore":
        return False
    m = mentor(world)
    anchor = residents.table(world)[m]["tile"] if m in residents.table(world) else [int(world.player["tx"]), int(world.player["ty"])]
    goal = residents.free_tile(world, anchor[0], anchor[1], 2) or tuple(anchor)
    found = _spawn(world, goal)
    spawn = found[0] if found else (residents.free_tile(world, anchor[0], anchor[1], 5) or goal)
    spec = personas.authored()["characters"]["attacker"]
    ident_tribe = spec["tribe"]
    rec = residents.table(world).get(m, {})
    pid = residents.create(world, settlement=rec.get("settlement", ""), role="stranger", graph="", speaker="", tile=spawn, tribe=rec.get("tribe", "barbarians"),
                           faction=rec.get("faction", ""), key="attacker", identity_tribe=ident_tribe)
    personas.set_authored(world, pid, "attacker")
    st["attacker"] = pid
    st["stranger_goal"] = [goal[0], goal[1]]
    residents.table(world)[pid]["hostile"] = True
    if found:
        residents.walk_to(world, pid, goal, limit=found[1] + 10)
    if m in residents.table(world):
        residents.table(world)[m]["stay"] = True  # the mentor stops to meet him
    _set_stage(world, "arrival")
    st["arrival_ms"] = now(world)
    events.log(world, "stranger_arrived", person=pid, spawn=list(spawn))
    start_scene_for_all(world, "notice")
    return True


def _arrival_step(world: Any, st: dict[str, Any]) -> None:
    pid = st["attacker"]
    r = residents.table(world)[pid]
    goal = st["stranger_goal"]
    close = max(abs(r["tile"][0] - goal[0]), abs(r["tile"][1] - goal[1])) <= 1
    if (close or not r.get("walk")) or now(world) - int(st["arrival_ms"]) > int(config.get("campaign", "arrival_walk_cap_ms", 60000)):
        if _quiet(world):
            start_confrontation(world)


def start_confrontation(world: Any) -> None:
    st = state(world)
    m = mentor(world)
    present = mentor_present(world)
    if not present and not st["mentor_fate"]:
        st["mentor_fate"] = "died_earlier"  # the mentor was already lost to something else: never resurrected, never killed twice
        wizard.wiz(world)["mentor_dead"] = True
    centre = residents.table(world)[m]["tile"] if m in residents.table(world) else [int(world.player["tx"]), int(world.player["ty"])]
    r = int(config.get("campaign", "witness_radius", 12))
    st["witnesses"] = sorted(characters.link_key(kind, eid) for kind, table in characters.TABLES.items() for eid, row in getattr(world, table).items()
                             if max(abs(int(row["tx"]) - centre[0]), abs(int(row["ty"]) - centre[1])) <= r)
    residents.table(world)[st["attacker"]]["walk"] = []
    _set_stage(world, "confrontation")
    start_scene_for_all(world, "confrontation" if present else "confrontation_alone")
    if not party.present_humans(world) and party.multi(world):
        world_effects(world)  # nobody is here to see it: it happens all the same (the plan's section 3.4); they will hear of it from people


def world_effects(world: Any) -> None:
    """The confrontation's effects on the world (the mentor's death) happen exactly once whether or not anybody reads the scene: when no human is
    present, and when the stage moves on before the present ones acknowledged the page. Each effect is idempotent."""
    st = state(world)
    if st["stage"] not in ("confrontation", "duel", "victory", "aftermath", "complete") or not st["attacker"]:
        return
    ctx = scene_ctx(world)
    for sid in ("confrontation",):
        for page in scenes()[sid]["pages"]:
            for eff in page.get("effects", []):
                if eff["kind"] == "kill_mentor":
                    _SCENE_EFFECTS[eff["kind"]](world, ctx, eff)


# ------------------------------------------------------------------ scenes: pages the player acknowledges

def scene_ctx(world: Any) -> dict[str, Any]:
    """The scene's context: the cast's names and the facts the pages may read (the ledger's counts, this wizard's own with `my_`, the lessons done)."""
    from wizard_rts.narrative import mortality

    st = state(world)
    facts = ledger.facts(world, mortality.me(world))
    facts["lessons_done"] = len(wizard.wiz(world).get("lessons", {}))
    facts["mira_present"] = 1 if party.ai_alive(world) else 0  # the fellow apprentice lives in this world: the pages may give her a line
    return {"template": "scene", "speaker": "scene", "speaker_pid": st["attacker"], "name": names(world)["attacker"], "cast": names(world), "facts": facts}


def active_scene(world: Any) -> dict[str, Any] | None:
    return _scene(world)


def start_scene(world: Any, scene_id: str) -> None:
    conversation.end(world, None, "scene")
    _set_scene(world, {"id": scene_id, "i": 0, "applied": -1, "answered": {}})
    _enter_page(world, 0)


def start_scene_for_all(world: Any, scene_id: str) -> None:
    """The story's big moments are lived by every wizard in the world, each at their own pace, each with their own answers. A wizard who is
    away is not waited for; `welcome_back` brings them up to date when they return."""
    if not party.multi(world):
        start_scene(world, scene_id)
        return
    for _seat in party.players(world, humans_only=True, present_only=True):
        if not over(world):
            start_scene(world, scene_id)


def _page(world: Any, sc: dict[str, Any]) -> dict[str, Any]:
    return scenes()[sc["id"]]["pages"][sc["i"]]


def _enter_page(world: Any, i: int) -> None:
    """Apply a page's effects, once, when it is first shown (a reload or a repeated request never applies them again)."""
    sc = _scene(world)
    sc["i"] = i
    if i <= sc["applied"]:
        return
    sc["applied"] = i
    ctx = scene_ctx(world)
    for eff in _page(world, sc).get("effects", []):
        _SCENE_EFFECTS[eff["kind"]](world, ctx, eff)


def scene_view(world: Any) -> dict[str, Any] | None:
    """What the client shows for the current page of the scene: speaker, text, camera focus, and the answers open to the apprentice."""
    sc = active_scene(world)
    if sc is None:
        return None
    from wizard_rts.narrative import mortality
    from wizard_rts.trial import run as trial

    if trial.inside(world, mortality.me(world)):  # a wizard in the dungeon is not interrupted: the scene is shown when they come out (it stays theirs)
        return None
    ctx = scene_ctx(world)
    spec = scenes()[sc["id"]]
    page = _page(world, sc)
    n = names(world)
    key = f"{sc['id']}:{sc['i']}"
    answered = sc["answered"].get(key)
    text = "\n\n".join(graph._fmt(page["lines"], ctx, world, "scene"))
    choices: list[dict[str, Any]] = []
    if answered is None and page_responses(page):
        choices = graph.response_choices(world, ctx, key, page_responses(page))
    who = page.get("speaker", "narrator")
    speaker_name = {"narrator": "", "mentor": n["mentor"], "attacker": n["attacker"], "apprentice": "You"}.get(who, who)
    out = {"id": sc["id"], "i": sc["i"], "n": len(spec["pages"]), "speaker": who, "name": speaker_name, "text": text, "choices": choices,
           "focus": _focus(world, page.get("focus", "mentor")), "fx": page.get("fx", ""), "last": sc["i"] >= len(spec["pages"]) - 1,
           "answer": answered or {}, "needs_answer": bool(choices), "final": spec.get("final", "")}
    return out


def _focus(world: Any, who: str) -> list[int]:
    st = state(world)
    if who == "player":
        return [int(world.player["tx"]), int(world.player["ty"])]
    pid = st["attacker"] if who == "attacker" else mentor(world)
    r = residents.table(world).get(pid)
    return [int(r["tile"][0]), int(r["tile"][1])] if r else [int(world.player["tx"]), int(world.player["ty"])]


def scene_choose(world: Any, choice_id: str) -> dict[str, Any]:
    sc = active_scene(world)
    if sc is None:
        return {"status": "rejected", "reason": "no_scene"}
    page = _page(world, sc)
    key = f"{sc['id']}:{sc['i']}"
    if key in sc["answered"] or not choice_id.startswith("resp:" + key + ":"):
        return {"status": "rejected", "reason": "choice_unavailable"}
    ctx = scene_ctx(world)
    out = graph.respond(world, ctx, key, page_responses(page), choice_id[len("resp:" + key + ":"):])
    if out is None:
        return {"status": "rejected", "reason": "choice_unavailable"}
    sc["answered"][key] = {"text": "\n".join(out["lines"]), "reply": "\n".join(out["reply"]), "check": out["check"], "reaction": out["reaction"]}
    return {"status": "ok", "scene": scene_view(world)}


def scene_next(world: Any) -> dict[str, Any]:
    """The player acknowledges the page: the next page (its effects apply now), or, after the last, the scene's ending action."""
    st = state(world)
    sc = _scene(world)
    if sc is None:
        return {"status": "rejected", "reason": "no_scene"}
    view = scene_view(world)
    if view["needs_answer"]:
        return {"status": "rejected", "reason": "answer_required"}
    if not view["last"]:
        _enter_page(world, sc["i"] + 1)
        return {"status": "ok", "scene": scene_view(world)}
    final = scenes()[sc["id"]].get("final", "")
    _set_scene(world, None)
    out: dict[str, Any] = {"status": "ok", "scene": None, "ended": sc["id"]}
    if final == "departure":  # the stranger has said his piece; whoever challenged him fights, everybody else watches him go (plan amendment 1)
        if wizard.wiz(world).get("lethal") == "challenged":
            final = "duel"
        else:
            if wizard.wiz(world).get("lethal") in (None, ""):
                wizard.wiz(world)["lethal"] = "declined"
            _depart_check(world, st)
            return out
    if final == "duel":
        if st["stage"] in ("victory", "aftermath", "complete"):
            # somebody else has already driven the stranger off while this wizard was reading: nothing is left to fight, and nothing is lost
            wizard.wiz(world)["lethal"] = "spared"
            wizard.wiz(world)["journal_notes"].append({"game_ms": now(world), "text": "The stranger withdrew from the village before it came to a duel with me.", "source": NOTE_SOURCE})
            return out
        lease = duel_lease.begin(world, OPPONENT, purpose=DUEL_PURPOSE, display_name=names(world)["attacker"])
        if lease["status"] != "started":
            _lost_duel(world, "no_lease:" + str(lease.get("reason", "")))
        else:
            lease["payload"]["duel"]["speaker"] = ""
            out["duel_lease"] = lease
            wizard.wiz(world)["lethal"] = "active"
            if st["stage"] != "duel":
                _set_stage(world, "duel")
    elif final == "arrival":
        pass  # the stranger is already walking; control returns to the player
    elif final == "aftermath":
        if st["stage"] == "victory" or not party.multi(world):
            st["aftermath_start_ms"] = now(world)
            _set_stage(world, "aftermath")
    return out


# ------------------------------------------------------------------ scene effects

def _kill_mentor(world: Any, ctx: dict[str, Any], eff: dict[str, Any]) -> None:
    """The mentor dies, for real: a Person death with its tombstone, a body in the world, a journal note. Idempotent; never touches an already-dead mentor."""
    st = state(world)
    pid = mentor(world)
    if st["mentor_fate"] or pid not in world.dmb.people:
        return
    st["mentor_fate"] = "killed_by_stranger"
    st["mentor_died_ms"] = now(world)
    wizard.wiz(world)["mentor_dead"] = True  # crosses a cycle reset with the wizard: a new cycle never casts a second mentor
    rec = world.dmb.people[pid]
    if rec.get("alive", True):
        PeopleService(world.dmb).record_death(pid, cause_id="killed_by:" + st["attacker"])
    residents.table(world)[pid]["status"] = "dead"
    residents.table(world)[pid]["walk"] = []
    conversation.end(world, pid, "died")
    events.log(world, "character_died", person=pid, name=rec["name"], cause="killed_by:" + st["attacker"])
    n = names(world)
    wizard.wiz(world)["journal_notes"].append({"game_ms": now(world), "text": f"{n['mentor']}, my teacher, was killed in {n['settlement']} by a wizard who called himself {n['attacker']}.",
                                               "source": NOTE_SOURCE})


def _retreat(world: Any, ctx: dict[str, Any], eff: dict[str, Any]) -> None:
    """The stranger leaves: he walks away from the apprentice and, a little later, is gone. He is alive and keeps his identity."""
    st = state(world)
    pid = st["attacker"]
    r = residents.table(world).get(pid)
    if r is None or r["status"] != "present" or r.get("leaving"):
        return  # he withdraws once, whoever's scene shows it first
    px, py = int(world.player["tx"]), int(world.player["ty"])
    best = None
    for dist in (18, 14, 10, 6):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            t = residents.free_tile(world, r["tile"][0] + dx * dist, r["tile"][1] + dy * dist, 1)
            if t is not None and (best is None or abs(t[0] - px) + abs(t[1] - py) > best[0]):
                if residents.walk_to(world, pid, t, limit=dist * 3 + 10):
                    best = (abs(t[0] - px) + abs(t[1] - py), t)
                    break
        if best:
            break
    r["leaving"] = True
    events.log(world, "stranger_retreats", person=pid)


def _note(world: Any, ctx: dict[str, Any], eff: dict[str, Any]) -> None:
    wizard.wiz(world)["journal_notes"].append({"game_ms": now(world), "text": eff["text"].format_map(graph.placeholders(ctx)), "source": NOTE_SOURCE})


def _fact(world: Any, ctx: dict[str, Any], eff: dict[str, Any]) -> None:
    wizard.learn_fact(world, eff["id"])


def _aspect(world: Any, ctx: dict[str, Any], eff: dict[str, Any]) -> None:
    checks.change_once(world, eff["aspect"], int(eff["delta"]), "scene/" + eff["id"])


_SCENE_EFFECTS = {"kill_mentor": _kill_mentor, "retreat": _retreat, "note": _note, "fact": _fact, "aspect": _aspect}


# ------------------------------------------------------------------ the duel's end

def on_duel_resolved(world: Any, lease: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    """The stranger's duel finished and the report verified. A victory is the only way on; everything else ends the game."""
    st = state(world)
    if out["outcome"] != "won":
        wizard.wiz(world)["lethal"] = "lost"
        return game_over(world, "duel_" + str(out["outcome"]))
    wizard.wiz(world)["lethal"] = "won"
    checks.change_once(world, "resolve", 1, "campaign/duel_victory")
    wizard.wiz(world)["journal_notes"].append({"game_ms": now(world), "text": "I defeated the stranger with the magic my teacher taught me. He withdrew from the village, alive.", "source": NOTE_SOURCE})
    if st["stage"] == "duel" or not party.multi(world):
        st["outcome"] = "victory"
        _set_stage(world, "victory")
        _spare_others(world, party.current(world))
    start_scene(world, "victory")
    return {"status": "ok", "stage": "victory"}


def _spare_others(world: Any, winner: str) -> None:
    """Somebody broke the stranger's Ward: he withdraws from the whole settlement. The other wizards' duels with him end here, unpenalised, and
    every one of them is shown the retreat; a wizard who is away is told in the journal and shown it on return (`welcome_back`)."""
    if not party.multi(world):
        return
    for seat in party.players(world, humans_only=True):
        if seat == winner or (not winner and party.is_host_seat(world, seat)):
            continue
        w = wizard.wiz(world)
        if w.get("fate") is not None:
            continue
        if w.get("lethal") == "active":
            duel_lease.release_spared(world, party.current(world), "stranger_withdrew")
        if w.get("lethal") != "won":
            w["lethal"] = "spared"
        w["journal_notes"].append({"game_ms": now(world), "text": "A fellow apprentice broke the stranger's Ward, and he withdrew from the village, alive.", "source": NOTE_SOURCE})
        if party.seats(world).get(seat, {}).get("present"):
            start_scene(world, "victory")


def on_duel_void(world: Any, lease: dict[str, Any], why: str) -> dict[str, Any]:
    """The lethal duel was left, abandoned, rejected or lost to a load: it is a defeat (there is no way to step out of it)."""
    return game_over(world, "duel_" + why)


def _lost_duel(world: Any, why: str) -> dict[str, Any]:
    return game_over(world, why)


def game_over(world: Any, cause: str) -> dict[str, Any]:
    """The apprentice acting now dies (the stranger's duel lost, left or voided). Death is personal and the same everywhere (`mortality.die`): a
    body, a tombstone, the ledger, the mother; the world and the other wizards go on. Whether the game ends for this player is the session's
    decision (a private session ends with its human; a shared one when every human is dead); the classic single-process server marks the death
    final at once. The campaign stage never changes for it: a new wizard may still arrive in this world."""
    from wizard_rts.narrative import mortality

    st = state(world)
    if over(world):
        return {"status": "ok", "stage": st["stage"], "already": True}
    _set_scene(world, None)
    seat = mortality.me(world)
    out = mortality.die(world, seat, cause, by=st.get("attacker", ""))
    events.log(world, "player_died", cause=cause, seat=party.current(world))
    if not st["outcome"] and not _someone_alive(world):
        st["outcome"] = "defeat"
    return {"status": "ok", "stage": st["stage"], "personal": True, "death": out}


def _someone_alive(world: Any) -> bool:
    for _seat in party.players(world, humans_only=True):
        fate = wizard.wiz(world).get("fate")
        if not fate or fate.get("alive", True):
            return True
    return False


# ------------------------------------------------------------------ the aftermath and the one objective

def _aftermath_step(world: Any, st: dict[str, Any]) -> None:
    talks = len(st["aftermath_talks"])
    elapsed = now(world) - int(st["aftermath_start_ms"] or now(world))
    if (talks >= int(config.get("campaign", "aftermath_min_talks", 2)) or elapsed >= int(config.get("campaign", "aftermath_fallback_ms", 150000))) and not party.anyone_busy(world):
        complete(world)


def _stranger_leaves(world: Any, st: dict[str, Any]) -> None:
    r = residents.table(world).get(st["attacker"])
    if r is not None and r["status"] == "present" and r.get("leaving") and not r.get("walk"):
        residents.remove(world, st["attacker"], "gone")
        home = residents.table(world).get(mentor(world), {}).get("anchor") or [int(world.player["tx"]), int(world.player["ty"])]
        dx, dy = int(r["tile"][0]) - int(home[0]), int(r["tile"][1]) - int(home[1])
        compass = ("east" if abs(dx) >= abs(dy) and dx > 0 else "west" if abs(dx) >= abs(dy) else "south" if dy > 0 else "north")
        st["stranger_gone_to"] = {"tile": [int(r["tile"][0]), int(r["tile"][1])], "direction": compass, "game_ms": now(world)}
        events.log(world, "stranger_gone", person=st["attacker"], direction=compass, tile=list(r["tile"]))


def complete(world: Any) -> None:
    """The introduction is over: the journal records the objective. The next chapter is not started here."""
    st = state(world)
    if st["stage"] == "complete":
        return
    _set_stage(world, "complete")
    for _seat in party.players(world):  # every wizard of the party has the objective in their journal
        if wizard.wiz(world).get("fate"):
            continue
        wizard.wiz(world)["campaign_finished"] = True
        wizard.wiz(world)["journal_notes"].append({"game_ms": now(world), "text": "Objective: seek greater magical power. What I know is not enough; the people here believe there are teachers and traditions beyond this valley.",
                                                   "source": NOTE_SOURCE})


# ------------------------------------------------------------------ what the client and the HUD read

def objective(world: Any) -> str:
    st = state(world)
    return {"explore": "Explore the settlement and talk to the people who live in it.", "arrival": "A stranger is coming.", "confrontation": "",
            "victory": "", "aftermath": "Speak with the people of the settlement about what happened.", "complete": "Seek greater magical power.",
            "game_over": "The apprentice was defeated."}.get(st["stage"], "")


def snapshot(world: Any) -> dict[str, Any]:
    st = state(world)
    fate = wizard.wiz(world).get("fate")
    return {"stage": st["stage"], "scene": scene_view(world), "game_over": dict(fate) if fate and not fate.get("alive", True) and fate.get("terminal") else {},
            "dead": dict(fate) if fate and not fate.get("alive", True) else {}, "mentor_fate": st["mentor_fate"],
            "explore": explore_due(world) if st["stage"] == "explore" else {}, "aspects": checks.scores(world), "worldview": wizard.worldview_scores(world),
            "worldview_primary": wizard.worldview_primary(world), "mentor": mentor(world),
            "mentor_dead": st["mentor_fate"] in ("killed_by_stranger", "died_earlier"), "stranger": st["attacker"]}


# ------------------------------------------------------------------ a wizard joins, or comes back (company)

STAGE_ORDER = {name: i for i, name in enumerate(STAGES)}


def catch_up(world: Any) -> bool:
    """The wizard acting now has the colours and the weave, whatever they missed: the lessons are over for the world, nobody is left unable to fight
    (the stranger's duel and the Wards of the settlement need the magic). True when anything was granted."""
    changed = False
    w = wizard.wiz(world)
    if not all(wizard.knows(world, sp) for sp in wizard.palette()) or int(w["weave_size"]) < 3:
        wizard.learn(world, wizard.palette(), 3)
        changed = True
    for lesson in config.get("tutorial", "essential", []):
        if wizard.complete_lesson(world, lesson):
            changed = True
    if changed:
        w["caught_up"] = True
        events.log(world, "caught_up", seat=party.current(world), spells=wizard.spells(world))
    return changed


def on_join(world: Any) -> None:
    """A new wizard has a seat (call it as that wizard): the mentor knows them as well as he knows the first apprentice, and whatever the world has
    already been through is theirs to have lived (they are caught up, and the journal says what happened before they came)."""
    st = state(world)
    teacher = world.narrative.get("tutorial", {}).get("teacher", "")
    if teacher and teacher in world.dmb.people and not wizard.wiz(world).get("fate"):
        PeopleService(world.dmb).set_relationship(teacher, checks.actor(world), int(config.get("campaign", "mentor_relationship", 40)))
    grant_basics(world)
    if st["stage"] != "training":
        catch_up(world)
    welcome_back(world)


def welcome_back(world: Any) -> None:
    """A wizard who was away (or has just arrived) is brought up to date with the story, once per stage: what happened is in their journal, a
    stranger who is still at the settlement is faced in a scene of their own, and a duel that has already been won for everybody is not theirs to lose."""
    w = wizard.wiz(world)
    if w.get("fate"):
        return
    st = state(world)
    seen = int(STAGE_ORDER.get(str(w.get("seen_stage", "")), -1))
    stage = st["stage"]
    now_i = STAGE_ORDER.get(stage, 0)
    w["seen_stage"] = stage
    if seen >= now_i or stage in ("training", "explore", "game_over"):
        return
    n = names(world)
    notes = w["journal_notes"]
    if seen < STAGE_ORDER["confrontation"] and st["mentor_fate"] in ("killed_by_stranger", "died_earlier"):
        notes.append({"game_ms": now(world), "text": f"I came to {n['settlement']} too late: {n['mentor']}, the teacher here, had already been killed by a wizard who called himself {n['attacker']}.",
                      "source": NOTE_SOURCE})
    if stage in ("victory", "aftermath", "complete"):
        if w.get("lethal") not in ("won", "lost"):
            w["lethal"] = "spared"
        notes.append({"game_ms": now(world), "text": "The stranger has been driven out of the village. I did not have to face him.", "source": NOTE_SOURCE})
    elif stage in ("confrontation", "duel") and _scene(world) is None and w.get("lethal") in (None, "") and st["attacker"]:
        start_scene(world, "confrontation_alone")  # the stranger is here now: this wizard meets him with the rest
