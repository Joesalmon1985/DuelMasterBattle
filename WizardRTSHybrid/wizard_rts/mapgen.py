"""Deterministic square-grid map generator using Widelands terrain and resource rules.

Engineering proposal (not a Widelands algorithm): value-noise elevation, a ridged
mountain field and a moisture field choose Widelands summer terrains. Six homelands
are stamped identically (rotated and mirrored by the seed) so every faction has
arable land, a mountain with coal, iron, gold and stones, and a lake; the six lakes
are joined to a central sea so one body of water carries fishing and ships.
Terrain classes, resources and amounts follow data/world/terrains and resources.
"""

from __future__ import annotations

import random
from typing import Sequence

from wizard_rts import terrain as T
from wizard_rts.grid import DIRS4

SIZES = {"small": (384, 224), "standard": (544, 288), "large": (800, 480)}
# capital tiles on the standard map; other sizes scale these
STANDARD_STARTS = ((83, 48), (208, 72), (332, 96), (180, 168), (333, 192), (457, 168))
HOME_RADIUS = 26

PALETTE = [
    "summer_water", "summer_beach", "summer_meadow1", "summer_meadow2", "summer_meadow3", "summer_meadow4",
    "summer_steppe", "summer_steppe_barren", "summer_mountain_meadow",
    "summer_mountain1", "summer_mountain2", "summer_mountain3", "summer_mountain4",
    "summer_forested_mountain1", "summer_snow",
]
P = {n.replace("summer_", ""): i for i, n in enumerate(PALETTE)}
MEADOWS = (P["meadow1"], P["meadow2"], P["meadow3"], P["meadow4"])
MOUNTAINS = (P["mountain1"], P["mountain2"], P["mountain3"], P["mountain4"])
ORE_AMOUNT = {"coal": 30, "iron": 30, "gold": 24, "stones": 30}

_CACHE: dict[tuple, T.TerrainGrid] = {}


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _field(rng: random.Random, w: int, h: int, cells: Sequence[int], weights: Sequence[float]) -> list[float]:
    """Sum of bilinear value-noise octaves, normalised to [0, 1]."""
    out = [0.0] * (w * h)
    total = float(sum(weights))
    for cell, wt in zip(cells, weights):
        gw, gh = w // cell + 2, h // cell + 2
        lat = [rng.random() for _ in range(gw * gh)]
        xs = [(x // cell, _smooth((x % cell) / cell)) for x in range(w)]
        for y in range(h):
            gy, fy = y // cell, _smooth((y % cell) / cell)
            r0, r1 = gy * gw, (gy + 1) * gw
            base = y * w
            k = wt / total
            for x in range(w):
                gx, fx = xs[x]
                a = lat[r0 + gx]
                b = lat[r0 + gx + 1]
                c = lat[r1 + gx]
                d = lat[r1 + gx + 1]
                top = a + (b - a) * fx
                out[base + x] += k * (top + (c + (d - c) * fx - top) * fy)
    return out


def starts_for(w: int, h: int) -> list[tuple[int, int]]:
    sx, sy = w / SIZES["standard"][0], h / SIZES["standard"][1]
    if (w, h) == SIZES["standard"]:
        return list(STANDARD_STARTS)
    return [(int(x * sx), int(y * sy)) for x, y in STANDARD_STARTS]


def _disk(cx: float, cy: float, r: float, w: int, h: int):
    r2 = r * r
    for y in range(max(0, int(cy - r) - 1), min(h, int(cy + r) + 2)):
        for x in range(max(0, int(cx - r) - 1), min(w, int(cx + r) + 2)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                yield x, y


def _channel(g: T.TerrainGrid, rng: random.Random, a: tuple[int, int], b: tuple[int, int], width: int, margin: int) -> None:
    """A meandering water channel from a to b, three tiles wide by default."""
    x, y = float(a[0]), float(a[1])
    steps = 0
    while (abs(x - b[0]) + abs(y - b[1])) > 3 and steps < 4000:
        steps += 1
        dx, dy = b[0] - x, b[1] - y
        n = max(abs(dx), abs(dy), 1.0)
        x += dx / n + (rng.random() - 0.5) * 1.1
        y += dy / n + (rng.random() - 0.5) * 1.1
        xi, yi = int(x), int(y)
        if not (margin <= xi < g.w - margin and margin <= yi < g.h - margin):
            continue
        for ox in range(-(width // 2), width // 2 + 1):
            for oy in range(-(width // 2), width // 2 + 1):
                i = (yi + oy) * g.w + xi + ox
                g.terrain[i] = P["water"]


def generate(seed: int = 507, size: str | tuple[int, int] = "standard") -> T.TerrainGrid:
    """Return a computed TerrainGrid. Same (seed, size) always gives the same map."""
    w, h = SIZES[size] if isinstance(size, str) else (int(size[0]), int(size[1]))
    key = (int(seed), w, h)
    if key not in _CACHE:
        _CACHE[key] = _generate(int(seed), w, h)
    return _CACHE[key].copy()


def _generate(seed: int, w: int, h: int) -> T.TerrainGrid:
    rng = random.Random(seed * 7919 + w * 31 + h)
    g = T.TerrainGrid(w, h, PALETTE)
    starts = starts_for(w, h)
    g.starts = list(starts)
    n = w * h
    elev = _field(rng, w, h, (96, 48, 24, 12), (0.45, 0.30, 0.17, 0.08))
    ridge_src = _field(rng, w, h, (64, 32, 16), (0.55, 0.30, 0.15))
    moist = _field(rng, w, h, (80, 24), (0.7, 0.3))
    detail = _field(rng, w, h, (6,), (1.0,))

    # --- sea level: edge ocean and a central sea (the homelands are stamped on top afterwards)
    mx = sum(s[0] for s in starts) / 6.0
    my = sum(s[1] for s in starts) / 6.0
    rx, ry = w * 0.125, h * 0.155
    edge = max(24, min(w, h) // 9)
    land = bytearray(n)
    mountain = bytearray(n)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            e = elev[i]
            d_edge = min(x, y, w - 1 - x, h - 1 - y)
            if d_edge < edge:
                e -= (edge - d_edge) / edge * 0.75
            q = ((x - mx) / rx) ** 2 + ((y - my) / ry) ** 2
            if q < 1.4:
                e -= (1.4 - q) / 1.4 * 0.9
            land[i] = 1 if e > 0.38 else 0
            if edge - 8 <= d_edge < edge + 12:
                land[i] = 1  # a land belt keeps the central sea from joining the outer ocean
            r = 1.0 - abs(2.0 * ridge_src[i] - 1.0)
            if land[i] and e > 0.42 and r > 0.87:
                mountain[i] = 2 if r > 0.965 else 1
            g.height[i] = max(2, min(250, int(20 + 60 * max(e, 0.0) + (22 * (r - 0.7) / 0.3 if mountain[i] else 0))))

    # --- homelands
    homes = []
    for k, (cx, cy) in enumerate(starts):
        # the lake sits on the side facing the central sea, so its channel never crosses the homeland;
        # the mountain takes the opposite or a side direction (seeded), away from the map edge
        vx, vy = mx - cx, my - cy
        lake_dir = (0 if vx > 0 else 2) if abs(vx) >= abs(vy) else (1 if vy > 0 else 3)  # index into dirs: E, S, W, N
        opts = [(lake_dir + 2) % 4, (lake_dir + 1) % 4, (lake_dir + 3) % 4]
        dirs4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        opts = [o for o in opts if min(cx + dirs4[o][0] * 20, cy + dirs4[o][1] * 20, w - 1 - (cx + dirs4[o][0] * 20), h - 1 - (cy + dirs4[o][1] * 20)) >= 38] or [(lake_dir + 2) % 4]
        homes.append((cx, cy, lake_dir, opts[rng.randrange(len(opts))]))
    for cx, cy, _ld, _md in homes:
        for x, y in _disk(cx, cy, HOME_RADIUS, w, h):
            i = y * w + x
            land[i] = 1
            mountain[i] = 0
            g.height[i] = 40 + (g.height[i] % 5)

    # --- base terrain
    for i in range(n):
        if not land[i]:
            g.terrain[i] = P["water"]
            continue
        if mountain[i] == 2:
            g.terrain[i] = P["snow"]
        elif mountain[i] == 1:
            g.terrain[i] = MOUNTAINS[int(detail[i] * 4) % 4]
        else:
            m = moist[i]
            if m < 0.30:
                g.terrain[i] = P["steppe_barren"]
            elif m < 0.42:
                g.terrain[i] = P["steppe"]
            else:
                g.terrain[i] = MEADOWS[int(detail[i] * 4) % 4]
    # snow needs a mountain skirt so it never touches arable land directly
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            i = y * w + x
            if g.terrain[i] != P["snow"]:
                continue
            for dx, dy in DIRS4:
                j = i + dy * w + dx
                if g.terrain[j] not in (P["snow"], P["water"], *MOUNTAINS):
                    g.terrain[j] = MOUNTAINS[0]

    # --- homeland stamps: identical content, rotated per seed
    for k, (cx, cy, ld, md) in enumerate(homes):
        _stamp_home(g, rng, cx, cy, ld, md)

    # --- the six lakes are joined to the central sea by channels (a tree, so the land stays connected)
    centre = (int(mx), int(my))
    for k, (cx, cy, _ld, _md) in enumerate(homes):
        lake = g.meta["homes"][k]["lake"]
        _channel(g, rng, tuple(lake), centre, 3, edge + 6)
    for y in range(max(0, centre[1] - 3), min(h, centre[1] + 4)):
        for x in range(max(0, centre[0] - 3), min(w, centre[0] + 4)):
            g.terrain[y * w + x] = P["water"]

    # --- shorelines: land touching water becomes beach (two tiles wide), swamp pockets by water
    _beach(g)
    _ensure_ground_links(g, rng, starts)
    g.compute()
    _resources(g, rng, homes)
    _features(g, rng, homes, moist)
    g.meta["generator"] = "wizard_rts.mapgen v1"
    g.meta["seed"] = seed
    g.meta["capitals"] = [list(s) for s in starts]
    return g


def _stamp_home(g: T.TerrainGrid, rng: random.Random, cx: int, cy: int, lake_dir: int, mount_dir: int) -> None:
    w, h = g.w, g.h
    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    d_mount = dirs[mount_dir]
    d_lake = dirs[lake_dir]
    mcx, mcy = cx + d_mount[0] * 20, cy + d_mount[1] * 20
    lcx, lcy = cx + d_lake[0] * 19, cy + d_lake[1] * 19
    # meadow core: fertile arable land around the capital
    for x, y in _disk(cx, cy, 13, w, h):
        i = y * w + x
        g.terrain[i] = MEADOWS[(x // 3 + y // 5) % 4]
        g.height[i] = 40 + ((x + y) // 6) % 2
    # mountain with a skirt of mountain meadow
    for x, y in _disk(mcx, mcy, 11, w, h):
        g.terrain[y * w + x] = P["mountain_meadow"]
    for x, y in _disk(mcx, mcy, 9, w, h):
        i = y * w + x
        g.terrain[i] = MOUNTAINS[(x + 2 * y) % 4]
        g.height[i] = 55 + min(12, int(12 - ((x - mcx) ** 2 + (y - mcy) ** 2) ** 0.5))
    # the lake
    for x, y in _disk(lcx, lcy, 7.5, w, h):
        g.terrain[y * w + x] = P["water"]
        g.height[y * w + x] = 10
    g.meta.setdefault("homes", []).append({
        "capital": [cx, cy], "mountain": [mcx, mcy], "lake": [lcx, lcy], "lake_dir": lake_dir, "mount_dir": mount_dir,
    })


def _beach(g: T.TerrainGrid) -> None:
    w, h = g.w, g.h
    water = P["water"]
    near = bytearray(w * h)
    frontier = [i for i in range(w * h) if g.terrain[i] == water]
    for _ in range(2):
        nxt = []
        for i in frontier:
            x, y = i % w, i // w
            for dx, dy in DIRS4:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    j = ny * w + nx
                    if g.terrain[j] != water and not near[j]:
                        near[j] = 1
                        nxt.append(j)
        frontier = nxt
    for i in range(w * h):
        if near[i] and g.terrain[i] not in (water, P["snow"]):
            g.terrain[i] = P["beach"]


def _ensure_ground_links(g: T.TerrainGrid, rng: random.Random, starts: list[tuple[int, int]]) -> None:
    """Carve land links until every capital reaches every other on foot."""
    w, h = g.w, g.h
    ground = {P["beach"], P["steppe"], P["steppe_barren"], P["mountain_meadow"], *MEADOWS, *MOUNTAINS}

    def reach(src: tuple[int, int]) -> set[int]:
        seen = {src[1] * w + src[0]}
        stack = [src[1] * w + src[0]]
        while stack:
            i = stack.pop()
            x, y = i % w, i // w
            for dx, dy in DIRS4:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    j = ny * w + nx
                    if j not in seen and g.terrain[j] in ground:
                        seen.add(j)
                        stack.append(j)
        return seen

    for _round in range(8):
        seen = reach(starts[0])
        missing = [s for s in starts if s[1] * w + s[0] not in seen]
        if not missing:
            return
        tgt = missing[0]
        x, y = tgt
        # walk west/north toward the first capital until the reached region is entered
        while y * w + x not in seen:
            tx, ty = starts[0]
            if abs(x - tx) > abs(y - ty):
                x += 1 if tx > x else -1
            else:
                y += 1 if ty > y else -1
            i = y * w + x
            if g.terrain[i] not in ground:
                g.terrain[i] = P["mountain_meadow"] if g.terrain[i] != P["water"] else P["beach"]


def _resources(g: T.TerrainGrid, rng: random.Random, homes) -> None:
    w, h = g.w, g.h
    d = T.defs()["terrains"]
    ores = ("coal", "iron", "gold", "stones")
    # homeland ore blobs: four per mountain, each on its own quarter of the mountain
    for k, home in enumerate(g.meta["homes"]):
        mcx, mcy = home["mountain"]
        ang = rng.randrange(4)
        for j, res in enumerate(ores):
            off = [(-4, -4), (4, -4), (-4, 4), (4, 4)][(j + ang) % 4]
            _blob(g, rng, mcx + off[0], mcy + off[1], 3.4, res, ORE_AMOUNT[res])
    # wild deposits on every other mountain
    n_wild = 0
    for _ in range(400):
        x, y = rng.randrange(w), rng.randrange(h)
        if g.cls[y * w + x] == T.MINEABLE and all((x - m["mountain"][0]) ** 2 + (y - m["mountain"][1]) ** 2 > 16 ** 2 for m in g.meta["homes"]):
            _blob(g, rng, x, y, 3.0 + rng.random() * 2, rng.choice(ores), 20 + rng.randrange(11))
            n_wild += 1
    # water under arable land (Widelands default_resource for those terrains)
    for i in range(w * h):
        if g.res_kind[i]:
            continue
        t = d[g.palette[g.terrain[i]]]
        if t["default_resource"] == "water" and g.cls[i] == T.ARABLE:
            g.res_kind[i] = T.RES_WATER
            g.res_amt[i] = int(t["default_amount"]) or 10
    # fish: richer near shore, thin in the open sea
    for i in range(w * h):
        if g.cls[i] == T.WATER:
            dep = g.depth[i]
            g.res_kind[i] = T.RES_FISH
            g.res_amt[i] = (6 + rng.randrange(9)) if dep <= 8 else (2 + rng.randrange(3))
    g.res_init[:] = g.res_amt
    g.meta["wild_deposits"] = n_wild


def _blob(g: T.TerrainGrid, rng: random.Random, cx: float, cy: float, r: float, res: str, amount: int) -> None:
    for x, y in _disk(cx, cy, r, g.w, g.h):
        i = y * g.w + x
        if g.cls[i] != T.MINEABLE or g.res_kind[i]:
            continue
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        a = int(amount * (1.15 - 0.6 * dist / r)) + rng.randrange(-2, 3)
        if a > 0:
            g.res_kind[i] = T.RES_CODE[res]
            g.res_amt[i] = min(255, a)


def _features(g: T.TerrainGrid, rng: random.Random, homes, moist: list[float]) -> None:
    """Initial trees and rocks as data; the world turns them into persistent objects."""
    w, h = g.w, g.h
    trees: list[list] = []
    rocks: list[list] = []
    stages = ["old"] * 6 + ["mature"] * 3 + ["pole"] * 2 + ["sapling"]
    species_for = ("beech", "oak", "birch", "spruce", "maple", "larch", "alder")
    # homeland forests: a woodland within each homeland's meadow ring
    for home in g.meta["homes"]:
        cx, cy = home["capital"]
        for _ in range(260):
            x, y = cx + rng.randint(-24, 24), cy + rng.randint(-24, 24)
            if not g.in_bounds(x, y) or g.cls[y * w + x] != T.ARABLE:
                continue
            if (x - cx) ** 2 + (y - cy) ** 2 < 36:
                continue
            sp = "beech" if rng.random() < 0.5 else species_for[rng.randrange(len(species_for))]
            if g.growth_probability(sp, x, y) < 0.25:
                continue
            trees.append([x, y, sp, stages[rng.randrange(len(stages))]])
        mcx, mcy = home["mountain"]
        for _ in range(70):
            x, y = mcx + rng.randint(-14, 14), mcy + rng.randint(-14, 14)
            if g.in_bounds(x, y) and g.terrain[y * w + x] == P["mountain_meadow"]:
                rocks.append([x, y])
        for _ in range(22):  # a few rocks on meadow near the quarry search radius
            x, y = cx + rng.randint(-14, 14), cy + rng.randint(4, 18)
            if g.in_bounds(x, y) and g.cls[y * w + x] == T.ARABLE and (x - cx) ** 2 + (y - cy) ** 2 > 64:
                rocks.append([x, y])
    # wild forests in the open country
    for _ in range(2500):
        x, y = rng.randrange(w), rng.randrange(h)
        if g.cls[y * w + x] != T.ARABLE or moist[y * w + x] < 0.5:
            continue
        sp = species_for[rng.randrange(len(species_for))]
        if g.growth_probability(sp, x, y) < 0.35:
            continue
        for _k in range(rng.randrange(2, 8)):
            tx, ty = x + rng.randint(-5, 5), y + rng.randint(-5, 5)
            if g.in_bounds(tx, ty) and g.cls[ty * w + tx] == T.ARABLE:
                trees.append([tx, ty, sp, stages[rng.randrange(len(stages))]])
    seen = set()
    dedup = []
    for t in trees:
        if (t[0], t[1]) not in seen:
            seen.add((t[0], t[1]))
            dedup.append(t)
    rocks = [list(r) for r in {tuple(r) for r in rocks if tuple(r) not in seen}]
    rocks.sort()
    g.features = {"trees": dedup, "rocks": rocks}
