"""The world's magic ladder: how many colours and slots a Ward duel has in this world (plan `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md`, section 4).

The owner's rules (18 Oct 2026): after three duels, whatever else has happened, the fourth colour is in the game; after an hour of play the
players weave four slots from six colours, whether or not they have duelled; the gain belongs to the *world*, not to the wizard, so it survives the
wizard's death, "A new apprentice", Continue, a restart of the host and the offline catch-up, exactly as the world does; and when a rung is due it
interrupts whatever the player is doing, except a duel already on the board.

State lives in `world.narrative["progression"]` (saved with the world, carried across a cycle reset): the world's duel count (every resolved duel
by anyone, human or Mira: lessons, the stranger, rats, Trial creatures, PvP), the play clock (`played_ms`: game time that passed while at least one
human wizard was present; the offline catch-up is not play), the rung reached, and the announcements owed to each seat. Each rung of the ladder
(`config.json` `progression.rungs`) fires on whichever of its two triggers comes first. The ladder order of the colours is Flame, Frost, Vine, Light,
Stone, Shadow, Arcane, Storm: the first three are the apprentice's palette, the rest arrive one at a time.

Every duel reads the ladder as a floor: `wizard.combatant` (story duels: the mentor, the stranger, the rats, the Trial) takes the union of the
wizard's own spells (the Dwarf's Stone stays a personal extra until the ladder catches up) and the world's colours, and the larger of the two weaves;
`net/pvp.py` builds the adaptive format from the ladder alone, so both players always duel at the same format.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import config, events, ledger, party, wizard

ORDER = [0, 1, 6, 4, 3, 5, 9, 2]  # the ladder order of the colours: the palette, then the rungs, then the two the dev formats may add
DEFAULT_RUNGS = [
    {"id": "light", "colour": 4, "duels": 3, "minutes": 12},
    {"id": "weave4", "weave": 4, "duels": 5, "minutes": 25},
    {"id": "stone", "colour": 3, "duels": 7, "minutes": 40},
    {"id": "shadow", "colour": 5, "duels": 10, "minutes": 60},
]
GAIN_TEXT = {"light": "a fourth colour: Light", "weave4": "a fourth slot in the weave", "stone": "a fifth colour: Stone", "shadow": "a sixth colour: Shadow"}


def rungs() -> list[dict[str, Any]]:
    return [dict(r) for r in config.get("progression", "rungs", DEFAULT_RUNGS)]


def state(world: Any) -> dict[str, Any]:
    st = world.narrative.get("progression")
    if st is None:
        # a world that existed before the ladder (0.3.0): its duels so far are the PvP duels it counted plus every story duel its wizards fought
        duels = ledger.count(world, "pvp_duels") // 2 if ledger.count(world, "pvp_duels") else 0
        for _seat in party.players(world):
            duels += len(wizard.wiz(world).get("duels", {}).get("attempts", []))
        st = world.narrative["progression"] = {"duels": int(duels), "played_ms": 0, "rung": 0, "history": [], "pending": {}, "version": 1}
    return st


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


# ------------------------------------------------------------------ what the world has

def reached(world: Any) -> list[dict[str, Any]]:
    return rungs()[: int(state(world)["rung"])]


def colours(world: Any) -> list[int]:
    """The world's colours in ladder order: the palette plus every colour rung reached."""
    out = list(wizard.palette())
    for r in reached(world):
        if "colour" in r and int(r["colour"]) not in out:
            out.append(int(r["colour"]))
    return out


def weave(world: Any) -> int:
    size = 3
    for r in reached(world):
        if "weave" in r:
            size = max(size, int(r["weave"]))
    return size


def pool_for(world: Any, spells: list[int] | None = None) -> list[int]:
    """The colours a duel in this world is played with: the world's, plus any the wizard knows on their own (the Dwarf's Stone), in ladder order."""
    have = set(colours(world)) | {int(s) for s in (spells or [])}
    ordered = [c for c in ORDER if c in have]
    return ordered + sorted(have - set(ordered))


def next_rung(world: Any) -> dict[str, Any] | None:
    st = state(world)
    ladder = rungs()
    if int(st["rung"]) >= len(ladder):
        return None
    r = ladder[int(st["rung"])]
    return {"id": r["id"], "gain": GAIN_TEXT.get(r["id"], r["id"]), "in_duels": max(0, int(r["duels"]) - int(st["duels"])),
            "in_minutes": max(0.0, round(int(r["minutes"]) - int(st["played_ms"]) / 60000.0, 1))}


def view(world: Any, seat: str | None = None) -> dict[str, Any]:
    """What the client shows in the journal and on the rung card: the world's magic now and what comes next."""
    st = state(world)
    return {"rung": int(st["rung"]), "colours": colours(world), "colour_names": [wizard.SPELL_NAMES.get(c, str(c)) for c in colours(world)],
            "weave": weave(world), "duels": int(st["duels"]), "played_min": round(int(st["played_ms"]) / 60000.0, 1), "next": next_rung(world),
            "pending": st["pending"].get(str(seat or party.current(world)))}


# ------------------------------------------------------------------ what moves it

def note_duel(world: Any, seat: str | None = None, kind: str = "") -> int:
    """A duel was resolved in this world (any kind, any wizard). Returns the world's count."""
    st = state(world)
    st["duels"] = int(st["duels"]) + 1
    events.log(world, "duel_counted", seat=seat or party.current(world), duel_kind=kind, duels=st["duels"])
    _advance(world, "duels")
    return int(st["duels"])


def tick(world: Any) -> None:
    """Once a game second from the narrative tick: the play clock runs while a human is present and the world is not catching up on its own."""
    from wizard_rts.narrative import tutorial

    if not tutorial.state(world).get("started") or getattr(world, "catching_up", False):
        return
    if party.multi(world) and not party.present_humans(world):
        return
    st = state(world)
    st["played_ms"] = int(st["played_ms"]) + 1000
    _advance(world, "time")


def _due(world: Any) -> dict[str, Any] | None:
    st = state(world)
    ladder = rungs()
    if int(st["rung"]) >= len(ladder):
        return None
    r = ladder[int(st["rung"])]
    if int(st["duels"]) >= int(r["duels"]) or int(st["played_ms"]) >= int(r["minutes"]) * 60000:
        return r
    return None


def _advance(world: Any, why: str) -> None:
    st = state(world)
    while True:
        r = _due(world)
        if r is None:
            return
        st["rung"] = int(st["rung"]) + 1
        by = "duels" if int(st["duels"]) >= int(r["duels"]) else "time"
        st["history"].append({"id": r["id"], "rung": st["rung"], "by": by, "game_ms": _now(world), "duels": int(st["duels"]), "played_ms": int(st["played_ms"])})
        for seat in party.players(world):  # every wizard of the world, human or AI, has the magic from this moment: the floor is applied, never just the flag
            wizard.learn(world, colours(world), weave(world))
            if party.seats(world).get(seat, {}).get("human", True) or not party.seats(world):
                st["pending"][str(seat)] = {"id": r["id"], "rung": st["rung"], "by": by, "gain": GAIN_TEXT.get(r["id"], r["id"])}
        events.log(world, "rung_reached", rung=st["rung"], id=r["id"], by=by)
        ledger.note(world, "rung", rung=st["rung"], id=r["id"], by=by)
        from wizard_rts.narrative import mortality

        mortality._announce(world, "rung_reached", rung=st["rung"], id=r["id"], by=by, gain=GAIN_TEXT.get(r["id"], r["id"]), colours=colours(world), weave=weave(world))


# ------------------------------------------------------------------ telling the apprentice

def speaker_for(world: Any, seat: str) -> tuple[str, str]:
    """Who announces a rung to this seat: the mentor if alive and the campaign still has him, else Mira if she lives, else the apprentice's own strongest
    Aspect (the inner voice). Returns (kind, display name)."""
    from wizard_rts.narrative import campaign, checks, mortality

    m = campaign.mentor(world)
    if m and campaign.mentor_present(world) and world.dmb.people.get(m, {}).get("alive", False):
        return "mentor", str(world.dmb.people[m]["name"])
    for ai_seat in party.ai_seats(world):
        if not mortality.is_dead(world, ai_seat):
            return "mira", mortality.name_of(world, ai_seat)
    with party.as_player(world, seat):
        scores = checks.scores(world)
    best = max(sorted(scores), key=lambda a: scores[a]) if scores else "wonder"
    return "voice", checks.LABELS.get(best, best.capitalize())


def lines_for(world: Any, seat: str, pending: dict[str, Any]) -> dict[str, Any]:
    """The announcement card for a rung owed to `seat`: speaker, name and text from `dialogue/progression.json`."""
    from wizard_rts.narrative import graph

    kind, name = speaker_for(world, seat)
    bank = graph.load("progression")["rungs"].get(pending["id"], {})
    choices = bank.get(kind) or bank.get("voice") or ["{gain}."]
    with party.as_player(world, seat):
        own = set(wizard.spells(world))
    idx = 0
    if kind == "mentor" and pending["by"] == "time" and bank.get("mentor_time"):
        choices, idx = bank["mentor_time"], 0
    r = next((x for x in rungs() if x["id"] == pending["id"]), {})
    if "colour" in r and int(r["colour"]) in own and bank.get(kind + "_known") and pending.get("already_known"):
        choices = bank[kind + "_known"]
    n = int(state(world).setdefault("said", {}).get(pending["id"], 0))
    state(world)["said"][pending["id"]] = n + 1
    text = choices[(n + idx) % len(choices)]
    env = {"gain": pending["gain"], "name": name, "colours": len(colours(world)), "weave": weave(world), "duels": int(state(world)["duels"]),
           "minutes": int(int(state(world)["played_ms"]) / 60000)}
    return {"speaker": kind, "name": name, "text": text.format_map(_Env(env)), "rung": int(pending["rung"]), "id": pending["id"], "gain": pending["gain"],
            "colours": colours(world), "weave": weave(world), "by": pending["by"]}


class _Env(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def take_pending(world: Any, seat: str) -> dict[str, Any] | None:
    """The announcement owed to `seat`, removed (the caller delivers it). The caller decides whether the moment is right (not in a duel on the board)."""
    st = state(world)
    p = st["pending"].pop(str(seat), None)
    if p is None:
        return None
    return lines_for(world, seat, p)


def deliverable(world: Any, seat: str) -> bool:
    """A rung may be told now: the wizard is not in the middle of a story duel (a PvP duel is the session's to check)."""
    from wizard_rts.narrative import duel_lease, mortality

    if mortality.is_dead(world, seat) and False:  # the dead are told too: the gain is theirs when they come back
        return False
    from wizard_rts.minigames import table as game_table

    with party.as_player(world, seat):
        return duel_lease.active(world) is None and not game_table.is_open(world)  # a game on the table is a board too: the rung waits for it to close
