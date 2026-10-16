"""Mortal apprentices: death, the body, resurrection, and who is alive (plan section 3.2).

A wizard who loses a duel to the death (another apprentice, the stranger, the Trial's monsters) dies: the seat's `fate` records it, a **body**
lies on the tile as a resident row (`role: body`, status `dead`, drawn as a body, inspectable, holding the wizard's Trial pockets later), a tombstone
is written, and the behaviour ledger and the mother are told. The dead wizard is refused every action but looking (`net/session.py`), and spectates.

**Resurrection** is an action in the world: a living wizard standing within `resurrect_range` tiles of the body channels for `resurrect_ms` of game
time (`resurrect_begin`, completed by `tick`); walking away or dying abandons it. When it completes the body is gone, the fate cleared, and the wizard
stands where the body lay with everything that was theirs (spells, weave, relationships, pockets). There is no remote resurrection and no menu for it.

**Endings** are the session's business (`session.ending`): a private session ends when its human is dead, a shared one when every human is; the
world is saved with the bodies in it. `terminal` on a fate marks a death the session has declared final (the classic single-process server, which has
no session, marks it at once). Everything here uses game time and sorted iteration and writes nothing to `world.events`.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts.narrative import config, events, ledger, party, residents, wizard

BODY_ROLE = "body"


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("mortality", {"bodies": {}, "channels": {}, "announce": [], "deaths": 0})


def me(world: Any) -> str:
    """The seat acting now, as a party key: the host's seat id when a party exists, else the host marker ``""``."""
    seat = party.current(world)
    if seat:
        return seat
    return party.party(world)["host"] if "narrative" in world.__dict__ and party.order(world) else party.HOST


def _seat_exists(world: Any, seat: str) -> bool:
    return seat == party.HOST or seat in party.seats(world)


def rename_seat(world: Any, old: str, new: str) -> None:
    """A seat was retired (`party.retire`): its body, channel and counts now belong to the retired key."""
    st = state(world)
    if old in st["bodies"]:
        pid = st["bodies"].pop(old)
        st["bodies"][new] = pid
        r = residents.table(world).get(pid)
        if r is not None:
            r["seat"], r["key"] = new, f"body:{new}"
    if old in st["channels"]:
        st["channels"][new] = st["channels"].pop(old)
    for ch in st["channels"].values():
        if ch.get("target") == old:
            ch["target"] = new


def fate_of(world: Any, seat: str) -> dict[str, Any] | None:
    if "narrative" not in world.__dict__ or not _seat_exists(world, seat):
        return None
    with party.as_player(world, seat):
        f = wizard.wiz(world).get("fate")
    return dict(f) if f else None


def is_dead(world: Any, seat: str) -> bool:
    f = fate_of(world, seat)
    return bool(f) and not f.get("alive", True)


def body_of(world: Any, seat: str) -> str | None:
    pid = state(world)["bodies"].get(str(seat))
    return pid if pid and pid in residents.table(world) else None


def seat_of_body(world: Any, pid: str) -> str | None:
    for seat, body in sorted(state(world)["bodies"].items()):
        if body == pid:
            return seat
    return None


def _pose_rec(world: Any, seat: str) -> dict[str, Any]:
    rec = world.players.get(seat) if getattr(world, "players", None) and seat else None
    return rec if rec is not None else world.player


def name_of(world: Any, seat: str) -> str:
    rec = _pose_rec(world, seat)
    if rec is not None and rec.get("name"):
        return str(rec["name"])
    return str(party.seats(world).get(seat, {}).get("name") or "the apprentice")


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _announce(world: Any, kind: str, **data: Any) -> None:
    """Something the clients should hear about (the session turns these into notices for every link)."""
    st = state(world)
    st["announce"].append({"kind": kind, "game_ms": _now(world), **data})
    del st["announce"][:-40]


def drain_announcements(world: Any) -> list[dict[str, Any]]:
    st = state(world)
    out = list(st["announce"])
    st["announce"].clear()
    return out


# ------------------------------------------------------------------ dying

def die(world: Any, seat: str, cause: str, *, by: str = "", terminal: bool | None = None) -> dict[str, Any]:
    """`seat` dies of `cause` (killed by `by`, a seat id or a person id, when there was a killer). Idempotent. Returns what happened."""
    if "narrative" not in world.__dict__:
        return {"status": "rejected", "reason": "no_narrative"}
    if is_dead(world, seat):
        return {"status": "ok", "already": True, "seat": seat}
    if terminal is None:
        terminal = not party.multi(world)  # alone and without a session (the classic server): nobody can bring this wizard back
    st = state(world)
    rec = _pose_rec(world, seat)
    tile = (int(rec["tx"]), int(rec["ty"]))
    with party.at_seat(world, seat):
        from wizard_rts.narrative import conversation, duel_lease

        conversation.end(world, None, "death")
        lease = duel_lease.active(world)
        if lease is not None and lease["purpose"] != duel_lease.LETHAL:
            duel_lease.abandon(world, "death")
        w = wizard.wiz(world)
        w["fate"] = {"alive": False, "cause": cause, "by": by, "game_ms": _now(world), "tile": list(tile), "terminal": bool(terminal),
                     "text": config.get("campaign", "dead_after_defeat", "The apprentice was defeated.")}
        w["deaths"] = int(w.get("deaths", 0)) + 1
        actor = party.actor(world)
    pid = _lay_body(world, seat, tile, cause)
    world.dmb.tombstones[actor] = {"kind": "wizard", "display_name": name_of(world, seat), "cause_id": cause, "profile_refs": {}, "body": pid}
    st["deaths"] = int(st["deaths"]) + 1
    events.log(world, "wizard_died", seat=seat, cause=cause, by=by, tile=list(tile), body=pid)
    ledger.bump(world, "deaths", seat=seat)
    ledger.note(world, "death", seat=seat, cause=cause, by=by)
    if by and _seat_exists(world, by):
        ledger.bump(world, "kills", seat=by)
    _announce(world, "wizard_died", seat=seat, name=name_of(world, seat), by=by, tile=list(tile), cause=cause)
    from wizard_rts.narrative import mother

    mother.on_death(world, seat, by, tile)
    return {"status": "ok", "seat": seat, "body": pid, "tile": list(tile), "terminal": bool(terminal)}


def _lay_body(world: Any, seat: str, tile: tuple[int, int], cause: str) -> str:
    """The body: a resident row that is dead from the start, with a Person so it can be named, inspected and mourned."""
    from wizard_rts.narrative import tutorial

    st = state(world)
    old = st["bodies"].get(str(seat))
    if old and old in residents.table(world):  # a second death while an old body row somehow survived: reuse it
        r = residents.table(world)[old]
        r["tile"], r["anchor"], r["status"] = [tile[0], tile[1]], [tile[0], tile[1]], "dead"
        return old
    settlement = tutorial.state(world).get("settlement", "")
    name = name_of(world, seat)
    person = PeopleService(world.dmb).create_person(name=name, role="villager", affiliation="", area_id="hybrid.world", position=[int(tile[0]), int(tile[1])])
    pid = person["id"]
    rec = world.dmb.people[pid]
    rec["identity"] = {"given": name, "family": "", "name": name, "tribe": ""}
    rec["link"] = {"kind": "resident", "id": pid, "building": "", "role": BODY_ROLE, "settlement": settlement}
    PeopleService(world.dmb).record_death(pid, cause_id=cause)
    avatar = str(_pose_rec(world, seat).get("avatar", "") or "")
    residents.table(world)[pid] = {"tile": [int(tile[0]), int(tile[1])], "anchor": [int(tile[0]), int(tile[1])], "settlement": settlement, "role": BODY_ROLE,
                                   "tribe": "", "faction": "", "graph": "", "speaker": "", "status": "dead", "next_beat_ms": 0, "expires_ms": None,
                                   "key": f"body:{seat}", "seat": str(seat), "avatar": avatar, "figure": "wizard_body"}
    st["bodies"][str(seat)] = pid
    return pid


# ------------------------------------------------------------------ resurrection

def resurrect_ms() -> int:
    return int(config.get("mortality", "resurrect_ms", 6000))


def resurrect_range() -> int:
    return int(config.get("mortality", "resurrect_range", 2))


def _target_seat(world: Any, target: str) -> str | None:
    if target in state(world)["bodies"]:
        return target
    return seat_of_body(world, target)


def channel_of(world: Any, caster: str) -> dict[str, Any] | None:
    ch = state(world)["channels"].get(str(caster))
    return dict(ch) if ch else None


def channel_view(world: Any, caster: str) -> dict[str, Any]:
    ch = state(world)["channels"].get(str(caster))
    if not ch:
        return {}
    return {"target": ch["target"], "name": name_of(world, ch["target"]), "left_ms": max(0, int(ch["until_ms"]) - _now(world)),
            "total_ms": int(ch["until_ms"]) - int(ch["started_ms"]), "tile": list(ch["tile"])}


def resurrect_begin(world: Any, caster: str, target: str) -> dict[str, Any]:
    """`caster` (a living wizard) starts bringing `target` (a seat id or its body's person id) back. The channel runs on game time (`tick`)."""
    if "narrative" not in world.__dict__:
        return {"status": "rejected", "reason": "no_narrative"}
    if is_dead(world, caster):
        return {"status": "rejected", "reason": "dead"}
    seat = _target_seat(world, str(target))
    if seat is None or not is_dead(world, seat):
        return {"status": "rejected", "reason": "no_body"}
    pid = body_of(world, seat)
    if pid is None:
        return {"status": "rejected", "reason": "no_body"}
    if str(caster) in state(world)["channels"]:
        return {"status": "rejected", "reason": "already_channelling"}
    body = residents.table(world)[pid]
    me_rec = _pose_rec(world, caster)
    dist = abs(int(me_rec["tx"]) - int(body["tile"][0])) + abs(int(me_rec["ty"]) - int(body["tile"][1]))
    if dist > resurrect_range():
        return {"status": "rejected", "reason": "too_far", "distance": dist, "range": resurrect_range()}
    now = _now(world)
    state(world)["channels"][str(caster)] = {"target": seat, "body": pid, "started_ms": now, "until_ms": now + resurrect_ms(), "tile": list(body["tile"])}
    events.log(world, "resurrection_started", by=caster, seat=seat)
    _announce(world, "resurrection_started", by=caster, by_name=name_of(world, caster), seat=seat, name=name_of(world, seat), tile=list(body["tile"]), ms=resurrect_ms())
    return {"status": "started", "target": seat, "until_ms": now + resurrect_ms(), "ms": resurrect_ms(), "tile": list(body["tile"])}


def _complete(world: Any, caster: str, ch: dict[str, Any]) -> None:
    seat, pid = ch["target"], ch["body"]
    body = residents.table(world).pop(pid, None)
    tile = tuple(body["tile"]) if body else tuple(ch["tile"])
    world.dmb.people.pop(pid, None)
    world.dmb.tombstones.pop(pid, None)
    with party.at_seat(world, seat):
        w = wizard.wiz(world)
        w.pop("fate", None)
        w["resurrections"] = int(w.get("resurrections", 0)) + 1
        world.dmb.tombstones.pop(party.actor(world), None)
    state(world)["bodies"].pop(str(seat), None)
    rec = _pose_rec(world, seat)
    rec.update(tx=int(tile[0]), ty=int(tile[1]), facing="down")
    events.log(world, "wizard_resurrected", seat=seat, by=caster, tile=list(tile))
    ledger.bump(world, "resurrections", seat=caster)
    ledger.note(world, "resurrection", seat=seat, by=caster)
    _announce(world, "wizard_resurrected", seat=seat, name=name_of(world, seat), by=caster, by_name=name_of(world, caster), tile=list(tile))
    from wizard_rts.narrative import mother

    mother.on_resurrected(world, seat, caster)


def abandon(world: Any, caster: str, why: str) -> bool:
    ch = state(world)["channels"].pop(str(caster), None)
    if ch is None:
        return False
    events.log(world, "resurrection_abandoned", by=caster, seat=ch["target"], why=why)
    _announce(world, "resurrection_abandoned", by=caster, seat=ch["target"], why=why)
    return True


def _free_tile_for_body(world: Any, tile: tuple[int, int]) -> tuple[int, int] | None:
    for radius in (1, 2, 3, 4):
        t = residents.free_tile(world, tile[0], tile[1], radius)
        if t is not None:
            return t
    return None


def relocate_blocked_bodies(world: Any) -> int:
    """A body must always be reachable: one that ends up under a building, a standing tree or a rock is moved to the nearest free tile."""
    moved = 0
    for seat, pid in sorted(state(world)["bodies"].items()):
        r = residents.table(world).get(pid)
        if r is None:
            continue
        t = (int(r["tile"][0]), int(r["tile"][1]))
        if t in world.blocked or world.solid_for_wizard(t) or not world.tile_in_map(*t):
            nt = _free_tile_for_body(world, t)
            if nt is not None:
                r["tile"], r["anchor"] = [nt[0], nt[1]], [nt[0], nt[1]]
                world.dmb.people[pid]["position"] = [nt[0], nt[1]]
                events.log(world, "body_moved", seat=seat, frm=list(t), to=list(nt))
                moved += 1
    return moved


def tick(world: Any) -> None:
    """Once a game second: channels complete or are abandoned; bodies stay reachable."""
    st = state(world)
    now = _now(world)
    for caster, ch in sorted(st["channels"].items()):
        if is_dead(world, caster) or ch["body"] not in residents.table(world) or not is_dead(world, ch["target"]):
            abandon(world, caster, "gone")
            continue
        body = residents.table(world)[ch["body"]]
        me_rec = _pose_rec(world, caster)
        dist = abs(int(me_rec["tx"]) - int(body["tile"][0])) + abs(int(me_rec["ty"]) - int(body["tile"][1]))
        if dist > resurrect_range():
            abandon(world, caster, "walked_away")
            continue
        if now >= int(ch["until_ms"]):
            st["channels"].pop(caster, None)
            _complete(world, caster, ch)
    if now % 5000 < 1000:
        relocate_blocked_bodies(world)


# ------------------------------------------------------------------ who is alive

def humans_alive(world: Any) -> list[str]:
    return [s for s in party.humans(world) if not is_dead(world, s)]


def all_humans_dead(world: Any) -> bool:
    humans = party.humans(world)
    return bool(humans) and not humans_alive(world)


def mark_terminal(world: Any, seat: str) -> None:
    """The session has declared this death final (the game ended for this wizard)."""
    if not _seat_exists(world, seat):
        return
    with party.as_player(world, seat):
        f = wizard.wiz(world).get("fate")
        if f:
            f["terminal"] = True
