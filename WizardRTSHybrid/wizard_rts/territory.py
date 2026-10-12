"""Command centres, construction territory and the Mobile Construction Vehicle.

Every faction starts with one warehouse. It is also its immobile command centre: buildings may only be placed inside the
square (Chebyshev) radius of one of the faction's command centres. The OpenRA war factory can build an MCV (a real queue, paid in
wares that were delivered to the factory, see construction.RECIPES). The MCV is a unit on the ground: it walks with the normal
pathfinder, can be selected, commanded, shot, and given a Deploy command. Deploying consumes it exactly once and creates a new
command centre (a warehouse, OpenRA Construction Yard art) with its own radius. Nothing is conjured: the starter wares the
new centre holds are the cargo the MCV carried, taken out of the war factory's stock when the vehicle was built.

Separation rule (config: `HybridWorld.cc_buffer`): a centre may only be deployed where its square would not touch the square of
ANY other centre, friendly or enemy, plus a buffer: Chebyshev distance > radius_new + radius_other + buffer.
"""

from __future__ import annotations

from typing import Any

HOME_RADIUS = 34  # the faction's first warehouse (construction.TERRITORY_RADIUS)
OUTPOST_RADIUS = 16  # a deployed command centre (a 33x33 settlement); two homes 125 tiles apart still leave a corridor between them
BUFFER = 4  # extra tiles between two centres' areas
DEPLOY_MS = 3_000
MCV_DEFINITION = "openra.mcv"
CC_DEFINITION = "openra.fact"
SETTLER_DEFINITION = "dmb.settlers"  # the Prehistoric settlement founder (tech card Settlers): unfolds into a Widelands warehouse
# what each settlement founder becomes: (definition of the new centre, label, footprint offsets)
DEPLOYERS: dict[str, tuple[str, str, list[tuple[int, int]] | None]] = {
    MCV_DEFINITION: (CC_DEFINITION, "Command centre", None),
    SETTLER_DEFINITION: ("widelands.warehouse", "Settlement", []),
}


def is_founder(unit: dict | None) -> bool:
    """An MCV or a settlers' wagon: a unit that can found a settlement."""
    return unit is not None and unit.get("definition") in DEPLOYERS
# Footprint relative to the door tile (bottom middle), the 3x3 of the Construction Yard picture (72x72 px at 24 px a cell).
CC_FOOTPRINT: list[tuple[int, int]] = [(-1, -2), (0, -2), (1, -2), (-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0)]


def radius_of(b: dict) -> int:
    return int(b.get("territory", HOME_RADIUS))


def command_centers(world: Any, faction: str | None = None, alive: bool = True) -> list[dict]:
    out = []
    for bid in world.cc_ids:
        b = world.buildings.get(bid)
        if b is None or (faction is not None and b["faction_name"] != faction):
            continue
        if alive and int(b.get("hp", 1)) <= 0:
            continue
        out.append(b)
    return out


def cheb(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def covering(world: Any, faction: str, tile: tuple[int, int]) -> dict | None:
    """The faction's command centre whose build area contains the tile (the nearest one), or None."""
    best = None
    for b in command_centers(world, faction):
        d = cheb(tile, (b["tx"], b["ty"]))
        if d <= radius_of(b) and (best is None or d < best[0]):
            best = (d, b)
    return best[1] if best else None


def frontier_distance(world: Any, faction: str, tile: tuple[int, int]) -> int:
    """Chebyshev distance from `tile` to the faction's nearest command centre (growth proceeds from the frontier, not from the capital)."""
    return min((cheb(tile, (c["tx"], c["ty"])) for c in command_centers(world, faction)), default=10**6)


def in_territory(world: Any, faction: str, tile: tuple[int, int]) -> bool:
    return covering(world, faction, tile) is not None


def settlement_of(world: Any, b: dict) -> dict | None:
    """The command centre a building belongs to: the nearest of its faction's centres."""
    best = None
    for cc in command_centers(world, b["faction_name"]):
        d = cheb((b["tx"], b["ty"]), (cc["tx"], cc["ty"]))
        if best is None or d < best[0]:
            best = (d, cc)
    return best[1] if best else None


def footprint(tile: tuple[int, int], definition: str = MCV_DEFINITION) -> list[tuple[int, int]]:
    offs = DEPLOYERS.get(definition, DEPLOYERS[MCV_DEFINITION])[2]
    return [tile] + [(tile[0] + dx, tile[1] + dy) for dx, dy in (CC_FOOTPRINT if offs is None else offs)]


def separation_problem(world: Any, faction: str, tile: tuple[int, int]) -> str | None:
    """None if a centre at `tile` keeps clear of every other centre's area, else which kind of area it would overlap."""
    buffer = int(getattr(world, "cc_buffer", BUFFER))
    for other in command_centers(world, None):
        if cheb(tile, (other["tx"], other["ty"])) <= OUTPOST_RADIUS + radius_of(other) + buffer:
            return "overlaps_friendly_territory" if other["faction_name"] == faction else "overlaps_enemy_territory"
    return None


def deploy_check(world: Any, unit: dict) -> str | None:
    """Every rule for deploying this MCV where it stands, with no side effects. None means it may deploy."""
    if unit is None or not unit.get("alive", True):
        return "no_unit"
    if not is_founder(unit):
        return "not_an_mcv"
    if unit.get("deploying_ms"):
        return "already_deploying"
    tile = (int(unit["tx"]), int(unit["ty"]))
    overlap = separation_problem(world, unit["faction_name"], tile)  # the rule that matters most is reported first
    if overlap:
        return overlap
    t = world.terrain
    fp = footprint(tile, unit["definition"])
    occupied = {(u["tx"], u["ty"]) for uid, u in world.units.items() if u.get("alive", True) and uid != unit["id"]}
    for p in fp:
        if not world.tile_in_bounds(*p):
            return "outside_map"
        if t is not None and not t.ground(*p):
            return "invalid_terrain"
    if not world.tile_in_bounds(tile[0], tile[1] + 1) or (t is not None and not t.ground(tile[0], tile[1] + 1)):
        return "no_access"
    for p in fp:
        if p in world.tree_tiles or p in world.road_tile_set or p in world.reserved_tiles:
            return "tile_occupied"
        if p in world.blocked and p != tile:
            return "tile_occupied"
        if p in occupied:
            return "units_in_the_way"
        if t is not None and not t.can_build(p[0], p[1], "medium" if p == tile else "small"):
            return "invalid_terrain"
    front = (tile[0], tile[1] + 1)
    if front in world.blocked:
        return "no_access"
    return None


def deploy(world: Any, unit_id: str) -> dict[str, Any]:
    """The Deploy command (God Mode and the AI): begin transforming the MCV where it stands."""
    unit = world.units.get(unit_id)
    why = deploy_check(world, unit) if unit is not None else "no_unit"
    if why:
        world.events.append({"kind": "deploy_rejected", "unit": unit_id, "reason": why})
        return {"status": "rejected", "reason": why}
    unit["deploying_ms"] = DEPLOY_MS
    unit["status"] = "deploying"
    unit.pop("order", None)
    unit["path"] = []
    unit["target"] = None
    world.events.append({"kind": "deploy_started", "unit": unit_id, "faction": unit["faction_name"], "tile": [unit["tx"], unit["ty"]]})
    return {"status": "ok"}


def deploy_quantum(world: Any) -> None:
    for uid, u in list(world.units.items()):
        if not u.get("deploying_ms"):
            continue
        if not u.get("alive", True):
            u.pop("deploying_ms", None)
            continue
        u["deploying_ms"] = int(u["deploying_ms"]) - 100
        if u["deploying_ms"] > 0:
            continue
        u.pop("deploying_ms", None)
        u["status"] = "idle"
        why = deploy_check(world, u)
        if why:  # the ground changed while the vehicle unfolded (another centre, a building, a unit in the way)
            world.events.append({"kind": "deploy_failed", "unit": uid, "reason": why})
            continue
        _create_command_center(world, u)


def _create_command_center(world: Any, unit: dict) -> str:
    from wizard_rts import rules

    tile = (int(unit["tx"]), int(unit["ty"]))
    faction = unit["faction_name"]
    info = world.faction_info[faction]
    cc_def, label, _offs = DEPLOYERS.get(unit["definition"], DEPLOYERS[MCV_DEFINITION])
    bid = world._building(info["id"], faction, "warehouse", tile, label, cc_def)
    b = world.buildings[bid]
    r = rules.actor(cc_def) if cc_def.startswith("openra.") else None
    b["hp"] = b["max_hp"] = int(r["hp"]) if r else 120_000  # a settlers' warehouse: sturdier than a hut, weaker than a capital
    b["command_center"] = True
    b["outpost"] = True
    from wizard_rts import tech

    b["territory"] = OUTPOST_RADIUS + tech.territory_bonus(world, faction)
    fp = footprint(tile, unit["definition"])
    if len(fp) > 1:
        b["ground_footprint"] = [list(p) for p in fp]
    for p in fp:
        world.blocked.add(p)
    cargo = dict(unit.get("cargo") or {})
    from wizard_rts.economy import produce

    for good, n in cargo.items():  # the vehicle's own load goes into the new store (through the economy totals): carried, not created
        produce(world, bid, good, int(n))
    world.units.pop(unit["id"], None)  # consumed exactly once
    world.stats["deployed"] = world.stats.get("deployed", 0) + 1
    world.fstat(faction, "command_centers_deployed")
    world.events.append({"kind": "deployed", "unit": unit["id"], "building": bid, "faction": faction, "tile": list(tile), "cargo": cargo})
    return bid
