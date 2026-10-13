"""Trade caravans between factions (owner request, 12 Oct 2026).

A caravan is a unit (definition "dmb.caravan", unarmed, on foot) that a faction with the Trade card sends from one of its warehouses
to another faction's warehouse. It is built from the sender's own store (CARAVAN_COST: log 2, ration 1, consumed) and loads the
goods it offers (`give`), which leave the store and ride on the unit (`cargo`, counted by the ware ledger as held). On arrival the
partner's warehouse takes the `give` goods and hands over the agreed `want` goods if it still holds them above its reserve; otherwise
the trade fails and the caravan brings its own goods home. Back home the cargo goes into the store and the caravan is dismissed.
A killed caravan loses its cargo (military.kill_unit books it as destroyed). Nothing is created: goods only move.

Partners must not be at war: `hostile(world, a, b)` is true when either attacked or damaged the other in the last HOSTILE_MS
(EventLog records ai_attack events; damage records the shooter's faction). The value of a deal is judged with WARE_VALUE; the
partner accepts a deal whose offered value is at least the value it gives away.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import construction as con
from wizard_rts import tech, territory

DEFINITION = "dmb.caravan"
CARAVAN_COST = {"log": 2, "ration": 1}
HOSTILE_MS = 15 * 60_000
RESERVE = 8  # a partner never trades away the last few of a ware
CHECK_EVERY = 10
REACH = 3  # tiles from the partner's warehouse that count as arrived
WARE_VALUE = {"log": 1.0, "plank": 2.0, "granite": 1.5, "coal": 2.0, "iron_ore": 2.0, "iron": 4.0, "gold": 6.0, "gold_ore": 3.0,
              "ration": 2.5, "meat": 1.0, "fish": 1.0, "bread": 2.0, "wheat": 1.0, "water": 0.5, "ax": 5.0, "marble": 2.0,
              "marble_column": 3.0, "cloth": 2.5, "brick": 2.0, "grout": 2.0, "blackwood": 2.0, "reed": 1.0, "rope": 2.0}


def is_post(b: dict) -> bool:
    """A building a caravan can leave from or arrive at: a command centre, a secondary warehouse, a port, a Mindustry core or a market."""
    return (b["kind"] == "warehouse" or bool(b.get("store")) or bool(b.get("market"))) and b.get("operational", True) and not b.get("constructing")


def value(goods: dict[str, int]) -> float:
    return sum(WARE_VALUE.get(g, 1.5) * int(n) for g, n in goods.items())


def note_hostility(world: Any, a: str, b: str) -> None:
    if not a or not b or a == b or a not in world.faction_info or b not in world.faction_info:
        return
    h = world.__dict__.setdefault("_hostile", {})
    h["|".join(sorted((a, b)))] = int(world.dmb.clock.get("game_ms", 0))


def hostile(world: Any, a: str, b: str) -> bool:
    from wizard_rts import diplomacy

    if diplomacy.state_of(world, a, b) != "war":
        return False  # a truce, peace or alliance (plan v2 7.3) opens trade whatever happened before it
    t = world.__dict__.get("_hostile", {}).get("|".join(sorted((a, b))))
    return t is not None and int(world.dmb.clock.get("game_ms", 0)) - t < HOSTILE_MS


def _stock(world: Any, wh: dict, g: str) -> int:
    return int(world.stocks.get(wh["id"], {}).get(g, 0))


def can_supply(world: Any, wh: dict, want: dict[str, int]) -> bool:
    return all(_stock(world, wh, g) - n >= RESERVE for g, n in want.items())


def send_caravan(world: Any, faction: str, wh_id: str, partner_wh_id: str, give: dict[str, int], want: dict[str, int]) -> dict[str, Any]:
    """The trade command (the AI's and God Mode's): load `give`, walk to the partner's warehouse, swap for `want`, walk home."""
    from wizard_rts.economy import _supply
    from wizard_rts.military import order_move

    wh, pw = world.buildings.get(wh_id), world.buildings.get(partner_wh_id)
    if wh is None or pw is None or not is_post(wh) or not is_post(pw) or int(wh.get("hp", 0)) <= 0 or int(pw.get("hp", 0)) <= 0:
        return {"status": "rejected", "reason": "no_warehouse"}
    if wh["faction_name"] != faction or pw["faction_name"] == faction:
        return {"status": "rejected", "reason": "not_a_trade"}
    if not tech.unit_allowed(world, faction, "caravan"):
        return {"status": "rejected", "reason": "locked_by_card"}
    partner = pw["faction_name"]
    if hostile(world, faction, partner):
        return {"status": "rejected", "reason": "at_war"}
    give = {g: int(n) for g, n in give.items() if int(n) > 0}
    want = {g: int(n) for g, n in want.items() if int(n) > 0}
    if not give or not want:
        return {"status": "rejected", "reason": "empty_deal"}
    need = dict(CARAVAN_COST)
    for g, n in give.items():
        need[g] = need.get(g, 0) + n
    if any(_stock(world, wh, g) < n for g, n in need.items()):
        return {"status": "rejected", "reason": "missing_goods"}
    if value(give) < value(want):
        return {"status": "rejected", "reason": "unfair_offer"}
    if not can_supply(world, pw, want):
        return {"status": "rejected", "reason": "partner_cannot_supply"}
    tile = con._exit_tile(world, wh)
    if tile is None:
        return {"status": "rejected", "reason": "no_exit"}
    for g, n in need.items():
        _supply(world, wh["id"]).remove_wares(g, n)
    for g, n in CARAVAN_COST.items():
        world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
    uid = world._unit(world.faction_info[faction]["id"], faction, "caravan", "Caravan", DEFINITION, tile)
    u = world.units[uid]
    u["cargo"] = dict(give)
    u["trade"] = {"home": wh["id"], "partner_wh": pw["id"], "partner": partner, "give": dict(give), "want": dict(want), "leg": "out",
                  "since_ms": int(world.dmb.clock.get("game_ms", 0))}
    dest = _beside(world, pw)
    if dest is not None:
        order_move(world, [uid], dest[0], dest[1])
    world.fstat(faction, "caravans_sent")
    world.events.append({"kind": "caravan_sent", "faction": faction, "partner": partner, "give": dict(give), "want": dict(want), "unit": uid})
    return {"status": "ok", "unit": uid}


def _beside(world: Any, b: dict) -> tuple[int, int] | None:
    for r in range(1, REACH + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                t = (b["tx"] + dx, b["ty"] + dy)
                if max(abs(dx), abs(dy)) == r and world.tile_in_map(*t) and t not in world.blocked:
                    return t
    return None


def trade_quantum(world: Any) -> None:
    if world.economy_quanta % CHECK_EVERY:
        return
    from wizard_rts.economy import _supply
    from wizard_rts.military import order_move

    for uid, u in sorted(world.units.items()):
        tr = u.get("trade")
        if not tr or not u.get("alive", True):
            continue
        target = world.buildings.get(tr["partner_wh"] if tr["leg"] == "out" else tr["home"])
        if target is None or int(target.get("hp", 0)) <= 0:
            if tr["leg"] == "out":  # the partner's warehouse is gone: go home with the goods
                tr["leg"] = "home"
                home = world.buildings.get(tr["home"])
                dest = _beside(world, home) if home else None
                if dest:
                    order_move(world, [uid], dest[0], dest[1])
                continue
            home = territory.covering(world, u["faction_name"], (u["tx"], u["ty"])) or con.faction_warehouse(world, u["faction_name"])
            if home is None:
                continue
            tr["home"] = home["id"]
            continue
        if territory.cheb((int(u["tx"]), int(u["ty"])), (target["tx"], target["ty"])) > REACH:
            if not u.get("order"):
                dest = _beside(world, target)
                if dest:
                    order_move(world, [uid], dest[0], dest[1])
            continue
        if tr["leg"] == "out":
            ok = can_supply(world, target, tr["want"]) and not hostile(world, u["faction_name"], tr["partner"])
            if ok:
                for g, n in tr["give"].items():
                    _supply(world, target["id"]).add_wares(g, n)
                for g, n in tr["want"].items():
                    _supply(world, target["id"]).remove_wares(g, n)
                u["cargo"] = dict(tr["want"])
                world.fstat(u["faction_name"], "trades_done")
                world.fstat(tr["partner"], "trades_done")
                hist = world.__dict__.setdefault("_trade_partners", {})
                key = "|".join(sorted((u["faction_name"], tr["partner"])))
                hist[key] = hist.get(key, 0) + 1
            world.events.append({"kind": "caravan_traded" if ok else "caravan_refused", "faction": u["faction_name"], "partner": tr["partner"],
                                 "give": dict(tr["give"]), "want": dict(tr["want"])})
            tr["leg"] = "home"
            home = world.buildings.get(tr["home"])
            dest = _beside(world, home) if home else None
            if dest:
                order_move(world, [uid], dest[0], dest[1])
            continue
        for g, n in sorted((u.pop("cargo", None) or {}).items()):  # home: unload and dismiss
            _supply(world, target["id"]).add_wares(g, n)
        world.units.pop(uid, None)
        world.events.append({"kind": "caravan_home", "faction": target["faction_name"], "unit": uid})


def partners_traded(world: Any, a: str, b: str) -> int:
    return int(world.__dict__.get("_trade_partners", {}).get("|".join(sorted((a, b))), 0))


def active(world: Any, faction: str) -> int:
    return sum(1 for u in world.units.values() if u.get("trade") and u["faction_name"] == faction and u.get("alive", True))
