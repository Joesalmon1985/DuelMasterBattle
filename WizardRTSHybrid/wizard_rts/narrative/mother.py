"""The mother: a real resident of the home settlement for every apprentice, who will not let her child abandon a dead friend (plan section 3.2).

Every seat is cast a mother when it joins a campaign world (`ensure`), lazily, like other residents. When her child kills the other apprentice inside
the home territory she walks over, confronts them (a conversation she opens herself, pushed to the client as a notice) and **grounds** them: the
host refuses a step beyond `home_radius` of the settlement centre and an entry to the Trial, with her line as the reason, until the victim is alive
again (`is_grounded`, `allows_tile`, `refusal_line`). Her lines escalate with the behaviour ledger (kills, protests, resurrections). A death outside
the territory she only hears about. If she is dead or gone, nobody is grounded: nothing waits on her.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts.narrative import checks, config, events, ledger, party, residents

ROLE = "mother"
GRAPH = "mother"
LINES_REFUSE = [
    "Where do you think you are going? {victim} is lying in the dirt. Put them back first.",
    "Not one step further. I mean it. You know what you have to do.",
    "Your friend is dead and you are going for a walk? Turn around.",
]


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("mothers", {"by_seat": {}, "grounded": {}, "accosts": {}, "walks": {}})


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def home_tile(world: Any) -> tuple[int, int] | None:
    from wizard_rts.narrative import tutorial

    sid = tutorial.state(world).get("settlement", "")
    rec = world.dmb.settlements.get(sid) if sid else None
    if rec is None:
        return None
    return int(rec["tile"][0]), int(rec["tile"][1])


def in_home(world: Any, tile: tuple[int, int]) -> bool:
    home = home_tile(world)
    if home is None:
        return True
    r = int(config.get("mortality", "home_radius", 20))
    return max(abs(int(tile[0]) - home[0]), abs(int(tile[1]) - home[1])) <= r


def pid_of(world: Any, seat: str) -> str | None:
    pid = state(world)["by_seat"].get(str(seat))
    return pid if pid and pid in residents.table(world) and residents.table(world)[pid]["status"] == "present" else None


def _pose(world: Any, seat: str) -> tuple[int, int]:
    rec = world.players.get(seat) if getattr(world, "players", None) and seat else None
    rec = rec if rec is not None else world.player
    return int(rec["tx"]), int(rec["ty"])


def ensure(world: Any, seat: str) -> str | None:
    """Cast `seat`'s mother beside where they stand, once. Needs the campaign's home settlement (the mentor's casting names it)."""
    if "narrative" not in world.__dict__ or world.profile != "campaign":
        return None
    from wizard_rts.narrative import tutorial

    st = state(world)
    have = st["by_seat"].get(str(seat))
    if have and have in residents.table(world):
        return have
    sid = tutorial.state(world).get("settlement", "")
    home = world.dmb.settlements.get(sid) if sid else None
    if home is None:
        return None
    px, py = _pose(world, seat)
    tile = residents.free_tile(world, px, py, 5)
    if tile is None:
        return None
    tribe = world.faction_info.get(home["faction"], {}).get("tribe", "barbarians")
    pid = residents.create(world, settlement=sid, role=ROLE, graph=GRAPH, speaker="mother", tile=tile, tribe=tribe, faction=home["faction"], key=f"mother:{seat}")
    residents.table(world)[pid]["child"] = str(seat)
    st["by_seat"][str(seat)] = pid
    actor = party.seats(world).get(seat, {}).get("actor", party.ACTOR_HOST)
    PeopleService(world.dmb).set_relationship(pid, actor, int(config.get("mortality", "mother_relationship", 60)))
    events.log(world, "mother_cast", seat=seat, person=pid)
    return pid


def facts(world: Any, pid: str) -> dict[str, Any]:
    """What her lines may read: whether she has her child grounded, who the victim is, the counts, and whether her child arrived after the mentor died."""
    r = residents.table(world).get(pid) or {}
    seat = str(r.get("child", ""))
    g = state(world)["grounded"].get(seat)
    from wizard_rts.narrative import campaign, mortality

    st = campaign.state(world)
    mentor_dead = 1 if st.get("mentor_fate") in ("killed_by_stranger", "died_earlier") else 0
    joined = int(party.seats(world).get(seat, {}).get("joined_ms", 0))
    died_ms = int(st.get("mentor_died_ms", 0) or 0)
    out = {"grounded": 1 if g else 0, "victim": mortality.name_of(world, g["victim"]) if g else "", "child": mortality.name_of(world, seat) if seat else "",
           "kills": ledger.count(world, "kills", seat), "protests": ledger.count(world, "protests", seat), "resurrections": ledger.count(world, "resurrections", seat),
           "deaths": ledger.count(world, "deaths", seat), "role": ROLE, "mentor_dead": mentor_dead, "arrived_after": 1 if (mentor_dead and joined >= died_ms) else 0,
           "generation": int(party.seats(world).get(seat, {}).get("generation", 1)), "previous": _previous_name(world, seat)}
    return out


def _previous_name(world: Any, seat: str) -> str:
    """The name of the apprentice who came before this one in the same seat (a retired wizard), or ''."""
    best = None
    for key, rec in sorted(party.retired(world).items()):
        if rec.get("was") == seat.split(":")[0] and (best is None or int(rec.get("retired_ms", 0)) > int(best.get("retired_ms", 0))):
            best = rec
    return str(best["name"]) if best else ""


def rename_seat(world: Any, old: str, new: str) -> None:
    st = state(world)
    if old in st["by_seat"]:
        pid = st["by_seat"].pop(old)
        st["by_seat"][new] = pid
        r = residents.table(world).get(pid)
        if r is not None:
            r["child"] = new
    for k in ("grounded", "accosts", "walks"):
        if old in st[k]:
            st[k][new] = st[k].pop(old)
    for g in st["grounded"].values():
        if g.get("victim") == old:
            g["victim"] = new
    heard = st.get("heard", {})
    if old in heard:
        heard[new] = heard.pop(old)


# ------------------------------------------------------------------ what happens

def on_death(world: Any, victim: str, killer: str, tile: tuple[int, int]) -> None:
    if not killer or killer not in party.seats(world) or killer == victim:
        return
    st = state(world)
    if not in_home(world, tile):
        st.setdefault("heard", {})[str(killer)] = {"victim": victim, "game_ms": _now(world)}  # she will have words when they come home, no more
        return
    if pid_of(world, killer) is None and ensure(world, killer) is None:
        return
    st["grounded"][str(killer)] = {"victim": victim, "since_ms": _now(world), "kills": ledger.count(world, "kills", killer)}
    st["accosts"].pop(str(killer), None)
    events.log(world, "grounded", seat=killer, victim=victim)
    _announce(world, "grounded", seat=killer, victim=victim, mother=pid_of(world, killer))


def on_resurrected(world: Any, victim: str, caster: str) -> None:
    st = state(world)
    for seat, g in sorted(st["grounded"].items()):
        if g["victim"] == victim:
            st["grounded"].pop(seat, None)
            st["accosts"].pop(seat, None)
            events.log(world, "ungrounded", seat=seat, victim=victim)
            pid = pid_of(world, seat)
            _announce(world, "ungrounded", seat=seat, victim=victim, mother=pid, by=caster)


def _announce(world: Any, kind: str, **data: Any) -> None:
    from wizard_rts.narrative import mortality

    mortality._announce(world, kind, **data)


def is_grounded(world: Any, seat: str) -> bool:
    if "narrative" not in world.__dict__:
        return False
    g = state(world)["grounded"].get(str(seat))
    if not g:
        return False
    from wizard_rts.narrative import mortality

    if not mortality.is_dead(world, g["victim"]) or mortality.is_dead(world, seat) or pid_of(world, seat) is None:
        state(world)["grounded"].pop(str(seat), None)  # the victim lives, the killer died too, or she is no longer here: nothing holds
        return False
    return True


def allows_tile(world: Any, seat: str, tile: tuple[int, int]) -> bool:
    return not is_grounded(world, seat) or in_home(world, tile)


def refusal_line(world: Any, seat: str) -> str:
    from wizard_rts.narrative import mortality

    g = state(world)["grounded"].get(str(seat)) or {}
    n = int(ledger.count(world, "refused_steps", seat))
    ledger.bump(world, "refused_steps", seat=seat)
    line = LINES_REFUSE[min(n // 3, len(LINES_REFUSE) - 1)]
    return line.format(victim=mortality.name_of(world, g.get("victim", "")) if g else "your friend")


def refusal(world: Any, seat: str) -> dict[str, Any]:
    pid = pid_of(world, seat)
    name = world.dmb.people[pid]["name"] if pid else "Your mother"
    return {"status": "rejected", "reason": "grounded", "by": pid or "", "name": name, "line": refusal_line(world, seat)}


# ------------------------------------------------------------------ the tick: she walks over and has words

def tick(world: Any) -> None:
    st = state(world)
    now = _now(world)
    every = int(config.get("mortality", "accost_every_ms", 45000))
    walk_every = int(config.get("mortality", "mother_walk_every_ms", 8000))
    reach = int(config.get("mortality", "accost_range", 2))
    for seat in sorted(st["grounded"]):
        if not is_grounded(world, seat):
            continue
        pid = pid_of(world, seat)
        if pid is None:
            continue
        r = residents.table(world)[pid]
        cx, cy = _pose(world, seat)
        dist = abs(int(r["tile"][0]) - cx) + abs(int(r["tile"][1]) - cy)
        if dist > reach:
            if not r.get("walk") and now - int(st["walks"].get(seat, -10**9)) >= walk_every:
                st["walks"][seat] = now
                goal = residents.free_tile(world, cx, cy, 1) or (cx, cy)
                if residents.walk_to(world, pid, goal, limit=80) == 0:
                    r["tile"], r["anchor"] = [goal[0], goal[1]], [goal[0], goal[1]]  # no path: she is a mother, she gets there
                    world.dmb.people[pid]["position"] = [goal[0], goal[1]]
            continue
        r["anchor"] = [int(r["tile"][0]), int(r["tile"][1])]
        if now - int(st["accosts"].get(seat, -10**9)) < every:
            continue
        with party.at_seat(world, seat):
            from wizard_rts.narrative import conversation

            if conversation.table(world) or _busy(world):
                continue
            reply = conversation.talk(world, pid)
        if reply.get("status") != "ok":
            continue
        st["accosts"][seat] = now
        ledger.bump(world, "accosted", seat=seat)
        _announce(world, "conversation", seat=seat, reply=reply)


def _busy(world: Any) -> bool:
    from wizard_rts.narrative import campaign, duel_lease

    return duel_lease.active(world) is not None or campaign.active_scene(world) is not None or bool((world.__dict__.get("story") or {}).get("in_dungeon"))


def relationship(world: Any, seat: str) -> int:
    pid = pid_of(world, seat)
    if pid is None:
        return 0
    with party.as_player(world, seat):
        return checks.relationship(world, pid)
