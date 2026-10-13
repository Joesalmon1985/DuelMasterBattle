"""Validated commands for the industry layer. The player never calls these (no faction control, D02); the AI, God Mode in the
developer profile, the training API and the developer fixtures do, through the same checks.

Machines are ordinary construction sites (`construction.place_building`): they request their hybrid cost in delivered Widelands
goods over the road network and become operational only when built. A belt run is one site paid per tile in planks.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import territory
from wizard_rts.industry import extraction as X
from wizard_rts.industry import registry as R
from wizard_rts.industry import sim as S

MAX_BELT = 120
UPGRADE_FRACTION = 0.25  # S08: the new recipe minus the old one, plus a quarter of the old one, paid in delivered wares


def _tile_free(world: Any, tile: tuple[int, int], extra_ok: set[tuple[int, int]] | None = None, allow_road: bool = False, allow_trees: bool = False,
               allow_water: bool = False) -> str | None:
    """A belt may cross a road (units and carriers walk over both); a machine may not stand on one. A pump may stand in the water."""
    if extra_ok and tile in extra_ok:
        return None
    if not world.tile_in_bounds(*tile):
        return "outside_map"
    if world.terrain is not None and not world.terrain.ground(*tile) and not (allow_water and world.terrain.is_water(*tile)):
        return "unsuitable_terrain"
    st = S.ind(world)
    if (tile in world.blocked or (tile in world.tree_tiles and not allow_trees) or (tile in world.road_tile_set and not allow_road) or tile in world.reserved_tiles
            or tile in st.belts or tile in st.tile_owner):
        return "tile_occupied"
    if any((u["tx"], u["ty"]) == tile for u in world.units.values() if u.get("alive", True)):
        return "tile_occupied"
    return None


def check_machine(world: Any, faction: str, kind: str, tile: tuple[int, int], own: set[tuple[int, int]] | None = None) -> tuple[str | None, dict[str, Any]]:
    """Placement rules of a machine: inside the faction's territory, every footprint tile free ground, and (drills) existing
    resource sites underneath that the drill's tier can work. Returns (reason or None, ctx)."""
    spec = R.block(kind)
    if spec is None or world.terrain is None:
        return "unknown_kind", {}
    n = spec["size"]
    tiles = [(tile[0] + dx, tile[1] + dy) for dy in range(n) for dx in range(n)]
    ctx: dict[str, Any] = {"footprint": tiles}
    wet = spec["role"] == "pump" and spec["class"] == "Pump"
    for t in tiles:
        if not territory.in_territory(world, faction, t):
            return "outside_territory", ctx
        why = _tile_free(world, t, own, allow_water=wet)
        if why:
            return why, ctx
    if wet:
        if not any(world.terrain.is_water(*t) for t in tiles):
            return "needs_water", ctx
        return None, ctx
    if spec["role"] not in ("drill",) and not world.terrain.can_build(tile[0], tile[1], "small"):  # the anchor needs a Widelands building site; the rest only ground
        return "unsuitable_terrain", ctx
    if spec["role"] == "drill":
        if not X.options(world, tiles, int(spec["tier"])):
            return "no_deposit_here", ctx
    return None, ctx


def check_belt(world: Any, faction: str, tiles: list[tuple[int, int]]) -> str | None:
    if not (2 <= len(tiles) <= MAX_BELT) and len(tiles) != 1:
        return "bad_length"
    seen = set()
    for i, t in enumerate(tiles):
        if t in seen:
            return "self_overlap"
        seen.add(t)
        if i and abs(t[0] - tiles[i - 1][0]) + abs(t[1] - tiles[i - 1][1]) != 1:
            return "not_contiguous"
        if not territory.in_territory(world, faction, t):
            return "outside_territory"
        why = _tile_free(world, t, allow_road=True, allow_trees=True)  # a belt run clears the trees on its tiles
        if why:
            return why
    return None


def place_belt(world: Any, faction: str, tiles: list[Any], end_dir: int | None = None, kind: str = "mdy:conveyor") -> dict[str, Any]:
    """One run of belt, stack belt, duct, conduit or payload conveyor as a construction site: `tiles` in flow order, hybrid cost per tile."""
    from wizard_rts import tech

    spec_ = R.block(kind)
    if spec_ is None or spec_["role"] not in S.LINE_ROLES:
        return {"status": "rejected", "reason": "not_a_line_block"}
    if not tech.kind_allowed(world, faction, kind):
        return {"status": "rejected", "reason": "locked_by_card"}
    info = world.faction_info.get(faction)
    if info is None:
        return {"status": "rejected", "reason": "unknown_faction"}
    pts = [(int(t[0]), int(t[1])) for t in tiles]
    why = check_belt(world, faction, pts)
    if why:
        return {"status": "rejected", "reason": why}
    dirs = []
    for i, t in enumerate(pts):
        if i + 1 < len(pts):
            d = (pts[i + 1][0] - t[0], pts[i + 1][1] - t[1])
        elif end_dir is not None:
            d = S.DIRS[int(end_dir) % 4]
        elif i:
            d = (t[0] - pts[i - 1][0], t[1] - pts[i - 1][1])
        else:
            d = (1, 0)
        dirs.append(S.DIRS.index(d))
    spec = R.build_spec(kind)
    cost = belt_cost(len(pts)) if kind == "mdy:conveyor" else {g: n * len(pts) for g, n in spec["cost"].items()}
    bid = world._building(info["id"], faction, kind, pts[0], f"{spec['label']} x{len(pts)}", spec["definition"], block=False)
    b = world.buildings[bid]
    b["line"] = {"tiles": [list(t) for t in pts], "dirs": dirs}
    b["operational"] = False
    b["constructing"] = {"cost": cost, "progress_ms": 0}
    b["hp"] = max(1, b["max_hp"] // 10)
    from wizard_rts.workers import remove_tree

    for t in pts:  # clearing: the trees standing on the run are removed (logged), as a builder would
        tid = world.tree_tiles.get(t)
        if tid is not None:
            remove_tree(world, tid, "belt_clearing")
            world.stats["trees_cleared"] = world.stats.get("trees_cleared", 0) + 1
    world.reserved_tiles.update(pts)
    world.recipe_requests[bid] = dict(cost)
    world.events.append({"kind": "construction_started", "id": bid, "building_kind": kind, "faction": faction})
    return {"status": "ok", "id": bid, "tiles": len(pts), "cost": cost}


def belt_cost(n_tiles: int) -> dict[str, int]:
    per = R.block("mdy:conveyor")["cost_per_tiles"]
    return {g: math.ceil(n_tiles / per["tiles"]) * c for g, c in per["cost"].items()}


def activate_line_tiles(world: Any, b: dict) -> None:
    for t in b["line"]["tiles"]:
        world.reserved_tiles.discard((int(t[0]), int(t[1])))


def upgrade_cost(old: dict[str, int], new: dict[str, int]) -> dict[str, int]:
    """S08: max(0, new - old) plus ceil(25% of old) per ware. Pure function of the two recipes."""
    out: dict[str, int] = {}
    for g in sorted(set(old) | set(new)):
        n = max(0, new.get(g, 0) - old.get(g, 0)) + math.ceil(UPGRADE_FRACTION * old.get(g, 0))
        if n:
            out[g] = n
    return out


def upgrade_mine(world: Any, faction: str, building_id: str, to_kind: str) -> dict[str, Any]:
    """Turn an existing Widelands mine (or a mechanical drill) into advanced equipment on the SAME site, keeping the building id,
    faction, history and tile; the new equipment is paid for in delivered wares through the normal construction site."""
    from wizard_rts import construction as con
    from wizard_rts import tech

    b = world.buildings.get(str(building_id))
    spec = R.block(to_kind)
    if b is None or spec is None or spec["role"] != "drill":
        return {"status": "rejected", "reason": "cannot_upgrade"}
    if b["faction_name"] != faction:
        return {"status": "rejected", "reason": "not_yours"}
    if not tech.kind_allowed(world, faction, to_kind):
        return {"status": "rejected", "reason": "locked_by_card"}
    if b["kind"] not in spec["upgrade_from"]:
        return {"status": "rejected", "reason": "not_upgradeable"}
    if b.get("constructing") or not b.get("operational", True) or int(b.get("hp", 1)) <= 0:
        return {"status": "rejected", "reason": "not_operational"}
    old_spec = con.build_spec(b["kind"]) or R.build_spec(b["kind"])
    own = {(b["tx"], b["ty"])} | {(int(p[0]), int(p[1])) for p in b.get("ground_footprint", [])}
    why, ctx = check_machine(world, faction, to_kind, (b["tx"], b["ty"]), own=own)
    if why:
        return {"status": "rejected", "reason": why}
    cost = upgrade_cost(dict(old_spec["cost"]) if old_spec else {}, spec["cost"])
    # the mine's worker retires: an automated drill needs none. What it carried goes into the building's own stock.
    for wid in [w for w, w_ in world.workers.items() if w_.get("building") == b["id"]]:
        w = world.workers.pop(wid)
        if w.get("carrying"):
            world.stocks.setdefault(b["id"], {})[w["carrying"]] = world.stocks.setdefault(b["id"], {}).get(w["carrying"], 0) + 1
    b.pop("worker_ids", None)
    b.pop("deposit_exhausted", None)
    b.setdefault("history", []).append({"event": "upgraded", "from": b["kind"], "to": to_kind, "game_ms": int(world.dmb.clock.get("game_ms", 0))})
    from_kind = b["kind"]
    b["kind"] = to_kind
    b["definition"] = spec["definition"]
    b["label"] = f"{faction} {spec['label']}"
    b["operational"] = False
    b["working"] = False
    b["mdy"] = None
    b["constructing"] = {"cost": cost, "progress_ms": 0, "upgrade_from": from_kind}
    b["hp"] = max(1, b["max_hp"] // 10)
    b["ground_footprint"] = [list(t) for t in ctx["footprint"]]
    for t in ctx["footprint"]:
        world.blocked.add(t)
    world.recipe_requests[b["id"]] = dict(cost)
    world.events.append({"kind": "construction_started", "id": b["id"], "building_kind": to_kind, "faction": faction, "upgrade_from": from_kind})
    return {"status": "ok", "id": b["id"], "cost": cost}


def configure(world: Any, faction: str, building_id: str, key: str, value: Any) -> dict[str, Any]:
    """Set a drill's target item or a factory's unit plan."""
    from wizard_rts import tech

    b = world.buildings.get(str(building_id))
    if b is None or b["faction_name"] != faction or b.get("mdy") is None:
        return {"status": "rejected", "reason": "no_machine"}
    m, spec = b["mdy"], R.block(b["kind"])
    if key == "target" and m["role"] == "drill":
        opts = S.drill_options(world, b)
        if value not in opts:
            return {"status": "rejected", "reason": "cannot_extract_here", "options": sorted(opts)}
        m["target"] = str(value)
        m["progress"] = 0
        return {"status": "ok"}
    if key == "plan" and m["role"] == "unit_factory":
        if value not in [p["unit"] for p in spec["plans"]]:
            return {"status": "rejected", "reason": "no_such_plan"}
        if not tech.unit_allowed(world, faction, str(value)):
            return {"status": "rejected", "reason": "locked_by_card"}
        m["plan"] = str(value)
        m["progress"] = 0
        return {"status": "ok"}
    return {"status": "rejected", "reason": "bad_config"}


def link_power(world: Any, faction: str, node_id: str, target_id: str) -> dict[str, Any]:
    st = S.ind(world)
    a, t = world.buildings.get(str(node_id)), world.buildings.get(str(target_id))
    if a is None or t is None or a.get("mdy") is None or t.get("mdy") is None or a["faction_name"] != faction or t["faction_name"] != faction:
        return {"status": "rejected", "reason": "no_such_block"}
    spec = R.block(a["kind"])
    if spec["role"] != "node":
        return {"status": "rejected", "reason": "not_a_node"}
    if not S._powered_role(t):
        return {"status": "rejected", "reason": "not_a_power_block"}
    if _edge_distance(a, t) > spec["laser_range"]:
        return {"status": "rejected", "reason": "out_of_range"}
    links = st.links.setdefault(a["id"], [])
    if t["id"] in links:
        return {"status": "rejected", "reason": "already_linked"}
    if len(links) >= spec["max_nodes"]:
        return {"status": "rejected", "reason": "node_full"}
    links.append(t["id"])
    st.dirty = True
    return {"status": "ok"}


def _edge_distance(a: dict, b: dict) -> float:
    """Gap in tiles between two footprints (Mindustry PowerNode.overlaps measures from the block edge)."""
    best = 1e9
    for p in S.footprint(a):
        for q in S.footprint(b):
            best = min(best, math.hypot(p[0] - q[0], p[1] - q[1]) - 1 if p != q else 0)
    return max(0.0, best)


def auto_link(world: Any, node: dict) -> None:
    """A node that has just come online links to the nearest block of each power graph in range (PowerNode.getNodeLinks)."""
    st = S.ind(world)
    spec = R.block(node["kind"])
    links = st.links.setdefault(node["id"], [])
    seen_graphs = {st.graph_of.get(node["id"], -2)}
    cands = []
    for b in world.buildings.values():
        if b["id"] == node["id"] or b["faction_name"] != node["faction_name"] or b.get("mdy") is None or not S._powered_role(b):
            continue
        d = _edge_distance(node, b)
        if d <= spec["laser_range"]:
            cands.append((d, b["id"]))
    for _d, bid in sorted(cands):
        g = st.graph_of.get(bid, -3 - len(links))
        if g in seen_graphs or len(links) >= spec["max_nodes"]:
            continue
        seen_graphs.add(g)
        links.append(bid)
    st.dirty = True


def attach_to_nodes(world: Any, b: dict) -> None:
    """A power block that has just come online is laser-linked by the nearest node in range of each other power graph
    (Mindustry links new blocks to nodes at placement time)."""
    st = S.ind(world)
    seen = {st.graph_of.get(b["id"], -2)}
    cands = []
    for n in world.buildings.values():
        if n.get("mdy") is None or n["faction_name"] != b["faction_name"] or R.block(n["kind"])["role"] != "node":
            continue
        d = _edge_distance(n, b)
        if d <= R.block(n["kind"])["laser_range"] and len(st.links.get(n["id"], [])) < R.block(n["kind"])["max_nodes"]:
            cands.append((d, n["id"]))
    for _d, nid in sorted(cands):
        g = st.graph_of.get(nid, -3)
        if g in seen:
            continue
        seen.add(g)
        st.links.setdefault(nid, []).append(b["id"])
    st.dirty = True
