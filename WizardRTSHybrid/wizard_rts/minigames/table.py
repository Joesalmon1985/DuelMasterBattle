"""A game at a conversation (plan section 2.1): one table per apprentice seat, opened by a `game:<id>` choice, played by `minigame_act`, closed by
`minigame_leave`, by the conversation ending, or at the result.

The table lives in `world.narrative["minigames"][seat]` (a JSON dict, saved with the world; a loaded world drops it, because the host is no longer
held). The bots' seats are played here, between the human's moves, until it is the human's turn or the game is over. Nothing in the world changes
because of a game: one `events.log` entry and a line in the journal's Games page, that is all (owner's brief: no reward for winning or losing).
"""

from __future__ import annotations

import zlib
from typing import Any

from wizard_rts.minigames import base, catalogue
from wizard_rts.narrative import events

BOT_CAP = 400  # moves the bots may make in a row before the table gives up (a stuck engine never loops the host)


def _store(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("minigames", {"tables": {}, "played": [], "found": []})


def _seat(world: Any) -> str:
    from wizard_rts.narrative import mortality

    return str(mortality.me(world))


def active(world: Any) -> dict[str, Any] | None:
    """The table of the seat acting now, or None."""
    if "narrative" not in world.__dict__:
        return None
    return _store(world)["tables"].get(_seat(world))


def is_open(world: Any) -> bool:
    return active(world) is not None


def _run_bots(game: str, state: dict[str, Any]) -> None:
    eng = catalogue.engine(game)
    for _ in range(BOT_CAP):
        if state["over"] or eng.actions(state, 0):
            return
        moved = False
        for seat in range(1, len(state["seats"])):
            if eng.actions(state, seat):
                r = base.rng(state, f"bot:{seat}")
                eng.act(state, seat, eng.bot(state, seat, r))
                moved = True
                break
        if not moved:
            return  # nobody can move: the engine should have ended the game; the view says so


def begin(world: Any, sp: dict[str, Any], game_id: str) -> dict[str, Any]:
    """Lay out `game_id` at the conversation with `sp`. Returns the table's first view (the reply's `minigame` extra)."""
    g = catalogue.entry(game_id)
    if g is None or not catalogue.playable(game_id):
        return {"status": "rejected", "reason": "no_such_game"}
    store = _store(world)
    seat = _seat(world)
    store["tables"].pop(seat, None)
    n = len(store["played"]) + 1
    seed = zlib.crc32(f"{world.seed}|{game_id}|{seat}|{n}".encode())
    host_name = world.dmb.people[sp["pid"]]["name"]
    opts = {**g.get("opts", {}), **catalogue.skin_for(g, sp), "host": host_name}
    eng = catalogue.engine(game_id)
    if hasattr(eng, "prepare"):  # an engine that reads the world as the table is laid (Guess Who takes the village's people)
        opts = eng.prepare(world, sp, opts)
    state = eng.new(seed, opts)
    _run_bots(game_id, state)
    store["tables"][seat] = {"game": game_id, "npc": sp["key"], "pid": sp["pid"], "host": host_name, "state": state,
                            "started_ms": int(world.dmb.clock.get("game_ms", 0)), "title": g["title"]}
    if game_id not in store["found"]:
        store["found"].append(game_id)
    events.log(world, "minigame_begun", game=game_id, host=sp["pid"], seat=seat)
    return view(world)


def view(world: Any) -> dict[str, Any]:
    t = active(world)
    if t is None:
        return {"status": "rejected", "reason": "no_table"}
    v = catalogue.engine(t["game"]).view(t["state"], 0)
    return {"status": "ok", "game": t["game"], "npc": t["npc"], "host": t["host"], "catalogue_title": t["title"], "view": v}


def act(world: Any, action: dict[str, Any]) -> dict[str, Any]:
    t = active(world)
    if t is None:
        return {"status": "rejected", "reason": "no_table"}
    state = t["state"]
    if state["over"]:
        return {**view(world), "status": "rejected", "reason": "finished"}
    eng = catalogue.engine(t["game"])
    try:
        eng.act(state, 0, dict(action))
    except base.Illegal as exc:
        return {**view(world), "status": "rejected", "reason": "illegal", "detail": str(exc)}
    _run_bots(t["game"], state)
    if state["over"]:
        _record(world, t)
    return view(world)


def _record(world: Any, t: dict[str, Any]) -> None:
    if t.get("recorded"):
        return
    t["recorded"] = True
    rec = {"game": t["game"], "host": t["host"], "result": t["state"]["result"], "moves": int(t["state"]["moves"]), "game_ms": int(world.dmb.clock.get("game_ms", 0))}
    _store(world)["played"].append(rec)
    del _store(world)["played"][:-200]
    events.log(world, "minigame_played", seat=_seat(world), **rec)


def leave(world: Any) -> dict[str, Any]:
    """Close the table. Returns what happened: the game, whether it was finished, the result ("" when abandoned)."""
    t = active(world)
    if t is None:
        return {"status": "rejected", "reason": "no_table"}
    finished = bool(t["state"]["over"])
    if not finished:
        events.log(world, "minigame_abandoned", game=t["game"], host=t["host"], moves=int(t["state"]["moves"]))
    _store(world)["tables"].pop(_seat(world), None)
    return {"status": "ok", "game": t["game"], "npc": t["npc"], "finished": finished, "result": t["state"]["result"] if finished else "", "title": t["title"]}


def on_conversation_end(world: Any, key: str) -> None:
    """The conversation the table belongs to ended (walked away, idle, the person removed): the table goes with it, for every seat."""
    if "narrative" not in world.__dict__:
        return
    tables = _store(world)["tables"]
    for seat in [s for s, t in tables.items() if t.get("npc") == key]:
        t = tables.pop(seat)
        if not t["state"]["over"]:
            events.log(world, "minigame_abandoned", game=t["game"], host=t["host"], moves=int(t["state"]["moves"]), why="conversation_ended")


def drop_all(world: Any) -> None:
    """A loaded save: nobody is held, so no table is open."""
    if "narrative" in world.__dict__:
        _store(world)["tables"].clear()


def journal(world: Any) -> dict[str, Any]:
    """The journal's Games page: the games found so far (their villagers' names) and the last results."""
    if "narrative" not in world.__dict__:
        return {}
    s = _store(world)
    found = [{"id": gid, "title": (catalogue.entry(gid) or {}).get("title", gid), "game": (catalogue.entry(gid) or {}).get("game", gid)} for gid in s["found"]]
    return {"found": found, "played": list(s["played"][-12:]), "all": [{"id": g["id"], "title": g["title"], "game": g.get("game", g["id"]), "where": g.get("where", "")}
                                                                        for g in catalogue.entries() if catalogue.playable(g["id"])]}
