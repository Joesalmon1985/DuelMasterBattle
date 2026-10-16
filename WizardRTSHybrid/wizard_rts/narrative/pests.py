"""The Central Warehouse's infestation: the "rats" (plan section 3.5, the brief's scenario C).

An infestation is a handful of narrative pests (resident rows, role `pest`, hostile, drawn with the imported Mindustry crawler and dagger sprites at a
small scale: nothing is added to the entity roster, D33) that live around the home settlement's warehouse and eat its food wares one at a time
(`economy.move_good` into the `narrative:eaten` bin, so the ware ledger still balances). Each pest is fought through a story Ward Duel lease
(`opponent.rat`, `opponent.rat_big`: brief by configuration, their Wards drawn from two colours), opened by `pest_fight` when a wizard stands beside it;
a verified win removes the pest with a visible break, a loss wounds the apprentice (one cast fewer in their next duel) and the rat scurries off. Two
wizards may fight at once; an AI wizard's duel is played on the Python core (`autoduel`) and verified the same way. The warehouse keeper (a resident,
`warehouse.json`) reads the facts here: pests left, who killed what, wares eaten, duels fought since the complaint, whether the warehouse was burned,
and whether the apprentices cooperated. When the last pest is gone the keeper reacts; after `return_ms` a smaller wave comes back, so the village stays alive.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts import economy
from wizard_rts.narrative import config, duel_lease, events, ledger, party, residents

ROLE = "pest"
KEEPER = "keeper"
GRAPH = "warehouse"
FOOD = ("ration", "bread", "meat", "fish", "grain", "flour", "fruit", "honey")
EATEN_BIN = "narrative:eaten"
FIGHT_RANGE = 2  # tiles (Manhattan); must equal wizard_labels.gd PEST_RANGE
RADIUS = 3


def settings() -> dict[str, Any]:
    return {"count": int(config.get("pests", "count", 5)), "eat_every_ms": int(config.get("pests", "eat_every_ms", 30000)),
            "return_ms": int(config.get("pests", "return_ms", 1200000)), "return_count": int(config.get("pests", "return_count", 3)),
            "max_waves": int(config.get("pests", "max_waves", 6))}


def state(world: Any) -> dict[str, Any]:
    return world.narrative.setdefault("pests", {"infestations": {}, "keepers": {}, "counter": 0, "next_eat_ms": 0, "announce": []})


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _announce(world: Any, kind: str, **data: Any) -> None:
    from wizard_rts.narrative import mortality

    mortality._announce(world, kind, **data)


def home(world: Any) -> tuple[str, dict[str, Any]] | None:
    """(settlement id, warehouse building) of the campaign's home settlement."""
    from wizard_rts.narrative import tutorial

    sid = tutorial.state(world).get("settlement", "")
    rec = world.dmb.settlements.get(sid) if sid else None
    b = world.buildings.get(rec["centre"]) if rec else None
    if b is None or b.get("kind") != "warehouse" or int(b.get("hp", 1)) <= 0:
        return None
    return sid, b


def live(world: Any, sid: str | None = None) -> dict[str, Any] | None:
    for iid, inf in sorted(state(world)["infestations"].items()):
        if inf["cleared_ms"] is None and (sid is None or inf["settlement"] == sid):
            return inf
    return None


def latest(world: Any, sid: str) -> dict[str, Any] | None:
    best = None
    for iid, inf in sorted(state(world)["infestations"].items()):
        if inf["settlement"] == sid and (best is None or int(inf["started_ms"]) > int(best["started_ms"])):
            best = inf
    return best


def pests_of(world: Any, inf: dict[str, Any]) -> list[str]:
    return [pid for pid in inf["pests"] if residents.table(world).get(pid, {}).get("status") == "present"]


def is_pest(world: Any, pid: str) -> bool:
    r = residents.table(world).get(pid)
    return bool(r) and r["role"] == ROLE and r["status"] == "present"


# ------------------------------------------------------------------ casting

def ensure_keeper(world: Any, sid: str, b: dict[str, Any]) -> str | None:
    st = state(world)
    pid = st["keepers"].get(sid)
    if pid and residents.table(world).get(pid, {}).get("status") == "present":
        return pid
    tile = residents.free_tile(world, int(b["tx"]) + 1, int(b["ty"]) + 1, 3)
    if tile is None:
        return None
    tribe = world.faction_info.get(b["faction_name"], {}).get("tribe", "barbarians")
    pid = residents.create(world, settlement=sid, role=KEEPER, graph=GRAPH, speaker=KEEPER, tile=tile, tribe=tribe, faction=b["faction_name"], key=f"keeper:{sid}")
    residents.table(world)[pid]["anchor"] = [int(b["tx"]) + 1, int(b["ty"]) + 1]
    st["keepers"][sid] = pid
    events.log(world, "keeper_cast", settlement=sid, person=pid)
    return pid


def cast(world: Any, sid: str, b: dict[str, Any], count: int) -> str | None:
    st = state(world)
    st["counter"] += 1
    iid = f"pests:{sid}:{st['counter']}"
    pests: list[str] = []
    taken: set[tuple[int, int]] = set()
    for i in range(count):
        tile = residents.free_tile(world, int(b["tx"]), int(b["ty"]), RADIUS, avoid=taken)
        if tile is None:
            break
        taken.add(tile)
        big = i == 0
        person = PeopleService(world.dmb).create_person(name="Big rat" if big else "Rat", role="villager", affiliation="", area_id="hybrid.world", position=[tile[0], tile[1]])
        pid = person["id"]
        world.dmb.people[pid]["identity"] = {"given": "Rat", "family": "", "name": "Big rat" if big else "Rat", "tribe": ""}
        world.dmb.people[pid]["link"] = {"kind": "resident", "id": pid, "building": b["id"], "role": ROLE, "settlement": sid}
        residents.table(world)[pid] = {"tile": [tile[0], tile[1]], "anchor": [int(b["tx"]), int(b["ty"])], "settlement": sid, "role": ROLE, "tribe": "", "faction": "",
                                       "graph": "", "speaker": "", "status": "present", "next_beat_ms": 0, "expires_ms": None, "key": f"pest:{iid}:{i}",
                                       "hostile": True, "pest": {"size": "big" if big else "small", "inf": iid}, "figure": "pest:dagger" if big else "pest:crawler"}
        pests.append(pid)
    if not pests:
        return None
    inf = {"id": iid, "settlement": sid, "warehouse": b["id"], "pests": pests, "started_ms": _now(world), "cleared_ms": None, "eaten": {}, "eaten_total": 0,
           "killed_by": {}, "wave": st["counter"], "complained_ms": None, "complained_to": [], "pvp_at_complaint": 0, "burned_by": [], "escapes": 0, "keeper": ""}
    st["infestations"][iid] = inf
    inf["keeper"] = ensure_keeper(world, sid, b) or ""
    events.log(world, "pests_arrived", infestation=iid, settlement=sid, warehouse=b["id"], count=len(pests))
    _announce(world, "pests_arrived", settlement=sid, count=len(pests), tile=[int(b["tx"]), int(b["ty"])])
    return iid


def ensure(world: Any) -> None:
    """The home warehouse has an infestation from the start; when it is cleared, a smaller one returns after a while (for a few waves)."""
    found = home(world)
    if found is None:
        return
    sid, b = found
    if live(world, sid) is not None:
        return
    s = settings()
    last = latest(world, sid)
    if last is None:
        cast(world, sid, b, s["count"])
        return
    if last["wave"] >= s["max_waves"] or last["cleared_ms"] is None:
        return
    if _now(world) - int(last["cleared_ms"]) >= s["return_ms"]:
        cast(world, sid, b, s["return_count"])


# ------------------------------------------------------------------ what they do

def _eat(world: Any, inf: dict[str, Any]) -> None:
    b = world.buildings.get(inf["warehouse"])
    if b is None:
        return
    stock = world.stocks.get(b["id"], {})
    for good in FOOD:
        if int(stock.get(good, 0)) > 0 and economy.move_good(world, b["id"], EATEN_BIN, good, 1):
            inf["eaten"][good] = int(inf["eaten"].get(good, 0)) + 1
            inf["eaten_total"] += 1
            events.log(world, "pests_ate", infestation=inf["id"], good=good)
            return


def tick(world: Any) -> None:
    from wizard_rts.narrative import tutorial

    if not tutorial.state(world).get("started"):
        return
    ensure(world)
    st = state(world)
    now = _now(world)
    inf = live(world)
    if inf is None:
        return
    if now >= int(st["next_eat_ms"]):
        st["next_eat_ms"] = now + settings()["eat_every_ms"] // max(1, len(pests_of(world, inf)))
        _eat(world, inf)


def note_fire(world: Any, seat: str, target: str) -> None:
    """A wizard burned a building: if it was the warehouse with the rats in it, the keeper will have words (called by the session on a `fire`)."""
    inf = live(world)
    if inf is not None and target == inf["warehouse"] and seat not in inf["burned_by"]:
        inf["burned_by"].append(seat)
        ledger.bump(world, "burned_warehouse", seat=seat)


def complained(world: Any, seat: str) -> None:
    inf = live(world)
    if inf is None:
        return
    if inf["complained_ms"] is None:
        inf["complained_ms"] = _now(world)
        inf["pvp_at_complaint"] = ledger.count(world, "pvp_duels")
    if seat not in inf["complained_to"]:
        inf["complained_to"].append(seat)


def anyone_complained(world: Any) -> bool:
    inf = live(world)
    return bool(inf and inf["complained_ms"] is not None)


# ------------------------------------------------------------------ fighting

def _opponent(world: Any, pid: str) -> tuple[str, str]:
    r = residents.table(world)[pid]
    return ("opponent.rat_big", "A big rat") if r["pest"]["size"] == "big" else ("opponent.rat", "A rat")


def fight(world: Any, pid: str) -> dict[str, Any]:
    """The wizard acting now fights the pest `pid`: a story lease (the board for a human; the Python core for an AI seat, verified the same way)."""
    from wizard_rts.narrative import campaign, mortality

    seat = mortality.me(world)
    if not is_pest(world, pid):
        return {"status": "rejected", "reason": "no_pest"}
    if campaign.over(world):
        return {"status": "rejected", "reason": "dead"}
    r = residents.table(world)[pid]
    dist = abs(int(world.player["tx"]) - int(r["tile"][0])) + abs(int(world.player["ty"]) - int(r["tile"][1]))
    if dist > FIGHT_RANGE:
        return {"status": "rejected", "reason": "too_far", "distance": dist}
    if duel_lease.active(world) is not None:
        return {"status": "rejected", "reason": "duel_open"}
    opp, name = _opponent(world, pid)
    lease = duel_lease.begin(world, opp, purpose=f"pest:{pid}", display_name=name)
    if lease["status"] != "started":
        return {"status": "rejected", "reason": lease.get("reason", "no_lease")}
    r["stay"] = True  # it stands its ground while the duel is on
    rec_seat = party.seats(world).get(seat, {})
    if seat and rec_seat and not rec_seat.get("human", True):
        from wizard_rts.narrative import autoduel

        report = autoduel.play_lease(world, lease["payload"]["duel"], seed=f"{seat}|{pid}")
        out = duel_lease.resolve(world, lease["payload"]["duel"]["id"], report)
        done = on_duel_resolved(world, lease["payload"]["duel"], out) if out.get("status") == "resolved" else {}
        return {"status": "resolved", "auto": True, "outcome": out.get("outcome"), **done}
    return {"status": "started", "duel_lease": lease, "pest": pid, "name": name}


def on_duel_resolved(world: Any, lease: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    from wizard_rts.narrative import mortality, wizard

    pid = str(lease["purpose"])[len("pest:"):]
    seat = mortality.me(world)
    r = residents.table(world).get(pid)
    if r is None:
        return {"pest": pid, "gone": True}
    r.pop("stay", None)
    inf = state(world)["infestations"].get(r["pest"]["inf"])
    if out.get("outcome") == "won":
        tile = list(r["tile"])
        residents.table(world).pop(pid, None)  # a broken rat leaves no body to mourn: the row goes, the Person is marked dead
        if pid in world.dmb.people:
            world.dmb.people[pid]["alive"] = False
            world.dmb.people[pid]["status"] = "dead"
        if inf is not None:
            inf["killed_by"][seat] = int(inf["killed_by"].get(seat, 0)) + 1
        ledger.bump(world, "pests_killed", seat=seat)
        events.log(world, "pest_killed", pest=pid, seat=seat, tile=tile)
        _announce(world, "pest_killed", pest=pid, seat=seat, tile=tile, size=r["pest"]["size"])
        left = len(pests_of(world, inf)) if inf else 0
        if inf is not None and left == 0:
            inf["cleared_ms"] = _now(world)
            ledger.bump(world, "infestations_cleared")
            events.log(world, "pests_cleared", infestation=inf["id"], by=sorted(inf["killed_by"]))
            _announce(world, "pests_cleared", infestation=inf["id"], settlement=inf["settlement"])
        return {"pest": pid, "killed": True, "left": left}
    wizard.wiz(world)["wounded"] = True
    if inf is not None:
        inf["escapes"] += 1
    t = residents.free_tile(world, r["anchor"][0], r["anchor"][1], RADIUS + 1, avoid={tuple(r["tile"])})
    if t is not None:
        r["tile"] = [t[0], t[1]]
        world.dmb.people[pid]["position"] = [t[0], t[1]]
    ledger.bump(world, "pest_escapes", seat=seat)
    _announce(world, "pest_escaped", pest=pid, seat=seat, tile=list(r["tile"]))
    return {"pest": pid, "killed": False, "wounded": True}


# ------------------------------------------------------------------ what the keeper knows

def facts(world: Any, keeper_pid: str) -> dict[str, Any]:
    from wizard_rts.narrative import mortality

    seat = mortality.me(world)
    sid = residents.table(world).get(keeper_pid, {}).get("settlement", "")
    inf = live(world, sid) or latest(world, sid)
    if inf is None:
        return {"pests_left": 0, "pests_total": 0, "killed_total": 0, "my_killed": 0, "others_killed": 0, "cooperated": 0, "eaten_total": 0, "complained": 0,
                "duels_since_complaint": 0, "burned": 0, "wave": 0, "cleared": 0, "minutes_since_complaint": 0, "escapes": 0, "role": KEEPER}
    killed = inf["killed_by"]
    my = int(killed.get(seat, 0))
    others = sum(int(v) for s, v in killed.items() if s != seat)
    since = (_now(world) - int(inf["complained_ms"])) // 60000 if inf["complained_ms"] is not None else 0
    return {"pests_left": len(pests_of(world, inf)), "pests_total": len(inf["pests"]), "killed_total": my + others, "my_killed": my, "others_killed": others,
            "cooperated": 1 if (my > 0 and others > 0) else 0, "eaten_total": int(inf["eaten_total"]), "complained": 1 if inf["complained_ms"] is not None else 0,
            "duels_since_complaint": max(0, ledger.count(world, "pvp_duels") - int(inf["pvp_at_complaint"])) if inf["complained_ms"] is not None else 0,
            "burned": 1 if inf["burned_by"] else 0, "wave": int(inf["wave"]), "cleared": 1 if inf["cleared_ms"] is not None else 0, "minutes_since_complaint": int(since),
            "escapes": int(inf["escapes"]), "role": KEEPER}


def snapshot(world: Any) -> dict[str, Any]:
    inf = live(world)
    if inf is None:
        return {}
    return {"id": inf["id"], "left": len(pests_of(world, inf)), "total": len(inf["pests"]), "eaten": int(inf["eaten_total"]), "warehouse": inf["warehouse"], "keeper": inf["keeper"]}
