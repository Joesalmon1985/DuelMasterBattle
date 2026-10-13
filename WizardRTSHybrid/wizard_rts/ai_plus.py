"""The improved heuristic faction AI ("plus"), the challenger to the original commander in `ai.py` ("baseline").

Fairness contract: it issues only the commands every faction has (construction.place_building / build_road / queue_unit,
territory.deploy, military.order_move / order_attack, tech.draft) on the same decision cadence (ai.DECIDE_EVERY), reads only what
the baseline reads (its own stocks and buildings, publicly visible enemy positions within sight, the public start positions, the
outbreak overlay that every player sees), and gets no wares, units, cards, vision or speed the baseline does not. Wizard magic is not
available to it. Where it is better, it is better at *deciding*:

- drafting: scores every offered card against measured needs (food, threats, expansion, the tribe's soldier wares, shore access)
  and a goal path per era, instead of one fixed list;
- economy: dynamic targets from the faction's own measurements, two or three construction sites in parallel, food before mines,
  extra sawmills only when logs pile up, defences where the enemy comes from, and no new workplaces in infected regions;
- expansion: settlers as soon as the Settlers card and food allow, more settlements per era, sites scored for wood, stone, fields and
  distance from enemies and outbreaks, path-checked for the founder's own locomotor;
- military: a cost-aware choice of the best unit each building can make, a home guard sized to the threat, squads that gather at a
  rally point and attack only with a measured strength advantage, targets chosen for value (outpost command centres are VP),
  retreat when the local balance turns, garrisons for unruly settlements;
- crisis: repairs fed first (props, rations), unrest answered with food and garrisons, outposts linked by road to the capital.

Every decision that cannot be carried out leaves a reason in `world.ai_notes[faction]` (diagnostics, P3).
"""

from __future__ import annotations

import math
import zlib
from typing import Any

from wizard_rts import ai as base
from wizard_rts import construction as con
from wizard_rts import tech, territory

POLICY = "plus"
FOOD = ("ration", "bread", "meat", "fish", "smoked_fish", "smoked_meat", "bread_frisians")
MAX_CC_BY_ERA = (3, 4, 5, 6)
ARMY_CAP_BY_ERA = (10, 20, 28, 34)
SQUAD_BY_ERA = (5, 7, 9, 11)
ATTACK_RATIO = 1.4  # our squad strength over the defenders' near the target
RETREAT_RATIO = 0.6
ATTACK_AFTER_MS = 10 * 60_000
WARE_WEIGHT = {"iron": 3.0, "gold": 5.0, "coal": 1.5, "ration": 1.5, "plank": 1.0, "log": 0.5, "granite": 0.8, "ax": 2.5}

# Card priorities per era (earlier = more urgent when nothing else is pressing). Needs move cards up (score_card).
PRIORITY = {
    0: ["farming", "settlers", "cookery", "warrior_bands", "mining", "smelting", "trade", "crafts", "slings", "husbandry"],
    1: ["metalwork", "drill_tactics", "motor_pool", "fortification", "armour", "weaving", "grenadiers", "artillery", "rocketry", "seafaring"],
    2: ["automation", "heavy_armour", "industry", "unit_fabrication", "tesla", "rocket_artillery", "deep_mining", "submarines"],
    3: ["tesla_armour", "machine_war", "shock_troops", "phase_armour", "arcology"],
}
NEEDS_WEAVING = ("atlanteans", "frisians", "amazons", "empire")  # soldier wares need cloth/tabards/garments/tunics


def note(world: Any, name: str, text: str) -> None:
    notes = world.__dict__.setdefault("ai_notes", {}).setdefault(name, [])
    notes.append(text)
    del notes[:-12]


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _era(world: Any) -> int:
    return int(getattr(world, "era_index", 0))


def _food(world: Any, name: str, anchor: dict | None = None) -> int:
    return sum(base._stock(world, name, g, anchor) for g in FOOD)


# ------------------------------------------------------------------ threat and strength

def strength_of(definition: str, hp: int | None = None) -> float:
    """A rough fighting value from the OpenRA-schema rules: sqrt(HP) x damage per second x a range factor."""
    from wizard_rts import rules

    r = rules.actor(definition)
    if r is None:
        return 1.0
    dps = 0.0
    rng = 0.0
    for wname in r.get("armaments", []):
        w = rules.weapon(wname)
        if not w:
            continue
        dmg = sum(int(h.get("damage", 0)) for h in w.get("warheads", [])) * max(1, int(w.get("burst", 1)))
        dps += dmg / max(1.0, int(w.get("reload", 25)) * rules.TICK_MS / 1000.0)
        rng = max(rng, float(w.get("range", 1.0)))
    return math.sqrt(max(1, hp if hp is not None else int(r["hp"]))) * (dps / 100.0 + 0.1) * (1.0 + rng / 8.0)


def building_strength(b: dict) -> float:
    """An armed building's fighting value from the weapon it actually fires (OpenRA defence, settlement militia, blight nest)."""
    from wizard_rts.military import building_weapon

    w = building_weapon(b)
    if not w:
        return 0.0
    dmg = sum(int(h.get("damage", 0)) for h in w.get("warheads", [])) * max(1, int(w.get("burst", 1)))
    dps = dmg / max(1.0, int(w.get("reload", 25)) * 0.04)
    return math.sqrt(max(1, int(b.get("hp", 1)))) * (dps / 100.0 + 0.1) * (1.0 + float(w.get("range", 1.0)) / 8.0)


def unit_strength(u: dict) -> float:
    return strength_of(u.get("definition", ""), int(u.get("hp", 1)))


def force_near(world: Any, pos: tuple[float, float], radius: float, side: str, enemy: bool) -> float:
    """Strength of armed units (and armed buildings) within radius: of `side` (enemy=False) or of everyone else (enemy=True)."""
    from wizard_rts.military import building_weapon

    total = 0.0
    for u in world.units.values():
        if not u.get("alive", True) or not u.get("weapon") or u.get("loco") in base.NAVAL:
            continue
        if (u["faction_name"] != side) != enemy:
            continue
        if math.hypot(u["tx"] - pos[0], u["ty"] - pos[1]) <= radius:
            total += unit_strength(u)
    for b in world.buildings.values():
        if (b["faction_name"] != side) != enemy or int(b.get("hp", 0)) <= 0 or b.get("constructing"):
            continue
        if math.hypot(b["tx"] - pos[0], b["ty"] - pos[1]) <= radius and building_weapon(b):
            total += building_strength(b)
    return total


def _threats(world: Any, name: str) -> list[tuple[dict, dict]]:
    """(our command centre, nearest enemy armed unit) for every centre an enemy has come within its territory + 6."""
    out = []
    for cc in territory.command_centers(world, name):
        t = base._nearest_enemy_unit(world, name, (cc["tx"], cc["ty"]), territory.radius_of(cc) + 6.0)
        if t is not None and t.get("weapon"):
            out.append((cc, t))
    return out


# ------------------------------------------------------------------ drafting

MILITARY_KINDS = ("barracks", "vehicle_factory", "war_lodge", "defense", "flame_tower", "tesla_coil", "naval_yard", "sub_pen")


def score_generated(world: Any, name: str, cid: str) -> tuple[float, str]:
    """Value of a content-graph card for this faction now: does the entity fit its tribe, extend a working chain, answer a shortage or a threat."""
    from wizard_rts.content import graph

    ents = graph.entities()
    tribe = world.faction_info.get(name, {}).get("tribe", "")
    c = tech.lookup()[cid]
    s, why = 40.0 - 2.0 * c["era"], "base"
    threatened = bool(_threats(world, name)) or world.fstats.get(name, {}).get("building_losses", 0) > 0
    held_kinds = {b["kind"] for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0}
    for eid in c["entities"]:
        e = ents[eid]
        if e["type"] == "building" and e["game"] == "widelands":
            if e["tribe"] != tribe:
                s -= 60
                why = "another tribe's building"
                continue
            fresh = [g for g in e.get("outputs", []) if not base._makes(world, name, g)]
            s += 12 * min(len(fresh), 2)
            fed = sum(1 for g in e.get("inputs", []) if base._makes(world, name, g) or base._stock(world, name, g) > 0)
            s += 6 * fed - 6 * (len(e.get("inputs", [])) - fed)
            if any(g in ("ration", "bread", "fish", "meat") for g in e.get("outputs", [])) and _food(world, name) < 8:
                s += 30
                why = "food is short"
            if any(g in ("iron", "coal", "gold", "iron_ore", "coal_ore") for g in e.get("outputs", [])) and _era(world) >= 1:
                s += 14
                why = "metal for an army"
        elif e["type"] == "building":
            if eid in MILITARY_KINDS:
                s += 30 if threatened else 8
                why = "under threat" if threatened else "military"
            if eid in ("farm", "mine", "ironmine", "smelter") and eid not in held_kinds:
                s += 18
        else:
            unit = eid[5:]
            producer = e["producer"]
            held = {k for cid2 in world.tech[name]["cards"] for k in tech.lookup()[cid2].get("kinds", ())}
            if producer not in held and not tech.kind_allowed(world, name, producer) and producer != "warehouse":
                s -= 35
                why = "no building to make it"
            if threatened:
                s += 15
    return s, why


def score_card(world: Any, name: str, cid: str) -> tuple[float, str]:
    if cid.startswith("gen."):
        return score_generated(world, name, cid)
    c = tech.lookup()[cid]
    short = cid.split(".")[-1]
    era = _era(world)
    order = PRIORITY.get(c["era"], [])
    s = 100.0 - 6.0 * (order.index(short) if short in order else len(order))
    why = "priority"
    food = _food(world, name)
    tribe = world.faction_info.get(name, {}).get("tribe", "")
    if food < 8 and short in ("farming", "cookery", "husbandry"):
        s += 45
        why = "food is short (%d)" % food
    if _threats(world, name) or world.fstats.get(name, {}).get("building_losses", 0) > 0:
        if short in ("warrior_bands", "slings", "fortification", "drill_tactics", "tesla", "grenadiers"):
            s += 40
            why = "under threat"
    if short == "settlers" and len(territory.command_centers(world, name)) < 2:
        s += 30
        why = "no second settlement yet"
    if short == "motor_pool":
        s += 20
    if short == "weaving" and tribe in NEEDS_WEAVING and "dmb.card.drill_tactics" in world.tech[name]["cards"]:
        s += 35
        why = "%s soldiers need woven wares" % tribe
    if short in ("seafaring", "submarines"):
        wh = con.faction_warehouse(world, name)
        if wh is None or world.terrain is None or base._naval_site(world, name, wh) is None:
            s -= 80
            why = "no shore for a yard"
    if short == "arcology":
        s += 10
    if short == "deep_mining" and not any(b["faction_name"] == name and b["kind"].startswith("wl:") and "mine" in b["kind"] for b in world.buildings.values()):
        s -= 30
    return s, why


def pick_card(world: Any, name: str) -> str | None:
    st = world.tech.get(name)
    if not st or not st["offers"]:
        return None
    scored = sorted(((score_card(world, name, cid), cid) for cid in st["offers"]), key=lambda x: (-x[0][0], x[1]))
    (score, why), cid = scored[0]
    note(world, name, "draft %s (%s; %d offered)" % (cid.split(".")[-1], why, len(st["offers"])))
    world.events.append({"kind": "ai_draft_reason", "faction": name, "card": cid, "why": why, "score": round(score, 1),
                         "offered": len(st["offers"])})
    return cid


# ------------------------------------------------------------------ economy

def _infected(world: Any, tile: tuple[int, int], at_least: int = 2) -> bool:
    rg = world.__dict__.get("regions")
    return rg is not None and rg.cubes[rg.region_at(tile[0], tile[1])] >= at_least


def _targets(world: Any, name: str, wh: dict, main: bool, mine: list[dict]) -> list[tuple[str, int]]:
    """(kind, wanted count) in priority order for one settlement, from the faction's measurements."""
    era = _era(world)
    logs = base._stock(world, name, "log", wh)
    planks = base._stock(world, name, "plank", wh)
    granite = base._stock(world, name, "granite", wh)
    food = _food(world, name, wh)
    threatened = any(cc is wh for cc, _t in _threats(world, name))
    tribe = world.faction_info.get(name, {}).get("tribe", "")
    fisher = base.FISHER_OF.get(tribe, "")
    n = len(mine)
    if not main:
        out = [("producer", 2), ("ranger", 1), ("processor", 1), ("quarry", 1), ("hunter", 1)]
        if fisher:
            out.append((fisher, 1))
        out += [("farm", 1), ("tavern", 1), ("well", 1)]
        out += [("flame_tower", 1)] if era >= 1 else [("war_lodge", 0)]
        out += [("defense", 1), ("tesla_coil", 1 if era >= 2 else 0)]
        return out
    wood = max(3, 2 + n // 8)
    out: list[tuple[str, int]] = []
    if threatened:
        out += [("war_lodge", 1), ("defense", 2), ("flame_tower", 1), ("tesla_coil", 1)]
    out += [("producer", wood), ("ranger", wood - 1), ("processor", 2 if logs > 40 and planks < 15 else 1), ("quarry", 3 if granite < 10 else 2)]
    rations = base._stock(world, name, "ration", wh)
    food_first = food < 10 or rations < 6  # rations feed miners, soldiers and settlers: the tavern comes before the mines
    eaters = have_n(mine, "mine") + have_n(mine, "ironmine") + 2 * have_n(mine, "war_lodge") + 2 * have_n(mine, "barracks")
    taverns = 1 + eaters // 3 + (1 if rations < 4 and eaters else 0)  # rations feed every miner and soldier: taverns scale with them
    food_block = [("hunter", 2 + (eaters >= 4)), ("tavern", min(4, taverns)), ("well", 2), ("farm", 3 if era >= 1 else 2), ("bakery", 1)]
    if fisher:
        food_block.insert(1, (fisher, 2))
    mines = [("mine", 2 if era >= 1 else 1), ("ironmine", 2 if era >= 1 else 1), ("smelter", 1 if era < 2 else 2), ("smithy", 1)]
    military = [("war_lodge", 1 if era <= 1 else 0), ("barracks", 1 if era < 2 else 2), ("vehicle_factory", 1 if era < 2 else 2),
                ("defense", 1 + (era >= 1)), ("flame_tower", 1 if era >= 1 else 0), ("tesla_coil", 1 if era >= 2 else 0)]
    out += (food_block + mines) if food_first else (mines[:1] + food_block + mines[1:])
    out += military
    return out


def have_n(mine: list[dict], kind: str) -> int:
    return sum(1 for b in mine if b["kind"] == kind)


def _reserved(world: Any, name: str) -> dict[str, int]:
    """Wares a queued settlers' wagon or MCV is still waiting for: recruits must not eat them first."""
    out: dict[str, int] = {}
    for b in world.buildings.values():
        if b["faction_name"] != name:
            continue
        for item in b.get("queue", []):
            if item["unit"] in ("settlers", "mcv") and item["state"] == "waiting":
                for g, n in con.recipe_for(world, b, item["unit"])["cost"].items():
                    out[g] = out.get(g, 0) + n
    return out


def _settlement_step(world: Any, name: str, wh: dict, main: bool) -> None:
    mine = [b for b in base._mine(world, name) if territory.settlement_of(world, b) is wh]
    now = _now(world)
    cool_road = world.__dict__.setdefault("_ai_noroad", {})
    if world.hazard_tile is not None:  # a road through a tile carriers cannot pass strands its goods: lay one round it
        for b in mine:
            if b["kind"] != "warehouse" and any(world.tile_blocked_for_carrier(tuple(t)) for _n, rid in world.adjacency.get(b["id"], []) for t in world.roads.get(rid, [])):
                if con.reroute(world, name, b["id"])["status"] == "ok":
                    note(world, name, "rerouted %s round a blocked road" % b["kind"])
    for b in mine:  # repair the road network first (a building with no road can get nothing)
        if b["kind"] not in ("warehouse", "ranger") and not world.adjacency.get(b["id"]) and cool_road.get(b["id"], -1) <= now:
            if base._road(world, name, b["id"], wh["id"])["status"] != "ok":
                cool_road[b["id"]] = now + 60_000 + zlib.crc32(b["id"].encode()) % 30_000
    if main:
        base._bottleneck_step(world, name, wh)
        if base.naval_economy_step(world, name, wh, base._mine(world, name)):
            return
    sites = sum(1 for b in mine if b.get("constructing"))
    limit = (2 + (_era(world) >= 2)) if main else (1 + (_era(world) >= 1))
    if sites >= limit:
        return
    have: dict[str, int] = {}
    for b in mine:
        have[b["kind"]] = have.get(b["kind"], 0) + 1
    cool = world.__dict__.setdefault("_ai_cool", {})
    placed = 0
    for kind, want in _targets(world, name, wh, main, mine):
        if not kind or have.get(kind, 0) >= want or not tech.kind_allowed(world, name, kind):
            continue
        if kind in ("mine", "ironmine") and not base._deposit_site(world, name, kind):
            continue
        if not base._affordable(world, name, kind, wh):
            note(world, name, "cannot pay for %s at %s yet" % (kind, wh["id"]))
            continue
        key = (name, wh["id"], kind)
        if cool.get(key, -1) > now:
            continue
        site = base._place_near(world, name, kind, wh) if kind not in ("mine", "ironmine") else base._build_mine(world, name, kind, wh)
        if site and _infected(world, (world.buildings[site]["tx"], world.buildings[site]["ty"])) and kind not in ("defense", "flame_tower", "tesla_coil"):
            base._cancel_site(world, site)  # no new workplace inside an outbreak: it would start at a fraction of its pace
            note(world, name, "skipped %s: the site is in an infected region" % kind)
            site = None
        if not site:
            cool[key] = now + 45_000 + zlib.crc32(repr(key).encode()) % 30_000
            note(world, name, "no reachable site for %s" % kind)
            continue
        world.events.append({"kind": "ai_build", "faction": name, "building": kind, "id": site, "settlement": wh["id"], "policy": POLICY})
        have[kind] = have.get(kind, 0) + 1
        placed += 1
        if sites + placed >= limit:
            return
    if main and sites + placed < limit and not placed:
        tribe_step(world, name, wh)


def tribe_step(world: Any, name: str, wh: dict) -> None:
    """The baseline's tribe-chain planner (ai.tribe_step: soldier wares, build-cost wares, starved inputs), with what the baseline
    lacks: a cadence (every 30 game seconds) and a cooldown on every building it could not place, so a failing search is not
    repeated every decision. Places at most one building."""
    from wizard_rts import tribes, wl_defs

    now = _now(world)
    st = world.__dict__.setdefault("_ai_tribe", {}).setdefault(name, {"next": 0, "cool": {}})
    if now < st["next"]:
        return
    st["next"] = now + 30_000
    tribe = world.faction_info.get(name, {}).get("tribe")
    if not tribe:
        return
    have_kinds = {b["kind"] for b in world.buildings.values() if b["faction_name"] == name and int(b.get("hp", 1)) > 0}
    plan: list[str] = []
    seen: set = set()
    for ware in wl_defs.soldier_wares(tribe):
        plan += [b for b in base._resolve(world, name, tribe, ware, seen) if b not in plan]
    for bname in list(plan):
        spec = con.build_spec(wl_defs.PREFIX + bname)
        for ware, n in (spec or {"cost": {}})["cost"].items():
            if base._stock(world, name, ware) < n:
                for dep in base._resolve(world, name, tribe, ware, set(seen), force=base._stock(world, name, ware) == 0):
                    if dep not in plan:
                        plan.insert(0, dep)
    for b in world.buildings.values():
        if b["faction_name"] == name and b["kind"].startswith("wl:") and int(b.get("hp", 1)) > 0:
            spec = wl_defs.spec_for_kind(b["kind"])
            for ware in (spec["inputs"] if spec else {}):
                if ware not in ("recruit", "carrier") and base._stock(world, name, ware) == 0:
                    for dep in base._resolve(world, name, tribe, ware, set(seen), force=True):
                        if dep not in plan:
                            plan.append(dep)
    for bname in plan:
        kind = wl_defs.PREFIX + bname
        if kind in have_kinds or st["cool"].get(bname, -1) > now:
            continue
        spec = con.build_spec(kind)
        if spec is None or not tech.kind_allowed(world, name, kind) or not base._can_pay(world, name, spec["cost"]):
            continue
        site = base._build_tribe_building(world, name, bname, wh)
        if site:
            world.events.append({"kind": "ai_build", "faction": name, "building": bname, "id": site, "policy": POLICY})
            return
        st["cool"][bname] = now + 90_000 + zlib.crc32(bname.encode()) % 60_000
        note(world, name, "no site for tribe building %s" % bname)


def _link_outposts(world: Any, name: str, home: dict) -> None:
    """An outpost within road reach of the capital is joined to it: one network, one economy, no isolation unrest."""
    from wizard_rts import society

    st = world.__dict__.setdefault("_ai_links", {}).setdefault(name, {})
    now = _now(world)
    for cc in territory.command_centers(world, name):
        if cc is home or st.get(cc["id"], -1) > now or society._connected(world, cc["id"], home["id"]):
            continue
        if territory.cheb((cc["tx"], cc["ty"]), (home["tx"], home["ty"])) > 70:
            st[cc["id"]] = now + 10 ** 9
            continue
        res = con.build_road(world, name, cc["id"], home["id"], 90)
        st[cc["id"]] = now + (10 ** 9 if res["status"] == "ok" else 5 * 60_000)
        if res["status"] == "ok":
            world.events.append({"kind": "ai_link_outpost", "faction": name, "outpost": cc["id"], "policy": POLICY})


def economy_step(world: Any, name: str) -> None:
    world._ai_road_fails = 0
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        note(world, name, "no warehouse")
        return
    for cc in territory.command_centers(world, name):
        _settlement_step(world, name, cc, main=cc is wh)
    from wizard_rts import ai_industry

    ai_industry.industry_step(world, name, wh)
    if _era(world) >= 1:
        _link_outposts(world, name, wh)
    expansion_step(world, name, wh)
    trade_step(world, name, wh)


TRADABLE = ("log", "plank", "granite", "meat", "fish", "wheat", "bread", "coal", "iron_ore", "iron", "ration", "water")


def _wants(world: Any, name: str, wh: dict) -> list[tuple[str, int]]:
    """What the faction is short of, most urgent first (ware, amount to ask for)."""
    era = _era(world)
    have = lambda g: base._stock(world, name, g, wh)  # noqa: E731
    out = []
    if have("ration") < 4:
        out.append(("ration", 5))
    if era >= 1 and have("iron") < 3:
        out.append(("iron", 3))
    if have("plank") < 5:
        out.append(("plank", 6))
    if have("granite") < 5:
        out.append(("granite", 6))
    if any(b["faction_name"] == name and b["kind"] == "smelter" for b in world.buildings.values()) and have("coal") < 3:
        out.append(("coal", 5))
    return out


def trade_step(world: Any, name: str, wh: dict) -> None:
    """Offer the largest surplus for the worst shortage, by caravan, to a faction we are at peace with (past partners first)."""
    from wizard_rts import trade

    if not tech.unit_allowed(world, name, "caravan") or trade.active(world, name):
        return
    now = _now(world)
    st = world.__dict__.setdefault("_ai_trade", {}).setdefault(name, {"next": 0})
    if now < st["next"]:
        return
    st["next"] = now + 120_000
    wants = _wants(world, name, wh)
    if not wants:
        return
    stock = world.stocks.get(wh["id"], {})
    for want, n_want in wants:
        surplus = sorted(((int(stock.get(g, 0)), g) for g in TRADABLE if g != want and int(stock.get(g, 0)) >= 30), reverse=True)
        if not surplus:
            note(world, name, "trade: nothing in surplus to offer for %s" % want)
            return
        give = surplus[0][1]
        n_give = int(math.ceil(trade.value({want: n_want}) / trade.WARE_VALUE.get(give, 1.5) * 1.15))
        if int(stock.get(give, 0)) - n_give - trade.CARAVAN_COST.get(give, 0) < 10:
            continue
        best = None
        for cc in territory.command_centers(world, None):
            p = cc["faction_name"]
            if p == name or not p or trade.hostile(world, name, p) or not trade.can_supply(world, cc, {want: n_want}):
                continue
            d = territory.cheb((wh["tx"], wh["ty"]), (cc["tx"], cc["ty"]))
            score = 30 * trade.partners_traded(world, name, p) - d / 4.0
            if best is None or score > best[0]:
                best = (score, cc)
        if best is None:
            note(world, name, "trade: no peaceful partner has %s" % want)
            continue
        res = trade.send_caravan(world, name, wh["id"], best[1]["id"], {give: n_give}, {want: n_want})
        if res["status"] == "ok":
            note(world, name, "trade: %d %s for %d %s with %s" % (n_give, give, n_want, want, best[1]["faction_name"]))
            return
        note(world, name, "trade refused: %s" % res["reason"])


# ------------------------------------------------------------------ expansion

def _seg_dist(p: tuple, a: tuple, b: tuple) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _nests(world: Any) -> list[dict]:
    return [b for b in world.buildings.values() if b.get("kind") == "blight_nest" and int(b.get("hp", 0)) > 0]


def _site_value(world: Any, name: str, tile: tuple[int, int]) -> float:
    v = base._site_score(world, name, tile)
    home = con.faction_warehouse(world, name)
    if home is not None:  # a wagon walking past a blight nest is shot: no site whose road leads by one
        from wizard_rts.military import building_weapon

        for nb in _nests(world):
            w = building_weapon(nb)
            if w and _seg_dist((nb["tx"], nb["ty"]), (home["tx"], home["ty"]), tile) <= float(w["range"]) + 4:
                v -= 200
    if _infected(world, tile, 1):
        v -= 40
    enemy = min((territory.cheb(tile, (b["tx"], b["ty"])) for b in territory.command_centers(world, None) if b["faction_name"] != name), default=200)
    if enemy < 60:
        v -= (60 - enemy) * 0.8  # a frontier settlement is the first one to be razed
    return v


def _expansion_site(world: Any, name: str, unit: dict | None, bad: list | None = None, definition: str = territory.SETTLER_DEFINITION) -> tuple[int, int] | None:
    from wizard_rts.workers import find_path

    t = world.terrain
    home = con.faction_warehouse(world, name)
    if home is None or t is None:
        return None
    probe = {"id": "probe", "definition": definition, "faction_name": name, "alive": True, "tx": 0, "ty": 0}
    legal = []
    frontier = bool(tech.foundation_on(world))
    for y in range(8, t.h - 8, 6):
        for x in range(8, t.w - 8, 6):
            d = territory.frontier_distance(world, name, (x, y)) if frontier else territory.cheb((x, y), (home["tx"], home["ty"]))
            if d > (70 if frontier else 95) or not t.ground(x, y) or territory.separation_problem(world, name, (x, y)):
                continue
            if bad and any(territory.cheb((x, y), tuple(b)) < 10 for b in bad):
                continue
            probe["tx"], probe["ty"] = x, y
            if territory.deploy_check(world, probe) is None:
                legal.append((d, (x, y)))
    if not legal:
        return None
    legal.sort()
    if len(legal) > 48:
        legal = legal[:: len(legal) // 48 + 1]
    cands = sorted(((_site_value(world, name, tile) - d * 0.5, tile) for d, tile in legal), reverse=True)
    if unit is None:
        return cands[0][1]
    loco = (unit.get("loco") or "foot")
    start = (int(unit["tx"]), int(unit["ty"]))
    for _v, tile in cands[:6]:
        if find_path(world, start, tile, limit=500, avoid=set(), max_nodes=250_000, loco=loco) is not None:
            return tile
    return None


def founder_lost(world: Any, unit: dict, by: str) -> None:
    """Called when a founder dies: remember it (the faction holds expansion for a while and turns on the nest that did it)."""
    shooter = world.buildings.get(by)
    world.__dict__.setdefault("_ai_founder_lost", {})[unit["faction_name"]] = int(world.dmb.clock.get("game_ms", 0))
    if shooter is not None and shooter.get("kind") == "blight_nest":
        world.__dict__.setdefault("_ai_nest_priority", {})[unit["faction_name"]] = shooter["id"]


def _drive(world: Any, name: str, u: dict, now: int) -> None:
    from wizard_rts.military import order_move

    if u.get("deploying_ms"):
        return
    st = u.setdefault("ai", {"site": None, "bad": [], "since": now, "fails": 0})
    here = (int(u["tx"]), int(u["ty"]))
    site = st["site"]
    if site is not None and here == tuple(site):
        res = territory.deploy(world, u["id"])
        if res["status"] != "ok":
            st["bad"].append(list(site))
            st["site"] = None
            note(world, name, "deploy rejected: %s" % res["reason"])
            world.events.append({"kind": "ai_expand_rejected", "faction": name, "reason": res["reason"], "tile": list(site), "policy": POLICY})
        else:
            world.fstat(name, "mcv_deployed")
            world.events.append({"kind": "ai_expand_deploy", "faction": name, "tile": list(site), "policy": POLICY})
        return
    if site is None or st["fails"] >= 3 or now - st["since"] > 6 * 60_000:
        if site is not None:
            st["bad"].append(list(site))
        site = _expansion_site(world, name, u, st["bad"], u["definition"])
        st.update(site=list(site) if site else None, fails=0, since=now)
        if site is None:
            note(world, name, "founder has no reachable legal site")
            return
        world.events.append({"kind": "ai_expand_site", "faction": name, "tile": list(site), "policy": POLICY})
        order_move(world, [u["id"]], site[0], site[1])
        return
    if not u.get("order"):
        st["fails"] += 1
        order_move(world, [u["id"]], site[0], site[1])


def expansion_step(world: Any, name: str, wh: dict) -> None:
    if world.terrain is None or not getattr(world, "ai_expand", True):
        return
    now = _now(world)
    founders = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and territory.is_founder(u)]
    for u in founders:
        _drive(world, name, u, now)
    if founders:
        return
    mine = base._mine(world, name)
    if any(i["unit"] in ("mcv", "settlers") for b in mine for i in b.get("queue", [])):
        return
    ccs = territory.command_centers(world, name)
    cap = 10**6 if tech.foundation_on(world) else MAX_CC_BY_ERA[min(_era(world), 3)]  # nocards: growth is limited by wares, space and food, not a quota
    if len(ccs) >= cap:
        return
    if _food(world, name, wh) < 4 and len(ccs) >= 2:
        note(world, name, "expansion waits for food")
        return
    st = world.__dict__.setdefault("_ai_expand", {}).setdefault(name, {"last": -10**9})
    if now - st["last"] < 90_000:
        return
    options = []
    if tech.unit_allowed(world, name, "settlers"):
        options.append((wh, "settlers"))
    options += [(b, "mcv") for b in mine if b["kind"] == "vehicle_factory" and b.get("operational") and tech.unit_allowed(world, name, "mcv")]
    if not options:
        return
    lost = world.__dict__.get("_ai_founder_lost", {}).get(name)
    if lost is not None and now - lost < 5 * 60_000:
        note(world, name, "expansion waits: a blight nest killed our last founder")
        return
    b, founder = options[-1] if len(options) > 1 and base._can_pay(world, name, con.RECIPES["vehicle_factory"]["mcv"]["cost"]) else options[0]
    cost = con.RECIPES["warehouse" if founder == "settlers" else "vehicle_factory"][founder]["cost"]
    short = {g: n - base._stock(world, name, g, wh) for g, n in cost.items() if base._stock(world, name, g, wh) < n and g not in base.FLOWING}
    if short and not any(base._makes(world, name, g) for g in short):
        # nothing of ours makes what is missing: queuing would only hold the store's goods hostage
        note(world, name, "settlers wait for %s" % ", ".join("%s %d" % kv for kv in sorted(short.items())))
        return
    # otherwise queue now: a queued founder reserves its goods in the warehouse as they arrive (logistics), so the mines cannot keep
    # taking every ration first (Red never expanded that way in the 12 Oct runs)
    if now - st.get("site_checked", -10**9) < 60_000 and not st.get("site_ok"):
        return
    st["site_checked"] = now
    st["site_ok"] = _expansion_site(world, name, None) is not None  # a full sweep: at most once a game minute
    if not st["site_ok"]:
        note(world, name, "no legal settlement site left")
        st["last"] = now
        return
    if con.queue_unit(world, b["id"], founder)["status"] == "ok":
        q = b["queue"]
        item = q.pop()
        q.insert(0 if not q or q[0]["state"] == "waiting" else 1, item)  # the settlement comes before more soldiers
        con._sync_requests(world, b)
        st["last"] = now
        world.fstat(name, "mcv_queued")
        world.events.append({"kind": "ai_expand_queue", "faction": name, "building": b["id"], "founder": founder, "policy": POLICY})


# ------------------------------------------------------------------ military

def _recipe_value(world: Any, name: str, b: dict, kind: str) -> float:
    rec = con.recipe_for(world, b, kind)
    if rec is None:
        return -1.0
    cost = sum(WARE_WEIGHT.get(g, 1.2) * n for g, n in rec["cost"].items()) + rec["ms"] / 30_000
    afford = all(base._stock(world, name, g) >= n for g, n in rec["cost"].items())
    return strength_of(rec["definition"]) / max(1.0, cost) * (1.6 if afford else 1.0)


def choose_unit(world: Any, name: str, b: dict) -> str | None:
    kinds = [k for k in con.RECIPES.get(b["kind"], {}) if k not in ("mcv", "settlers") and tech.unit_allowed(world, name, k)]
    if not kinds:
        return None
    army = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon")]
    counts: dict[str, int] = {}
    for u in army:
        counts[u["kind"]] = counts.get(u["kind"], 0) + 1
    # value per cost, with a diminishing return on a kind the army already has many of (a mixed force has fewer counters)
    return max(kinds, key=lambda k: (_recipe_value(world, name, b, k) / (1.0 + 0.15 * counts.get(k, 0)), k))


def _recruit(world: Any, name: str, mine: list[dict]) -> None:
    era = _era(world)
    army = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon") and u.get("loco") not in base.NAVAL]
    navy = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("loco") in base.NAVAL]
    cap = ARMY_CAP_BY_ERA[min(era, 3)]
    food = _food(world, name)
    reserved = _reserved(world, name)
    for b in sorted(mine, key=lambda x: x["id"]):
        if b["kind"] not in con.RECIPES or b["kind"] == "warehouse" or not b.get("operational") or b.get("constructing") or len(b.get("queue", [])) >= 2:
            continue
        if b["kind"] in base.NAVAL_BUILDINGS:
            if len(navy) < base.MAX_NAVY:
                k = choose_unit(world, name, b)
                if k:
                    con.queue_unit(world, b["id"], k)
            continue
        if len(army) >= cap:
            note(world, name, "army at its cap (%d)" % cap)
            continue
        k = choose_unit(world, name, b)
        if k is None:
            continue
        rec = con.recipe_for(world, b, k)
        if "ration" in rec["cost"] and food < 3 and army:
            note(world, name, "recruiting waits: rations are needed by the miners")
            continue
        clash = [g for g in rec["cost"] if g in reserved and base._stock(world, name, g) < reserved[g] + rec["cost"][g]]
        if clash and army:
            note(world, name, "recruiting waits: %s is kept for the settlers" % ", ".join(clash))
            continue
        con.queue_unit(world, b["id"], k)


def _target_value(world: Any, name: str, b: dict, centre: tuple[float, float], power: float) -> float:
    d = math.hypot(b["tx"] - centre[0], b["ty"] - centre[1])
    if b.get("kind") == "blight_nest":
        # an outbreak nest is worth clearing only where it hurts us: in or beside one of our settlements; the reward grows with its cubes
        near = any(territory.cheb((b["tx"], b["ty"]), (cc["tx"], cc["ty"])) <= territory.radius_of(cc) + 14 for cc in territory.command_centers(world, name))
        if not near:
            return -1.0
        defence = force_near(world, (b["tx"], b["ty"]), 9.0, name, True)
        if power < ATTACK_RATIO * defence:
            return -1.0
        return (12.0 + 8.0 * int(b.get("nest_cubes", 1))) / (1.0 + d / 40.0)
    value = 30.0 if b.get("command_center") and b.get("outpost") else (22.0 if b.get("command_center") else 8.0)
    if b["kind"] in ("barracks", "vehicle_factory", "war_lodge", "mdy:ground_factory"):
        value = max(value, 14.0)
    defence = force_near(world, (b["tx"], b["ty"]), 12.0, name, True)
    if power < ATTACK_RATIO * defence:
        return -1.0  # not with this squad
    return value / (1.0 + d / 40.0) / (1.0 + defence / max(power, 1.0))


def _pick_target(world: Any, name: str, units: list[dict]) -> dict | None:
    if not units:
        return None
    cx = sum(u["tx"] for u in units) / len(units)
    cy = sum(u["ty"] for u in units) / len(units)
    power = sum(unit_strength(u) for u in units)
    best = None
    for b in base._known_targets(world, name):
        v = _target_value(world, name, b, (cx, cy), power)
        if v > 0 and (best is None or v > best[0]):
            best = (v, b)
    return best[1] if best else None


def military_step(world: Any, name: str) -> None:
    from wizard_rts.military import order_move

    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    mine = base._mine(world, name)
    _recruit(world, name, mine)
    navy = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("loco") in base.NAVAL]
    base.navy_step(world, name, wh, navy)
    army = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon") and u.get("loco") not in base.NAVAL]
    now = _now(world)
    squads = world.__dict__.setdefault("_ai_squads", {})
    sq = squads.get(name)
    alive = {u["id"]: u for u in army}
    if sq is not None:
        sq["ids"] = [i for i in sq["ids"] if i in alive]
        members = [alive[i] for i in sq["ids"]]
        tgt = world.buildings.get(sq["target"])
        if members and tgt is not None and int(tgt.get("hp", 0)) > 0:
            cx = sum(u["tx"] for u in members) / len(members)
            cy = sum(u["ty"] for u in members) / len(members)
            ours = sum(unit_strength(u) for u in members)
            theirs = force_near(world, (cx, cy), 10.0, name, True)
            if theirs > 0 and ours < RETREAT_RATIO * theirs:
                home = min(territory.command_centers(world, name), key=lambda c: territory.cheb((int(cx), int(cy)), (c["tx"], c["ty"])), default=wh)
                order_move(world, sq["ids"], home["tx"], home["ty"] + 4)
                world.events.append({"kind": "ai_retreat", "faction": name, "launched": sq["size0"], "left": len(members), "after_ms": now - sq["since"], "policy": POLICY})
                squads.pop(name)
                sq = None
        if sq is not None and (not members or tgt is None or int(tgt.get("hp", 0)) <= 0):
            nxt = _pick_target(world, name, members) if members else None
            if nxt is None:
                squads.pop(name)
                world.events.append({"kind": "ai_squad_done", "faction": name, "left": len(members), "policy": POLICY})
                sq = None
            else:
                sq["target"] = nxt["id"]
                world.events.append({"kind": "ai_retarget", "faction": name, "target": nxt["id"], "kind_of": nxt["kind"], "units": len(members), "policy": POLICY})
                base._send(world, members, nxt)
        elif sq is not None:
            stalled = [u for u in members if not u.get("order")]
            if stalled:
                base._send(world, stalled, tgt)
    in_squad = set(sq["ids"]) if sq is not None else set()
    idle = [u for u in army if u["id"] not in in_squad and not u.get("order") and u.get("status") in ("idle", None, "attacking", "blocked", "stuck", "waiting_route")]
    free = [u for u in army if u["id"] not in in_squad]
    # 1. defend: the strongest local answer to every threat, nearest units first
    for cc, t in _threats(world, name):
        enemy_power = force_near(world, (t["tx"], t["ty"]), 8.0, name, True)
        responders = sorted(free, key=lambda u: math.hypot(u["tx"] - t["tx"], u["ty"] - t["ty"]))
        sent, power = [], 0.0
        for u in responders:
            if power >= 1.5 * enemy_power and len(sent) >= 2:
                break
            sent.append(u)
            power += unit_strength(u)
        if sent:
            order_move(world, [u["id"] for u in sent], t["tx"], t["ty"], attack_move=True)
            world.events.append({"kind": "ai_defend", "faction": name, "at": [t["tx"], t["ty"]], "centre": cc["id"], "units": len(sent), "enemy": t.get("faction_name", ""), "policy": POLICY})
            ids = {u["id"] for u in sent}
            free = [u for u in free if u["id"] not in ids]
            idle = [u for u in idle if u["id"] not in ids]
        if sq is not None and enemy_power > sum(unit_strength(u) for u in sent) and cc is wh:
            order_move(world, sq["ids"], t["tx"], t["ty"], attack_move=True)  # the capital is in danger: the squad comes home
            squads.pop(name, None)
            sq = None
    if not getattr(world, "ai_aggressive", True):
        _garrison(world, name, idle)
        return
    # 2. attack: gather a squad at the rally point, launch it only with a measured advantage
    size = SQUAD_BY_ERA[min(_era(world), 3)]
    guard = max(2, len(army) // 4)
    prio = world.__dict__.get("_ai_nest_priority", {}).get(name)
    pn = world.buildings.get(prio) if prio else None
    if sq is None and pn is not None and int(pn.get("hp", 0)) > 0 and idle:
        pool = sorted(idle, key=lambda u: u["id"])
        power = sum(unit_strength(u) for u in pool)
        if power >= force_near(world, (pn["tx"], pn["ty"]), 9.0, name, True):  # everything we have, once it at least matches the nest
            squads[name] = {"ids": [u["id"] for u in pool], "size0": len(pool), "target": pn["id"], "since": now}
            world.events.append({"kind": "ai_attack", "faction": name, "target": pn["id"], "units": len(pool), "target_kind": "blight_nest", "of": "",
                                 "distance": 0, "policy": POLICY})
            base._send(world, pool, pn)
            idle = []
        else:
            note(world, name, "gathering to clear the nest that blocks our expansion (%.0f of %.0f)" % (power, force_near(world, (pn["tx"], pn["ty"]), 9.0, name, True)))
    elif prio and (pn is None or int(pn.get("hp", 0)) <= 0):
        world._ai_nest_priority.pop(name, None)
    if sq is None and len(idle) >= size + guard:
        pool = sorted(idle, key=lambda u: (-unit_strength(u), u["id"]))[: len(idle) - guard]
        target = _pick_target(world, name, pool)
        if target is not None and now < ATTACK_AFTER_MS and target.get("kind") != "blight_nest":
            target = None  # before the war window only an outbreak nest at home is worth a sortie
        if target is not None:
            squads[name] = {"ids": [u["id"] for u in pool], "size0": len(pool), "target": target["id"], "since": now}
            world.events.append({"kind": "ai_attack", "faction": name, "target": target["id"], "units": len(pool), "target_kind": target["kind"],
                                 "of": target["faction_name"], "distance": round(math.hypot(target["tx"] - pool[0]["tx"], target["ty"] - pool[0]["ty"])),
                                 "policy": POLICY})
            base._send(world, pool, target)
            ids = {u["id"] for u in pool}
            idle = [u for u in idle if u["id"] not in ids]
        else:
            note(world, name, "no target worth the risk for %d units" % len(pool))
    _garrison(world, name, idle)


def _garrison(world: Any, name: str, idle: list[dict]) -> None:
    """Idle soldiers guard the settlement with the most unrest first (a garrison calms it), then the approaches as the baseline does."""
    from wizard_rts.military import order_move

    if not idle:
        return
    unruly = []
    for cc in territory.command_centers(world, name):
        rec = world.dmb.settlements.get(cc.get("settlement_id", ""), {})
        if float(rec.get("unrest", 0.0)) >= 0.25 and not any(u["faction_name"] == name and u.get("weapon") and territory.cheb((u["tx"], u["ty"]), (cc["tx"], cc["ty"])) <= territory.radius_of(cc)
                                                              for u in world.units.values() if u.get("alive", True)):
            unruly.append((-float(rec.get("unrest", 0.0)), cc["id"], cc))
    unruly.sort()
    rest = list(sorted(idle, key=lambda u: u["id"]))
    for _neg, _id, cc in unruly:
        if len(rest) <= 1:
            break
        pair = sorted(rest, key=lambda u: territory.cheb((u["tx"], u["ty"]), (cc["tx"], cc["ty"])))[:2]
        tile = base._free_ground_near(world, (cc["tx"] + 2, cc["ty"] + 3))
        if tile is not None:
            order_move(world, [u["id"] for u in pair], tile[0], tile[1], attack_move=True)
            world.events.append({"kind": "ai_garrison", "faction": name, "centre": cc["id"], "units": len(pair), "policy": POLICY})
        ids = {u["id"] for u in pair}
        rest = [u for u in rest if u["id"] not in ids]
    base._station(world, name, rest)


def decide(world: Any, name: str) -> None:
    pick = pick_card(world, name)
    if pick:
        tech.draft(world, name, pick)
    economy_step(world, name)
    military_step(world, name)
