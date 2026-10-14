"""The rest of the HybridEnv command surface as candidates: abilities, focus orders, rally points, stop, power links, waterways, cancel, configure, convert
(neuro/candidates.py). Each is checked against the same preconditions the simulator applies, using only the faction's own knowledge.

COMMAND CODES. The head feature widths are fixed by the plan, so a command type is encoded in the existing flag fields; `refs["op"]` always names the op.
  H2 flags (is_settlement_link, is_belt, is_waterway): road 000, settlement link 100, belt 010, waterway 001, power link 110.
  H5 type flags (t_enemy_building, t_nest, t_defend, t_rally): attack-move on an enemy building 1000, on a nest 0100, defend 0010, rally 0001, stop (hold) 0000,
     focus `order` on an enemy building 1100, on a nest 0101, rally point of a factory 0001 with distance 0, ability on an enemy building (capture, infiltrate,
     c4) 1001, repair 0011, power strike 1010, board or unload 0110, lay mine 0111.
  H9 action flags (a_demolish, a_dismantle_convert, a_enhance_upgrade, a_other): demolish 1000, dismantle 0100, convert 0110, enhance/upgrade 0010,
     configure 0001, cancel a queue entry 1001.
M3 may add a learned op embedding to the head inputs; that would change the declared widths and is left to the owner (see the milestone report).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro.cand_base import Candidate, feat
from wizard_rts import construction as con
from wizard_rts import diplomacy, openra_abilities as A, tech, territory

MAX_EXTRA_PER_KIND = 4


def _near(a: dict, tile: tuple[int, int]) -> float:
    return math.hypot(a["tx"] - tile[0], a["ty"] - tile[1])


class ExtraCandidates:
    world: Any
    faction: str
    observer: Any

    # ------------------------------------------------------------------------------------------------------------------------ H2
    def extra_links(self, obs: Any, fr: Any) -> list[Candidate]:
        """Power links (a node and a powered block in laser range that are not linked yet) and waterways (two operational own ports)."""
        w = fr.world
        out: list[Candidate] = []
        idx = {b["id"]: i for i, b in enumerate(fr.own_b)}
        from wizard_rts.industry import registry as R
        from wizard_rts.industry import sim as ISIM

        nodes = [b for b in fr.own_b if b.get("mdy") is not None and not b.get("constructing") and (R.block(b["kind"]) or {}).get("role") == "node"]
        blocks = [b for b in fr.own_b if b.get("mdy") is not None and not b.get("constructing") and ISIM._powered_role(b)]
        st = ISIM.ind(w)
        for a in nodes[:6]:
            spec = R.block(a["kind"])
            links = st.links.get(a["id"], [])
            if len(links) >= spec["max_nodes"]:
                continue
            for t in blocks:
                if t["id"] in links or t["id"] == a["id"]:
                    continue
                from wizard_rts.industry.commands import _edge_distance

                if _edge_distance(a, t) <= spec["laser_range"]:
                    out.append(Candidate("H2", {"op": "link_power", "a": a["id"], "b": t["id"]}, feat("H2", is_settlement_link=1.0, is_belt=1.0, path_estimate=_edge_distance(a, t) / 50.0),
                                         ("H2", "power", a["id"], t["id"]), {"a": idx[a["id"]], "b": idx[t["id"]], "op": "link_power"}))
                    if len(out) >= MAX_EXTRA_PER_KIND:
                        return out
        shore = self._shore_buildings(fr)
        for i in range(len(shore)):
            for j in range(i + 1, len(shore)):
                a, b = shore[i], shore[j]
                d = territory.cheb((a["tx"], a["ty"]), (b["tx"], b["ty"]))
                if 3 <= d <= 16 and not any(n == b["id"] for n, _r in w.adjacency.get(a["id"], [])) and self._waterway_ok(w, fr.me, a["id"], b["id"], fr.game_s):
                    out.append(Candidate("H2", {"op": "waterway", "a": a["id"], "b": b["id"]}, feat("H2", is_waterway=1.0, path_estimate=d / 50.0), ("H2", "waterway", a["id"], b["id"]),
                                         {"a": idx[a["id"]], "b": idx[b["id"]], "op": "waterway"}))
                    if sum(1 for c in out if c.refs.get("op") == "waterway") >= MAX_EXTRA_PER_KIND:
                        return out
        return out

    def _shore_buildings(self, fr: Any) -> list[dict]:
        """Own finished buildings with shallow water within two tiles (a waterway joins two such buildings), cached per building for ten game minutes."""
        t = fr.world.terrain
        if t is None:
            return []
        cache = self.__dict__.setdefault("_shore_cache", {})
        out = []
        for b in fr.own_b:
            if b.get("constructing") or not b.get("operational", True):
                continue
            hit = cache.get(b["id"])
            if hit is None or fr.game_s - hit[0] > 600:
                near = any(t.is_shallow(b["tx"] + dx, b["ty"] + dy) for dx in range(-2, 3) for dy in range(-2, 3) if t.in_bounds(b["tx"] + dx, b["ty"] + dy))
                hit = cache[b["id"]] = (fr.game_s, near)
            if hit[1]:
                out.append(b)
        return out[:12]

    def _waterway_ok(self, w: Any, me: str, a: str, b: str, game_s: int) -> bool:
        """Could a waterway be built between these two ports? The planning search `build_waterway` runs, cached for three game minutes."""
        from wizard_rts import maritime

        cache = self.__dict__.setdefault("_waterway_cache", {})
        hit = cache.get((a, b))
        if hit is None or game_s - hit[0] > 180:
            hit = cache[(a, b)] = (game_s, maritime.plan_waterway(w, me, a, b)["status"] == "ok")
        return hit[1]

    # ------------------------------------------------------------------------------------------------------------------------ H5
    def extra_orders(self, obs: Any, fr: Any, squads: list[list[int]], enemy_b: list[dict]) -> list[Candidate]:
        """Focus orders, stop, rally points, and the unit abilities."""
        w, me = fr.world, fr.me
        out: list[Candidate] = []
        s2 = {n: i for i, n in enumerate(S.N2_RAW)}
        idx = {b["id"]: i for i, b in enumerate(fr.own_b)}
        by_def: dict[str, list[int]] = {}
        for i, u in enumerate(fr.own_u):
            by_def.setdefault(u.get("definition", ""), []).append(i)

        def tile_of(m: dict) -> tuple[int, int]:
            return tuple(m["tile"])

        def add(key: tuple, action: dict, unit_row: int | None, tile: tuple[int, int] | None, op: str, hp: float = 1.0, kind_row: int = 0, **fields: float) -> None:
            u = fr.own_u[unit_row] if unit_row is not None else None
            d = math.hypot(tile[0] - u["tx"], tile[1] - u["ty"]) if (u is not None and tile is not None) else 0.0
            row = np.zeros(len(S.N1_RAW), dtype=np.float32)
            row[S.N1_RAW.index("hp")] = hp
            out.append(Candidate("H5", action, feat("H5", distance=min(d, 200.0) / 200.0, force_ratio=1.0, **fields), key,
                                 {"squad": [unit_row] if unit_row is not None else [], "target_kind": kind_row, "target_n1": row, "target_b": -1, "tile": tile, "op": op}))

        # stop: a squad that still has orders stands where it is
        for rows in squads[:2]:
            if any(fr.own_u[r].get("order") for r in rows):
                ids = [fr.own_u[r]["id"] for r in rows]
                out.append(Candidate("H5", {"op": "stop", "units": ids}, feat("H5"), ("H5", "stop", ids[0], len(ids)),
                                     {"squad": list(rows), "target_kind": 0, "target_n1": np.zeros(len(S.N1_RAW), dtype=np.float32), "target_b": -1, "tile": None, "op": "stop"}))
        # focus order of the squad's lead unit on the nearest remembered enemy building or visible nest
        for rows in squads[:2]:
            lead = rows[0]
            cx, cy = fr.own_u[lead]["tx"], fr.own_u[lead]["ty"]
            near = sorted(enemy_b, key=lambda m: (math.hypot(m["tile"][0] - cx, m["tile"][1] - cy), m["id"]))[:2]
            for m in near:
                if math.hypot(m["tile"][0] - cx, m["tile"][1] - cy) <= 120:
                    add(("H5", "focus", fr.own_u[lead]["id"], m["id"]), {"op": "order", "unit": fr.own_u[lead]["id"], "target": m["id"]}, lead, tile_of(m), "order",
                        float(m["hp"]), fr.idx.get(m["kind"], 0), t_enemy_building=1.0, t_nest=1.0)
            for nid, m in sorted(self.observer.nest_memory.items())[:1]:
                if math.hypot(m["tile"][0] - cx, m["tile"][1] - cy) <= 80:
                    add(("H5", "focus", fr.own_u[lead]["id"], nid), {"op": "order", "unit": fr.own_u[lead]["id"], "target": nid}, lead, tuple(m["tile"]), "order", float(m["hp"]),
                        fr.idx.get("blight_nest", 0), t_nest=1.0, t_rally=1.0, is_nest=1.0)
        # rally points of the factories
        if fr.standing:
            for i, b in enumerate(fr.own_b):
                if b["kind"] in con.RECIPES and b["kind"] != "warehouse" and b.get("operational") and not b.get("constructing"):
                    cc = min(fr.standing, key=lambda c: (territory.cheb((c["tx"], c["ty"]), (b["tx"], b["ty"])), c["id"]))
                    tile = (int(cc["tx"]), int(cc["ty"]) + 6)
                    if w.tile_in_bounds(*tile) and tuple(b.get("rally", ())) != tile:
                        out.append(Candidate("H5", {"op": "rally", "building": b["id"], "tx": tile[0], "ty": tile[1]}, feat("H5", t_rally=1.0), ("H5", "rally", b["id"], tile[0], tile[1]),
                                             {"squad": [], "target_kind": fr.idx.get(b["kind"], 0), "target_n1": np.zeros(len(S.N1_RAW), dtype=np.float32), "target_b": i, "tile": tile, "op": "rally"}))
                        if sum(1 for c in out if c.refs.get("op") == "rally") >= 4:
                            break
        # abilities
        targets = [m for m in enemy_b if m["kind"] != "blight_nest"][:MAX_EXTRA_PER_KIND]
        for definition, what, building_kind in (("openra.e6", "capture", None), ("openra.spy", "infiltrate", None), ("openra.thf", "infiltrate", None), ("openra.e7", "c4", None)):
            for r in by_def.get(definition, [])[:2]:
                u = fr.own_u[r]
                if u.get("order"):
                    continue
                for m in sorted(targets, key=lambda m: (math.hypot(m["tile"][0] - u["tx"], m["tile"][1] - u["ty"]), m["id"]))[:2]:
                    if what == "capture" and (m["kind"] == "warehouse" and float(m["hp"]) > 0.5):
                        continue  # a settlement falls only when its defenders are beaten down to half
                    if math.hypot(m["tile"][0] - u["tx"], m["tile"][1] - u["ty"]) <= 120:
                        add(("H5", what, u["id"], m["id"]), {"op": "ability", "what": what, "unit": u["id"], "building": m["id"]}, r, tile_of(m), "ability:" + what, float(m["hp"]),
                            fr.idx.get(m["kind"], 0), t_enemy_building=1.0, t_rally=1.0)
        for r in by_def.get("openra.e6", [])[:2]:  # engineers repair damaged own buildings
            u = fr.own_u[r]
            if u.get("order"):
                continue
            hurt = sorted((b for b in fr.own_b if int(b["hp"]) < int(b.get("max_hp", b["hp"])) and not b.get("constructing")), key=lambda b: (int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))), b["id"]))
            for b in hurt[:1]:
                add(("H5", "repair", u["id"], b["id"]), {"op": "ability", "what": "repair", "unit": u["id"], "building": b["id"]}, r, (b["tx"], b["ty"]), "ability:repair",
                    int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))), fr.idx.get(b["kind"], 0), t_defend=1.0, t_rally=1.0)
        for r in by_def.get("openra.mnly", [])[:1]:
            u = fr.own_u[r]
            if int(u.get("ammo", 0)) > 0 and not any(b.get("kind") == "landmine" and (b["tx"], b["ty"]) == (u["tx"], u["ty"]) for b in w.buildings.values() if b["faction_name"] == me):
                add(("H5", "lay_mine", u["id"], u["tx"], u["ty"]), {"op": "ability", "what": "lay_mine", "unit": u["id"]}, r, None, "ability:lay_mine", t_nest=1.0, t_defend=1.0, t_rally=1.0)
        for t_i, t in enumerate(fr.own_u):
            cap, kinds = A.capacity_of(t)
            if not cap or t.get("inside"):
                continue
            if t.get("passengers"):
                add(("H5", "unload", t["id"]), {"op": "ability", "what": "unload", "transport": t["id"]}, t_i, None, "ability:unload", t_enemy_building=0.0, t_nest=1.0, t_defend=1.0)
                continue
            for r, u in enumerate(fr.own_u):
                if r == t_i or u.get("inside") or u.get("order") or math.hypot(u["tx"] - t["tx"], u["ty"] - t["ty"]) > 12:
                    continue
                kind = "infantry" if A.is_infantry(u) else ("vehicle" if A.is_vehicle(u) else "other")
                if kind in kinds and len(t.get("passengers", [])) < cap and u["faction"] == t["faction"]:
                    add(("H5", "board", u["id"], t["id"]), {"op": "ability", "what": "board", "unit": u["id"], "transport": t["id"]}, r, (t["tx"], t["ty"]), "ability:board",
                        t_nest=1.0, t_defend=1.0)
                    break
        for i, b in enumerate(fr.own_b):  # support powers
            st = A.power_status(w, b)
            if st is None or not st["charged"] or not st["paid"]:
                continue
            if st["power"] == "nuke" and targets:
                m = sorted(targets, key=lambda m: m["id"])[0]
                out.append(Candidate("H5", {"op": "ability", "what": "power", "building": b["id"], "tx": int(m["tile"][0]), "ty": int(m["tile"][1])}, feat("H5", t_enemy_building=1.0, t_defend=1.0),
                                     ("H5", "power", b["id"], m["id"]), {"squad": [], "target_kind": fr.idx.get(m["kind"], 0), "target_n1": np.zeros(len(S.N1_RAW), dtype=np.float32), "target_b": i,
                                                                            "tile": tile_of(m), "op": "ability:power"}))
            elif st["power"] in ("curtain", "paradrop") and squads:
                rows = squads[0]
                cx = int(sum(fr.own_u[r]["tx"] for r in rows) / len(rows))
                cy = int(sum(fr.own_u[r]["ty"] for r in rows) / len(rows))
                out.append(Candidate("H5", {"op": "ability", "what": "power", "building": b["id"], "tx": cx, "ty": cy}, feat("H5", t_enemy_building=1.0, t_defend=1.0),
                                     ("H5", "power", b["id"], cx, cy), {"squad": list(rows), "target_kind": 0, "target_n1": np.zeros(len(S.N1_RAW), dtype=np.float32), "target_b": i, "tile": (cx, cy),
                                                                        "op": "ability:power"}))
        return out

    # ------------------------------------------------------------------------------------------------------------------------ H9
    def extra_management(self, obs: Any, fr: Any) -> list[Candidate]:
        """Cancel a queued unit, configure a machine (a drill's target item, a factory's or assembler's plan), convert a Widelands building into its industrial successor."""
        w, me = fr.world, fr.me
        from wizard_rts.industry import hybrid
        from wizard_rts.industry import registry as R
        from wizard_rts.industry import sim as ISIM

        out: list[Candidate] = []
        s_of = obs.b_settlement
        for i, b in enumerate(fr.own_b):
            if b.get("constructing") or b.get("destroyed"):
                continue
            refs = {"building": i, "settlement": int(s_of[i]), "kind_row": fr.idx.get(b["kind"], 0)}
            for k, item in list(enumerate(b.get("queue", ())))[:2]:
                out.append(Candidate("H9", {"op": "cancel", "building": b["id"], "index": k}, feat("H9", a_demolish=1.0, a_other=1.0), ("H9", "cancel", b["id"], k), {**refs, "op": "cancel"}))
            m = b.get("mdy")
            if m is not None and b.get("operational", True):
                spec = R.block(b["kind"])
                if m.get("role") == "drill":
                    for opt in sorted(ISIM.drill_options(w, b)):
                        if opt != m.get("target"):
                            out.append(Candidate("H9", {"op": "configure", "building": b["id"], "key": "target", "value": opt}, feat("H9", a_other=1.0),
                                                 ("H9", "configure", b["id"], "target", opt), {**refs, "op": "configure"}))
                elif m.get("role") == "unit_factory":
                    for p in spec["plans"]:
                        if p["unit"] != m.get("plan") and tech.unit_allowed(w, me, p["unit"]):
                            out.append(Candidate("H9", {"op": "configure", "building": b["id"], "key": "plan", "value": p["unit"]}, feat("H9", a_other=1.0),
                                                 ("H9", "configure", b["id"], "plan", p["unit"]), {**refs, "op": "configure"}))
                elif m.get("role") == "assembler":
                    for p in spec.get("assembler_plans") or []:
                        if p["unit"] != m.get("plan"):
                            out.append(Candidate("H9", {"op": "configure", "building": b["id"], "key": "plan", "value": p["unit"]}, feat("H9", a_other=1.0),
                                                 ("H9", "configure", b["id"], "plan", p["unit"]), {**refs, "op": "configure"}))
            if b["kind"].startswith("wl:") and b.get("operational", True) and not b.get("dismantle"):
                base = b["kind"].split("_", 1)[1] if "_" in b["kind"] else b["kind"]
                target = hybrid.REPLACES.get(base)
                if target is not None and R.block(target) is not None and tech.kind_allowed(w, me, target):
                    out.append(Candidate("H9", {"op": "convert", "building": b["id"], "to": target}, feat("H9", a_dismantle_convert=1.0, a_enhance_upgrade=1.0),
                                         ("H9", "convert", b["id"], target), {**refs, "op": "convert"}))
        return out
