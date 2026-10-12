"""Square-grid terrain: one node per tile, rules derived from Widelands.

Source: Widelands data/world/terrains (is, fertility, humidity, temperature,
valid and default resources), data/world/resources, src/logic/map.cc
(calc_nodecaps_pass1/pass2, calc_buildsize) and
src/logic/map_objects/terrain_affinity.cc (probability_to_grow).
GPL-2.0-or-later, Widelands Development Team.

Differences from Widelands (square grid, see DECISIONS.md D5): a node has one
terrain, not two triangles; adjacency is 4 or 8 neighbours instead of 6;
building size is decided by the terrain class of the node and its neighbours
and by the height difference to them; roads are tile paths.
"""

from __future__ import annotations

import hashlib
import json
import math
import zlib
from base64 import b64encode
from functools import lru_cache
from pathlib import Path

from wizard_rts.grid import DIRS4, DIRS8

DATA = Path(__file__).resolve().parent / "data" / "terrain_defs.json"

# terrain class codes (Widelands TerrainDescription::Is)
ARABLE, MINEABLE, WALKABLE, WATER, UNWALKABLE, UNREACHABLE = range(6)
CLASS_CODE = {"arable": ARABLE, "mineable": MINEABLE, "walkable": WALKABLE, "water": WATER,
              "unwalkable": UNWALKABLE, "unreachable": UNREACHABLE}

# resource layer codes
RES_NONE, RES_COAL, RES_IRON, RES_GOLD, RES_STONES, RES_FISH, RES_WATER = range(7)
RES_NAMES = ("", "coal", "iron", "gold", "stones", "fish", "water")
RES_CODE = {n: i for i, n in enumerate(RES_NAMES)}
# D22 (owner decision, 12 Oct 2026): a mineral site never runs dry. Mines and drills on these kinds read the deposit but do not
# shrink it; the ware they make is logged as `mined_from_inexhaustible_deposit` by the caller. Fish and water keep their own
# finite, breeding ecology.
MINERALS = frozenset(("coal", "iron", "gold", "stones"))


def is_mineral(res: str) -> bool:
    return res in MINERALS

# build capability values (Widelands BUILDCAPS_*)
B_NONE, B_SMALL, B_MEDIUM, B_BIG, B_MINE = 0, 1, 2, 3, 4
B_PORT = 8  # flag bit, only on a big site
SIZE_CODE = {"small": B_SMALL, "medium": B_MEDIUM, "big": B_BIG, "mine": B_MINE, "port": B_BIG}

MOVE_WALK = 1
MOVE_SWIM = 2

SHALLOW_DEPTH = 2  # water within this many tiles of land is shallow (engineering proposal)
PORT_MIN_WATER = 150  # a port or shipyard needs water of at least this many tiles (engineering)


@lru_cache(maxsize=1)
def defs() -> dict:
    return json.loads(DATA.read_text())


class TerrainGrid:
    def __init__(self, w: int, h: int, palette: list[str]) -> None:
        self.w, self.h = int(w), int(h)
        n = self.w * self.h
        self.palette = list(palette)
        self.terrain = bytearray(n)
        self.height = bytearray(n)
        self.res_kind = bytearray(n)
        self.res_amt = bytearray(n)
        self.res_init = bytearray(n)  # Widelands get_initial_res_amount: fish can only be bred back up to this
        self.cls = bytearray(n)
        self.move = bytearray(n)
        self.build = bytearray(n)
        self.depth = bytearray(n)  # water: distance to land (1 = shore water); land: 0
        self.water_comp = [0] * n  # water component id per tile, 0 = land
        self.comp_size: dict[int, int] = {}
        self.starts: list[tuple[int, int]] = []
        self.meta: dict = {}
        self.features: dict = {"trees": [], "rocks": []}
        self._palette_cls: list[int] = []
        self._refresh_palette()

    # ------------------------------------------------------------ basics
    def _refresh_palette(self) -> None:
        d = defs()["terrains"]
        self._palette_cls = [CLASS_CODE[d[name]["is"]] for name in self.palette]

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def terrain_name(self, x: int, y: int) -> str:
        return self.palette[self.terrain[y * self.w + x]]

    def terrain_def(self, x: int, y: int) -> dict:
        return defs()["terrains"][self.terrain_name(x, y)]

    def ground(self, x: int, y: int) -> bool:
        """A ground unit or worker may stand here."""
        return 0 <= x < self.w and 0 <= y < self.h and bool(self.move[y * self.w + x] & MOVE_WALK)

    def swimmable(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and bool(self.move[y * self.w + x] & MOVE_SWIM)

    def is_water(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and self.cls[y * self.w + x] == WATER

    def class_at(self, x: int, y: int) -> int:
        return self.cls[y * self.w + x]

    # ------------------------------------------------------------ caps
    def compute(self) -> None:
        """Derive class, movement, build caps, shore depth and water components."""
        self._refresh_palette()
        w, h = self.w, self.h
        pc = self._palette_cls
        cls, terr, move = self.cls, self.terrain, self.move
        for i in range(w * h):
            c = pc[terr[i]]
            cls[i] = c
            move[i] = MOVE_WALK if c in (ARABLE, MINEABLE, WALKABLE) else (MOVE_SWIM if c == WATER else 0)
        self._compute_water()
        self._compute_build()

    def _compute_water(self) -> None:
        w, h = self.w, self.h
        cls, depth = self.cls, self.depth
        comp = self.water_comp
        for i in range(w * h):
            comp[i] = 0
            depth[i] = 0
        self.comp_size = {}
        cid = 0
        for start in range(w * h):
            if cls[start] != WATER or comp[start]:
                continue
            cid += 1
            comp[start] = cid
            stack = [start]
            size = 0
            while stack:
                i = stack.pop()
                size += 1
                x, y = i % w, i // w
                for dx, dy in DIRS4:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if cls[j] == WATER and not comp[j]:
                            comp[j] = cid
                            stack.append(j)
            self.comp_size[cid] = size
        # shore distance by multi-source BFS from land
        frontier = []
        for i in range(w * h):
            if cls[i] == WATER:
                x, y = i % w, i // w
                for dx, dy in DIRS4:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < w and 0 <= ny < h) or cls[ny * w + nx] != WATER:
                        depth[i] = 1
                        frontier.append(i)
                        break
        d = 1
        while frontier:
            d = min(d + 1, 255)
            nxt = []
            for i in frontier:
                x, y = i % w, i // w
                for dx, dy in DIRS4:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if cls[j] == WATER and depth[j] == 0:
                            depth[j] = d
                            nxt.append(j)
            frontier = nxt

    def _compute_build(self) -> None:
        w, h = self.w, self.h
        cls, hgt, build = self.cls, self.height, self.build
        for i in range(w * h):
            build[i] = 0
        for y in range(1, h - 1):
            row = y * w
            for x in range(1, w - 1):
                i = row + x
                c = cls[i]
                if c == MINEABLE:
                    if all(cls[i + dy * w + dx] == MINEABLE for dx, dy in DIRS4):
                        build[i] = B_MINE
                    continue
                if c != ARABLE:
                    continue
                if not all(cls[i + dy * w + dx] == ARABLE for dx, dy in DIRS4):
                    continue
                size = B_MEDIUM
                if all(cls[i + dy * w + dx] == ARABLE for dx, dy in DIRS8[4:]):
                    size = B_BIG
                hh = hgt[i]
                slope = max(abs(hgt[i + dy * w + dx] - hh) for dx, dy in DIRS8)
                if slope >= 4:
                    continue
                if slope >= 3:
                    size = B_SMALL
                build[i] = size
        # port flag: a big site with a big enough water body within 4 tiles
        for y in range(4, h - 4):
            for x in range(4, w - 4):
                i = y * w + x
                if build[i] == B_BIG and self.coast_component(x, y, 4):
                    build[i] |= B_PORT

    # ------------------------------------------------------------ water
    def coast_component(self, x: int, y: int, radius: int, min_size: int = PORT_MIN_WATER) -> int:
        """Id of the largest water component within radius of (x, y), or 0 if none is big enough."""
        best, best_size = 0, 0
        w = self.w
        for yy in range(max(0, y - radius), min(self.h, y + radius + 1)):
            for xx in range(max(0, x - radius), min(w, x + radius + 1)):
                c = self.water_comp[yy * w + xx]
                if c and self.comp_size[c] > best_size:
                    best, best_size = c, self.comp_size[c]
        return best if best_size >= min_size else 0

    def is_shallow(self, x: int, y: int) -> bool:
        i = y * self.w + x
        return self.cls[i] == WATER and self.depth[i] <= SHALLOW_DEPTH

    # ------------------------------------------------------------ building rules
    def can_build(self, x: int, y: int, size: str) -> bool:
        if not self.in_bounds(x, y):
            return False
        cap = self.build[y * self.w + x]
        if size == "port":
            return bool(cap & B_PORT)
        base = cap & 7
        if size == "mine":
            return base == B_MINE
        return B_SMALL <= base <= B_BIG and base >= SIZE_CODE[size]

    def build_cap_name(self, x: int, y: int) -> str:
        cap = self.build[y * self.w + x]
        base = cap & 7
        name = ("none", "small", "medium", "big", "mine")[base]
        return name + ("+port" if cap & B_PORT else "")

    # ------------------------------------------------------------ resources
    def resource(self, x: int, y: int) -> tuple[str, int]:
        i = y * self.w + x
        return RES_NAMES[self.res_kind[i]], self.res_amt[i]

    def amount(self, x: int, y: int, res: str) -> int:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return 0
        i = y * self.w + x
        return self.res_amt[i] if self.res_kind[i] == RES_CODE[res] else 0

    def take(self, x: int, y: int, res: str, n: int = 1) -> int:
        i = y * self.w + x
        if self.res_kind[i] != RES_CODE[res]:
            return 0
        if res in MINERALS:  # D22: the site is inexhaustible; the reserve figure is its richness, not a stock
            return n if (self.res_amt[i] > 0 or self.res_init[i] > 0) else 0
        got = min(n, self.res_amt[i])
        self.res_amt[i] -= got
        return got

    def add(self, x: int, y: int, res: str, n: int = 1, cap: int = 255) -> int:
        i = y * self.w + x
        if self.res_kind[i] != RES_CODE[res]:
            return 0
        add = min(n, cap - self.res_amt[i])
        self.res_amt[i] += add
        return add

    def nodes_with(self, cx: int, cy: int, radius: int, res: str):
        """Nodes within Chebyshev radius holding res, row-major (deterministic)."""
        code = RES_CODE[res]
        w = self.w
        out = []
        for y in range(max(0, cy - radius), min(self.h, cy + radius + 1)):
            base = y * w
            for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
                i = base + x
                if self.res_kind[i] == code and (self.res_amt[i] > 0 or (res in MINERALS and self.res_init[i] > 0)):
                    out.append((x, y))
        return out

    def cells(self, cx: int, cy: int, radius: int, res: str) -> list[tuple[int, int, int, int]]:
        """(x, y, amount, initial) for every node of this resource kind in the square, row-major (Widelands MapRegion order)."""
        code = RES_CODE[res]
        out = []
        for y in range(max(0, cy - radius), min(self.h, cy + radius + 1)):
            base = y * self.w
            for x in range(max(0, cx - radius), min(self.w, cx + radius + 1)):
                i = base + x
                if self.res_kind[i] == code:
                    out.append((x, y, self.res_amt[i], self.res_init[i]))
        return out

    def total(self, cx: int, cy: int, radius: int, res: str) -> int:
        code = RES_CODE[res]
        s = 0
        for y in range(max(0, cy - radius), min(self.h, cy + radius + 1)):
            for x in range(max(0, cx - radius), min(self.w, cx + radius + 1)):
                i = y * self.w + x
                if self.res_kind[i] == code:
                    s += self.res_amt[i]
        return s

    # ------------------------------------------------------------ growth (terrain_affinity.cc)
    def environment(self, x: int, y: int) -> tuple[int, int, int]:
        """Mean (humidity, fertility, temperature) over the node and its four neighbours."""
        d = defs()["terrains"]
        hum = fer = tem = 0
        cells = [(x, y)] + [(x + dx, y + dy) for dx, dy in DIRS4]
        n = 0
        for cx, cy in cells:
            if not self.in_bounds(cx, cy):
                continue
            t = d[self.palette[self.terrain[cy * self.w + cx]]]
            hum += t["humidity"]
            fer += t["fertility"]
            tem += t["temperature"]
            n += 1
        return (hum + n // 2) // n, (fer + n // 2) // n, (tem + n // 2) // n

    def growth_probability(self, species: str, x: int, y: int) -> float:
        """Widelands probability_to_grow in [0, 1] for a tree species at a node."""
        aff = defs()["tree_affinity"].get(species)
        if aff is None:
            return 1.0
        hum, fer, tem = self.environment(x, y)
        sigma = math.floor(100.0 - aff["pickiness"])
        v = -(((aff["preferred_fertility"] - fer) / (5.292268046607387 * sigma)) ** 2
              + ((aff["preferred_humidity"] - hum) / (5.00086642549548 * sigma)) ** 2
              + ((aff["preferred_temperature"] - tem) / (0.6131300863608306 * sigma)) ** 2) / 2.0
        return math.exp(v)

    # ------------------------------------------------------------ identity and transport
    def copy(self) -> "TerrainGrid":
        g = TerrainGrid(self.w, self.h, self.palette)
        for name in ("terrain", "height", "res_kind", "res_amt", "res_init", "cls", "move", "build", "depth"):
            setattr(g, name, bytearray(getattr(self, name)))
        g.water_comp = list(self.water_comp)
        g.comp_size = dict(self.comp_size)
        g.starts = list(self.starts)
        g.meta = json.loads(json.dumps(self.meta))
        g.features = json.loads(json.dumps(self.features))
        return g

    def state_hash(self) -> str:
        h = hashlib.sha1()
        for layer in (self.terrain, self.height, self.res_kind, self.res_amt, self.res_init):
            h.update(layer)
        h.update(json.dumps(self.palette).encode())
        return h.hexdigest()

    def static_hash(self) -> str:
        """Hash of the layers that never change in play (terrain and height)."""
        h = hashlib.sha1()
        h.update(self.terrain)
        h.update(self.height)
        h.update(json.dumps(self.palette).encode())
        return h.hexdigest()

    def wire(self) -> dict:
        """The terrain as sent to Godot once: zlib + base64 layers and a palette."""
        def enc(b: bytes) -> str:
            return b64encode(zlib.compress(bytes(b), 6)).decode()

        d = defs()["terrains"]
        return {
            "w": self.w, "h": self.h, "palette": self.palette,
            "palette_class": [d[n]["is"] for n in self.palette],
            "terrain": enc(self.terrain), "height": enc(self.height), "cls": enc(self.cls),
            "build": enc(self.build), "res_kind": enc(self.res_kind), "res_amt": enc(self.res_amt),
            "static_hash": self.static_hash(), "starts": [list(s) for s in self.starts], "meta": self.meta,
        }

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for t in self.terrain:
            counts[self.palette[t]] = counts.get(self.palette[t], 0) + 1
        cls_counts = {}
        names = ("arable", "mineable", "walkable", "water", "unwalkable", "unreachable")
        for c in self.cls:
            cls_counts[names[c]] = cls_counts.get(names[c], 0) + 1
        res: dict[str, int] = {}
        for k, a in zip(self.res_kind, self.res_amt):
            if k:
                res[RES_NAMES[k]] = res.get(RES_NAMES[k], 0) + a
        return {"size": [self.w, self.h], "terrain": counts, "classes": cls_counts, "resources": res,
                "water_components": len(self.comp_size), "largest_water": max(self.comp_size.values(), default=0),
                "static_hash": self.static_hash()}
