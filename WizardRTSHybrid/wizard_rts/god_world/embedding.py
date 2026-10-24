"""The terrain embedding: the logical 30/80/109 Catan graph laid onto a real Widelands map (docs/PLAN_GOD_WORLD_LIVING.md, stage A).

The graph stays the rule (production, legality, ownership, connectivity: `board.py`). This module decides WHERE each node's village plot, each
edge's road corridor and each hex's catchment and work site sit on the map's square tile grid, and validates them: every plot on buildable
land clear of water, every corridor a passable winding path between the same two endpoints, no two corridors crossing (a crossing would be a
junction the graph does not have), every plot far enough from every other. The result is deterministic for a map and a board shape, so it
is generated once (`scripts/god_world_embed.py`) and checked in as `data/god_world/embedding_<map>.json`; `GodWorld` loads it and attaches it
to its board. Widelands maps wrap at their borders; this world is bounded, so the search never wraps and no route crosses a seam."""

from __future__ import annotations

import heapq
import json
import math
from pathlib import Path
from typing import Any

from wizard_rts import terrain as T

from . import rules

VERSION = 1
DATA = Path(__file__).resolve().parents[1] / "data" / "god_world"
BASE_MAP = "Egyptian_Mandala_v1.2"
DEFAULT_MAP = "Egyptian_Mandala_v1.2@2x"  # the island resampled to 384 x 384 with the nodes twice as far apart (D53); older saves keep their own map
PLOT_RADIUS = 6  # tiles around a node that a village needs clear and buildable, on the base map (scaled with the map: `_pr`)
SEARCH_RADIUS = 11  # how far a node may move from its ideal regular position, on the base map (scaled with the map: `_sr`)


def _k(grid) -> int:
    """The map's resampling factor against the base island (1 for the 192-tile map, 2 for the 384-tile one)."""
    return max(1, int(round(grid.w / 192.0)))


def _pr(grid) -> int:
    return PLOT_RADIUS * _k(grid)


def _sr(grid) -> int:
    return SEARCH_RADIUS * _k(grid)
MIN_NODE_GAP = 0.55  # of the unit edge length
TREE_SPECIES = ("beech", "alder", "aspen", "birch")

PASSABLE = (T.ARABLE, T.WALKABLE, T.MINEABLE)
STEP_COST = {T.ARABLE: 1.0, T.WALKABLE: 1.15, T.MINEABLE: 2.4}


def embedding_path(map_name: str = DEFAULT_MAP) -> Path:
    return DATA / f"embedding_{map_name}.json"


def load(map_name: str = DEFAULT_MAP) -> dict[str, Any] | None:
    p = embedding_path(map_name)
    if not p.exists():
        return None
    emb = json.loads(p.read_text(encoding="utf-8"))
    if int(emb.get("version", 0)) != VERSION:
        return None
    return emb


class _Rng:
    """A tiny deterministic generator for scenery (never the simulation RNG)."""

    def __init__(self, seed: int) -> None:
        self.s = (seed * 2654435761 + 12345) & 0xFFFFFFFF

    def next(self) -> float:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s / float(0x7FFFFFFF)


def _land_bbox(grid: T.TerrainGrid) -> tuple[int, int, int, int]:
    xs, ys = [], []
    for y in range(grid.h):
        for x in range(grid.w):
            if grid.cls[y * grid.w + x] in PASSABLE:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _buildable_fraction(grid: T.TerrainGrid, cx: int, cy: int, r: int) -> float:
    n = ok = 0
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                continue
            n += 1
            if grid.in_bounds(x, y) and grid.cls[y * grid.w + x] in (T.ARABLE, T.WALKABLE):
                ok += 1
    return ok / max(1, n)


def _segments_cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and o1 != 0 and o2 != 0 and o3 != 0 and o4 != 0


def _astar(grid: T.TerrainGrid, start: tuple[int, int], goal: tuple[int, int], avoid: dict[tuple[int, int], float], box: tuple[int, int, int, int]) -> list[tuple[int, int]] | None:
    x0, y0, x1, y1 = box
    w = grid.w
    sx, sy = start
    gx, gy = goal
    best: dict[tuple[int, int], float] = {start: 0.0}
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    heap = [(0.0, 0.0, start)]
    while heap:
        _f, g, cur = heapq.heappop(heap)
        if cur == goal:
            break
        if g > best.get(cur, 1e18):
            continue
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + dx, cy + dy
            if nx < x0 or ny < y0 or nx > x1 or ny > y1 or not grid.in_bounds(nx, ny):
                continue
            cls = grid.cls[ny * w + nx]
            if cls not in PASSABLE and (nx, ny) != goal:
                continue
            step = STEP_COST.get(cls, 1.0) * (1.414 if dx and dy else 1.0)
            if dx and dy:  # no corner cutting through impassable tiles
                if grid.cls[cy * w + nx] not in PASSABLE or grid.cls[ny * w + cx] not in PASSABLE:
                    continue
            ng = g + step + avoid.get((nx, ny), 0.0)
            if ng < best.get((nx, ny), 1e18):
                best[(nx, ny)] = ng
                prev[(nx, ny)] = cur
                h = math.hypot(gx - nx, gy - ny)
                heapq.heappush(heap, (ng + h, ng, (nx, ny)))
    if goal not in best:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def _simplify(path: list[tuple[int, int]], tol: float = 0.9) -> list[tuple[float, float]]:
    """Douglas-Peucker on tile centres: a winding path with few points."""
    pts = [(x + 0.5, y + 0.5) for x, y in path]
    if len(pts) <= 2:
        return pts

    def dp(a: int, b: int, out: list[int]) -> None:
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1.0
        best_i, best_d = -1, 0.0
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L
            if d > best_d:
                best_i, best_d = i, d
        if best_d > tol and best_i > 0:
            dp(a, best_i, out)
            out.append(best_i)
            dp(best_i, b, out)

    keep = [0]
    dp(0, len(pts) - 1, keep)
    keep.append(len(pts) - 1)
    return [pts[i] for i in sorted(set(keep))]


def _corridor_crosses(poly_a, poly_b, board, ea: str, eb: str) -> bool:
    if set(board.edge_endpoints[ea]) & set(board.edge_endpoints[eb]):
        return False
    for i in range(len(poly_a) - 1):
        for j in range(len(poly_b) - 1):
            if _segments_cross(tuple(poly_a[i]), tuple(poly_a[i + 1]), tuple(poly_b[j]), tuple(poly_b[j + 1])):
                return True
    return False


def _poly_length(poly: list[tuple[float, float]]) -> float:
    return sum(math.hypot(poly[i + 1][0] - poly[i][0], poly[i + 1][1] - poly[i][1]) for i in range(len(poly) - 1))


def _place_nodes(board, grid: T.TerrainGrid, ideal: dict[str, tuple[float, float]], unit: float) -> dict[str, tuple[float, float]] | None:
    """Each node to the best buildable plot near its ideal spot, poorest spots first; None when one has no plot."""
    gap = MIN_NODE_GAP * unit
    placed: dict[str, tuple[float, float]] = {}
    order = sorted(board.nodes, key=lambda n: (_buildable_fraction(grid, int(ideal[n][0]), int(ideal[n][1]), _pr(grid)), n))
    for n in order:
        ix, iy = ideal[n]
        best = None
        for r in range(0, _sr(grid) + 1):
            cands = []
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = int(round(ix)) + dx, int(round(iy)) + dy
                    if not grid.in_bounds(x, y) or grid.cls[y * grid.w + x] not in (T.ARABLE, T.WALKABLE):
                        continue
                    if any(math.hypot(x + 0.5 - px, y + 0.5 - py) < gap for px, py in placed.values()):
                        continue
                    frac = _buildable_fraction(grid, x, y, _pr(grid))
                    if frac < 0.6:
                        continue
                    score = frac * 2.0 - math.hypot(dx, dy) / _sr(grid)
                    cands.append((score, -abs(dx) - abs(dy), x, y))
            if cands:
                cands.sort(reverse=True)
                best = (cands[0][2] + 0.5, cands[0][3] + 0.5)
                break
        if best is None:
            return None
        placed[n] = best
    return placed


def build(board, grid: T.TerrainGrid, map_name: str, strict: bool = True) -> dict[str, Any]:
    """Lay the board's graph onto the grid. Raises if a plot or a corridor cannot be found; a map that fails here is not a host."""
    x0, y0, x1, y1 = _land_bbox(grid)
    bx0, by0, bx1, by1 = board.bounds
    margin = _pr(grid) + 4
    base_scale = min((x1 - x0 - 2 * margin) / max(bx1 - bx0, 1e-6), (y1 - y0 - 2 * margin) / max(by1 - by0, 1e-6))
    best_trial = None
    # the board's scale and offset are searched: the placement that moves nodes least and keeps the fewest chords over water hosts the game
    for sf in (1.0, 0.95, 0.9, 0.86):
        scale = base_scale * sf
        cx = x0 + (x1 - x0 - (bx1 - bx0) * scale) / 2.0
        cy = y0 + (y1 - y0 - (by1 - by0) * scale) / 2.0
        for shx in (v * _k(grid) for v in (-9, -6, -3, 0, 3, 6, 9)):
            for shy in (v * _k(grid) for v in (-9, -6, -3, 0, 3, 6, 9)):
                ox, oy = cx + shx, cy + shy
                ideal = {n: ((board.node_xy(n)[0] - bx0) * scale + ox, (board.node_xy(n)[1] - by0) * scale + oy) for n in board.nodes}
                placed = _place_nodes(board, grid, ideal, scale)
                if placed is None:
                    continue
                disp = sum(math.hypot(placed[n][0] - ideal[n][0], placed[n][1] - ideal[n][1]) for n in board.nodes)
                water = 0
                for a, b in board.edge_endpoints.values():
                    (ax, ay), (bx_, by_) = placed[a], placed[b]
                    steps = int(math.hypot(bx_ - ax, by_ - ay)) + 1
                    for k in range(steps + 1):
                        t = k / steps
                        tx, ty = int(ax + (bx_ - ax) * t), int(ay + (by_ - ay) * t)
                        if not grid.in_bounds(tx, ty) or grid.cls[ty * grid.w + tx] not in PASSABLE:
                            water += 1
                cost = disp + 2.5 * water
                if best_trial is None or cost < best_trial[0]:
                    best_trial = (cost, scale, ox, oy, ideal, placed, disp, water)
    if best_trial is None:
        raise ValueError(f"{map_name}: no scale and offset places every node on buildable land")
    _cost, scale, ox, oy, ideal, placed, disp, water = best_trial
    return _finish(board, grid, map_name, scale, ox, oy, ideal, placed, disp, water, strict,
                   "nodes relaxed to buildable plots from the regular layout (scale and offset searched); corridors A* over passable tiles avoiding other plots; no terrain edits")


def build_scaled(board, grid: T.TerrainGrid, map_name: str, base: dict[str, Any], strict: bool = True) -> dict[str, Any]:
    """The embedding of a resampled map from the base map's geometry (D53): every node at k times its base position, so the separation is k times
    the base one and the picture is the same island at a finer grain; corridors are routed afresh on the fine grid."""
    k = _k(grid)
    if int(base.get("map_w", 0)) * k != grid.w:
        raise ValueError(f"{map_name}: base embedding is {base.get('map_w')} wide, the map {grid.w}: not a x{k} resample")
    scale = float(base["unit"]) * k
    ox, oy = float(base["offset"][0]) * k, float(base["offset"][1]) * k
    ideal = {n: (p[0] * k, p[1] * k) for n, p in base["ideal"].items()}
    placed: dict[str, tuple[float, float]] = {}
    gap = MIN_NODE_GAP * scale
    for n, p in base["nodes"].items():
        x, y = p[0] * k, p[1] * k
        # the smoothed coast may have moved a plot's ground: the nearest buildable tile with a good plot, never far
        best = None
        for r in range(0, 4 * k + 1):
            cands = []
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    tx, ty = int(x) + dx, int(y) + dy
                    if not grid.in_bounds(tx, ty) or grid.cls[ty * grid.w + tx] not in (T.ARABLE, T.WALKABLE):
                        continue
                    if any(math.hypot(tx + 0.5 - px, ty + 0.5 - py) < gap for px, py in placed.values()):
                        continue
                    frac = _buildable_fraction(grid, tx, ty, _pr(grid))
                    if frac < 0.6:
                        continue
                    cands.append((frac * 2.0 - math.hypot(dx, dy) / (4.0 * k), -abs(dx) - abs(dy), tx, ty))
            if cands:
                cands.sort(reverse=True)
                best = (cands[0][2] + 0.5, cands[0][3] + 0.5)
                break
        if best is None:
            raise ValueError(f"{map_name}: no buildable plot near the scaled position of {n}")
        placed[n] = best
    disp = sum(math.hypot(placed[n][0] - ideal[n][0], placed[n][1] - ideal[n][1]) for n in board.nodes)
    water = 0
    for a_, b_ in board.edge_endpoints.values():
        (ax, ay), (bx_, by_) = placed[a_], placed[b_]
        steps = int(math.hypot(bx_ - ax, by_ - ay)) + 1
        for i in range(steps + 1):
            t = i / steps
            tx, ty = int(ax + (bx_ - ax) * t), int(ay + (by_ - ay) * t)
            if not grid.in_bounds(tx, ty) or grid.cls[ty * grid.w + tx] not in PASSABLE:
                water += 1
    out = _finish(board, grid, map_name, scale, ox, oy, ideal, placed, disp, water, strict,
                  f"the base map's geometry ({base['map']}) at x{k}: nodes at {k} times their base positions, corridors re-routed on the resampled grid; no terrain edits")
    out["base_map"] = base["map"]
    out["resampled"] = k
    return out


def _finish(board, grid: T.TerrainGrid, map_name: str, scale: float, ox: float, oy: float, ideal: dict[str, tuple[float, float]], placed: dict[str, tuple[float, float]],
            disp: float, water: int, strict: bool, notes: str) -> dict[str, Any]:
    unit = scale  # the regular edge length is one board unit
    # planarity: corridors are routed over terrain, but the straight chords must not cross either (they are the overlay and the sanity of the layout)
    edges = list(board.edge_endpoints.items())
    for _round in range(60):
        moved = False
        for i, (ea, (a1, a2)) in enumerate(edges):
            for eb, (b1, b2) in edges[i + 1:]:
                if {a1, a2} & {b1, b2}:
                    continue
                if _segments_cross(placed[a1], placed[a2], placed[b1], placed[b2]):
                    # pull the node furthest from its ideal back halfway
                    worst = max((a1, a2, b1, b2), key=lambda n: math.hypot(placed[n][0] - ideal[n][0], placed[n][1] - ideal[n][1]))
                    px, py = placed[worst]
                    ix, iy = ideal[worst]
                    placed[worst] = ((px + ix) / 2.0, (py + iy) / 2.0)
                    moved = True
        if not moved:
            break
    for i, (ea, (a1, a2)) in enumerate(edges):
        for eb, (b1, b2) in edges[i + 1:]:
            if not ({a1, a2} & {b1, b2}) and _segments_cross(placed[a1], placed[a2], placed[b1], placed[b2]):
                raise ValueError(f"{map_name}: corridors {ea} and {eb} cross after relaxation")
    # corridors: A* over passable tiles, steering clear of every other plot
    avoid: dict[tuple[int, int], float] = {}
    for n, (px, py) in placed.items():
        for dy in range(-_pr(grid), _pr(grid) + 1):
            for dx in range(-_pr(grid), _pr(grid) + 1):
                d = math.hypot(dx, dy)
                if d <= _pr(grid):
                    t = (int(px) + dx, int(py) + dy)
                    avoid[t] = avoid.get(t, 0.0) + (_pr(grid) - d) * 3.0
    corridors: dict[str, list[list[float]]] = {}
    paths: dict[str, list[tuple[int, int]]] = {}

    def tiles_of(eid: str, pad: int = 1) -> set[tuple[int, int]]:
        out = set()
        for x, y in paths[eid]:
            for dy in range(-pad, pad + 1):
                for dx in range(-pad, pad + 1):
                    out.add((x + dx, y + dy))
        return out

    def route(eid: str, hard: set[str], soft: set[str]) -> bool:
        a, b = board.edge_endpoints[eid]
        pa, pb = placed[a], placed[b]
        near_end = lambda t: math.hypot(t[0] + 0.5 - pa[0], t[1] + 0.5 - pa[1]) <= _pr(grid) or math.hypot(t[0] + 0.5 - pb[0], t[1] + 0.5 - pb[1]) <= _pr(grid)  # noqa: E731
        av = {t: c for t, c in avoid.items() if not near_end(t)}
        shares = set(board.node_edges[a]) | set(board.node_edges[b])
        for other in soft | hard:
            if other == eid or other not in paths:
                continue
            for t in tiles_of(other):
                if other in shares and near_end(t):
                    continue
                av[t] = 1e9 if other in hard else av.get(t, 0.0) + 60.0
        box = (max(0, int(min(pa[0], pb[0])) - 18 * _k(grid)), max(0, int(min(pa[1], pb[1])) - 18 * _k(grid)), min(grid.w - 1, int(max(pa[0], pb[0])) + 18 * _k(grid)), min(grid.h - 1, int(max(pa[1], pb[1])) + 18 * _k(grid)))
        path = _astar(grid, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), av, box)
        if path is None:
            return False
        for tol in (0.9, 0.4, 0.0):  # a simplified line may cut a corner into another corridor: fall back to the raw tile path
            cand = _simplify(path, tol) if tol > 0 else [(x + 0.5, y + 0.5) for x, y in path]
            cand[0] = (pa[0], pa[1])
            cand[-1] = (pb[0], pb[1])
            if not any(_corridor_crosses(cand, corridors[o], board, eid, o) for o in corridors if o != eid):
                paths[eid] = path
                corridors[eid] = [[round(x, 2), round(y, 2)] for x, y in cand]
                return True
        return False

    order_e = sorted(board.edge_endpoints, key=lambda e: math.hypot(placed[board.edge_endpoints[e][0]][0] - placed[board.edge_endpoints[e][1]][0], placed[board.edge_endpoints[e][0]][1] - placed[board.edge_endpoints[e][1]][1]))
    for eid in order_e:
        if not route(eid, set(), set(corridors)):
            # soft avoidance failed: try with every routed corridor as a wall, then let the crossing repair below sort it out
            if not route(eid, set(corridors), set()):
                a, b = board.edge_endpoints[eid]
                pa, pb = placed[a], placed[b]
                raw = _astar(grid, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), {t: c for t, c in avoid.items()}, (0, 0, grid.w - 1, grid.h - 1))
                if raw is None:
                    raise ValueError(f"{map_name}: no passable corridor for {eid} between {a} and {b}")
                paths[eid] = raw
                cand = [(x + 0.5, y + 0.5) for x, y in raw]
                cand[0], cand[-1] = (pa[0], pa[1]), (pb[0], pb[1])
                corridors[eid] = [[round(x, 2), round(y, 2)] for x, y in cand]
    # repair: any crossing pair is re-routed, the longer (detouring) corridor first, with the rest as walls
    for _round in range(40):
        crossing = []
        ids = list(corridors)
        for i, ea in enumerate(ids):
            for eb in ids[i + 1:]:
                if _corridor_crosses(corridors[ea], corridors[eb], board, ea, eb):
                    crossing.append((ea, eb))
        if not crossing:
            break
        ea, eb = crossing[0]
        first, second = sorted((ea, eb), key=lambda e: -len(paths[e]))
        if not route(first, set(corridors) - {first}, set()):
            if not route(second, set(corridors) - {second}, set()):
                if strict:
                    raise ValueError(f"{map_name}: corridors {ea} and {eb} cross and neither can be re-routed")
                break
    else:
        if strict:
            raise ValueError(f"{map_name}: corridor crossings could not be repaired")
    # regions: catchment polygon from the embedded corners and a centroid (work sites and woodland depend on the roles: `dress()`)
    regions: dict[str, dict[str, Any]] = {}
    for hid in board.hexes:
        corners = [placed[n] for n in board.hex_nodes[hid]]
        cx = sum(c[0] for c in corners) / 6.0
        cy = sum(c[1] for c in corners) / 6.0
        regions[hid] = {"centroid": [round(cx, 2), round(cy, 2)], "corners": [[round(c[0], 2), round(c[1], 2)] for c in corners]}
    corridor_tiles: set[tuple[int, int]] = set()
    for poly in corridors.values():
        for i in range(len(poly) - 1):
            (ax, ay), (bx, by) = poly[i], poly[i + 1]
            steps = int(math.hypot(bx - ax, by - ay) * 2) + 1
            for k in range(steps + 1):
                t = k / steps
                x, y = int(ax + (bx - ax) * t), int(ay + (by - ay) * t)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        corridor_tiles.add((x + dx, y + dy))
    # the coast: for bank caravans, the nearest water tile outward from each node (an exterior endpoint on this bounded island)
    coast: dict[str, list[float]] = {}
    mapc = (grid.w / 2.0, grid.h / 2.0)
    for n, (px, py) in placed.items():
        dx, dy = px - mapc[0], py - mapc[1]
        L = math.hypot(dx, dy) or 1.0
        dx, dy = dx / L, dy / L
        found = None
        for k in range(1, 120 * _k(grid)):
            x, y = int(px + dx * k), int(py + dy * k)
            if not grid.in_bounds(x, y):
                found = (px + dx * (k - 1), py + dy * (k - 1))
                break
            if grid.cls[y * grid.w + x] == T.WATER:
                found = (x + 0.5, y + 0.5)
                break
        coast[n] = [round(found[0], 2), round(found[1], 2)] if found else [round(px + dx * 20 * _k(grid), 2), round(py + dy * 20 * _k(grid), 2)]
    out = {"version": VERSION, "map": map_name, "map_static_hash": grid.static_hash(), "map_w": grid.w, "map_h": grid.h, "shape": board.shape, "unit": round(unit, 4), "scale": round(scale, 4),
           "offset": [round(ox, 3), round(oy, 3)], "plot_radius": _pr(grid), "nodes": {n: [round(p[0], 2), round(p[1], 2)] for n, p in placed.items()},
           "ideal": {n: [round(p[0], 2), round(p[1], 2)] for n, p in ideal.items()}, "corridors": corridors, "regions": regions, "coast": coast,
           "corridor_tiles": sorted([list(t) for t in corridor_tiles]),
           "displacement": round(disp, 1), "chord_water_tiles": water,
           "edits": [], "notes": notes}
    if strict:
        validate(out, board, grid)
    return out


def dress(emb: dict[str, Any], board, grid: T.TerrainGrid) -> dict[str, Any]:
    """The role-dependent dressing of one world's board on the shared geometry: each region's work site on ground that suits its role, and the
    trees (dense woodland in WOOD regions, a few elsewhere) on arable ground clear of plots and corridors. Deterministic; not saved."""
    pref = {"WOOD": (T.ARABLE,), "SHEEP": (T.ARABLE, T.WALKABLE), "WHEAT": (T.ARABLE,), "BRICK": (T.MINEABLE, T.WALKABLE), "ORE": (T.MINEABLE,), rules.DESERT: (T.ARABLE, T.WALKABLE, T.MINEABLE)}
    corridor_tiles = {tuple(t) for t in emb.get("corridor_tiles", [])}
    placed = {n: (float(x), float(y)) for n, (x, y) in emb["nodes"].items()}
    unit = float(emb["unit"])
    work_sites: dict[str, list[float]] = {}
    trees: list[dict[str, Any]] = []
    rng = _Rng(7)
    for hid in board.hexes:
        reg = emb["regions"][hid]
        role = board.role(hid)
        cx, cy = reg["centroid"]
        best = None
        for dy in range(-8 * _k(grid), 8 * _k(grid) + 1):
            for dx in range(-8 * _k(grid), 8 * _k(grid) + 1):
                x, y = int(cx) + dx, int(cy) + dy
                if not grid.in_bounds(x, y) or grid.cls[y * grid.w + x] not in pref[role] or (x, y) in corridor_tiles:
                    continue
                if any(math.hypot(x + 0.5 - px, y + 0.5 - py) < _pr(grid) + 1.0 for px, py in placed.values()):
                    continue
                d = math.hypot(dx, dy)
                if best is None or d < best[0]:
                    best = (d, x + 0.5, y + 0.5)
        work_sites[hid] = [round(best[1], 2), round(best[2], 2)] if best else [round(cx, 2), round(cy, 2)]
        n = 48 if role == "WOOD" else (8 if role in ("SHEEP", "WHEAT") else 3)
        ground = (T.ARABLE, T.WALKABLE, T.MINEABLE) if role == "WOOD" else (T.ARABLE, T.WALKABLE)  # woodland climbs the mountain sides too
        count = 0
        spots: list[tuple[float, float]] = []
        for _ in range(n * 12):
            if count >= n:
                break
            ang = rng.next() * math.tau
            rad = math.sqrt(rng.next()) * unit * 0.95
            spots.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
            count += 1
        if role == "WOOD":
            # a stand of trees just outside every corner plot, toward the region, so each village that works this woodland has trees in reach
            for nid in board.hex_nodes[hid]:
                px, py = placed[nid]
                dx, dy = cx - px, cy - py
                d = math.hypot(dx, dy) or 1.0
                for k in range(7):
                    off = _pr(grid) + 1.6 + rng.next() * 3.0
                    side = (rng.next() - 0.5) * 5.0
                    spots.append((px + dx / d * off - dy / d * side, py + dy / d * off + dx / d * side))
        for x, y in spots:
            tx, ty = int(x), int(y)
            if not grid.in_bounds(tx, ty) or grid.cls[ty * grid.w + tx] not in ground or (tx, ty) in corridor_tiles:
                continue
            if any(math.hypot(x - px, y - py) < _pr(grid) + 1.0 for px, py in placed.values()):
                continue
            trees.append({"hex": hid, "x": round(x, 2), "y": round(y, 2), "species": TREE_SPECIES[int(rng.next() * len(TREE_SPECIES)) % len(TREE_SPECIES)]})
    return {"work_sites": work_sites, "trees": trees}


def validate(emb: dict[str, Any], board, grid: T.TerrainGrid) -> dict[str, Any]:
    """The checks a host map must pass; returns a report (and raises on a hard failure)."""
    nodes = emb["nodes"]
    if set(nodes) != set(board.nodes):
        raise ValueError("embedding does not cover every node")
    if set(emb["corridors"]) != set(board.edges):
        raise ValueError("embedding does not cover every edge")
    unit = float(emb["unit"])
    gap = MIN_NODE_GAP * unit
    poor = []
    for n, (x, y) in nodes.items():
        if not grid.in_bounds(int(x), int(y)) or grid.cls[int(y) * grid.w + int(x)] not in (T.ARABLE, T.WALKABLE):
            raise ValueError(f"{n} plot is not on buildable land")
        frac = _buildable_fraction(grid, int(x), int(y), _pr(grid))
        if frac < 0.6:
            poor.append((n, round(frac, 2)))
    ids = list(nodes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1]) < gap - 1e-6:
                raise ValueError(f"plots {a} and {b} are closer than {gap:.1f} tiles")
    for eid, poly in emb["corridors"].items():
        a, b = board.edge_endpoints[eid]
        if [round(v, 2) for v in poly[0]] != nodes[a] or [round(v, 2) for v in poly[-1]] != nodes[b]:
            raise ValueError(f"corridor {eid} does not join its endpoints")
        for x, y in poly[1:-1]:
            if grid.cls[int(y) * grid.w + int(x)] not in PASSABLE:
                raise ValueError(f"corridor {eid} crosses impassable ground at {x},{y}")
    # corridor segments of unrelated edges must not cross
    segs = []
    for eid, poly in emb["corridors"].items():
        for i in range(len(poly) - 1):
            segs.append((eid, tuple(poly[i]), tuple(poly[i + 1])))
    ends = board.edge_endpoints
    for i, (ea, a1, a2) in enumerate(segs):
        for eb, b1, b2 in segs[i + 1:]:
            if ea == eb or set(ends[ea]) & set(ends[eb]):
                continue
            if _segments_cross(a1, a2, b1, b2):
                raise ValueError(f"corridors {ea} and {eb} cross at {a1}-{a2} / {b1}-{b2}")
    lengths = [_poly_length([tuple(p) for p in poly]) for poly in emb["corridors"].values()]
    return {"nodes": len(nodes), "edges": len(emb["corridors"]), "poor_plots": poor, "unit": unit, "corridor_tiles_min": round(min(lengths), 1),
            "corridor_tiles_max": round(max(lengths), 1), "corridor_tiles_mean": round(sum(lengths) / len(lengths), 1)}
