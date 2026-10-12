"""Settlement unrest from real conditions (D18/S12: splits need an unrest score; the first M4 version had nothing that produced it).

Once a game minute every standing settlement's `unrest` (0..1, on its chronicle record) moves by the sum of pressures that are read
from the world, never from a ranking:

  hunger      +0.03  its warehouse holds no food ware (ration, bread, fish, meat, smoked food) while it has workplaces
  closures    +0.01  per disrupted workplace in it (collapse, sickness... see disruption.py)
  war         +0.06  per building of it destroyed in the last ten game minutes (by any cause)
  isolation   +0.01 an outpost further than history.SPLIT_DISTANCE from its faction's capital with no road link to it
  garrison    -0.02  armed units of its own faction stand within its territory
  plenty      -0.02  its warehouse holds 10 or more rations
  (garrison and plenty count half with one outbreak cube in the settlement's region, not at all with two or more)

The outbreak pressure (per cube) and the slow fading of unrest (-0.01 a minute where no outbreak sits) are regions._unrest's, on the
same cadence. A faction AI can lower unrest only with legal means
(food, repairs, a garrison, roads); nothing here gives the wizard's magic to a faction. history.split_candidates reads the result.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import territory

CHECK_EVERY = 600
FOOD = ("ration", "bread", "fish", "meat", "smoked_fish", "smoked_meat", "bread_frisians", "honey_bread", "snack", "meal")
WINDOW_MS = 10 * 60_000


def note_loss(world: Any, building: dict) -> None:
    """Called when a building is destroyed: remember it against its settlement for the war pressure."""
    sid = building.get("settlement_id")
    if not sid:
        cc = territory.settlement_of(world, building)
        sid = cc.get("settlement_id") if cc else None
    if not sid:
        return
    losses = world.__dict__.setdefault("_losses", {})
    losses.setdefault(sid, []).append(int(world.dmb.clock.get("game_ms", 0)))


def _connected(world: Any, a: str, b: str) -> bool:
    seen, stack = {a}, [a]
    while stack:
        cur = stack.pop()
        for nxt, _r in world.adjacency.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return b in seen


def pressures(world: Any, rec: dict) -> dict[str, float]:
    from wizard_rts import history

    now = int(world.dmb.clock.get("game_ms", 0))
    cc = world.buildings.get(rec["centre"])
    out: dict[str, float] = {}
    if cc is None:
        return out
    stock = world.stocks.get(cc["id"], {})
    members = [b for b in world.buildings.values() if b["faction_name"] == rec["faction"] and "hp" in b and int(b["hp"]) > 0
               and territory.settlement_of(world, b) is cc]
    workplaces = [b for b in members if b["kind"] != "warehouse" and not b.get("constructing")]
    if workplaces and not any(int(stock.get(g, 0)) > 0 for g in FOOD):
        out["hunger"] = 0.03
    closed = sum(1 for b in members if b.get("disrupted"))
    if closed:
        out["closures"] = 0.01 * closed
    recent = [t for t in world.__dict__.get("_losses", {}).get(rec["id"], []) if now - t <= WINDOW_MS]
    if recent:
        out["war"] = 0.06 * len(recent)
    if cc.get("outpost"):
        home = next((c for c in territory.command_centers(world, rec["faction"]) if not c.get("outpost")), None)
        if home is None or (territory.cheb((cc["tx"], cc["ty"]), (home["tx"], home["ty"])) > history.SPLIT_DISTANCE and not _connected(world, cc["id"], home["id"])):
            out["isolation"] = 0.01  # was 0.015: almost every distant outpost drifted to a split
    r = territory.radius_of(cc)
    rg = world.__dict__.get("regions")
    cubes = rg.cubes[rg.region_at(cc["tx"], cc["ty"])] if rg is not None else 0
    calm = 0.0 if cubes >= 2 else (0.5 if cubes == 1 else 1.0)  # the sick are not calmed by full stores or soldiers in the square
    if calm and any(u["faction_name"] == rec["faction"] and u.get("alive", True) and u.get("weapon") and territory.cheb((u["tx"], u["ty"]), (cc["tx"], cc["ty"])) <= r
                    for u in world.units.values()):
        out["garrison"] = -0.02 * calm
    if calm and int(stock.get("ration", 0)) >= 10:
        out["plenty"] = -0.02 * calm
    return out  # the slow fading of unrest is regions._unrest's (-0.01 a minute where no outbreak sits)


def society_quantum(world: Any) -> None:
    if world.economy_quanta % CHECK_EVERY or world.economy_quanta == 0:
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    for sid, lst in list(world.__dict__.get("_losses", {}).items()):
        world._losses[sid] = [t for t in lst if now - t <= WINDOW_MS]
    for sid, rec in sorted(world.dmb.settlements.items()):
        if rec.get("state") != "standing":
            continue
        p = pressures(world, rec)
        rec["pressures"] = {k: round(v, 3) for k, v in p.items()}
        rec["unrest"] = round(min(1.0, max(0.0, float(rec.get("unrest", 0.0)) + sum(p.values()))), 4)
