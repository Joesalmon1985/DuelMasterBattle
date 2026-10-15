"""H1 (build) and H4 (expand) candidates: everything that is about where something stands (neuro/candidates.py)."""
from __future__ import annotations

from typing import Any

import zlib

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro import vision
from neuro.cand_base import Candidate, feat
from wizard_rts import ai, construction as con, regions, tech, territory, wl_defs
from wizard_rts import terrain as T

N_KINDS_OFFERED = 24  # kinds offered per decision (a fixed, balanced rule: see kind_pool)
N_SITES_PER_CLASS = 12
SITE_SPACING = 3
PAIR_CAP = 96
VALIDATION_CAP = 220
RING_REFRESH_S = 150  # stale entries are dropped by the live check, so a ring may live through a couple of decisions
RING_RADIUS = 22
N_CATEGORIES = 11  # clinic, factory, military, six ware groups, store, other


class SiteCandidates:
    world: Any
    faction: str
    observer: Any
    _site_cache: dict
    _kind_sig: tuple | None
    _kinds: list[str]

    # ------------------------------------------------------------------------------------------------------------------------ the kinds
    def buildable_kinds(self, fr: Any) -> list[str]:
        """Kinds the faction's cards unlock and that can be placed as a new building (not an enhancement); recomputed when the card count or the era changes."""
        w, me = fr.world, fr.me
        sig = (len(w.tech.get(me, {}).get("cards", [])), int(getattr(w, "era_index", 0)))
        if sig != self._kind_sig:
            from wizard_rts.industry import registry as ind

            menu = con.full_menu()
            kinds = set(menu) | set(ind.kinds())
            self._kinds = sorted(k for k in kinds if (con.build_spec(k) or {}).get("size") != "water3" or True)
            self._kinds = [k for k in self._kinds if con.build_spec(k) is not None and not (con.build_spec(k) or {}).get("enhancement_of") and self.kind_ok(k)]
            self._kind_sig = sig
        return self._kinds

    @staticmethod
    def category(fr: Any, kind: str) -> int:
        row = fr.idx.get(kind, 0)
        c = fr.col
        r = fr.ks[row]
        if r[c["is_clinic"]]:
            return 0
        if r[c["is_factory"]]:
            return 1
        if r[c["is_military"]]:
            return 2
        prod = [r[c["produces_" + g]] for g in S.GROUP_NAMES]
        if max(prod) > 0:
            return 3 + int(np.argmax(prod))
        return 9 if r[c["is_centre"]] else 10

    def kind_pool(self, fr: Any, stock: dict[str, int]) -> list[str]:
        """The kinds offered this decision: unlocked and affordable from the faction's total stock, then N_KINDS_OFFERED chosen round-robin over the categories
        (clinic, factory, military, the six ware groups, store, other), cheapest first within a category. A fixed rule, so every kind of building stays reachable."""
        buckets: dict[int, list[tuple[int, str]]] = {}
        for k in self.buildable_kinds(fr):
            spec = con.build_spec(k)
            cost = spec["cost"]
            if all(stock.get(g, 0) >= n for g, n in cost.items()):
                buckets.setdefault(self.category(fr, k), []).append((sum(cost.values()), k))
        for b in buckets.values():
            b.sort()
        pool: list[str] = []
        depth = 0
        while len(pool) < N_KINDS_OFFERED and any(depth < len(b) for b in buckets.values()):
            for cat in sorted(buckets):
                if depth < len(buckets[cat]) and len(pool) < N_KINDS_OFFERED:
                    pool.append(buckets[cat][depth][1])
            depth += 1
        return pool

    # ------------------------------------------------------------------------------------------------------------------------ the sites
    def _grid(self, fr: Any) -> dict[str, Any]:
        """Per-minute numpy views of the terrain and of what stands on it (shared by every settlement's ring)."""
        key = fr.game_s // RING_REFRESH_S
        g = fr.scratch.get("grid")
        if g is not None:
            return g
        w, t = fr.world, fr.world.terrain
        cached = getattr(self, "_grid_cache", None)
        if cached is not None and cached[0] == (key, id(t)):
            fr.scratch["grid"] = cached[1]
            return cached[1]
        occ = np.zeros((t.h, t.w), dtype=bool)
        roads = np.zeros((t.h, t.w), dtype=bool)
        for p in w.blocked:
            if 0 <= p[0] < t.w and 0 <= p[1] < t.h:
                occ[p[1], p[0]] = True
        for p in w.tree_tiles:
            if 0 <= p[0] < t.w and 0 <= p[1] < t.h:
                occ[p[1], p[0]] = True
        for p in w.road_tile_set:
            if 0 <= p[0] < t.w and 0 <= p[1] < t.h:
                occ[p[1], p[0]] = True
                roads[p[1], p[0]] = True
        for p in w.reserved_tiles:
            if 0 <= p[0] < t.w and 0 <= p[1] < t.h:
                occ[p[1], p[0]] = True
        g = {"build": np.frombuffer(t.build, dtype=np.uint8).reshape(t.h, t.w), "occ": occ, "roads": roads,
             "cls": np.frombuffer(t.cls, dtype=np.uint8).reshape(t.h, t.w), "res_kind": np.frombuffer(t.res_kind, dtype=np.uint8).reshape(t.h, t.w),
             "res_amt": np.frombuffer(t.res_amt, dtype=np.uint8 if len(t.res_amt) == t.w * t.h else np.uint16).reshape(t.h, t.w)}
        self._grid_cache = ((key, id(t)), g)
        fr.scratch["grid"] = g
        return g

    def _site_vector(self, fr: Any, tile: tuple[int, int], cc: dict, g: dict[str, Any]) -> np.ndarray:
        """The 11 static site fields (everything but the region's cube count): distance, trees, arable, deposit one-hot (none, coal, iron, gold, stone) and amount, water, frontier."""
        t = fr.world.terrain
        x, y = tile
        d = max(abs(x - cc["tx"]), abs(y - cc["ty"]))
        trees = sum(1 for dy in range(-3, 4) for dx in range(-3, 4) if (x + dx, y + dy) in fr.world.tree_tiles)
        y0, y1, x0, x1 = max(0, y - 2), min(t.h, y + 3), max(0, x - 2), min(t.w, x + 3)
        arable = int((g["cls"][y0:y1, x0:x1] == 0).sum())
        ry0, ry1, rx0, rx1 = max(0, y - 4), min(t.h, y + 5), max(0, x - 4), min(t.w, x + 5)
        kinds_w, amt_w = g["res_kind"][ry0:ry1, rx0:rx1], g["res_amt"][ry0:ry1, rx0:rx1].astype(np.int64)
        amounts = [int(amt_w[kinds_w == T.RES_CODE[r]].sum()) for r in ("coal", "iron", "gold", "stones")]
        best = int(np.argmax(amounts)) if max(amounts) > 0 else -1
        wy0, wy1, wx0, wx1 = max(0, y - 3), min(t.h, y + 4), max(0, x - 3), min(t.w, x + 4)
        water = bool((g["cls"][wy0:wy1, wx0:wx1] == T.WATER).any())
        radius = territory.radius_of(cc)
        v = np.zeros(11, dtype=np.float32)
        v[0], v[1], v[2] = d / 34.0, trees / 20.0, arable / 10.0
        v[3 + (best + 1)] = 1.0
        v[8] = amounts[best] / 1000.0 if best >= 0 else 0.0
        v[9], v[10] = float(water), float(d > radius - 6)
        return v

    @staticmethod
    def ring_ttl(settlement_centre: str) -> int:
        """Ring caches live RING_REFRESH_S to RING_REFRESH_S + 80 game seconds, a fixed offset per settlement, so they are not all rebuilt in the same decision."""
        return RING_REFRESH_S + 20 * (zlib.crc32(settlement_centre.encode()) % 5)

    def ring_sites(self, fr: Any, cc: dict, cls: str) -> list[tuple[tuple[int, int], np.ndarray]]:
        """Up to N_SITES_PER_CLASS candidate tiles of one size class around a settlement centre, with their site vectors, cached for RING_REFRESH_S game seconds.
        A site must satisfy the terrain's build capability for the class, lie in the centre's build area, and be free of trees, roads, buildings and reservations;
        sites are taken nearest first (a site beside a road counts two tiles nearer) and at least SITE_SPACING apart. Stale entries are dropped by the live check."""
        key = (cc["id"], cls)
        hit = self._site_cache.get(key)
        if hit is not None and fr.game_s - hit[0] < self.ring_ttl(cc["id"]):
            return hit[1]
        t = fr.world.terrain
        out: list[tuple[tuple[int, int], np.ndarray]] = []
        if t is not None:
            g = self._grid(fr)
            R = min(territory.radius_of(cc), RING_RADIUS)
            x0, x1, y0, y1 = max(0, cc["tx"] - R), min(t.w, cc["tx"] + R + 1), max(0, cc["ty"] - R), min(t.h, cc["ty"] + R + 1)
            win = g["build"][y0:y1, x0:x1]
            base = win & 7
            if cls == "port":
                ok = (win & T.B_PORT) != 0
            elif cls == "mine":
                ok = base == T.B_MINE
            elif cls == "deposit":
                ok = (g["res_amt"][y0:y1, x0:x1] > 0) & (base >= T.B_SMALL) & (base <= T.B_BIG)
            else:
                ok = (base >= T.SIZE_CODE[cls]) & (base <= T.B_BIG)
            ok = ok & ~g["occ"][y0:y1, x0:x1]
            ys, xs = np.nonzero(ok)
            if len(xs):
                gx, gy = xs + x0, ys + y0
                dist = np.maximum(np.abs(gx - cc["tx"]), np.abs(gy - cc["ty"]))
                near_road = np.zeros(len(xs), dtype=bool)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
                    px, py = np.clip(gx + dx, 0, t.w - 1), np.clip(gy + dy, 0, t.h - 1)
                    near_road |= g["roads"][py, px]
                order = np.lexsort((gx, gy, dist - 2 * near_road))
                picked: list[tuple[int, int]] = []
                for i in order:
                    tile = (int(gx[i]), int(gy[i]))
                    if dist[i] >= 3 and all(max(abs(tile[0] - p[0]), abs(tile[1] - p[1])) >= SITE_SPACING for p in picked):
                        picked.append(tile)
                        if len(picked) == N_SITES_PER_CLASS:
                            break
                out = [(p, None) for p in picked]  # the site vector is computed when a site is offered (site_vec)
        self._site_cache[key] = (fr.game_s, out)
        return out

    def site_vec(self, fr: Any, cc: dict, tile: tuple[int, int]) -> np.ndarray:
        """The 11 static site fields of a site, computed once per (settlement, tile) while the ring cache lives."""
        cache = self.__dict__.setdefault("_vec_cache", {})
        key = (cc["id"], tile)
        hit = cache.get(key)
        if hit is None or fr.game_s - hit[0] > 600:
            hit = cache[key] = (fr.game_s, self._site_vector(fr, tile, cc, self._grid(fr)))
        return hit[1]

    def naval_sites(self, fr: Any, cc: dict) -> list[tuple[tuple[int, int], np.ndarray]]:
        key = (cc["id"], "water3")
        hit = self._site_cache.get(key)
        if hit is not None and fr.game_s - hit[0] < 4 * self.ring_ttl(cc["id"]):  # the shore does not move: this search is the dearest of the lot
            return hit[1]
        site = ai._naval_site(fr.world, fr.me, cc)
        out = []
        if site is not None:
            out = [(tuple(site), None)]
        self._site_cache[key] = (fr.game_s, out)
        return out

    def is_plain(self, kind: str, spec: dict) -> bool:
        """A kind whose placement is the generic one (a small, medium or big site with no extra footprint, no deposit, rocks or fish requirement): its legality is then
        decided by the same few tests `check_placement` makes, which `quick_check` repeats without the per-call overhead. Cached per kind."""
        cache = self.__dict__.setdefault("_plain_cache", {})
        if kind not in cache:
            plain = (not kind.startswith("mdy:") and kind not in con.GROUND_FOOTPRINT and spec.get("size") != "water3" and con.site_size(kind, spec) in ("small", "medium", "big")
                     and not spec.get("enhancement_of"))
            if plain:
                spec_w = wl_defs.spec_for_kind(kind)
                for role in set((spec_w or {}).get("worker_for_program", {}).values()):
                    for steps in (wl_defs.worker_programs(role) or {}).values():
                        plain = plain and not any(cmd == "findspace" and args.get("resource") == "fish" for cmd, args in steps)
                plain = plain and not any(cmd == "mine" or (cmd == "findobject" and args.get("attrib") == "rocks") for cmd, args in con._program_steps(kind))
            cache[kind] = plain
        return cache[kind]

    def placement_ok(self, fr: Any, kind: str, tile: tuple[int, int]) -> bool:
        """`check_placement` for a kind with special rules (mines, rocks, fish, extra footprint, Mindustry machines, ports, docks): the verdict is cached for a minute and
        trusted only while the tile is still free, because the full check is the expensive part of a decision."""
        w = fr.world
        cache = self.__dict__.setdefault("_placement_cache", {})
        hit = cache.get((kind, tile))
        free = not (tile in w.blocked or tile in w.tree_tiles or tile in w.road_tile_set or tile in w.reserved_tiles
                    or tile in fr.scratch.setdefault("unit_tiles", {(u["tx"], u["ty"]) for u in w.units.values() if u.get("alive", True)}))
        if hit is not None and fr.game_s - hit[0] < 150 and (free or not hit[1]):
            return hit[1] and free
        ok = con.check_placement(w, fr.me, kind, tile[0], tile[1])[0] is None
        cache[(kind, tile)] = (fr.game_s, ok)
        return ok

    def quick_check(self, fr: Any, kind: str, spec: dict, tile: tuple[int, int]) -> bool:
        """`check_placement` for a plain kind: prerequisites, build area, free tile, no unit on it, terrain capability. The kind is already unlocked (it is in the pool)."""
        w = fr.world
        if spec.get("requires") and tech.gated(w):
            memo = fr.scratch.setdefault("prereq", {})
            req = tuple(spec["requires"])
            if req not in memo:
                memo[req] = con._openra_content.prerequisites_met(w, fr.me, list(req))
            if memo[req]:
                return False
        if tile in w.blocked or tile in w.tree_tiles or tile in w.road_tile_set or tile in w.reserved_tiles or tile in fr.scratch.setdefault("unit_tiles", {(u["tx"], u["ty"]) for u in w.units.values() if u.get("alive", True)}):
            return False
        if not territory.in_territory(w, fr.me, tile):
            return False
        return w.terrain.can_build(tile[0], tile[1], con.site_size(kind, spec)) and not w.terrain.is_water(*tile)

    @staticmethod
    def site_class(kind: str, spec: dict) -> str:
        if spec.get("size") == "water3":
            return "water3"
        if kind.startswith("mdy:"):
            from wizard_rts.industry import registry as ind

            return "deposit" if (ind.block(kind) or {}).get("role") == "drill" else "small"
        return con.site_size(kind, spec)

    # ------------------------------------------------------------------------------------------------------------------------ H1
    def build(self, obs: Any) -> list[Candidate]:
        """(kind, site) pairs: up to N_KINDS_OFFERED kinds (balanced over categories) x the sites of each settlement, nearest first; at most PAIR_CAP pairs, each one
        checked with `check_placement` (placement, territory, card lock, terrain) before it is offered."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        if w.terrain is None or not fr.standing:
            return []
        stock = self.observer.own_stock(fr)
        kinds = self.kind_pool(fr, stock)
        cands: list[Candidate] = []
        seen: set[tuple] = set()
        validated = 0
        for rank in range(N_SITES_PER_CLASS):
            for j, cc in enumerate(fr.standing):
                for kind in kinds:
                    if len(cands) >= PAIR_CAP or validated >= VALIDATION_CAP:
                        return cands
                    spec = con.build_spec(kind)
                    cls = self.site_class(kind, spec)
                    sites = self.naval_sites(fr, cc) if cls == "water3" else self.ring_sites(fr, cc, cls)
                    if rank >= len(sites):
                        continue
                    tile, vec = sites[rank]
                    key = ("H1", kind, tile[0], tile[1])
                    if key in seen or key in self.excluded:
                        continue
                    seen.add(key)
                    validated += 1
                    if self.is_plain(kind, spec):
                        if not self.quick_check(fr, kind, spec, tile):
                            continue
                    elif not self.placement_ok(fr, kind, tile):
                        continue
                    site = (vec if vec is not None else self.site_vec(fr, cc, tile)).copy()
                    rg = regions.state(w)
                    cubes = self.observer.known_cubes(fr, rg.region_at(*tile)) if rg is not None else 0
                    row = fr.idx.get(kind, 0)
                    f = np.concatenate([fr.ks[row], site, np.array([cubes / 3.0], dtype=np.float32)]).astype(np.float32)
                    assert f.shape[0] == len(S.HEAD_RAW["H1"])
                    cands.append(Candidate("H1", {"op": "build", "kind": kind, "tx": tile[0], "ty": tile[1]}, f, key, {"kind_row": row, "settlement": j, "tile": tile}))
        return cands

    # ------------------------------------------------------------------------------------------------------------------------ H4
    def expand(self, obs: Any) -> list[Candidate]:
        """(founder unit, site) moves to the top-4 expansion sites of the observation, and `deploy` for a founder whose own tile passes the terrain rules."""
        fr = obs.extra["frame"]
        founders = [(i, u) for i, u in enumerate(fr.own_u) if territory.is_founder(u) and not u.get("deploying_ms")]
        if not founders:
            return []
        out: list[Candidate] = []
        n7 = {n: i for i, n in enumerate(S.N7_RAW)}
        for i, u in founders:
            if not u.get("order"):  # a founder already walking somewhere is left alone
                for k, tile in enumerate(obs.expansion_sites):
                    d = max(abs(u["tx"] - tile[0]), abs(u["ty"] - tile[1]))
                    f = feat("H4", distance=d / 200.0, fertility=obs.n7_raw[n7[f"cand{k}_fertility"]], threat=obs.n7_raw[n7[f"cand{k}_threat"]],
                             region_cubes=obs.n7_raw[n7[f"cand{k}_region_cubes"]])
                    out.append(Candidate("H4", {"op": "move", "units": [u["id"]], "tx": tile[0], "ty": tile[1]}, f, ("H4", "move", u["id"], tile[0], tile[1]),
                                         {"founder": i, "site": k, "tile": tile}))
            here = (int(u["tx"]), int(u["ty"]))
            if self.local_site_ok(fr, here) and self._clear_of_centres(fr, here):
                from neuro.obs_world import sq

                f = feat("H4", distance=0.0, fertility=self.observer.site_features(fr, 0, here)["fertility"], threat=self.observer.site_features(fr, 0, here)["threat"],
                         region_cubes=self.observer.site_features(fr, 0, here)["region_cubes"])
                out.append(Candidate("H4", {"op": "deploy", "unit": u["id"]}, f, ("H4", "deploy", u["id"], here[0], here[1]), {"founder": i, "site": -1, "tile": here}))
        return out

    def _clear_of_centres(self, fr: Any, tile: tuple[int, int]) -> bool:
        """Is the tile outside the build areas of the faction's own centres and of the enemy centres it remembers? (what the deploy rule would say, from knowledge)"""
        buffer = int(getattr(fr.world, "cc_buffer", territory.BUFFER))
        blockers = [((c["tx"], c["ty"]), territory.radius_of(c)) for c in fr.ccs] + [(tuple(m["tile"]), territory.HOME_RADIUS) for m in fr.known_b if m["kind"] == "warehouse"]
        return all(max(abs(tile[0] - c[0]), abs(tile[1] - c[1])) > territory.OUTPOST_RADIUS + r + buffer for c, r in blockers)

    def local_site_ok(self, fr: Any, tile: tuple[int, int]) -> bool:
        return self.observer.local_site_ok(fr, tile)
