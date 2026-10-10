"""Faction commanders. They use the same commands as God Mode, and nothing else.

An AI faction never gets free wares or units. It assesses what its economy
lacks, places construction sites near its warehouse (paid for with warehouse
stock, delivered over roads), connects them, queues recruits (paid in axes,
granite and planks that its own industry made), gathers idle units, and sends
them against an enemy, defending its base first.

Shaped after Widelands' DefaultAI (build priorities driven by economy needs and
space) and OpenRA's HackyAI/SquadManager (assemble a squad, pick an enemy
target, attack-move). It is far smaller than either; see docs/feature_catalogue.json.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import construction as con

DECIDE_EVERY = 50  # quanta (5 s) between decisions per faction
BASE_PLAN = {
    "producer": 2, "ranger": 2, "quarry": 1, "mine": 1, "ironmine": 1,
    "smelter": 1, "smithy": 1, "processor": 1, "barracks": 1, "vehicle_factory": 1, "defense": 1,
}
# Personality: extra buildings, squad size before attacking, target preference.
PERSONALITY = {
    "Red": {"plan": {"barracks": 2, "smithy": 2}, "squad": 6, "targets": ["barracks", "vehicle_factory", "warehouse"]},
    "Blue": {"plan": {"producer": 3, "ranger": 3, "processor": 2}, "squad": 8, "targets": ["warehouse", "processor", "barracks"]},
    "Green": {"plan": {"quarry": 2, "vehicle_factory": 2}, "squad": 7, "targets": ["vehicle_factory", "barracks", "warehouse"]},
    "Yellow": {"plan": {"mine": 2, "ironmine": 2, "smithy": 2}, "squad": 7, "targets": ["smithy", "mine", "warehouse"]},
    "Purple": {"plan": {"defense": 3, "barracks": 2}, "squad": 9, "targets": ["defense", "barracks", "warehouse"]},
    "Orange": {"plan": {"vehicle_factory": 2, "barracks": 2, "quarry": 2}, "squad": 7, "targets": ["warehouse", "vehicle_factory", "barracks"]},
}
MAX_ARMY = 30


def _plan(name: str) -> dict[str, int]:
    plan = dict(BASE_PLAN)
    for k, v in PERSONALITY.get(name, {}).get("plan", {}).items():
        plan[k] = max(plan.get(k, 0), v)
    return plan


def _mine(world: Any, name: str) -> list[dict]:
    return [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]


def _stock(world: Any, name: str, good: str) -> int:
    return sum(
        int(world.stocks.get(b["id"], {}).get(good, 0))
        for b in world.buildings.values()
        if b["faction_name"] == name and b["kind"] == "warehouse" and int(b.get("hp", 1)) > 0
    )


def _affordable(world: Any, name: str, kind: str) -> bool:
    return all(_stock(world, name, g) >= n for g, n in con.BUILD_MENU[kind]["cost"].items())


def _place_near(world: Any, name: str, kind: str, anchor: dict) -> str | None:
    """First legal tile on a spiral around the warehouse that a road can reach."""
    cx, cy = anchor["tx"], anchor["ty"]
    for r in range(4, 26, 2):
        for dy in range(-r, r + 1, 3):
            for dx in range(-r, r + 1, 3):
                if max(abs(dx), abs(dy)) != r:
                    continue
                res = con.place_building(world, name, kind, cx + dx, cy + dy)
                if res["status"] != "ok":
                    continue
                road = con.build_road(world, name, res["id"], anchor["id"])
                if road["status"] == "ok":
                    return res["id"]
                _cancel_site(world, res["id"])
    return None


def _cancel_site(world: Any, bid: str) -> None:
    from wizard_rts.lifecycle import purge_building

    purge_building(world, bid, "site_cancelled")


def economy_step(world: Any, name: str) -> None:
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    mine = _mine(world, name)
    have: dict[str, int] = {}
    for b in mine:
        have[b["kind"]] = have.get(b["kind"], 0) + 1  # sites count: they are on their way
    # repair the road network: a building with no road gets one
    for b in mine:
        if b["kind"] != "warehouse" and b["kind"] not in ("ranger",) and not world.adjacency.get(b["id"]):
            con.build_road(world, name, b["id"], wh["id"])
    # one new site at a time
    if any(b.get("constructing") for b in mine):
        return
    plan = _plan(name)
    logs = _stock(world, name, "log")
    order = ["producer", "ranger", "processor", "quarry", "mine", "ironmine", "smelter", "smithy", "barracks", "vehicle_factory", "defense"]
    if logs < 6:  # wood first when it runs short
        order = ["producer", "ranger"] + [k for k in order if k not in ("producer", "ranger")]
    for kind in order:
        if have.get(kind, 0) >= plan.get(kind, 0):
            continue
        if kind in ("mine", "ironmine") and not _deposit_site(world, name, kind):
            continue
        if not _affordable(world, name, kind):
            continue
        site = _place_near(world, name, kind, wh) if kind not in ("mine", "ironmine") else None
        if site:
            world.events.append({"kind": "ai_build", "faction": name, "building": kind, "id": site})
            return


def _deposit_site(world: Any, name: str, kind: str) -> bool:
    """A mine can only be rebuilt where a deposit still has something in it; the AI has no prospecting yet."""
    return False


def military_step(world: Any, name: str) -> None:
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    mine = _mine(world, name)
    army = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon")]
    # recruitment: keep two orders queued per production building, within the army cap
    for b in mine:
        if b["kind"] in con.RECIPES and b.get("operational") and len(b.get("queue", [])) < 2 and len(army) < MAX_ARMY:
            unit_kind = next(iter(con.RECIPES[b["kind"]]))
            con.queue_unit(world, b["id"], unit_kind)
    idle = [u for u in army if not u.get("order") and u.get("status") in ("idle", None, "attacking", "blocked", "stuck")]
    if not idle:
        return
    # defend first: enemies near the capital
    threat = _nearest_enemy_unit(world, name, (wh["tx"], wh["ty"]), 22.0)
    if threat is not None:
        from wizard_rts.military import order_move

        order_move(world, [u["id"] for u in idle], threat["tx"], threat["ty"], attack_move=True)
        world.events.append({"kind": "ai_defend", "faction": name, "at": [threat["tx"], threat["ty"]]})
        return
    squad = PERSONALITY.get(name, {}).get("squad", 4)
    if len(idle) < squad:
        return
    target = _pick_target(world, name, idle)
    if target is None:
        return
    from wizard_rts.military import order_attack, order_move

    ids = [u["id"] for u in idle]
    # march together to the enemy base, then the squad attacks what it meets (attack-move),
    # then the specific building order takes over once they are in sight
    centre = (target["tx"], target["ty"])
    near = min(idle, key=lambda u: math.hypot(u["tx"] - centre[0], u["ty"] - centre[1]))
    if math.hypot(near["tx"] - centre[0], near["ty"] - centre[1]) > 12:
        order_move(world, ids, centre[0], centre[1], attack_move=True)
    else:
        for uid in ids:
            order_attack(world, uid, target["id"])
    world.events.append({"kind": "ai_attack", "faction": name, "target": target["id"], "units": len(ids)})


def _nearest_enemy_unit(world: Any, name: str, pos: tuple[int, int], radius: float) -> dict | None:
    best = None
    for u in world.units.values():
        if u["faction_name"] == name or not u.get("alive", True):
            continue
        d = math.hypot(u["tx"] - pos[0], u["ty"] - pos[1])
        if d <= radius and (best is None or d < best[0]):
            best = (d, u)
    return best[1] if best else None


def _pick_target(world: Any, name: str, squad: list[dict]) -> dict | None:
    prefs = PERSONALITY.get(name, {}).get("targets", ["warehouse"])
    cx = sum(u["tx"] for u in squad) / len(squad)
    cy = sum(u["ty"] for u in squad) / len(squad)
    best = None
    for b in world.buildings.values():
        if b["faction_name"] == name or "hp" not in b or int(b["hp"]) <= 0:
            continue
        rank = prefs.index(b["kind"]) if b["kind"] in prefs else len(prefs)
        d = math.hypot(b["tx"] - cx, b["ty"] - cy)
        score = d + rank * 25.0  # a preferred kind is worth walking 25 cells further per rank
        if best is None or score < best[0]:
            best = (score, b)
    return best[1] if best else None


def ai_quantum(world: Any) -> None:
    n = world.economy_quanta
    if n % DECIDE_EVERY != 0:
        return
    for k, name in enumerate(world.faction_info):
        if name == world.controlled_faction or (n // DECIDE_EVERY + k) % 1 != 0:
            continue
        economy_step(world, name)
        military_step(world, name)
