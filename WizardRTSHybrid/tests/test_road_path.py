"""Road planning: the flat-array A* (performance rewrite of 12 Oct 2026) returns exactly the paths of the original tuple/dict A*,
and no new road shares the tile a carrier cannot pass (the Ward Duel hazard)."""
import heapq
import random

from wizard_rts import construction as con
from wizard_rts.world import HybridWorld


def reference_path(world, start, goal, shared, limit):
    """The original implementation (before the rewrite), kept verbatim apart from taking `shared` as an argument."""
    blocked, roads, trees = world.blocked, world.road_tile_set, world.tree_tiles

    def open_tile(t):
        return t == goal or (((t not in blocked and t not in roads and t not in trees) or t in shared) and world.tile_in_map(*t))

    for end in (start, goal):
        if not any(open_tile((end[0] + dx, end[1] + dy)) or (end[0] + dx, end[1] + dy) == start for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            return None
    max_expand = 4 * (2 * limit + 1) * (2 * limit + 1) // 5
    heap = [(0, 0, start)]
    came, cost, n = {}, {start: 0}, 0
    while heap:
        _f, _c, cur = heapq.heappop(heap)
        if n > max_expand:
            return None
        if cur == goal:
            path = [cur]
            while cur != start:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            return path
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt != goal and (((nxt in blocked or nxt in roads or nxt in trees) and nxt not in shared) or not world.tile_in_map(*nxt)):
                continue
            if abs(nxt[0] - start[0]) > limit or abs(nxt[1] - start[1]) > limit:
                continue
            c = cost[cur] + 1
            if nxt not in cost or c < cost[nxt]:
                cost[nxt] = c
                came[nxt] = cur
                n += 1
                heapq.heappush(heap, (c + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1]), n, nxt))
    return None


def test_flat_array_astar_matches_the_reference():
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = True
    for s in range(240):  # a few minutes of AI building: roads, sites and trees to route round
        w.advance(1000, s + 1, snapshot=False)
    rng = random.Random(3)
    wh = con.faction_warehouse(w, "Blue")
    checked = found = 0
    for _ in range(80):
        a = (wh["tx"] + rng.randint(-30, 30), wh["ty"] + rng.randint(-30, 30))
        b = (wh["tx"] + rng.randint(-30, 30), wh["ty"] + rng.randint(-30, 30))
        if not w.tile_in_map(*a) or not w.tile_in_map(*b):
            continue
        for limit in (20, 45):
            new = con._road_path(w, a, b, ("", ""), limit)
            old = reference_path(w, a, b, set(), limit)
            assert new == old, (a, b, limit)
            checked += 1
            found += new is not None
    assert checked >= 60 and found >= 10


def test_no_new_road_runs_through_the_hazard():
    """A new road may join an endpoint's existing roads (the hybrid has no flags), but never through the tile a carrier cannot pass:
    a road sharing the Ward Duel hazard tile starved Red's construction sites (12 Oct 2026)."""
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = True
    for s in range(20 * 60):
        w.advance(1000, s + 1, snapshot=False)
    assert w.hazard_tile is not None
    crossing = [rid for rid, tiles in w.roads.items() if w.hazard_tile in tiles]
    assert len(crossing) <= 1  # only the original lumberjack road it was placed on
    red_sites = [b for b in w.buildings.values() if b["faction_name"] == "Red" and b.get("constructing")]
    assert len(red_sites) <= 3 and sum(1 for b in w.buildings.values() if b["faction_name"] == "Red") >= 18  # Red builds like the others
