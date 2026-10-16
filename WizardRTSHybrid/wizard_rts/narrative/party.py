"""The party: every wizard in a Wizard World, human or AI, and what is theirs alone versus what the world shares.

A single-player world has one seat and none of this is visible: the host's wizard keeps living where it always lived (`world.narrative["wizard"]`,
`["conversations"]`, `["checks"]`, `["graph"]`, actor id `"player"`). Each further wizard (a second human on the LAN, or the AI companion of a single-player
game) is a *seat* in `world.narrative["party"]` with its own copy of that private state. Whoever acts does so through `as_player`, which points the
four containers (and the Aspect actor) at the seat for the duration of one command or one narrative quantum, exactly the way `net/session.py`
points `world.player` and `world.story` at the acting player's records. Nothing in the narrative modules had to learn about seats:
`wizard.wiz(world)`, `conversation.table(world)`, `graph.flags(world, ...)` and `checks.scores(world)` simply answer for whoever is acting.

Private to a seat: spells and weave, lessons, duels, worldview, journal notes, facts, the conversations in progress, the dialogue flags (what the
mentor and the villagers have told *this* wizard), Aspect scores and relationships (the actor id), the scene being read, and fate.
Shared by everybody: the settlement, its people and residents, the stranger and the mentor's body, the quest cast, the campaign stage, the clock.

The rules that keep any one person from owning the story (all inert with one seat):

* **Presence.** A seat is `present` while its player is connected (the AI companion is always present). Nothing waits for an absent seat.
* **Training** ends when every present human seat has finished the essential lessons, or `party.training_grace_ms` after the first one did. Whoever is
  not done is *caught up*: the colours and the weave are granted so nobody is unable to fight, and the lessons stay open to be taken later.
* **Late joiners** are caught up on arrival and told the story so far in their journal.
* **Death is personal.** A wizard who loses the stranger's duel is dead (their `fate`); the world and the other wizards go on. The campaign is
  over (`game_over`) only when no human wizard is left alive.
* **The first victory** over the stranger repels him for everybody; every other open duel against him is released without penalty.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from wizard_rts.narrative import config

HOST = ""  # the seat whose private state lives directly in `world.narrative[...]` (the host's own wizard)
SWAPPED = ("wizard", "conversations", "checks", "graph")
ACTOR_HOST = "player"


def _fresh_private(name: str) -> dict[str, Any]:
    from wizard_rts import narrative

    return {"wizard": narrative._wizard_default(), "conversations": {}, "checks": {}, "graph": {"flags": {}, "receipts": {}, "node": {}}, "scene": None, "name": name}


def party(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("party", {"seats": {}, "order": [], "host": ""})


def seats(world: Any) -> dict[str, dict[str, Any]]:
    return party(world)["seats"]


def order(world: Any) -> list[str]:
    return list(party(world)["order"])


def count(world: Any) -> int:
    return len(party(world)["order"]) if "narrative" in world.__dict__ else 1


def multi(world: Any) -> bool:
    """More than one wizard has a seat. A world nobody has joined behaves exactly like the single-player game."""
    return "narrative" in world.__dict__ and len(party(world)["order"]) > 1


def host_actor(world: Any) -> str:
    """The Aspect / relationship actor id of the host's wizard: `player` for the first apprentice of a world, `player:2` for the next (a new wizard in
    a permanent world is a new person to everybody, and the people's memories of the first stay under the first's id)."""
    return str(party(world).get("host_actor", ACTOR_HOST)) if "narrative" in world.__dict__ else ACTOR_HOST


def actor(world: Any) -> str:
    """The Aspect / relationship actor id of the wizard acting now (the host's own, or the seat id for everybody else)."""
    return world.narrative.get("actor", host_actor(world)) if "narrative" in world.__dict__ else ACTOR_HOST


def current(world: Any) -> str:
    """The seat acting now ("" while the host's own private state is in place)."""
    return world.narrative.get("seat", HOST)


def enroll(world: Any, seat: str, name: str, *, host: bool = False, human: bool = True) -> dict[str, Any]:
    """Give a wizard a seat (idempotent). The first host keeps the world's own private state; every other seat gets a copy of the defaults."""
    p = party(world)
    rec = p["seats"].get(seat)
    if rec is None:
        rec = {"seat": seat, "name": name, "human": bool(human), "present": True, "host": bool(host), "joined_ms": _now(world), "caught_up": False,
               "actor": host_actor(world) if host else seat, "player_id": seat, "generation": int(p.get("generation", 1))}
        p["seats"][seat] = rec
        p["order"].append(seat)
        if host:
            p["host"] = seat
        elif seat not in guests(world):
            guests(world)[seat] = _fresh_private(name)
    rec["name"] = name
    rec["human"] = bool(human)
    return rec


def guests(world: Any) -> dict[str, dict[str, Any]]:
    return world.narrative.setdefault("guests", {})


def is_host_seat(world: Any, seat: str) -> bool:
    return seat == party(world)["host"]


def leave(world: Any, seat: str) -> None:
    """A wizard is gone for good (a ghost removed after a long absence): their seat and private record go with them."""
    p = party(world)
    p["seats"].pop(seat, None)
    if seat in p["order"]:
        p["order"].remove(seat)
    guests(world).pop(seat, None)


def set_present(world: Any, seat: str, present: bool) -> None:
    rec = seats(world).get(seat)
    if rec is not None:
        rec["present"] = bool(present)


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


@contextmanager
def as_player(world: Any, seat: str) -> Iterator[None]:
    """Act as `seat`: its private containers and Aspect actor are in place for the block, whatever was in place before is put back after (even on
    an error). Blocks nest (a guest's command that starts a scene for everybody visits the host's seat and back)."""
    if "narrative" not in world.__dict__ or not seat:
        yield
        return
    n = world.narrative
    in_guest = bool(n.get("seat"))
    host = is_host_seat(world, seat)
    if host:
        if not in_guest:
            yield  # already the host
            return
        owner, new_seat, new_actor = n["_host"], None, host_actor(world)
    elif seat in guests(world):
        if n.get("seat") == seat:
            yield
            return
        owner, new_seat, new_actor = guests(world)[seat], seat, seats(world)[seat]["actor"]
    else:
        yield
        return
    outermost = not in_guest and new_seat is not None
    if outermost:
        n["_host"] = {k: n[k] for k in SWAPPED if k in n}  # the host's own containers, kept where a nested visit can find them
    prev = {k: n[k] for k in SWAPPED if k in n}
    prev_actor, prev_seat = n.get("actor"), n.get("seat")
    for k in SWAPPED:
        if k in owner:
            n[k] = owner[k]
        else:
            n.pop(k, None)
    n["actor"] = new_actor
    if new_seat is None:
        n.pop("seat", None)
    else:
        n["seat"] = new_seat
    try:
        yield
    finally:
        for k in SWAPPED:  # a container created or replaced during the block stays with the seat it belongs to
            if k in n:
                owner[k] = n[k]
        if outermost:
            host_bundle = n.pop("_host")
            for k in SWAPPED:
                if k in host_bundle:
                    n[k] = host_bundle[k]
                else:
                    n.pop(k, None)
        else:
            for k in SWAPPED:
                if k in prev:
                    n[k] = prev[k]
                else:
                    n.pop(k, None)
        if prev_actor is None:
            n.pop("actor", None)
        else:
            n["actor"] = prev_actor
        if prev_seat is None:
            n.pop("seat", None)
        else:
            n["seat"] = prev_seat


def players(world: Any, *, humans_only: bool = False, present_only: bool = False) -> Iterator[str]:
    """Iterate the seats, each one acting for the body of the loop (its private state and its pose in place). A world nobody has enrolled in
    has one implicit seat, `HOST` (""), so code written with this loop is the single-player code when there is only one wizard."""
    seated = order(world)
    if not seated:
        yield HOST
        return
    for seat in seated:
        rec = seats(world)[seat]
        if humans_only and not rec["human"]:
            continue
        if present_only and not rec["present"]:
            continue
        with at_seat(world, seat):
            yield seat


def pose(world: Any, seat: str) -> tuple[int, int]:
    """Where a seat's wizard stands."""
    rec = world.players.get(seat) if getattr(world, "players", None) else None
    if rec is None:
        rec = world.player
    return int(rec["tx"]), int(rec["ty"])


@contextmanager
def at_seat(world: Any, seat: str) -> Iterator[None]:
    """`as_player` plus the world's `player` pointer at that seat's pose, for quantum code that reads `world.player` (the session does the same for commands)."""
    if not seat or seat not in seats(world):
        yield
        return
    prev = world.player
    rec = world.players.get(seat) if getattr(world, "players", None) else None
    with as_player(world, seat):
        if rec is not None:
            world.player = rec
        try:
            yield
        finally:
            world.player = prev


def talking_keys(world: Any) -> set[str]:
    """Everybody anyone is talking to now (residents stand still for every conversation, not only the host's)."""
    keys = set(world.narrative["conversations"])
    for g in guests(world).values():
        keys |= set(g["conversations"])
    return keys


def anyone_busy(world: Any) -> bool:
    """Is any present human in a conversation?"""
    return bool(world.narrative["conversations"]) or any(g["conversations"] for s, g in guests(world).items() if seats(world).get(s, {}).get("present"))


def present_humans(world: Any) -> list[str]:
    return [s for s in order(world) if seats(world)[s]["human"] and seats(world)[s]["present"]]


def humans(world: Any) -> list[str]:
    return [s for s in order(world) if seats(world)[s]["human"]]


def training_grace_ms() -> int:
    return int(config.get("party", "training_grace_ms", 120_000))


# ------------------------------------------------------------------ generations: a new wizard in a permanent world

def retired(world: Any) -> dict[str, dict[str, Any]]:
    return party(world).setdefault("retired", {})


def retire(world: Any, seat: str, reason: str = "new_wizard") -> str:
    """The wizard in `seat` leaves the roster of the living players (dead and buried, or gone from the village): their private state is kept under a
    retired key (`gone:<seat>:<n>`) with everything the world remembers of them (their body, their mother, their counts) re-pointed at it, and the seat
    itself is free for the next apprentice. For the host seat the world's own private containers are reset to a fresh apprentice's and the host's
    actor id moves on (`player:2`), so the people keep their memories of the first under the first's id. Returns the retired key."""
    from wizard_rts.narrative import ledger, mortality, mother

    p = party(world)
    if seat not in p["seats"]:
        return ""
    gen = int(p.get("generation", 1))
    key = f"gone:{seat}:{gen}"
    rec = p["seats"].pop(seat)
    n = world.narrative
    if is_host_seat(world, seat):
        bundle = {k: n[k] for k in SWAPPED if k in n}
        retired_rec = {**bundle, "scene": p.get("host_scene"), "name": rec["name"], "retired": True}
        guests(world)[key] = retired_rec
        fresh = _fresh_private(rec["name"])
        for k in SWAPPED:
            n[k] = fresh[k]
        n.get("campaign", {})["scene"] = None
        p["generation"] = gen + 1
        p["host_actor"] = f"player:{gen + 1}"
        p["host"] = ""
    elif seat in guests(world):
        g = guests(world).pop(seat)
        g["retired"] = True
        guests(world)[key] = g
    if seat in p["order"]:
        p["order"].remove(seat)
    rec.update(seat=key, retired=True, retired_reason=reason, retired_ms=_now(world), was=seat)
    retired(world)[key] = rec
    p["seats"][key] = rec  # still a seat (bodies and mothers point at it; `players()` iterates `order`, so nothing acts for it)
    mortality.rename_seat(world, seat, key)
    mother.rename_seat(world, seat, key)
    ledger.rename_seat(world, seat, key)
    from wizard_rts.narrative import events

    events.log(world, "wizard_retired", seat=seat, key=key, reason=reason, dead=mortality.is_dead(world, key))
    if not mortality.is_dead(world, key):
        ledger.note(world, "wizard_left", seat=key, name=rec["name"])
    return key


def retire_humans(world: Any, reason: str = "session_over") -> list[str]:
    """Every human seat, host included, is retired (a new session seats whoever comes). AI companions keep their seats and memories."""
    out = []
    for seat in list(order(world)):
        rec = seats(world).get(seat)
        if rec is not None and rec.get("human"):
            out.append(retire(world, seat, reason))
    return out


def generation(world: Any) -> int:
    return int(party(world).get("generation", 1)) if "narrative" in world.__dict__ else 1
