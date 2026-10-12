"""Modern-era developer fixture for the first industrial-to-unit slice (roadmap M2).

It prepares ONE faction the way a Modern-era campaign would have reached: the cards for automation, industry and unit fabrication
(with their prerequisite cards) and a stock of construction goods. Everything else is the real game: machines and belts are placed
through the validated commands, paid for in delivered Widelands goods over roads, and the deposits they work are the ones the
generator put on the map (no ore squares are created). Granted goods are logged as `made_*` and `fixture_grant_*` so the ledger
still balances. Developer/test profiles only.

Layout (all placement is searched, nothing is hard-coded to a seed):
  coal drill -> belt -> silicon smelter        sand drill (desert/beach floor) -> belt -> smelter
  lead drill (iron-bearing site) -> belt -> ground factory        smelter -> belt -> ground factory
  two large solar panels and a power node link the smelter and the factory (a combustion generator burns the finite coal
  reserve in minutes, so the fixture does not use one; it is covered by its own tests)
"""

from __future__ import annotations

import heapq
from typing import Any

from wizard_rts import construction as con
from wizard_rts import tech, territory
from wizard_rts.economy import produce
from wizard_rts.industry import commands as C
from wizard_rts.industry import extraction as X
from wizard_rts.industry import registry as R
from wizard_rts.industry import sim as S

GRANT = {"plank": 160, "granite": 120, "iron": 80, "log": 40}
MIN_BELT = 8  # the slice shows a belt run of at least this many tiles


def _cands(world: Any, wh: dict, radius: int):
    for y in range(wh["ty"] - radius, wh["ty"] + radius + 1):
        for x in range(wh["tx"] - radius, wh["tx"] + radius + 1):
            yield (x, y)


def _drill_site(world: Any, faction: str, wh: dict, kind: str, item: str, taken: set[tuple[int, int]], min_tiles: int = 3, far: int = 7, avoid_ring: set[tuple[int, int]] | None = None):
    best = None
    for (x, y) in _cands(world, wh, territory.radius_of(wh)):
        fp = {(x + dx, y + dy) for dy in range(2) for dx in range(2)}
        if fp & taken or (avoid_ring and set(S.adjacent_tiles(sorted(fp))) & avoid_ring):
            continue  # a machine dumps into any belt that touches it: it must not stand beside someone else's belt
        why, ctx = C.check_machine(world, faction, kind, (x, y))
        if why:
            continue
        o = X.options(world, ctx["footprint"], int(R.block(kind)["tier"])).get(item)
        if not o or len(o["tiles"]) < min_tiles:
            continue
        d = abs(x - wh["tx"]) + abs(y - wh["ty"])
        if d < far:
            continue
        key = (d, -len(o["tiles"]), y, x)
        if best is None or key < best[0]:
            best = (key, (x, y))
    return best[1] if best else None


def _site_near(world: Any, faction: str, kind: str, around: tuple[int, int], taken: set[tuple[int, int]], min_dist: int = 0, anchor: tuple[int, int] | None = None, max_dist: int = 99):
    spec = R.block(kind)
    n = spec["size"]
    best = None
    for dy in range(-16, 17):
        for dx in range(-16, 17):
            t = (around[0] + dx, around[1] + dy)
            fp = {(t[0] + a, t[1] + b) for b in range(n) for a in range(n)}
            if fp & taken:
                continue
            why, _ctx = C.check_machine(world, faction, kind, t)
            if why:
                continue
            d_anchor = abs(t[0] - anchor[0]) + abs(t[1] - anchor[1]) if anchor else 99
            if anchor and (d_anchor < min_dist or d_anchor > max_dist):
                continue
            key = (abs(dx) + abs(dy), t[1], t[0])
            if best is None or key < best[0]:
                best = (key, t)
    return best[1] if best else None


def _ring(world: Any, tiles: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return S.adjacent_tiles(tiles)


def _route(world: Any, faction: str, src: list[tuple[int, int]], dst: list[tuple[int, int]], machine_rings: set[tuple[int, int]], planned: set[tuple[int, int]]):
    """A* over free ground from a ring tile of `src` to a ring tile of `dst`, not touching any other machine's ring. Returns (tiles, end_dir)."""
    st = S.ind(world)
    own_src, own_dst = set(_ring(world, src)), set(_ring(world, dst))
    dst_set = set(dst)

    def free(t: tuple[int, int]) -> bool:
        return C._tile_free(world, t, allow_road=True, allow_trees=True) is None and t not in planned and territory.in_territory(world, faction, t)

    goal_c = (sum(t[0] for t in dst) / len(dst), sum(t[1] for t in dst) / len(dst))
    starts = sorted(t for t in own_src if free(t) and t not in (machine_rings - own_src))
    heap: list[tuple[float, int, tuple[int, int]]] = []
    cost: dict[tuple[int, int], int] = {}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    n = 0
    for t in starts:
        cost[t] = 1
        heapq.heappush(heap, (abs(t[0] - goal_c[0]) + abs(t[1] - goal_c[1]), n, t))
        n += 1
    while heap:
        _f, _n, cur = heapq.heappop(heap)
        if cur in own_dst:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            last = path[-1]
            for d, (dx, dy) in enumerate(S.DIRS):
                if (last[0] + dx, last[1] + dy) in dst_set:
                    return path, d
        for dx, dy in S.DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in cost and cost[nxt] <= cost[cur] + 1:
                continue
            if not free(nxt) or (nxt in machine_rings and nxt not in own_dst and nxt not in own_src):
                continue
            cost[nxt] = cost[cur] + 1
            came[nxt] = cur
            n += 1
            heapq.heappush(heap, (cost[nxt] + abs(nxt[0] - goal_c[0]) + abs(nxt[1] - goal_c[1]), n, nxt))
    return None, 0


def grant_cards(world: Any, faction: str) -> None:
    for cid in ("dmb.card.automation", "dmb.card.industry", "dmb.card.unit_fabrication"):
        r = tech.grant(world, faction, cid)
        assert r["status"] == "ok", r


def grant_goods(world: Any, faction: str, goods: dict[str, int] | None = None) -> None:
    wh = con.faction_warehouse(world, faction)
    for g, n in (goods or GRANT).items():
        produce(world, wh["id"], g, n)
        world.stats["made_" + g] = world.stats.get("made_" + g, 0) + n
        world.stats["fixture_grant_" + g] = world.stats.get("fixture_grant_" + g, 0) + n


def modern_fixture(world: Any, faction: str = "Red") -> dict[str, Any]:
    """Place the slice; returns ids and a plan. Raises RuntimeError naming what could not be placed."""
    from wizard_rts import ai

    if not tech.god_allowed(world):
        raise PermissionError("the Modern fixture is a developer/test command")
    from wizard_rts import vp

    if world.era_index < 2:
        vp.set_era(world, 2)
    grant_cards(world, faction)
    grant_goods(world, faction)
    wh = con.faction_warehouse(world, faction)
    ids: dict[str, Any] = {"faction": faction, "belts": []}
    taken: set[tuple[int, int]] = set()
    names: list[str] = []

    def fp_of(key: str) -> list[tuple[int, int]]:
        return [(int(p[0]), int(p[1])) for p in world.buildings[ids[key]]["ground_footprint"]]

    def rings() -> set[tuple[int, int]]:
        out: set[tuple[int, int]] = set()
        for k in names:
            out.update(_ring(world, fp_of(k)))
        return out

    def place(kind: str, tile: tuple[int, int], key: str) -> str | None:
        """Place a machine and give it a road; a site that cannot get a road is withdrawn (the caller tries the next)."""
        res = con.place_building(world, faction, kind, tile[0], tile[1])
        if res["status"] != "ok":
            return None
        bid = res["id"]
        near = sorted((world.buildings[ids[k]] for k in names), key=lambda o: abs(o["tx"] - tile[0]) + abs(o["ty"] - tile[1]))[:2]
        if not any(con.build_road(world, faction, bid, o["id"], limit=90)["status"] == "ok" for o in near + [wh]):
            ai._cancel_site(world, bid)  # no road could be laid: the site is withdrawn and the caller tries another
            return None
        ids[key] = bid
        names.append(key)
        for p in world.buildings[bid]["ground_footprint"]:
            taken.add((int(p[0]), int(p[1])))
        return bid

    planned: set[tuple[int, int]] = set()

    def feed(src_key: str, dst_key: str) -> None:
        path, end_dir = _route(world, faction, fp_of(src_key), fp_of(dst_key), rings(), planned)
        if path is None:
            raise RuntimeError(f"no belt route {src_key} -> {dst_key}")
        res = C.place_belt(world, faction, path, end_dir)
        if res["status"] != "ok":
            raise RuntimeError(f"belt {src_key}->{dst_key}: {res}")
        planned.update(path)
        ids["belts"].append({"id": res["id"], "from": src_key, "to": dst_key, "tiles": len(path)})
        # the site needs a road to receive its planks: to its source machine, its target, then anywhere (the road may follow the cleared belt tiles)
        if not any(con.build_road(world, faction, res["id"], ids[k], limit=90)["status"] == "ok" for k in (src_key, dst_key)) \
                and con.build_road(world, faction, res["id"], wh["id"], limit=90)["status"] != "ok":
            raise RuntimeError(f"belt {src_key}->{dst_key} cannot get a road for its construction goods")

    # 1. the power-and-factory cluster near the warehouse
    around = (wh["tx"], wh["ty"])
    for _try in range(12):
        smelter = _site_near(world, faction, "mdy:silicon_smelter", around, taken, 0)
        if smelter is None or place("mdy:silicon_smelter", smelter, "smelter"):
            break
        taken.update({(smelter[0] + a, smelter[1] + b) for a in range(2) for b in range(2)})
    if "smelter" not in ids:
        raise RuntimeError("no room for the smelter")
    for _try in range(12):
        factory = _site_near(world, faction, "mdy:ground_factory", around, taken, min_dist=MIN_BELT + 1, anchor=(smelter[0], smelter[1]), max_dist=13)
        if factory is None:
            raise RuntimeError("no room for the ground factory")
        hypo = [(factory[0] + a, factory[1] + b) for b in range(3) for a in range(3)]
        path, _d = _route(world, faction, fp_of("smelter"), hypo, rings(), planned)
        if path is not None and len(path) <= 32 and place("mdy:ground_factory", factory, "factory"):
            break
        taken.update(hypo)
    mid = ((smelter[0] + factory[0]) // 2, (smelter[1] + factory[1]) // 2)
    for key, kind in (("node", "mdy:power_node"), ("solar_a", "mdy:solar_panel_large"), ("solar_b", "mdy:solar_panel_large")):
        for _try in range(12):
            ref = ids.get("solar_a") if key == "solar_b" else ids.get("node")  # the second panel touches the first: adjacent power blocks share a graph
            home = (world.buildings[ref]["tx"], world.buildings[ref]["ty"]) if ref else mid
            kw = ({"min_dist": 3, "anchor": home, "max_dist": 5} if key == "solar_b" else {"min_dist": 2, "anchor": home, "max_dist": 8}) if ref else {}
            t = _site_near(world, faction, kind, home, taken, **kw)
            if t is None:
                raise RuntimeError(f"no room for {key}")
            if place(kind, t, key):
                break
            taken.update({(t[0] + a, t[1] + b) for a in range(R.block(kind)["size"]) for b in range(R.block(kind)["size"])})
    feed("smelter", "factory")  # first: it is the one belt whose ends are both fixed, so it takes the shortest corridor
    # 2. each drill on an existing resource site that has both a road and a belt route to its target
    for key, item, target, min_tiles, far in (("coal_drill", "coal", "smelter", 3, 6),
                                              ("sand_drill", "sand", "smelter", 4, 5), ("lead_drill", "lead", "factory", 2, 6)):
        done = False
        for _try in range(25):
            site = _drill_site(world, faction, wh, "mdy:mechanical_drill", item, taken, min_tiles=min_tiles, far=far, avoid_ring=planned)
            if site is None:
                break
            hypo = [(site[0] + a, site[1] + b) for b in range(2) for a in range(2)]
            path, _d = _route(world, faction, hypo, fp_of(target), rings(), planned)
            if path is None or len(path) > 80:
                taken.update(hypo)
                continue
            if place("mdy:mechanical_drill", site, key) is None:
                taken.update(hypo)
                continue
            if item == "lead":
                world.buildings[ids[key]]["mdy_target"] = "lead"  # read when the drill comes online
            feed(key, target)
            done = True
            break
        if not done:
            raise RuntimeError(f"no workable site for {key} ({item})")
    ids["plan"] = [("coal_drill", "smelter"), ("sand_drill", "smelter"),
                   ("lead_drill", "factory"), ("smelter", "factory")]
    return ids


# ---------------------------------------------------------------- instant placement (unit-test and developer scaffolding)

def instant_machine(world: Any, faction: str, kind: str, tile: tuple[int, int]) -> str:
    """Place an already-built machine without paying or waiting (tests that isolate one mechanic). Developer/test profiles only;
    it moves no wares, so no ledger entry is needed. Placement rules still apply."""
    if not tech.god_allowed(world):
        raise PermissionError("instant placement is a developer/test command")
    why, ctx = C.check_machine(world, faction, kind, tile)
    if why:
        raise RuntimeError(f"{kind} at {tile}: {why}")
    spec = R.block(kind)
    bid = world._building(world.faction_info[faction]["id"], faction, kind, tile, spec["label"], spec["definition"])
    b = world.buildings[bid]
    b["ground_footprint"] = [list(t) for t in ctx["footprint"]]
    world.blocked.update(ctx["footprint"])
    S._init_machine(world, b)
    S.ind(world).dirty = True
    return bid


def instant_belt(world: Any, faction: str, tiles: list[tuple[int, int]], end_dir: int | None = None) -> str:
    res = C.place_belt(world, faction, tiles, end_dir)
    if res["status"] != "ok":
        raise RuntimeError(f"belt: {res}")
    b = world.buildings[res["id"]]
    b.pop("constructing")
    b["operational"] = True
    b["hp"] = b["max_hp"]
    world.recipe_requests.pop(b["id"], None)
    return b["id"]


def open_ground(world: Any, faction: str, w: int, h: int, near: tuple[int, int] | None = None, kind: str = "mdy:power_node") -> tuple[int, int]:
    """Top-left of a free w x h block of ground inside the faction's territory (nearest to `near`, default its warehouse).
    Trees on the block are cleared (test and fixture scaffolding)."""
    wh = con.faction_warehouse(world, faction)
    cx, cy = near or (wh["tx"], wh["ty"])
    best = None
    for dy in range(-22, 23):
        for dx in range(-22, 23):
            x, y = cx + dx, cy + dy
            if all(C._tile_free(world, (x + a, y + b), allow_trees=True) is None and territory.in_territory(world, faction, (x + a, y + b))
                   and world.terrain.can_build(x + a, y + b, "small") for a in range(w) for b in range(h)):
                key = (abs(dx) + abs(dy), y, x)
                if best is None or key < best[0]:
                    best = (key, (x, y))
    if best is None:
        raise RuntimeError(f"no free {w}x{h} ground near {cx, cy}")
    from wizard_rts.workers import remove_tree

    x, y = best[1]
    for a in range(w):
        for b in range(h):  # test scaffolding clears the block it asks for
            tid = world.tree_tiles.get((x + a, y + b))
            if tid is not None:
                remove_tree(world, tid, "fixture_clearing")
    return best[1]


def inject(world: Any, building_id: str, ware: str, n: int, bag: str = "buf") -> None:
    """Put wares straight into a machine buffer (tests that isolate one mechanic). Logged as a fixture source so the ledger balances."""
    m = world.buildings[building_id]["mdy"]
    m[bag][ware] = m[bag].get(ware, 0) + n
    world.stats["made_" + ware] = world.stats.get("made_" + ware, 0) + n
    world.stats["fixture_grant_" + ware] = world.stats.get("fixture_grant_" + ware, 0) + n


def drain_output(world: Any, building_id: str) -> int:
    """Empty a machine's output buffer into a logged sink (tests that measure rates without building a belt)."""
    m = world.buildings[building_id]["mdy"]
    n = 0
    for ware in list(m["out"]):
        n += m["out"][ware]
        world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + m["out"][ware]
        m["out"][ware] = 0
    return n
