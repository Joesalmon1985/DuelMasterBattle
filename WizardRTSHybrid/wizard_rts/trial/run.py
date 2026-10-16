"""The Trial of Champions on the host: one shared run per world, every wizard inside with a position of their own (plan section 3.6).

State: `world.narrative["trial"]`:
    gate        {"tile": [x, y], "settlement": sid}: a landmark on the world map a short walk from the home settlement, with the Rollkeeper beside it
    official    the Rollkeeper's person id (a resident, `trial_gate.json`)
    contestants the five of the book at the gate until a run begins (residents; their fates are run state)
    run         the live run or None: {id, started_ms, zones: {zid: {taken: [...], defeated: [...]}}, flags, throm, contestants, seats: {seat: ...}, bodies, ended}
    runs        how many runs there have been
    dead        apprentices who died in earlier runs: {retired seat: {zone, x, y, pockets, name}} (their bodies lie there for the next contestants)

Per wizard (`run["seats"][seat]`): zone, x, y, facing, pockets, gems, conditions, visited, inside. Shared: pickups taken (unique items are taken once),
creatures defeated, doors, flags, Throm's state, the other contestants' fates. A step is validated against the zone's rows and solid entities
(`trial/zones.py`); an exit entity moves the wizard to the next zone; interactions are explicit (`trial_interact`), choices too (`trial_choose`);
creatures are story Ward Duel leases (`trial/opponents.py`) resolved like any lease. Death inside the Trial lays the body where it fell, in the zone,
with the wizard's pockets; a living wizard resurrects beside it (`mortality.py` asks here). When every wizard in the run is dead the run ends: the
bodies and what they hold stay for the next contestants; traps, creatures and unheld unique items reset for the next run (decision D9).
"""

from __future__ import annotations

from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts.narrative import config, duel_lease, events, ledger, party, residents, wizard
from wizard_rts.trial import events as trial_events
from wizard_rts.trial import opponents, zones

ENTER_RANGE = 2
INTERACT_RANGE = 1
GATE_DISTANCE = (18, 30)
CONTESTANTS = [("knight", "Serra of the White Road", "knight"), ("elf", "An elven woman", "elf"), ("throm", "Throm", "throm"),
               ("barbarian2", "A second barbarian", "barbarian"), ("assassin", "A figure in black", "assassin")]
ITEM_NAMES = {"sukumvit_note": "Sukumvit's note and two gold pieces", "torch": "a dry torch", "vial": "a vial from the black book", "bone_ring": "a druidic bone ring",
              "bread": "the elf's bread", "charm": "the elf's vine-charm", "reed": "a hollow reed", "herbs": "bitter herbs", "gold": "the chest's gold",
              "glass_eye": "a green glass eye", "glass_diamond": "a glass diamond"}
MAX_POCKETS = 8


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("trial", {"gate": None, "official": "", "contestants": {}, "run": None, "runs": 0, "dead": {}})


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _announce(world: Any, kind: str, **data: Any) -> None:
    from wizard_rts.narrative import mortality

    mortality._announce(world, kind, **data)


def me(world: Any) -> str:
    from wizard_rts.narrative import mortality

    return mortality.me(world)


# ------------------------------------------------------------------ the gate on the map

def ensure_gate(world: Any) -> None:
    """Once the campaign's home settlement is known: a gate tile a short walk away (reachable over ground), the Rollkeeper and the contestants beside it."""
    from wizard_rts import workers
    from wizard_rts.narrative import tutorial

    st = state(world)
    if st["gate"] is not None:
        return
    sid = tutorial.state(world).get("settlement", "")
    rec = world.dmb.settlements.get(sid) if sid else None
    if rec is None:
        return
    hx, hy = int(rec["tile"][0]), int(rec["tile"][1])
    start = (int(world.player["tx"]), int(world.player["ty"]))
    best = None
    for dist in range(GATE_DISTANCE[0], GATE_DISTANCE[1] + 1, 2):
        for dx, dy in ((dist, 0), (0, dist), (dist, dist // 2), (dist // 2, dist), (-dist, 0), (0, -dist), (-dist, dist // 2), (dist // 2, -dist)):
            t = (hx + dx, hy + dy)
            if not world.tile_in_map(*t) or t in world.blocked or world.solid_for_wizard(t) or t in world.tree_tiles:
                continue
            path = workers.find_path(world, start, t, limit=120)
            if path:
                best = t
                break
        if best:
            break
    if best is None:
        events.log(world, "trial_gate_not_placed", why="no_reachable_tile")
        st["gate"] = {"tile": None, "settlement": sid}
        return
    st["gate"] = {"tile": [best[0], best[1]], "settlement": sid}
    tribe = world.faction_info.get(rec["faction"], {}).get("tribe", "barbarians")
    tile = residents.free_tile(world, best[0], best[1], 2)
    if tile is not None:
        st["official"] = residents.create(world, settlement=sid, role="official", graph="trial_gate", speaker="official", tile=tile, tribe=tribe, faction=rec["faction"], key="rollkeeper")
    taken = {tile} if tile else set()
    for cid, name, sprite in CONTESTANTS:
        t = residents.free_tile(world, best[0], best[1], 3, avoid=taken)
        if t is None:
            continue
        taken.add(t)
        pid = residents.create(world, settlement=sid, role="contestant", graph="trial_gate", speaker=cid, tile=t, tribe=tribe, faction="", key=f"contestant:{cid}")
        world.dmb.people[pid]["name"] = name
        world.dmb.people[pid]["display_name"] = name
        residents.table(world)[pid]["contestant"] = cid
        residents.table(world)[pid]["figure"] = f"contestant:{sprite}"
        st["contestants"][cid] = pid
    events.log(world, "trial_gate_placed", tile=list(best), official=st["official"])


def gate_tile(world: Any) -> tuple[int, int] | None:
    g = state(world).get("gate")
    return (int(g["tile"][0]), int(g["tile"][1])) if g and g.get("tile") else None


def entity_rows(world: Any) -> list[dict[str, Any]]:
    t = gate_tile(world)
    if t is None:
        return []
    run = state(world)["run"]
    return [{"id": "trial_gate", "class": "landmark", "kind": "trial_gate", "definition": "story.trial_gate", "faction": "", "faction_name": "",
             "label": "The Trial of Champions", "tx": t[0], "ty": t[1], "alive": True, "open": True, "run_live": bool(run and not run.get("ended")),
             "inside": 0 if not run else sum(1 for s in run["seats"].values() if s["inside"])}]


# ------------------------------------------------------------------ runs and seats

def run(world: Any) -> dict[str, Any] | None:
    return state(world)["run"]


def seat_rec(world: Any, seat: str | None = None) -> dict[str, Any] | None:
    r = run(world)
    if r is None:
        return None
    return r["seats"].get(seat if seat is not None else me(world))


def zone_distance(world: Any, a: str, b: str) -> int | None:
    """Manhattan distance between two wizards inside the Trial when they are in the same zone; None when either is outside or they are apart."""
    ra, rb = seat_rec(world, a), seat_rec(world, b)
    if ra is None or rb is None or not ra["inside"] or not rb["inside"] or ra["zone"] != rb["zone"]:
        return None
    return abs(int(ra["x"]) - int(rb["x"])) + abs(int(ra["y"]) - int(rb["y"]))


def inside(world: Any, seat: str | None = None) -> bool:
    s = seat_rec(world, seat)
    return bool(s and s["inside"])


def _new_run(world: Any) -> dict[str, Any]:
    st = state(world)
    st["runs"] += 1
    r = {"id": f"trial:{st['runs']}", "started_ms": _now(world), "zones": {}, "flags": {}, "throm": "ahead",
         "contestants": {cid: "ahead" for cid, _n, _s in CONTESTANTS}, "seats": {}, "bodies": {}, "ended": None}
    st["run"] = r
    for cid, pid in st["contestants"].items():  # they go in ahead of you, in the book's order; their fates are the run's
        if pid in residents.table(world) and residents.table(world)[pid]["status"] == "present":
            residents.remove(world, pid, "gone")
    events.log(world, "trial_run_started", run=r["id"])
    _announce(world, "trial_run_started", run=r["id"])
    return r


def _zone_state(r: dict[str, Any], zid: str) -> dict[str, Any]:
    return r["zones"].setdefault(zid, {"taken": [], "defeated": [], "doors": []})


def enter(world: Any) -> dict[str, Any]:
    """The wizard acting now walks through the gate: into the live run, or a new one when none is live."""
    from wizard_rts.narrative import campaign, mortality, mother

    seat = me(world)
    gate = gate_tile(world)
    if gate is None:
        return {"status": "rejected", "reason": "no_gate"}
    if campaign.over(world):
        return {"status": "rejected", "reason": "dead"}
    if inside(world, seat):
        return {"status": "rejected", "reason": "already_inside"}
    px, py = int(world.player["tx"]), int(world.player["ty"])
    if max(abs(px - gate[0]), abs(py - gate[1])) > ENTER_RANGE:
        return {"status": "rejected", "reason": "too_far"}
    if mother.is_grounded(world, seat):
        return {**mother.refusal(world, seat), "op": "trial_enter"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    r = run(world)
    if r is None or r.get("ended"):
        r = _new_run(world)
    rec = r["seats"].get(seat)
    if rec is None:
        rec = r["seats"][seat] = {"seat": seat, "zone": zones.ENTRY_ZONE, "x": zones.ENTRY_POS[0], "y": zones.ENTRY_POS[1], "facing": zones.ENTRY_FACING,
                                  "pockets": [], "gems": [], "conditions": [], "visited": [zones.ENTRY_ZONE], "inside": True, "entered_ms": _now(world), "steps": 0}
    else:
        rec.update(zone=zones.ENTRY_ZONE, x=zones.ENTRY_POS[0], y=zones.ENTRY_POS[1], facing=zones.ENTRY_FACING, inside=True)
    prepared = all(wizard.lesson_done(world, l) for l in config.get("tutorial", "essential", []))
    ledger.bump(world, "trial_entries", seat=seat)
    if not prepared:
        ledger.bump(world, "trial_entered_unprepared", seat=seat)
    events.log(world, "trial_entered", seat=seat, run=r["id"], prepared=prepared)
    _announce(world, "trial_entered", seat=seat, name=mortality.name_of(world, seat), run=r["id"])
    return {"status": "ok", "run": r["id"], "view": view(world)}


def leave(world: Any) -> dict[str, Any]:
    """Out through the entrance (only from the first zone's doorway): the wizard stands at the gate again. The run goes on without them."""
    seat = me(world)
    rec = seat_rec(world, seat)
    if rec is None or not rec["inside"]:
        return {"status": "rejected", "reason": "not_inside"}
    if not _at_door(rec):
        return {"status": "rejected", "reason": "not_at_the_door"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    rec["inside"] = False
    gate = gate_tile(world)
    if gate is not None:
        t = residents.free_tile(world, gate[0], gate[1], 2) or gate
        world.player.update(tx=int(t[0]), ty=int(t[1]), facing="down")
    events.log(world, "trial_left", seat=seat)
    return {"status": "ok", "left": True}


# ------------------------------------------------------------------ what a wizard sees

def _visible(world: Any, r: dict[str, Any], zid: str, e: dict[str, Any], rec: dict[str, Any]) -> bool:
    zs = _zone_state(r, zid)
    if e.get("requires_run_flag") and not r["flags"].get(e["requires_run_flag"]):
        return False
    if e.get("blocked_by_run_flag") and r["flags"].get(e["blocked_by_run_flag"]):
        return False
    if e.get("requires_defeated") and e["requires_defeated"] not in zs["defeated"]:
        return False
    if e.get("requires_spell") is not None and not wizard.knows(world, int(e["requires_spell"])):
        return False
    if e["kind"] == "pickup" and e["id"] in zs["taken"]:
        return False
    if e["kind"] in ("creature", "npc") and e["id"] in zs["defeated"]:
        return False
    if e["kind"] == "wizard":
        if e["id"] == "throm_arena" and r["throm"] in ("betrayed", "dead"):
            return False  # left at the pit, or already fallen: nobody to drag into the arena
        return bool(e.get("ported"))  # Throm's forced duel is; the legacy's rival wizard is not canon and not ported
    return True


def _text(r: dict[str, Any], e: dict[str, Any]) -> str:
    text = str(e.get("text", ""))
    for fl, variant in (e.get("text_run_flag") or {}).items():
        if r["flags"].get(fl):
            text = str(variant)
    return text


def _lines(r: dict[str, Any], e: dict[str, Any]) -> list[str]:
    lines = list(e.get("lines", []))
    for fl, variant in (e.get("lines_run_flag") or {}).items():
        if r["flags"].get(fl):
            lines = list(variant)
    return lines


def view(world: Any, seat: str | None = None) -> dict[str, Any]:
    from wizard_rts.narrative import mortality

    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return {}
    zid = rec["zone"]
    z = zones.zone(zid)
    ents = []
    for e in z["entities"]:
        if e["kind"] == "exit" or not _visible(world, r, zid, e, rec):
            continue
        ents.append({"id": e["id"], "kind": e["kind"], "pos": list(e["pos"]), "name": e.get("name", ""), "sprite": e.get("sprite", ""),
                     "enemy_id": e.get("enemy_id", ""), "marker": e.get("marker", ""), "facing": e.get("facing", "down"), "has_choice": bool(e.get("choice_event"))})
    others = []
    for s, o in sorted(r["seats"].items()):
        if s != rec["seat"] and o["inside"] and o["zone"] == zid:
            others.append({"id": s, "seat": s, "name": mortality.name_of(world, s), "x": o["x"], "y": o["y"], "facing": o["facing"], "dead": mortality.is_dead(world, s)})
    bodies = [{"seat": s, "name": b["name"], "x": b["x"], "y": b["y"], "pockets": list(b["pockets"])} for s, b in sorted(r["bodies"].items()) if b["zone"] == zid]
    bodies += [{"seat": s, "name": b["name"], "x": b["x"], "y": b["y"], "pockets": list(b["pockets"]), "old": True} for s, b in sorted(state(world)["dead"].items())
               if b["zone"] == zid and not s.startswith(r["id"] + ":")]  # this run's own dead are listed above, as themselves
    return {"run": r["id"], "zone": zid, "name": z["name"], "pos": [rec["x"], rec["y"]], "facing": rec["facing"], "entities": ents, "others": others, "bodies": bodies,
            "pockets": [{"id": i, "name": ITEM_NAMES.get(i, i)} for i in rec["pockets"]], "gems": list(rec["gems"]), "conditions": list(rec["conditions"]),
            "throm": r["throm"], "ended": r.get("ended"), "visited": list(rec["visited"]), "at_door": _at_door(rec)}


def _at_door(rec: dict[str, Any]) -> bool:
    """The way out: the doorway tiles of the first zone (the entry tile and its neighbours on the bottom rows)."""
    return rec["zone"] == zones.ENTRY_ZONE and int(rec["y"]) >= zones.ENTRY_POS[1] and abs(int(rec["x"]) - zones.ENTRY_POS[0]) <= 1


# ------------------------------------------------------------------ moving

def _occupied(world: Any, r: dict[str, Any], zid: str, x: int, y: int, except_seat: str) -> bool:
    for s, o in r["seats"].items():
        if s != except_seat and o["inside"] and o["zone"] == zid and o["x"] == x and o["y"] == y:
            return True
    for s, b in r["bodies"].items():
        if b["zone"] == zid and b["x"] == x and b["y"] == y:
            return True
    return False


def _exit_open(r: dict[str, Any], ex: dict[str, Any]) -> bool:
    if ex.get("requires_run_flag") and not r["flags"].get(ex["requires_run_flag"]):
        return False
    if ex.get("blocked_by_run_flag") and r["flags"].get(ex["blocked_by_run_flag"]):
        return False
    return True


def walkable(world: Any, r: dict[str, Any], zid: str, x: int, y: int, rec: dict[str, Any]) -> bool:
    if not zones.tile_walkable(zid, x, y):
        return False
    for e in zones.entities_at(zid, x, y):
        if e["kind"] in zones.SOLID_KINDS and _visible(world, r, zid, e, rec):
            return False
    return not _occupied(world, r, zid, x, y, rec["seat"])


def move(world: Any, dx: int, dy: int, facing: str | None = None) -> dict[str, Any]:
    from wizard_rts.narrative import campaign

    seat = me(world)
    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return {"status": "rejected", "reason": "not_inside"}
    if campaign.over(world):
        return {"status": "rejected", "reason": "dead"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    if abs(int(dx)) + abs(int(dy)) != 1:
        if facing in ("up", "down", "left", "right"):
            rec["facing"] = facing
            return {"status": "ok", "turned": True, "zone": rec["zone"], "pos": [rec["x"], rec["y"]]}
        return {"status": "rejected", "reason": "bad_step"}
    rec["facing"] = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}[(int(dx), int(dy))]
    zid = rec["zone"]
    nx, ny = int(rec["x"]) + int(dx), int(rec["y"]) + int(dy)
    exits = [ex for ex in zones.exits_at(zid, nx, ny) if _exit_open(r, ex)]
    if exits:
        ex = exits[0]
        to = str(ex["to_area"])
        if to not in zones.ported():
            return {"status": "rejected", "reason": "not_yet", "text": "The way on is dark and unfinished; the Trial has not opened it to you."}
        if zid == "dd_fork" and to == "dd_service":
            r["flags"]["fork_east_open"] = True  # the east loop reconnects (p.119, 56): the service tunnels' way back to the fork is open
        rec.update(zone=to, x=int(ex["to_pos"][0]), y=int(ex["to_pos"][1]), facing=str(ex.get("facing", rec["facing"])))
        rec["steps"] += 1
        if to not in rec["visited"]:
            rec["visited"].append(to)
            ledger.bump(world, "trial_zones_seen", seat=seat)
        events.log(world, "trial_zone", seat=seat, zone=to)
        return {"status": "ok", "zone": to, "pos": [rec["x"], rec["y"]], "changed_zone": True, "travel_text": str(ex.get("travel_text", "")), "view": view(world)}
    if not walkable(world, r, zid, nx, ny, rec):
        return {"status": "blocked", "zone": zid, "pos": [rec["x"], rec["y"]]}
    rec["x"], rec["y"] = nx, ny
    rec["steps"] += 1
    return {"status": "ok", "zone": zid, "pos": [nx, ny]}


# ------------------------------------------------------------------ interacting

def _adjacent(rec: dict[str, Any], e: dict[str, Any]) -> bool:
    return abs(int(rec["x"]) - int(e["pos"][0])) + abs(int(rec["y"]) - int(e["pos"][1])) <= INTERACT_RANGE


def _take(world: Any, r: dict[str, Any], rec: dict[str, Any], zid: str, e: dict[str, Any]) -> dict[str, Any]:
    zs = _zone_state(r, zid)
    grant = e.get("grant") or {}
    out: dict[str, Any] = {"status": "ok", "text": _text(r, e), "taken": e["id"]}
    item = e.get("item")
    if item:
        if len(rec["pockets"]) >= MAX_POCKETS:
            return {"status": "rejected", "reason": "pockets_full"}
        rec["pockets"].append(item)
        out["item"] = {"id": item, "name": ITEM_NAMES.get(item, item)}
    if grant.get("gem"):
        if grant["gem"] not in rec["gems"]:
            rec["gems"].append(grant["gem"])
        out["gem"] = grant["gem"]
    if grant.get("weave"):
        wizard.learn(world, [], int(grant["weave"]))
        out["weave"] = int(grant["weave"])
    if grant.get("spell") is not None:
        wizard.learn(world, [int(grant["spell"])])
        out["spell"] = int(grant["spell"])
    if grant.get("run_flag"):
        r["flags"][grant["run_flag"]] = True
    if e.get("set_flag"):
        r["flags"][e["set_flag"]] = True
    if e.get("clear_conditions"):
        rec["conditions"] = []
        wizard.wiz(world).pop("wounded", None)
        out["cleared"] = True
    if e.get("run_pickup") or e.get("item") or grant.get("gem"):
        zs["taken"].append(e["id"])  # unique: the other apprentice finds it gone (the aid box is the one exception: one each)
    r["flags"]["picked_" + e["id"]] = True
    ledger.bump(world, "trial_pickups", seat=rec["seat"])
    events.log(world, "trial_pickup", seat=rec["seat"], zone=zid, entity=e["id"])
    return out


def interact(world: Any, entity_id: str) -> dict[str, Any]:
    from wizard_rts.narrative import campaign

    seat = me(world)
    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return {"status": "rejected", "reason": "not_inside"}
    if campaign.over(world):
        return {"status": "rejected", "reason": "dead"}
    zid = rec["zone"]
    if entity_id.startswith("body:"):
        return _search_body(world, r, rec, zid, entity_id[len("body:"):])
    e = zones.entity(zid, entity_id)
    if e is None or e["kind"] == "exit" or not _visible(world, r, zid, e, rec):
        return {"status": "rejected", "reason": "no_such_entity"}
    if not _adjacent(rec, e):
        return {"status": "rejected", "reason": "too_far"}
    kind = e["kind"]
    if kind in ("sign", "logs", "corpse", "door"):
        out = {"status": "ok", "text": _text(r, e), "kind": kind}
        if e.get("choice_event"):  # the mirrors, the boulder's groove: a reading with a decision
            prompt = trial_events.EVENTS[e["choice_event"]](world, r, rec, None)
            out["event"] = e["choice_event"]
            out["prompt"] = prompt
        return out
    if kind == "pickup" and e.get("choice_first"):  # the false eye, the false diamond, the chest: the choice is the taking
        prompt = trial_events.EVENTS[e["choice_event"]](world, r, rec, None)
        return {"status": "ok", "kind": kind, "text": "", "event": e["choice_event"], "prompt": prompt}
    if kind == "pickup":
        if e["id"] == "aid_box" and e["id"] in _zone_state(r, zid)["taken"] and not r["flags"].get(f"aid_box:{seat}"):
            r["flags"][f"aid_box:{seat}"] = True  # one box per apprentice (the two-player rule): the second finds theirs beside it
            rec["pockets"].append("sukumvit_note") if len(rec["pockets"]) < MAX_POCKETS else None
            return {"status": "ok", "text": "A second box, beside the first, bears your own name. " + _text(r, e), "taken": e["id"], "item": {"id": "sukumvit_note", "name": ITEM_NAMES["sukumvit_note"]}}
        out = _take(world, r, rec, zid, e)
        if e["id"] == "aid_box":
            r["flags"][f"aid_box:{seat}"] = True
        if out.get("status") == "ok" and e.get("choice_event"):
            prompt = trial_events.EVENTS[e["choice_event"]](world, r, rec, None)
            out["event"] = e["choice_event"]
            out["prompt"] = prompt
        return out
    if kind == "npc":
        out = {"status": "ok", "kind": "npc", "name": e.get("name", ""), "lines": _lines(r, e)}
        if e.get("choice_event"):
            prompt = trial_events.EVENTS[e["choice_event"]](world, r, rec, None)
            out["event"] = e["choice_event"]
            out["prompt"] = prompt
            if prompt.get("fight"):
                return _fight_from_prompt(world, out, prompt)
        return out
    if kind == "wizard":  # Throm's forced duel: a person faced like a creature
        return fight(world, entity_id)
    if kind == "creature":
        return fight(world, entity_id)
    return {"status": "rejected", "reason": "nothing_to_do"}


def choose(world: Any, entity_id: str, choice: str) -> dict[str, Any]:
    seat = me(world)
    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return {"status": "rejected", "reason": "not_inside"}
    e = zones.entity(rec["zone"], entity_id)
    if e is None or not e.get("choice_event") or not _adjacent(rec, e):
        return {"status": "rejected", "reason": "no_such_entity"}
    out = trial_events.EVENTS[e["choice_event"]](world, r, rec, str(choice))
    if out.get("status") == "rejected":
        return out
    reply = {"status": "ok", "event": e["choice_event"], "prompt": out}
    if out.get("fight"):
        return _fight_from_prompt(world, reply, out)
    if out.get("champion"):
        _champion_exit(world, seat)
        reply["champion"] = True
    return reply


def _fight_from_prompt(world: Any, reply: dict[str, Any], prompt: dict[str, Any]) -> dict[str, Any]:
    """A choice began a duel (the false eye wakes the guardian, Ivy's thorns, the troglodytes' champion): the lease rides on the reply."""
    eid, enemy_id = prompt["fight"]
    f = fight(world, str(eid), enemy_id=str(enemy_id), comes_to_you=True)
    if f.get("status") not in ("started", "resolved"):
        return {**reply, "fight_refused": f.get("reason", "")}
    f["prompt"] = dict(prompt)
    f["intro"] = "\n\n".join(x for x in (str(prompt.get("text", "")), str(f.get("intro", ""))) if x)  # what the choice did, then the creature
    return f


def _champion_exit(world: Any, seat: str) -> None:
    """The door opened for `seat`: the Trial is over for this year. The champion walks out into daylight; everyone still inside is let out at the
    gate (the doors open); bodies and what they hold stay for the next run, which the next entrant begins."""
    from wizard_rts.narrative import mortality

    r = run(world)
    if r is None:
        return
    gate = gate_tile(world)
    for s, o in sorted(r["seats"].items()):
        if not o["inside"]:
            continue
        o["inside"] = False
        if gate is not None and not mortality.is_dead(world, s):
            t = residents.free_tile(world, gate[0], gate[1], 3) or gate
            with party.at_seat(world, s):
                world.player.update(tx=int(t[0]), ty=int(t[1]), facing="down")
    r["ended"] = {"why": "champion", "seat": seat, "game_ms": _now(world)}
    for s, b in r["bodies"].items():
        state(world)["dead"][f"{r['id']}:{s}"] = dict(b)
    events.log(world, "trial_run_ended", run=r["id"], why="champion", seat=seat)
    _announce(world, "trial_champion", seat=seat, name=mortality.name_of(world, seat), run=r["id"])
    _announce(world, "trial_run_ended", run=r["id"], why="champion")


def _search_body(world: Any, r: dict[str, Any], rec: dict[str, Any], zid: str, who: str) -> dict[str, Any]:
    body = r["bodies"].get(who) or state(world)["dead"].get(who)
    if body is None or body["zone"] != zid:
        return {"status": "rejected", "reason": "no_such_entity"}
    if abs(int(rec["x"]) - int(body["x"])) + abs(int(rec["y"]) - int(body["y"])) > INTERACT_RANGE:
        return {"status": "rejected", "reason": "too_far"}
    if who in r["bodies"]:
        return {"status": "ok", "text": f"{body['name']} lies here. " + ("Their pockets hold " + ", ".join(ITEM_NAMES.get(i, i) for i in body["pockets"]) + "." if body["pockets"] else "Their pockets are empty.") + " The weave of three can call them back, if you stand beside them and hold it."}
    taken = []
    for item in list(body["pockets"]):
        if len(rec["pockets"]) < MAX_POCKETS:
            rec["pockets"].append(item)
            body["pockets"].remove(item)
            taken.append(ITEM_NAMES.get(item, item))
    ledger.bump(world, "trial_bodies_searched", seat=rec["seat"])
    return {"status": "ok", "text": f"{body['name']}, an apprentice of this village, dead here some time. " + ("You take " + ", ".join(taken) + "." if taken else "There is nothing left to take."), "took": taken}


# ------------------------------------------------------------------ fighting

def _ban_for(world: Any, r: dict[str, Any], enemy_id: str) -> list[int]:
    """Colours the apprentice knows to be missing from a creature's Ward: the Bloodbeast's (the prisoner, the herbs), the Manticore's (the old man)."""
    if enemy_id == "bloodbeast" and (r["flags"].get("blood_weakness") or wizard.knows_fact(world, "bloodbeast_hates_vine")):
        return [trial_events.VINE]
    if enemy_id == "manticore" and wizard.knows_fact(world, "manticore_hates_light"):
        return [trial_events.LIGHT]
    return []


def fight(world: Any, entity_id: str, enemy_id: str | None = None, comes_to_you: bool = False) -> dict[str, Any]:
    seat = me(world)
    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return {"status": "rejected", "reason": "not_inside"}
    zid = rec["zone"]
    e = zones.entity(zid, entity_id)
    if e is None or not _visible(world, r, zid, e, rec) or (e["kind"] not in ("creature", "wizard") and not enemy_id):
        return {"status": "rejected", "reason": "no_such_entity"}
    if not comes_to_you and not _adjacent(rec, e):
        return {"status": "rejected", "reason": "too_far"}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    enemy_id = str(enemy_id or e["enemy_id"])
    sp = opponents.spec(enemy_id, wizard.combatant(world)["attack_pool"], ban=_ban_for(world, r, enemy_id))
    lease = duel_lease.begin(world, "trial:" + enemy_id, purpose=f"trial:{zid}:{entity_id}:{enemy_id}", display_name=sp["display_name"], spec=sp)
    if lease["status"] != "started":
        return {"status": "rejected", "reason": lease.get("reason", "no_lease")}
    party_rec = party.seats(world).get(seat, {})
    if seat and party_rec and not party_rec.get("human", True):
        from wizard_rts.narrative import autoduel

        report = autoduel.play_lease(world, lease["payload"]["duel"], seed=f"{seat}|{entity_id}")
        out = duel_lease.resolve(world, lease["payload"]["duel"]["id"], report)
        done = on_duel_resolved(world, lease["payload"]["duel"], out) if out.get("status") == "resolved" else {}
        return {"status": "resolved", "auto": True, "outcome": out.get("outcome"), **done}
    return {"status": "started", "duel_lease": lease, "intro": str(e.get("intro", "")), "lethal": sp["lethal"], "enemy": enemy_id, "name": sp["display_name"]}


def on_duel_resolved(world: Any, lease: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    from wizard_rts.narrative import mortality

    parts = str(lease["purpose"]).split(":", 3)
    _t, zid, eid = parts[0], parts[1], parts[2]
    seat = me(world)
    r = run(world)
    rec = seat_rec(world, seat)
    e = zones.entity(zid, eid)
    if r is None or rec is None or e is None:
        return {"trial": True, "gone": True}
    enemy = parts[3] if len(parts) > 3 else str(e.get("enemy_id", ""))
    if out.get("outcome") == "won":
        zs = _zone_state(r, zid)
        if eid not in zs["defeated"]:
            zs["defeated"].append(eid)
        if e.get("on_win_run_flag"):
            r["flags"][e["on_win_run_flag"]] = True
        if eid == "troll_lower1" and r["throm"] in ("uneasy_ally", "ahead"):
            r["throm"] = "wounded"  # Throm finishes his troll, wounded (authored, as the legacy had it)
        ledger.bump(world, "trial_wins", seat=seat)
        events.log(world, "trial_won", seat=seat, zone=zid, entity=eid, enemy=enemy)
        _announce(world, "trial_won", seat=seat, zone=zid, entity=eid, enemy=enemy)
        reply: dict[str, Any] = {"trial": True, "killed": True, "entity": eid}
        grant = e.get("grant_on_win") or {}
        if grant.get("spell") is not None:
            wizard.learn(world, [int(grant["spell"])])
            reply["spell"] = int(grant["spell"])
        if grant.get("weave"):
            wizard.learn(world, [], int(grant["weave"]))
            reply["weave"] = int(grant["weave"])
        if eid == "throm_arena":
            r["throm"] = "dead"
            r["contestants"]["throm"] = "dead"
            r["flags"]["trial_done"] = True
        if eid == "dd_trog_elder":
            r["flags"]["trog_beaten"] = True
        if eid == "dd_ivy":
            r["flags"]["ivy_paid"] = True
            r["flags"]["ivy_dead"] = True
        name = opponents.bestiary()[enemy]["display_name"] if enemy in opponents.bestiary() else enemy
        text = {"troll_lower1": "Your troll goes down. Throm finishes his, but his arm hangs wrong.\n\n\"Keep walking,\" he says. \"Don't look at it.\"\n\nSomething glints where your troll fell.",
                "fly_east": "The fly spins down into the dark, buzzing, and does not come up.", "dog_gal1": "The mastiff folds, silent to the end.",
                "boa_grotto1": "The snake loosens. The elven woman breathes, barely.",
                "throm_arena": "Throm falls. The delirium goes out of him like water, and for a moment he knows you.\n\n\"...Good fight, villager.\"\n\nThe Dwarf approaches with a loaded crossbow, and does not lower it. \"Only I know the way onward. West, when you're ready.\"",
                "dd_trog_elder": "Their champion falls. The tribe backs off, drumming: respect, or arithmetic.",
                "dd_ivy": "The thorns go slack. Ivy's last word is not a word.",
                "guard_idol2": "The second guardian comes apart in a storm of feathers. The emerald eye is yours to take.",
                "manticore_gate1": "The Manticore's Ward shatters. It looks at you with something like interest, and lets you pass.",
                "demon_mirror1": "The thing from the glass comes apart into silver. Something bright is left in the frame."}.get(eid, grant.get("text") or f"{name} is broken. The path is clearer.")
        if grant.get("text") and eid not in ("beast_blood1",):
            text = text + "\n\n" + str(grant["text"])
        elif grant.get("text"):
            text = str(grant["text"])
        reply["text"] = text
        return reply
    if out.get("outcome") == "draw" and out.get("broke"):  # both Wards broke in the same breath: nobody wins, nobody dies, the creature stays
        events.log(world, "trial_draw", seat=seat, zone=zid, entity=eid, enemy=enemy)
        return {"trial": True, "killed": False, "draw": True, "text": f"You break each other's Wards in the same breath. {opponents.bestiary()[enemy]['display_name']} backs off into the dark, and so do you.", "entity": eid}
    # a loss, or both ran dry: against a lethal creature the apprentice is finished either way
    lethal = enemy in opponents.LETHAL
    if lethal:
        mortality.die(world, seat, f"trial:{enemy}", by=enemy, terminal=False)
        events.log(world, "trial_lost", seat=seat, zone=zid, entity=eid, enemy=enemy, lethal=True)
        return {"trial": True, "killed": False, "dead": True, "text": f"{opponents.bestiary()[enemy]['display_name']} does not have to finish you. It does anyway.", "entity": eid}
    trial_events.wound(world, rec, enemy)
    events.log(world, "trial_lost", seat=seat, zone=zid, entity=eid, enemy=enemy, lethal=False)
    return {"trial": True, "killed": False, "wounded": True, "text": f"You get clear of {opponents.bestiary()[enemy]['display_name'].lower()} with a wound to show for it: one cast fewer in your next duel.", "entity": eid}


# ------------------------------------------------------------------ death and resurrection inside

def on_death(world: Any, seat: str) -> bool:
    """A wizard died inside the Trial: the body lies in the zone with their pockets (mortality.py asks here first). True when taken."""
    from wizard_rts.narrative import mortality

    r = run(world)
    rec = seat_rec(world, seat)
    if r is None or rec is None or not rec["inside"]:
        return False
    r["bodies"][seat] = {"zone": rec["zone"], "x": rec["x"], "y": rec["y"], "pockets": list(rec["pockets"]), "name": mortality.name_of(world, seat), "gems": list(rec["gems"])}
    rec["pockets"] = []
    _announce(world, "trial_death", seat=seat, zone=rec["zone"], x=rec["x"], y=rec["y"])
    _check_run_end(world)
    return True


def body_of(world: Any, seat: str) -> dict[str, Any] | None:
    r = run(world)
    return r["bodies"].get(seat) if r else None


def resurrect_distance(world: Any, caster: str, target: str) -> int | None:
    """Manhattan distance from the caster to the target's body when both are in the same zone, else None (too far by definition)."""
    body = body_of(world, target)
    rec = seat_rec(world, caster)
    if body is None or rec is None or not rec["inside"] or rec["zone"] != body["zone"]:
        return None
    return abs(int(rec["x"]) - int(body["x"])) + abs(int(rec["y"]) - int(body["y"]))


def on_resurrected(world: Any, seat: str) -> bool:
    r = run(world)
    rec = seat_rec(world, seat)
    body = r["bodies"].pop(seat, None) if r else None
    if body is None or rec is None:
        return False
    rec.update(zone=body["zone"], x=body["x"], y=body["y"], inside=True, pockets=list(body["pockets"]), gems=list(body["gems"]))
    return True


def _check_run_end(world: Any) -> None:
    from wizard_rts.narrative import mortality

    r = run(world)
    if r is None or r.get("ended"):
        return
    inside_seats = [s for s, o in r["seats"].items() if o["inside"]]
    if inside_seats and all(mortality.is_dead(world, s) for s in inside_seats):
        r["ended"] = {"why": "all_dead", "game_ms": _now(world)}
        for s, b in r["bodies"].items():
            state(world)["dead"][f"{r['id']}:{s}"] = dict(b)
        events.log(world, "trial_run_ended", run=r["id"], why="all_dead")
        _announce(world, "trial_run_ended", run=r["id"], why="all_dead")


def rename_seat(world: Any, old: str, new: str) -> None:
    r = run(world)
    if r is None:
        return
    if old in r["seats"]:
        r["seats"][new] = r["seats"].pop(old)
        r["seats"][new]["seat"] = new
    if old in r["bodies"]:
        r["bodies"][new] = r["bodies"].pop(old)


def tick(world: Any) -> None:
    from wizard_rts.narrative import tutorial

    if not tutorial.state(world).get("started"):
        return
    ensure_gate(world)
    _check_run_end(world)


def snapshot(world: Any) -> dict[str, Any]:
    r = run(world)
    rec = seat_rec(world)
    return {"gate": state(world).get("gate"), "run": r["id"] if r else "", "inside": bool(rec and rec["inside"]), "zone": rec["zone"] if rec and rec["inside"] else "",
            "ended": bool(r and r.get("ended"))}
