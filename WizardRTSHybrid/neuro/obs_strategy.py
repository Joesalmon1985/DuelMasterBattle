"""Observer sections for the strategic networks N4-N8, N10, N12, N13, N14 (neuro/observer.py). Field lists and widths: neuro/schema.py."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro import vision
from neuro.obs_world import cheb_to, log5, sq
from wizard_rts import construction as con
from wizard_rts import diagnostics, diplomacy, history, regions, tech, territory, trade, vp
from wizard_rts.content import graph

CLIP = 5.0
RECON_COLS = (0.12, 0.3, 0.5, 0.7, 0.88)
RECON_ROWS = (0.2, 0.5, 0.8)
SITE_STEP = 6
SITE_FRONTIER = 70
SITE_SPREAD = 25
TERRITORY_CELL = 16


def named(names: tuple[str, ...], width: int, **values: float) -> np.ndarray:
    """A float32 vector of `width` with the given named fields set (a name outside `names`, or a wrong width, is an error)."""
    if len(names) != width:
        raise AssertionError(f"schema has {len(names)} names for width {width}")
    v = np.zeros(width, dtype=np.float32)
    pos = {n: i for i, n in enumerate(names)}
    for k, x in values.items():
        v[pos[k]] = x
    np.clip(v, -CLIP, CLIP, out=v)
    return v


def mean_group(wares: dict[str, float]) -> np.ndarray:
    out = np.zeros(S.N_GROUPS)
    for ware, n in wares.items():
        g = F.group_of(ware)
        if g is not None:
            out[g] += n
    return out


class StrategyMixin:
    world: Any
    faction: str

    # ------------------------------------------------------------------------------------------------------------------------ N4
    def own_stock(self, fr: Any) -> dict[str, int]:
        """Wares in the faction's own stores (warehouses, ports, markets): the sum over buildings of world.stocks."""
        total: dict[str, int] = {}
        for b in fr.own_b:
            if b["kind"] == "warehouse" or fr.ks[fr.idx.get(b["kind"], 0), fr.col["is_centre"]]:
                for g, n in fr.world.stocks.get(b["id"], {}).items():
                    total[g] = total.get(g, 0) + int(n)
        return total

    def n4_economy(self, fr: Any) -> tuple[np.ndarray, np.ndarray]:
        w, ks, col = fr.world, fr.ks, fr.col
        stock = self.own_stock(fr)
        fl = fr.fl.get("_f", np.zeros(12))
        stock_g = mean_group(stock)
        req_g = np.zeros(S.N_GROUPS)
        for b in fr.own_b:
            for ware, n in (w.recipe_requests.get(b["id"], {}) or {}).items():
                g = F.group_of(ware)
                if g is not None:
                    req_g[g] += n
        short_g = np.zeros(S.N_GROUPS)
        for (_bid, ware), n in fr.shortage_delta.items():
            g = F.group_of(ware)
            if g is not None:
                short_g[g] += n
        prod_n = np.zeros(S.N_GROUPS)
        cons_n = np.zeros(S.N_GROUPS)
        pcols = [col["produces_" + g] for g in S.GROUP_NAMES]
        ccols = [col["consumes_" + g] for g in S.GROUP_NAMES]
        for b in fr.own_b:
            if b.get("constructing") or not b.get("operational", True):
                continue
            row = ks[fr.idx.get(b["kind"], 0)]
            prod_n += row[pcols]
            cons_n += row[ccols]
        made, used = fl[:6], fl[6:]
        unlocked = self.unlocked_groups()
        vals = [log5(stock.get(k, 0)) for k in S.KEY_WARES]
        vals += [log5(x) for x in stock_g] + [log5(x) for x in made] + [log5(x) for x in used] + [log5(x) for x in req_g] + [log5(x) for x in short_g]
        vals += list(prod_n / 10.0)
        for g in range(S.N_GROUPS):  # chain coverage per group: (unlocked, consumers, deficit), the order of schema.N4_RAW
            pass
        chain = {}
        for g in range(S.N_GROUPS):
            chain[f"chain_unlocked_{S.GROUP_NAMES[g]}"] = float(unlocked[g])
            chain[f"chain_consumers_{S.GROUP_NAMES[g]}"] = cons_n[g] / 10.0
            chain[f"chain_deficit_{S.GROUP_NAMES[g]}"] = float(np.clip((used[g] - made[g]) / (used[g] + made[g] + 1.0), -1.0, 1.0))
        out = np.zeros(len(S.N4_RAW), dtype=np.float32)
        out[:len(vals)] = vals
        pos = {n: i for i, n in enumerate(S.N4_RAW)}
        for k, v in chain.items():
            out[pos[k]] = v
        np.clip(out, -CLIP, CLIP, out=out)
        return out, np.array([log5(x) for x in stock_g], dtype=np.float32)

    # ------------------------------------------------------------------------------------------------------------------------ N5
    def n5_logistics(self, fr: Any) -> np.ndarray:
        w, ks, col = fr.world, fr.ks, fr.col
        own_ids = {b["id"] for b in fr.own_b}
        roads = sum(1 for a, _c in w.road_edges.values() if a in own_ids)
        unconnected = sum(1 for b in fr.own_b if b["id"] not in fr.road_ids and not b.get("command_center") and not b.get("constructing"))
        carriers = [c for c in w.carriers.values() if c["faction_name"] == fr.me]
        requests = sum(sum((w.recipe_requests.get(i, {}) or {}).values()) for i in own_ids)
        busy = sum(1 for c in carriers if c.get("status") in ("moving", "carrying")) / len(carriers) if carriers else 0.0
        waiting = (sum(1 for c in carriers if c.get("status") == "idle") / len(carriers)) if (carriers and requests > 0) else 0.0
        key = ("stuck", fr.game_s)
        if key not in fr.scratch:
            fr.scratch[key] = sum(1 for r in diagnostics.stuck_report(w) if r["faction"] == fr.me)
        from wizard_rts.industry import registry as ind
        from wizard_rts.industry.sim import LINE_ROLES

        roles = {b["id"]: (ind.block(b["kind"]) or {}).get("role", "") for b in fr.own_b if b["kind"].startswith("mdy:")}
        lines = sum(1 for r in roles.values() if r in LINE_ROLES)
        machines = [b for b in fr.own_b if b.get("mdy") is not None and roles.get(b["id"], "") not in LINE_ROLES]
        unpowered = (sum(1 for b in machines if b["mdy"].get("state") == "no power") / len(machines)) if machines else 0.0
        waterways = sum(1 for r in w.__dict__.get("waterways", {}).values() if r.get("faction") == fr.me)
        ports = sum(1 for b in fr.own_b if (con.build_spec(b["kind"]) or {}).get("port"))
        return named(S.N5_RAW, 12, roads=roads / 100.0, unconnected=unconnected / 10.0, carriers_busy=busy, carriers_waiting=waiting, stuck=fr.scratch[key] / 10.0,
                     belt_tiles=lines / 100.0, machines_unpowered=unpowered, waterways=waterways / 5.0, ports=ports / 3.0, caravans=trade.active(w, fr.me) / 5.0,
                     carriers=len(carriers) / 100.0, requests_outstanding=requests / 50.0)

    # ------------------------------------------------------------------------------------------------------------------------ N6
    def n6_military(self, fr: Any, u_armed: np.ndarray, own_strength: float) -> np.ndarray:
        ks, col = fr.ks, fr.col
        armed = [u for u, a in zip(fr.own_u, u_armed) if a]
        d_cc = cheb_to(fr.e_xy, fr.cc_xy)
        known = fr.known_b
        kd = cheb_to(np.array([m["tile"] for m in known], dtype=np.float64).reshape(-1, 2), fr.cc_xy) if known else np.array([])
        idle = sum(1 for u in armed if u.get("status") in ("idle", "waiting_route") and not u.get("order"))
        engaged = sum(1 for u in armed if u.get("target") is not None or u.get("status") == "attacking")
        defences = sum(1 for b in fr.own_b if ks[fr.idx.get(b["kind"], 0), col["is_military"]] and b.get("operational") and not b.get("constructing"))
        factories = sum(1 for b in fr.own_b if ks[fr.idx.get(b["kind"], 0), col["is_factory"]] and b.get("operational") and not b.get("constructing"))
        queue = sum(len(b.get("queue", ())) for b in fr.own_b)
        fd = fr.fd
        return named(S.N6_RAW, 16, own_count=len(armed) / 30.0, own_strength=sq(own_strength), enemy_count=len(fr.eu) / 30.0, enemy_strength=sq(float(fr.e_str.sum())),
                     enemy_mean_distance=float(np.minimum(d_cc[np.isfinite(d_cc)], 40.0).mean() / 40.0) if len(fr.eu) and np.isfinite(d_cc).any() else 1.0,
                     known_buildings=len(known) / 20.0, known_nearest_distance=min(float(kd.min()), 200.0) / 200.0 if len(kd) and np.isfinite(kd.min()) else 1.0,
                     known_mean_hp=float(np.mean([m["hp"] for m in known])) if known else 0.0,
                     kills_minus_losses_units=(fd["kill_value"] - fd["loss_value"]) / 2000.0, kills_minus_losses_buildings=(fd["building_kills"] - fd["building_losses"]) / 10.0,
                     defences=defences / 10.0, factories=factories / 5.0, production_queue=queue / 10.0,
                     own_idle_fraction=idle / len(armed) if armed else 0.0, own_engaged_fraction=engaged / len(armed) if armed else 0.0,
                     enemy_buildings_near=float((kd <= 80).sum()) / 10.0 if len(kd) else 0.0)

    # ------------------------------------------------------------------------------------------------------------------------ N7
    def local_site_ok(self, fr: Any, tile: tuple[int, int]) -> bool:
        """The terrain rules of a founder's deploy (territory.deploy_check) without the rules that read other factions' centres or units. Static terrain is
        public map knowledge; what stands on a tile (trees, roads, buildings, reservations) is only checked where the faction can see now (a site is never
        dropped because of something it has not seen); the simulator still decides on deploy."""
        world = fr.world
        t = world.terrain
        if t is None:
            return False
        srcs = fr.scratch.setdefault("srcs", vision.sources(world, fr.me))
        fp = territory.footprint(tile, territory.SETTLER_DEFINITION)
        front = (tile[0], tile[1] + 1)
        for p in fp:
            if not world.tile_in_bounds(*p) or not t.ground(*p) or not t.can_build(p[0], p[1], "medium" if p == tile else "small"):
                return False
            if vision.visible(world, fr.me, p[0], p[1], srcs) and (p in world.tree_tiles or p in world.road_tile_set or p in world.reserved_tiles
                                                                   or (p in world.blocked and p != tile)):
                return False
        if not world.tile_in_bounds(*front) or not t.ground(*front):
            return False
        return not (vision.visible(world, fr.me, front[0], front[1], srcs) and front in world.blocked)

    def expansion_sites(self, fr: Any) -> list[tuple[int, tuple[int, int]]]:
        """The N_TOP_CANDIDATES founding sites offered to the controller, as [(distance to the frontier, tile)]: nearest first, at least SITE_SPREAD tiles
        apart (a fixed rule, not a score). A site must lie within SITE_FRONTIER of one of the faction's centres, on ground it has explored, clear of its own
        centres and of the enemy centres it remembers, and pass the local terrain rules; the lattice is filtered with numpy first and the terrain rules run lazily
        in order of distance until four sites are chosen. Cached for two game minutes while the set of centres and the memory are unchanged."""
        w = fr.world
        t = w.terrain
        sig = (tuple(c["id"] for c in fr.ccs), len(fr.known_b), fr.game_s // 120)
        hit = getattr(self, "_sites", None)
        if hit is not None and hit[0] == sig:
            return hit[1]
        chosen: list[tuple[int, tuple[int, int]]] = []
        if t is not None and len(fr.cc_xy):
            grid = getattr(self, "_grid", None)
            if grid is None or grid[0] != (t.w, t.h):
                ys, xs = np.mgrid[8:t.h - 8:SITE_STEP, 8:t.w - 8:SITE_STEP]
                self._grid = grid = ((t.w, t.h), np.stack([xs.ravel(), ys.ravel()], axis=1).astype(np.float64))
            pts = grid[1]
            d = np.abs(pts[:, None, :] - fr.cc_xy[None, :, :]).max(axis=2).min(axis=1)
            buffer = int(getattr(w, "cc_buffer", territory.BUFFER))
            blockers = [(c["tx"], c["ty"], territory.OUTPOST_RADIUS + territory.radius_of(c) + buffer) for c in fr.ccs]
            blockers += [(m["tile"][0], m["tile"][1], territory.OUTPOST_RADIUS + territory.HOME_RADIUS + buffer) for m in fr.known_b if m["kind"] == "warehouse"]
            ok = d <= SITE_FRONTIER
            for bx, by, br in blockers:
                ok &= np.maximum(np.abs(pts[:, 0] - bx), np.abs(pts[:, 1] - by)) > br
            order = np.flatnonzero(ok)
            order = order[np.lexsort((pts[order, 0], pts[order, 1], d[order]))]
            for i in order:
                tile = (int(pts[i, 0]), int(pts[i, 1]))
                if any(max(abs(tile[0] - c[1][0]), abs(tile[1] - c[1][1])) < SITE_SPREAD for c in chosen):
                    continue
                if vision.known(w, fr.me, tile[0], tile[1]) and self.local_site_ok(fr, tile):
                    chosen.append((int(d[i]), tile))
                    if len(chosen) == S.N_TOP_CANDIDATES:
                        break
        self._sites = (sig, chosen)
        return chosen

    def site_features(self, fr: Any, d: int, tile: tuple[int, int]) -> dict[str, float]:
        w = fr.world
        t = w.terrain
        rg = regions.state(w)
        near = fr.e_str[np.abs(fr.e_xy - tile).max(axis=1) <= 40].sum() if len(fr.e_xy) else 0.0
        return {"distance": min(d, 200) / 200.0, "fertility": history.fertility(w, tile, 20) / 400.0,
                "coal": t.total(tile[0], tile[1], 30, "coal") / 1000.0, "iron": t.total(tile[0], tile[1], 30, "iron") / 1000.0,
                "gold": t.total(tile[0], tile[1], 30, "gold") / 1000.0, "stone": t.total(tile[0], tile[1], 30, "stones") / 1000.0,
                "threat": sq(near), "region_cubes": self.known_cubes(fr, rg.region_at(*tile)) / 3.0 if rg is not None else 0.0}

    def n7_expansion(self, fr: Any, own_strength: float) -> tuple[np.ndarray, list[tuple[int, int]]]:
        w, me = fr.world, fr.me
        founders = [u for u in fr.own_u if territory.is_founder(u)]
        sites = self.expansion_sites(fr)
        vals: dict[str, float] = {"settlements": len(fr.standing) / 8.0, "founders": len(founders) / 3.0,
                                  "founder_cargo": (sum(1 for u in founders if u.get("cargo")) / len(founders)) if founders else 0.0}
        for i, (d, tile) in enumerate(sites):
            for k, v in self.site_features(fr, d, tile).items():
                vals[f"cand{i}_{k}"] = v
        wm = np.array([m["tile"] for m in fr.known_b if m["kind"] == "warehouse"], dtype=np.float64).reshape(-1, 2)
        near_enemy = (cheb_to(fr.cc_xy, wm) <= 80).sum() if len(wm) and len(fr.cc_xy) else 0
        t = w.terrain
        cells = set()
        for c in fr.ccs:
            r = territory.radius_of(c)
            for cy in range((c["ty"] - r) // TERRITORY_CELL, (c["ty"] + r) // TERRITORY_CELL + 1):
                for cx in range((c["tx"] - r) // TERRITORY_CELL, (c["tx"] + r) // TERRITORY_CELL + 1):
                    cells.add((cx, cy))
        total_cells = max(1, (t.w // TERRITORY_CELL) * (t.h // TERRITORY_CELL)) if t is not None else 1
        explored = len(vision.explored_of(w, me)) / max(1, (t.w // 4) * (t.h // 4)) if t is not None else 0.0
        unexplored = 1.0
        if t is not None and len(fr.cc_xy):
            pts = [(int(fx * t.w), int(fy * t.h)) for fy in RECON_ROWS for fx in RECON_COLS if not vision.known(w, me, int(fx * t.w), int(fy * t.h))]
            if pts:
                unexplored = min(float(cheb_to(np.array(pts, dtype=np.float64), fr.cc_xy).min()), 300.0) / 300.0
        settlers = sum(1 for b in fr.own_b for q in b.get("queue", ()) if q.get("unit") in ("settlers", "mcv"))
        afford = 0.0
        if tech.unit_allowed(w, me, "settlers"):
            for b in fr.own_b:
                if b["kind"] == "warehouse" and not b.get("constructing"):
                    try:
                        cost = con.recipe_for(w, b, "settlers")["cost"]
                    except Exception:  # a recipe the building cannot make
                        continue
                    if all(int(w.stocks.get(b["id"], {}).get(g, 0)) >= n for g, n in cost.items()):
                        afford = 1.0
                        break
        recent = sum(1 for r in w.dmb.settlements.values() if r["faction"] == me and fr.now_ms - int(r.get("founded_ms", 0)) < 30 * 60000)
        lost = sum(1 for r in w.dmb.settlements.values() if r["faction"] == me and r["state"] != "standing")
        vals.update(frontier_contact=float(near_enemy) / 5.0, map_fraction=len(cells) / total_cells, territory_cells=len(cells) / 100.0, explored_fraction=explored,
                    nearest_unexplored=unexplored, settlers_in_production=settlers / 3.0, can_afford_founder=afford, founded_recently=recent / 3.0, settlements_lost=lost / 3.0)
        return named(S.N7_RAW, 44, **vals), [t_ for _d, t_ in sites]

    # ------------------------------------------------------------------------------------------------------------------------ N8 and cards
    def cards(self, fr: Any) -> tuple[list[str], np.ndarray]:
        """The open offers (sorted by id) and their [k, 31] feature matrix: the 28 card features and three flags (affordable now, adds something new, era open)."""
        w, me = fr.world, fr.me
        offers = sorted(w.tech.get(me, {}).get("offers", []))
        if not offers:
            return [], np.zeros((0, S.N_CARD), dtype=np.float32)
        ents, lookup = graph.entities(), tech.lookup()
        stock = self.own_stock(fr)
        rows = []
        for cid in offers:
            c = lookup[cid]
            es = [ents[e] for e in c.get("entities", []) if e in ents]
            cost: dict[str, int] = {}
            for e in es:
                for g, n in (e.get("cost") or {}).items():
                    cost[g] = cost.get(g, 0) + n
            affordable = all(stock.get(g, 0) >= n for g, n in cost.items())
            adds_new = any(not tech.kind_allowed(w, me, e["id"]) for e in es if e["type"] == "building")
            era_open = c.get("era", 0) <= int(getattr(w, "era_index", 0))
            rows.append(np.concatenate([F.card_features(w, me, cid), np.array([affordable, adds_new, era_open], dtype=np.float32)]))
        a = np.stack(rows).astype(np.float32)
        np.clip(a, -CLIP, CLIP, out=a)
        return offers, a

    def n8_technology(self, fr: Any, n_offers: int) -> np.ndarray:
        w, me = fr.world, fr.me
        era = int(getattr(w, "era_index", 0))
        st = vp.era_state(w)
        totals = vp.totals(w)
        own_vp = vp.faction_vp(w, me)
        others = [v for k, v in totals.items() if k != me]
        bar = float(st.get("bar", vp.threshold(w))) if vp.draft_on(w) else float(vp.threshold(w))
        top = max(totals.values(), default=0)
        progress = (top if vp.draft_on(w) else vp.progress(w)) / max(1.0, bar)
        left = max(0, st["started_ms"] + int(getattr(w, "era_max_ms", vp.ERA_MAX_MS)) - fr.now_ms)
        ts = w.tech.get(me, {})
        lookup, ents = tech.lookup(), graph.entities()
        held = [lookup[c] for c in ts.get("cards", []) if c in lookup]
        counts = {"b": 0, "u": 0, "m": 0, "i": 0}
        for c in held:
            for e in c.get("entities", []):
                en = ents.get(e)
                if en is None:
                    continue
                counts["u" if en["type"] == "unit" else "b"] += 1
                row = fr.idx.get(e, 0)
                if row and (fr.ks[row, fr.col["is_military"]] or fr.ks[row, fr.col["is_factory"]]):
                    counts["m"] += 1
                if en["game"] == "mindustry":
                    counts["i"] += 1
        left_round = max(0, int(ts.get("expires_ms", 0)) - fr.now_ms) if n_offers else 0
        return named(S.N8_RAW, 18, **{f"era_{n}": float(era == i) for i, n in enumerate(("widelands", "openra", "historic", "modern"))},
                     era_progress=progress, minutes_to_stall=left / 60000.0 / 75.0, own_vp=own_vp / 10.0, max_other_vp=max(others, default=0) / 10.0,
                     rank=(1 + sum(1 for v in others if v > own_vp)) / 6.0, draft_round=int(ts.get("round", 0)) / 7.0, minutes_left_in_round=left_round / 60000.0 / 6.0,
                     cards_buildings=counts["b"] / 10.0, cards_units=counts["u"] / 10.0, cards_military=counts["m"] / 10.0, cards_industry=counts["i"] / 10.0,
                     offers=n_offers / 7.0, cards_total=len(held) / 40.0, drafts_lapsed=int(ts.get("lapsed", 0)) / 4.0)

    # ------------------------------------------------------------------------------------------------------------------------ N10
    def n10_war(self, fr: Any, own_strength: float) -> np.ndarray:
        by: dict[str, float] = {}
        for u, s in zip(fr.eu, fr.e_str):
            by[u["faction_name"]] = by.get(u["faction_name"], 0.0) + float(s)
        totals = vp.totals(fr.world)
        return named(S.N10_RAW, 3, strongest_enemy=sq(max(by.values(), default=0.0)), own_strength=sq(own_strength),
                     vp_gap=(max(totals.values(), default=0) - vp.faction_vp(fr.world, fr.me)) / 10.0)
