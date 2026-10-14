"""H2 (roads and links), H3 (production), H6 (drafting), H8 (diplomacy), H9 (management) candidates (neuro/candidates.py)."""
from __future__ import annotations

from typing import Any

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro.cand_base import Candidate, feat
from wizard_rts import construction as con
from wizard_rts import diplomacy, history, tech, territory, wl_defs

MAX_ROAD_CANDIDATES = 24
MAX_ROAD_REACH = 40
MAX_LINK_REACH = 50  # tiles between settlement centres; the road builder gives up beyond a 70-step path, so longer links would only be refused
MAX_MANAGE = 48
MAX_BELT_CANDIDATES = 3
ROAD_CHECKS_PER_DECISION = 6  # road path searches per decision (about 2 ms each); the result is cached for ROAD_CACHE_S
ROAD_CACHE_S = 180
BELT_REACH = 14
BELT_REFRESH_S = 120


class EconomyCandidates:
    world: Any
    faction: str
    observer: Any
    excluded: dict

    # ------------------------------------------------------------------------------------------------------------------------ H2
    def road(self, obs: Any) -> list[Candidate]:
        """Roads: each building without a road to the nearest building that has one (or a command centre); links between settlements that are not connected;
        belts from a machine to a warehouse in the Modern era. Both endpoints are the faction's own; the road's route is found by the simulator."""
        fr = obs.extra["frame"]
        w = fr.world
        idx = {b["id"]: i for i, b in enumerate(fr.own_b)}
        connected = [b for b in fr.own_b if (b["id"] in fr.road_ids or b.get("command_center")) and not b.get("destroyed")]
        out: list[Candidate] = []
        ks, col = fr.ks, fr.col
        if connected:
            cxy = np.array([[b["tx"], b["ty"]] for b in connected], dtype=np.float64)
            todo = [b for b in fr.own_b if b["id"] not in fr.road_ids and not b.get("command_center")]
            rows = []
            for b in todo:
                d = np.abs(cxy - (b["tx"], b["ty"])).max(axis=1)
                j = int(d.argmin())
                if d[j] <= MAX_ROAD_REACH and not any(n == connected[j]["id"] for n, _r in w.adjacency.get(b["id"], [])):
                    rows.append((int(d[j]), b["id"], b, connected[j]))
            budget = ROAD_CHECKS_PER_DECISION
            cache = self.__dict__.setdefault("_road_cache", {})
            for d, _id, b, t in sorted(rows, key=lambda r: (r[0], r[1]))[:MAX_ROAD_CANDIDATES]:
                hit = cache.get((b["id"], t["id"]))
                if hit is None or fr.game_s - hit[0] > ROAD_CACHE_S:
                    if budget <= 0:
                        continue  # not checked yet: offered at a later decision
                    budget -= 1
                    path = con._road_path(w, (b["tx"], b["ty"]), (t["tx"], t["ty"]), (b["id"], t["id"]), 70)  # the search build_road itself runs
                    hit = cache[(b["id"], t["id"])] = (fr.game_s, path is not None and len(path) >= 2)
                if not hit[1]:
                    continue
                f = feat("H2", path_estimate=d / 50.0, a_is_store=ks[idx_kind(fr, b), col["is_centre"]], b_is_store=ks[idx_kind(fr, t), col["is_centre"]])
                out.append(Candidate("H2", {"op": "road", "a": b["id"], "b": t["id"]}, f, ("H2", "road", b["id"], t["id"]), {"a": idx[b["id"]], "b": idx.get(t["id"], -1)}))
        cc = fr.standing
        for i in range(len(cc)):
            for j in range(i + 1, len(cc)):
                a, b = fr.srec[cc[i]["id"]]["centre"], fr.srec[cc[j]["id"]]["centre"]
                d = territory.cheb((cc[i]["tx"], cc[i]["ty"]), (cc[j]["tx"], cc[j]["ty"]))
                if d <= MAX_LINK_REACH and not history._connected(w, a, b):
                    f = feat("H2", is_settlement_link=1.0, path_estimate=d / 50.0, a_is_store=1.0, b_is_store=1.0)
                    out.append(Candidate("H2", {"op": "road", "a": a, "b": b}, f, ("H2", "link", a, b), {"a": idx.get(a, -1), "b": idx.get(b, -1)}))
        out += self._belts(obs, fr)
        out += self.extra_links(obs, fr)
        return out

    def _belts(self, obs: Any, fr: Any) -> list[Candidate]:
        """Belt runs from a Mindustry machine to the nearest own warehouse, found with the fixture router (an A* over free ground that keeps clear of other machines)
        and checked with the belt rules. Cached per machine for BELT_REFRESH_S seconds because routing is the expensive part."""
        w = fr.world
        machines = [b for b in fr.own_b if b.get("mdy") is not None and not b.get("constructing") and b["mdy"].get("role") in ("drill", "crafter", "separator", "factory")]
        if not machines:
            return []
        from wizard_rts.industry import commands as C
        from wizard_rts.industry import fixture as IF
        from wizard_rts.industry import sim as ISIM

        cache = self.__dict__.setdefault("_belt_cache", {})
        warehouses = [b for b in fr.own_b if b["kind"] == "warehouse" and not b.get("constructing")]
        out: list[Candidate] = []
        idx = {b["id"]: i for i, b in enumerate(fr.own_b)}
        tried = 0
        lines = {(t[0], t[1]) for b in fr.own_b if (b.get("mdy") or {}).get("role") in ISIM.LINE_ROLES for t in (b.get("ground_footprint") or [])}
        for m in sorted(machines, key=lambda b: b["id"]):
            if len(out) >= MAX_BELT_CANDIDATES:
                break
            hit = cache.get(m["id"])
            if hit is not None and fr.game_s - hit[0] < BELT_REFRESH_S:
                route = hit[1]
            else:
                route = None
                near = min(warehouses, key=lambda b: territory.cheb((b["tx"], b["ty"]), (m["tx"], m["ty"])), default=None)
                src = [tuple(p) for p in ISIM.footprint(m)]
                if near is not None and tried < 2 and territory.cheb((near["tx"], near["ty"]), (m["tx"], m["ty"])) <= BELT_REACH and not (set(IF._ring(w, src)) & lines):
                    tried += 1
                    dst = [tuple(p) for p in territory.footprint((near["tx"], near["ty"]), near["definition"])]
                    path, end_dir = IF._route(w, fr.me, src, dst, set(), set())
                    if path is not None and C.check_belt(w, fr.me, path) is None:
                        route = ([list(p) for p in path], end_dir, near["id"])
                cache[m["id"]] = (fr.game_s, route)
            if route is not None:
                tiles, end_dir, wid = route
                f = feat("H2", is_belt=1.0, path_estimate=len(tiles) / 50.0, b_is_store=1.0)
                out.append(Candidate("H2", {"op": "belt", "tiles": tiles, "end_dir": end_dir, "kind": "mdy:conveyor"}, f, ("H2", "belt", m["id"], tuple(map(tuple, tiles[:1]))),
                                     {"a": idx[m["id"]], "b": idx.get(wid, -1)}))
        return out

    # ------------------------------------------------------------------------------------------------------------------------ H3
    def produce(self, obs: Any) -> list[Candidate]:
        """(factory, unit kind) pairs the faction may queue now: the building is operational with room in its queue, the unit's recipe exists there, its card is
        held and the recipe's prerequisites are met (the same tests `queue_unit` applies), and the faction's stock covers the unit's cost."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        stock = self.observer.own_stock(fr)
        out: list[Candidate] = []
        us = F.unit_static()
        for i, b in enumerate(fr.own_b):
            if b["kind"] not in con.RECIPES or b.get("constructing") or not b.get("operational", True) or len(b.get("queue", ())) >= 5:
                continue
            for unit in sorted(con.RECIPES[b["kind"]]):
                recipe = con.recipe_for(w, b, unit)
                if recipe is None or not self.unit_ok(unit):
                    continue
                if recipe.get("requires") and tech.gated(w) and con._openra_content.prerequisites_met(w, me, recipe.get("requires", [])):
                    continue
                if not all(stock.get(g, 0) >= n for g, n in recipe["cost"].items()):
                    continue
                row = fr.idx.get("unit:" + unit, 0)
                out.append(Candidate("H3", {"op": "queue", "building": b["id"], "unit": unit}, us[row].copy(), ("H3", b["id"], unit), {"factory": i, "kind_row": row}))
        return out

    # ------------------------------------------------------------------------------------------------------------------------ H6
    def draft(self, obs: Any) -> list[Candidate]:
        """One candidate per open offer."""
        return [Candidate("H6", {"op": "draft", "card": cid}, np.zeros(0, dtype=np.float32), ("H6", cid), {"card": k}) for k, cid in enumerate(obs.card_ids)]

    # ------------------------------------------------------------------------------------------------------------------------ H8
    def diplomacy(self, obs: Any) -> list[Candidate]:
        """For every other faction the observation has a slot for: propose a truce, a peace or an alliance (unless a better relation holds or an offer of ours is
        open), break a standing treaty; for every offer addressed to the faction: accept or decline."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        offers = sorted(w.__dict__.get("offers", {}).values(), key=lambda o: o["id"])
        n13 = {n: i for i, n in enumerate(S.N13_SLOT)}
        out: list[Candidate] = []
        totals_gap = float(obs.n10_raw[S.N10_RAW.index("vp_gap")])
        for slot, n in enumerate(obs.n13_factions):
            row = obs.n13_slots[slot]
            if row[n13["collapsed"]]:
                continue
            state = diplomacy.state_of(w, me, n)
            mine_open = any(o["from"] == me and o["to"] == n for o in offers)
            pressure = obs.n13_pressure
            rel = float(row[n13["their_strength"]]) - float(obs.n10_raw[S.N10_RAW.index("own_strength")])
            base = dict(pressure=pressure, relative_strength=rel, vp_gap=totals_gap)
            if not mine_open:
                for target in diplomacy.STATES[1:]:
                    if diplomacy.STATES.index(target) > diplomacy.STATES.index(state):
                        out.append(Candidate("H8", {"op": "propose", "to": n, "state": target}, feat("H8", **base, **{"a_propose_" + target: 1.0}), ("H8", "propose", n, target),
                                             {"slot": slot}))
            if state != "war":
                out.append(Candidate("H8", {"op": "break_treaty", "with": n}, feat("H8", **base, a_break=1.0), ("H8", "break", n), {"slot": slot}))
        for o in offers:
            if o["to"] != me or o["from"] not in obs.n13_factions:
                continue
            slot = obs.n13_factions.index(o["from"])
            left = max(0, int(o["expires_ms"]) - fr.now_ms) / 120000.0
            base = dict(pressure=obs.n13_pressure, offer_time_left=left, vp_gap=totals_gap)
            out.append(Candidate("H8", {"op": "respond", "offer": o["id"], "accept": True}, feat("H8", **base, a_accept=1.0), ("H8", "accept", o["id"]), {"slot": slot}))
            out.append(Candidate("H8", {"op": "respond", "offer": o["id"], "accept": False}, feat("H8", **base, a_decline=1.0), ("H8", "decline", o["id"]), {"slot": slot}))
        return out

    # ------------------------------------------------------------------------------------------------------------------------ H9
    def manage(self, obs: Any) -> list[Candidate]:
        """Per own building where the command is legal: enhance (Widelands in-place upgrade), upgrade (a mine or drill into advanced equipment), dismantle, demolish.
        Improvements come first, then the buildings that have stood idle longest, then the rest by id; at most MAX_MANAGE candidates."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        from wizard_rts.industry import registry as ind

        drills = [(k, ind.block(k)) for k in ind.kinds()]
        drills = [(k, s) for k, s in drills if s and s["role"] == "drill" and self.kind_ok(k)]
        improve: list[Candidate] = []
        plain: list[tuple[float, str, Candidate]] = []
        s_of = obs.b_settlement
        for i, b in enumerate(fr.own_b):
            if b.get("constructing") or b.get("destroyed") or not b.get("operational", True) or b.get("dismantle"):
                continue
            refs = {"building": i, "settlement": int(s_of[i]), "kind_row": fr.idx.get(b["kind"], 0)}
            static = fr.ks[refs["kind_row"]]
            if b["kind"].startswith("wl:"):
                up = (wl_defs.spec_for_kind(b["kind"]) or {}).get("enhances_to")
                if up and self.kind_ok(up):
                    improve.append(Candidate("H9", {"op": "enhance", "building": b["id"], "to": up}, feat("H9", a_enhance_upgrade=1.0), ("H9", "enhance", b["id"]), refs))
            for kind, spec in drills:
                if b["kind"] in spec["upgrade_from"]:
                    improve.append(Candidate("H9", {"op": "upgrade", "building": b["id"], "to": kind}, feat("H9", a_enhance_upgrade=1.0), ("H9", "upgrade", b["id"], kind), refs))
            if b["kind"] != "warehouse" and not b.get("command_center"):
                stall = (b.get("stall") or {}).get("at_ms")
                idle = (fr.now_ms - int(stall)) if stall and not b.get("working") else 0
                for op, fld in (("dismantle", "a_dismantle_convert"), ("demolish", "a_demolish")):
                    plain.append((-float(idle), b["id"] + op, Candidate("H9", {"op": op, "building": b["id"]}, feat("H9", **{fld: 1.0}), ("H9", op, b["id"]), refs)))
        plain.sort(key=lambda t: (t[0], t[1]))
        return (improve + [c for _i, _k, c in plain])[:MAX_MANAGE] + self.extra_management(obs, fr)[:MAX_MANAGE]


def idx_kind(fr: Any, b: dict) -> int:
    return fr.idx.get(b["kind"], 0)
