"""Worlds for the neuro tests: built once per test session (a 20-minute AI game takes about 20 s) and handed out as pickled clones.

Not a test module (no tests here); imported by test_neuro_features.py and test_neuro_candidates.py.
"""
from __future__ import annotations

import os
import pickle
from typing import Any

from wizard_rts.world import HybridWorld

_BLOBS: dict[tuple, bytes] = {}


def _build(seed: int, minutes: int) -> HybridWorld:
    prev = os.environ.get("HYBRID_AI")
    os.environ["HYBRID_AI"] = "1"
    try:
        w = HybridWorld(seed, terrain=True, map_size="standard", profile="campaign")
    finally:
        if prev is None:
            os.environ.pop("HYBRID_AI", None)
        else:
            os.environ["HYBRID_AI"] = prev
    w.ai_enabled = True
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, True
    w.nest_policy = {n: "coop" for n in w.faction_info}
    w.ai_policy = {n: "plus" for n in w.faction_info}
    for i in range(minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
    return w


def world_at(minutes: int = 20, seed: int = 7) -> HybridWorld:
    """A fresh clone of a campaign world advanced `minutes` game minutes with the plus AI playing every faction."""
    key = (seed, minutes)
    if key not in _BLOBS:
        _BLOBS[key] = pickle.dumps(_build(seed, minutes), protocol=5)
    return pickle.loads(_BLOBS[key])


def fresh_world(seed: int = 7) -> HybridWorld:
    """A campaign world at game second 0 (no AI has acted)."""
    return world_at(0, seed)


def digest(arrays: dict[str, Any]) -> str:
    """sha256 of a set of arrays (name, dtype, shape, bytes), for reproducibility checks across processes."""
    import hashlib

    h = hashlib.sha256()
    for k in sorted(arrays):
        a = arrays[k]
        h.update(k.encode())
        h.update(str((a.dtype, a.shape)).encode())
        h.update(a.tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------------------------------- richer fixtures (candidate tests)
def free_tile(w: HybridWorld, near: tuple[int, int], skip: set | None = None) -> tuple[int, int]:
    """The nearest walkable tile to `near` with no building footprint, tree, road or unit on it."""
    occupied = {(u["tx"], u["ty"]) for u in w.units.values() if u.get("alive", True)} | (skip or set())
    for r in range(0, 30):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                t = (near[0] + dx, near[1] + dy)
                if (w.terrain.ground(*t) and t not in w.blocked and t not in w.tree_tiles and t not in w.road_tile_set and t not in w.reserved_tiles and t not in occupied):
                    return t
    raise RuntimeError("no free tile near %s" % (near,))


def rich_world() -> HybridWorld:
    """The 20-minute world made rich enough to exercise every head for Red: the trade card, plenty of stock, remembered enemy warehouses, an army and a settlers'
    wagon, a visible enemy unit and a blight nest by the capital, and an open truce offer from Blue."""
    from wizard_rts import construction as con
    from wizard_rts import diplomacy, tech, territory, visibility
    from wizard_rts.economy import produce

    w = world_at(20)
    me = "Red"
    for f in (me, "Blue"):
        tech.grant(w, f, "dmb.card.trade")
    tech.grant(w, me, "dmb.card.deep_mining")
    wh = con.faction_warehouse(w, me)
    for g, n in {"log": 60, "plank": 40, "granite": 40, "ration": 50, "water": 40, "iron": 20, "coal": 20, "cloth": 20, "ax": 10, "brick": 20}.items():
        produce(w, wh["id"], g, n)
        w.stats["made_" + g] = w.stats.get("made_" + g, 0) + n
    for f in ("Blue", "Green"):
        visibility.remember(w, me, con.faction_warehouse(w, f))
    fid = w.faction_info[me]["id"]
    taken: set = set()
    for k in range(6):
        t = free_tile(w, (wh["tx"] + 6, wh["ty"] + 8), taken)
        taken.add(t)
        w._unit(fid, me, "infantry", "Rifleman", "openra.e1", t)
    t = free_tile(w, (wh["tx"] - 6, wh["ty"] + 8), taken)
    taken.add(t)
    w._unit(fid, me, "settlers", "Settlers", territory.SETTLER_DEFINITION, t)
    t = free_tile(w, (wh["tx"] + 5, wh["ty"] - 5), taken)
    taken.add(t)
    w._unit(w.faction_info["Blue"]["id"], "Blue", "infantry", "Rifleman", "openra.e1", t)  # a raider in sight of the capital
    for kind, definition, label in (("engineer", "openra.e6", "Engineer"), ("spy", "openra.spy", "Spy"), ("commando", "openra.e7", "Tanya"), ("minelayer", "openra.mnly", "Minelayer"),
                                    ("apc", "openra.apc", "APC")):
        t = free_tile(w, (wh["tx"] - 3, wh["ty"] + 10), taken)
        taken.add(t)
        uid = w._unit(fid, me, kind, label, definition, t)
        if kind == "minelayer":
            w.units[uid]["ammo"] = 4
    t = free_tile(w, (wh["tx"] - 3, wh["ty"] + 11), taken)
    taken.add(t)
    w._unit(fid, me, "infantry", "Rifleman", "openra.e1", t)  # stands beside the APC
    blue_wh = con.faction_warehouse(w, "Blue")
    w._unit(w.faction_info["Blue"]["id"], "Blue", "settlers", "Settlers", territory.SETTLER_DEFINITION, free_tile(w, (blue_wh["tx"] + 5, blue_wh["ty"] + 9)))
    nid = w._building("", "", "blight_nest", free_tile(w, (wh["tx"] - 7, wh["ty"] - 6), taken), "nest", "dmb.blight_nest")
    w.buildings[nid]["hp"] = w.buildings[nid]["max_hp"] = 5000
    diplomacy.propose(w, "Blue", me, "truce")
    diplomacy.set_state(w, me, "Green", "truce", why="fixture")  # a standing treaty that can be broken
    hurt = next(b for b in w.buildings.values() if b["faction_name"] == me and b["kind"] != "warehouse" and not b.get("constructing") and "hp" in b)
    hurt["hp"] = int(hurt["max_hp"]) * 6 // 10  # a damaged building an engineer can repair
    from wizard_rts import openra_abilities as A

    silo = w._building(fid, me, "mslo", free_tile(w, (wh["tx"] + 9, wh["ty"] + 3), taken), "Missile silo", "openra.mslo")
    w.buildings[silo]["operational"] = True
    for g, n in A.NUKE["cost"].items():
        w.stocks.setdefault(silo, {})[g] = n  # charged and paid: the nuke can be launched at a remembered enemy building
    return w


def modern_world() -> HybridWorld:
    """A developer-profile world in the Modern era: the industrial slice from the fixture (belts, drills, smelter), instantly built machines (a power node, panels, a
    drill over two ores, a unit factory), an old Widelands mine to upgrade and a lumberjack's house the industry can convert, and one power link left to make."""
    from conftest import set_resource
    from wizard_rts import ai, construction as con, tech
    from wizard_rts.industry import fixture as IF
    from wizard_rts.industry import hybrid
    from wizard_rts.industry import registry as R
    from wizard_rts.industry import sim as ISIM

    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    IF.modern_fixture(w, "Red")
    for i in range(90):
        w.advance(1000, i + 1, snapshot=False)
    wh = con.faction_warehouse(w, "Red")
    for _try in range(8):  # an old mine, finished by hand
        tile = ai._mine_site(w, wh, "coal")
        if tile is None:
            break
        res = con.place_building(w, "Red", "mine", *tile)
        if res["status"] == "ok":
            b = w.buildings[res["id"]]
            b.pop("constructing", None)
            b["operational"], b["hp"] = True, b["max_hp"]
            break
        w.blocked.add(tile)
    # the card that unlocks the industrial successor of a Widelands building, then that building, finished by hand
    lookup = tech.lookup()
    for base, target in sorted(hybrid.REPLACES.items()):
        kind = "wl:barbarians_" + base
        cards = [c for c, v in lookup.items() if target in (v.get("entities") or [])]
        if kind in con.full_menu() and cards:
            tech.grant(w, "Red", cards[0])
            res = con.place_building(w, "Red", kind, *free_tile(w, (wh["tx"] + 6, wh["ty"] + 6)))
            if res["status"] == "ok":
                b = w.buildings[res["id"]]
                b.pop("constructing", None)
                b["operational"], b["hp"] = True, b["max_hp"]
                break
    # power: a node, two panels (one left unlinked), and a drill over two ores
    x, y = IF.open_ground(w, "Red", 12, 3)
    IF.instant_machine(w, "Red", "mdy:solar_panel", (x, y))
    far = IF.instant_machine(w, "Red", "mdy:solar_panel", (x + 8, y))
    IF.instant_machine(w, "Red", "mdy:power_node", (x + 4, y))
    for i in range(2):
        w.advance(1000, 100 + i, snapshot=False)
    for node, links in ISIM.ind(w).links.items():
        if far in links:
            links.remove(far)
    x2, y2 = IF.open_ground(w, "Red", 3, 3, near=(x, y + 6))
    for dx, dy, res_ in ((0, 0, "coal"), (1, 0, "coal"), (0, 1, "iron"), (1, 1, "iron")):
        set_resource(w, (x2 + dx, y2 + dy), res_, 30)
    IF.instant_machine(w, "Red", "mdy:mechanical_drill", (x2, y2))
    for k in range(2):  # two finished ports (whether a waterway between them is possible depends on the shore: the simulator decides)
        t = free_tile(w, (wh["tx"] + 12 + 8 * k, wh["ty"] - 8))
        bid = w._building(w.faction_info["Red"]["id"], "Red", "wl:barbarians_port", t, "Port", "widelands.barbarians_port")
        w.buildings[bid]["operational"] = True
    return w
