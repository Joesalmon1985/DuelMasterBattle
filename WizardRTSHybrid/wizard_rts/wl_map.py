"""Read a Widelands map (.wmf directory) into a square-grid TerrainGrid.

Source: src/map_io/map_terrain_packet.cc (v2), map_heights_packet.cc, map_resources_packet.cc, map_player_position_packet.cc,
src/logic/map_objects/descriptions_compatibility_table.cc (legacy terrain names). GPL-2.0-or-later, Widelands Development Team;
each map keeps its own author (see docs/LICENSES.md).

This is a TRANSLATION, not a reproduction (DECISIONS D5): every Widelands node becomes one tile on a square grid with four
neighbours. A node has two terrain triangles in Widelands; here the tile takes the more restrictive of the two so coasts,
mountain feet and impassable ground stay closed. Trees and animals in the map's object file are not read; the world plants
forests from the terrain (fertility and affinity). Heights and resources are copied node for node.
"""

from __future__ import annotations

import math

import re
import struct
from pathlib import Path

from wizard_rts import terrain as T

MAPS = Path(__file__).resolve().parent / "data" / "maps"
LEGACY = {
    "wiese1": "summer_meadow1", "wiese2": "summer_meadow2", "wiese3": "summer_meadow3", "wiese4": "summer_meadow4",
    "steppe": "summer_steppe", "steppe_kahl": "summer_steppe_barren", "bergwiese": "summer_mountain_meadow",
    "berg1": "summer_mountain1", "berg2": "summer_mountain2", "berg3": "summer_mountain3", "berg4": "summer_mountain4",
    "sumpf": "summer_swamp", "strand": "summer_beach", "schnee": "summer_snow", "wasser": "summer_water",
    "ashes": "ashes1", "taiga": "winter_tundra", "tundra": "winter_taiga1", "tundra2": "winter_taiga2", "tundra3": "winter_taiga3",
    "mountain1": "wasteland_mountain1", "mountain2": "wasteland_mountain2", "mountain3": "wasteland_mountain3",
    "mountain4": "wasteland_mountain4", "ice_flows": "ice_floes", "ice_flows2": "ice_floes2", "beach": "desert_beach",
    "wasser_desert": "desert_water", "granit": "stones",
}
# more restrictive wins when a node's two triangles differ: impassable first, beach and meadow last
PRIORITY = (T.UNREACHABLE, T.WATER, T.UNWALKABLE, T.MINEABLE, T.WALKABLE, T.ARABLE)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.d, self.i = data, 0

    def u8(self) -> int:
        v = self.d[self.i]
        self.i += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v

    def cstr(self) -> str:
        j = self.d.index(b"\0", self.i)
        s = self.d[self.i:j].decode("utf-8", "replace")
        self.i = j + 1
        return s


def upsample(base: T.TerrainGrid, k: int = 2) -> T.TerrainGrid:
    """The same island at k times the tile count (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 3, D53): every base tile becomes a k x k block, the
    terrain of each new tile is the weighted majority of the four nearest base tiles (so coast and class boundaries round off instead of
    stepping), heights are interpolated, resources follow the nearest base tile. Nothing else of the map changes; starts scale with it."""
    w, h = base.w * k, base.h * k
    g = T.TerrainGrid(w, h, list(base.palette))
    bw, bh = base.w, base.h
    for y in range(h):
        fy = (y + 0.5) / k - 0.5
        y0 = max(0, min(bh - 1, int(math.floor(fy))))
        y1 = min(bh - 1, y0 + 1)
        ty = min(1.0, max(0.0, fy - y0))
        for x in range(w):
            fx = (x + 0.5) / k - 0.5
            x0 = max(0, min(bw - 1, int(math.floor(fx))))
            x1 = min(bw - 1, x0 + 1)
            tx = min(1.0, max(0.0, fx - x0))
            weights = {}
            hsum = 0.0
            for (bx, by, wgt) in ((x0, y0, (1 - tx) * (1 - ty)), (x1, y0, tx * (1 - ty)), (x0, y1, (1 - tx) * ty), (x1, y1, tx * ty)):
                i = by * bw + bx
                t = base.terrain[i]
                weights[t] = weights.get(t, 0.0) + wgt
                hsum += base.height[i] * wgt
            best = max(weights.items(), key=lambda kv: (round(kv[1], 6), -kv[0]))[0]
            j = y * w + x
            g.terrain[j] = best
            g.height[j] = int(round(hsum))
            ni = int(round(fy)) * bw + int(round(fx))
            ni = max(0, min(bw * bh - 1, ni))
            g.res_kind[j] = base.res_kind[ni]
            g.res_amt[j] = base.res_amt[ni]
            g.res_init[j] = base.res_init[ni]
    g.compute()
    # a resource only where its class still allows it after the smoothing
    ok_class = {T.RES_CODE[n]: c for n, c in (("coal", T.MINEABLE), ("iron", T.MINEABLE), ("gold", T.MINEABLE), ("stones", T.MINEABLE), ("fish", T.WATER), ("water", T.ARABLE)) if n in T.RES_CODE}
    for j in range(w * h):
        rk = g.res_kind[j]
        if rk and ok_class.get(rk) is not None and g.cls[j] != ok_class[rk]:
            g.res_kind[j] = g.res_amt[j] = g.res_init[j] = 0
    g.starts = [(sx * k + k // 2, sy * k + k // 2) for sx, sy in base.starts]
    g.meta = dict(base.meta)
    g.meta.update({"map": f"{base.meta.get('map', '')}@{k}x", "base_map": base.meta.get("map", ""), "resampled": k,
                   "capitals": [[sx * k + k // 2, sy * k + k // 2] for sx, sy in base.starts], "all_starts": [[sx * k + k // 2, sy * k + k // 2] for sx, sy in base.meta.get("all_starts", [])],
                   "translation": base.meta.get("translation", "") + f"; resampled x{k} with weighted-majority terrain and interpolated heights (god_world embedding @2x)"})
    return g


def _ini(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*_?"?(.*?)"?\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def available() -> list[str]:
    return sorted(p.name[:-4] for p in MAPS.glob("*.wmf"))


def _terrain_name(raw: str, defs: dict) -> str:
    for cand in (raw, LEGACY.get(raw, ""), "summer_" + raw, "desert_" + raw):
        if cand and cand in defs:
            return cand
    raise ValueError(f"unknown Widelands terrain {raw!r}")


def load(name: str, players: int = 6) -> T.TerrainGrid:
    if name.endswith("@2x"):
        return upsample(load(name[:-3], players), 2)
    root = MAPS / f"{name}.wmf"
    if not root.is_dir():
        raise FileNotFoundError(f"no Widelands map {name}; available: {available()}")
    el = _ini((root / "elemental").read_text(encoding="utf-8", errors="replace"))
    w, h = int(el["map_w"]), int(el["map_h"])
    defs = T.defs()["terrains"]
    classes = {n: T.CLASS_CODE[d["is"]] for n, d in defs.items()}
    # terrain: version 2, per node (right, down) triangles as (u16 index, name when first seen)
    r = _Reader((root / "binary" / "terrain").read_bytes())
    version = r.u16()
    seen: dict[int, str] = {}
    cells: list[tuple[str, str]] = []
    if version == 1:  # a name table first, then one byte per triangle
        for _ in range(r.u16()):
            idx = r.u16()
            seen[idx] = _terrain_name(r.cstr(), defs)
        for _ in range(w * h):
            tr, td = r.u8(), r.u8()
            cells.append((seen[tr], seen[td]))
    elif version == 2:  # u16 index per triangle, the name written when the index first appears
        for _ in range(w * h):
            pair = []
            for _tri in range(2):
                idx = r.u16()
                if idx not in seen:
                    seen[idx] = _terrain_name(r.cstr(), defs)
                pair.append(seen[idx])
            cells.append((pair[0], pair[1]))
    else:
        raise ValueError(f"terrain packet version {version} is not read")
    g = T.TerrainGrid(w, h, ["summer_water"])
    pal: dict[str, int] = {"summer_water": 0}

    def index_of(n: str) -> int:
        if n not in pal:
            if len(pal) >= 250:
                raise ValueError("too many terrains")
            pal[n] = len(pal)
            g.palette.append(n)
        return pal[n]

    for i, (a, b) in enumerate(cells):
        ca, cb = classes[a], classes[b]
        pick = a if PRIORITY.index(ca) <= PRIORITY.index(cb) else b
        g.terrain[i] = index_of(pick)
    hp = _Reader((root / "binary" / "heights").read_bytes())
    hver = hp.u16()
    if hver >= 2:
        hp.u8()
    for i in range(w * h):
        g.height[i] = hp.u8()
    g.compute()
    # resources: version 1 stores u8 id, u8 amount, u8 start amount per node
    rr = _Reader((root / "binary" / "resource").read_bytes())
    rver = rr.u16()
    nres = rr.u32() if rver >= 2 else rr.u16()
    names = {}
    for _ in range(nres):
        rid = rr.u32() if rver >= 2 else rr.u16()
        raw = rr.cstr().replace("resource_", "")
        names[rid] = LEGACY.get(raw, raw)
    ok_class = {"coal": T.MINEABLE, "iron": T.MINEABLE, "gold": T.MINEABLE, "stones": T.MINEABLE, "fish": T.WATER, "water": T.ARABLE}
    for i in range(w * h):
        rid = rr.u32() if rver >= 2 else rr.u8()
        amount = rr.u32() if rver >= 2 else rr.u8()
        start = rr.u32() if rver >= 2 else rr.u8()
        res = names.get(rid)
        if res in ok_class and g.cls[i] == ok_class[res] and start > 0:
            g.res_kind[i] = T.RES_CODE[res]
            g.res_amt[i] = min(255, amount)
            g.res_init[i] = min(255, max(start, amount))
    # fish and water the map did not state: Widelands default resources of the terrain
    for i in range(w * h):
        if not g.res_kind[i]:
            t = defs[g.palette[g.terrain[i]]]
            if t["default_resource"] in ("fish", "water") and g.cls[i] in (T.WATER, T.ARABLE):
                g.res_kind[i] = T.RES_CODE[t["default_resource"]]
                g.res_amt[i] = g.res_init[i] = int(t["default_amount"]) or 5
    pp = _ini((root / "player_position").read_text(encoding="utf-8", errors="replace"))
    starts = []
    for k in range(1, int(el.get("nr_players", "0")) + 1):
        if f"player_{k}" in pp:
            x, y = (int(v) for v in pp[f"player_{k}"].split())
            starts.append((x, y))
    if len(starts) < players:
        raise ValueError(f"{name} has {len(starts)} start positions, {players} needed")
    # six of the start positions, spread evenly when the map has more (a fairness choice of ours)
    pick = [starts[round(i * len(starts) / players)] for i in range(players)] if len(starts) > players else starts[:players]
    g.starts = pick
    g.meta.update({
        "generator": "widelands_map", "map": name, "name": el.get("name", name), "author": el.get("author", ""),
        "descr": el.get("descr", ""), "source": f"widelands/widelands {T.defs()['source']['commit'][:8]} data/maps/{name}.wmf",
        "capitals": [list(s) for s in pick], "all_starts": [list(s) for s in starts], "homes": [],
        "translation": "square grid, four neighbours, more restrictive triangle per node (docs/DECISIONS.md D5)",
    })
    return g
