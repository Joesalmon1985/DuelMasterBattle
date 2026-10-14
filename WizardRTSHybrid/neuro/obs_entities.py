"""Observer sections for buildings (N1), settlements (N2) and units (N3). Field lists and widths: neuro/schema.py (N1_RAW, N2_RAW, N3_RAW)."""
from __future__ import annotations

from typing import Any

import numpy as np

from neuro import schema as S
from neuro.obs_world import cheb_to, finite_or, log5, sq
from wizard_rts import regions, rules, territory, wl_defs
from wizard_rts.construction import BUILD_MS

CLIP = 5.0
STALL_REASON = {"inputs": 0, "worker": 1, "no_tree": 2, "no_rock": 2, "no_terrain": 2, "no_resource": 2, "no_fish": 2, "construct": 1, "full": 3, "not_needed": 3,
                "disrupted": 4}
IDLE_NONE = 5
LOCO_COL = {"foot": 0, "legs": 0, "wheeled": 1, "heavywheeled": 1, "tracked": 1, "lighttracked": 1, "heavytracked": 1, "hover": 1, "fly": 2, "naval": 3, "lcraft": 3}
_B = {n: i for i, n in enumerate(S.N1_RAW)}
_U = {n: i for i, n in enumerate(S.N3_RAW)}
_S = {n: i for i, n in enumerate(S.N2_RAW)}


class EntitiesMixin:
    world: Any
    faction: str
    _input_total: dict[str, int]

    # ------------------------------------------------------------------------------------------------------------------------ N1
    def _inputs_of(self, kind: str) -> int:
        """Total input capacity of a building kind (Widelands inputs; 4 for everything else): the denominator of 'input satisfaction'."""
        if kind not in self._input_total:
            spec = wl_defs.spec_for_kind(kind) if kind.startswith("wl:") else None
            self._input_total[kind] = int(sum((spec or {}).get("inputs", {}).values())) if spec else 4
        return self._input_total[kind]

    def building_rows(self, fr: Any) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
        w, ks, col = fr.world, fr.ks, fr.col
        n = len(fr.own_b)
        raw = np.zeros((n, len(S.N1_RAW)), dtype=np.float32)
        kinds = np.zeros(n, dtype=np.int32)
        sets = np.full(n, -1, dtype=np.int32)
        if n == 0:
            return [], kinds, raw, sets
        bxy = np.array([[b["tx"], b["ty"]] for b in fr.own_b], dtype=np.float64)
        st_xy = np.array([[c["tx"], c["ty"]] for c in fr.standing], dtype=np.float64).reshape(-1, 2)
        dist = np.full(n, np.inf)
        if len(st_xy):
            d = np.abs(bxy[:, None, :] - st_xy[None, :, :]).max(axis=2)
            sets[:] = d.argmin(axis=1)
            dist = d.min(axis=1)
        nest_xy = np.array([r["tile"] for r in fr.nests] + [m["tile"] for m in self.nest_memory.values() if m["seen_s"] != fr.game_s], dtype=np.float64).reshape(-1, 2)
        near_nest = cheb_to(bxy, nest_xy) <= 10
        threat = cheb_to(bxy, fr.e_xy) <= 12
        rg = regions.state(w)
        anycubes = rg is not None and any(rg.cubes)
        requests = w.recipe_requests
        for i, b in enumerate(fr.own_b):
            r = raw[i]
            mhp = max(1, int(b.get("max_hp", b["hp"])))
            kinds[i] = fr.idx.get(b["kind"], 0)
            con_state = b.get("constructing")
            working = bool(b.get("working"))
            stall = b.get("stall") or {}
            r[_B["hp"]] = int(b["hp"]) / mhp
            r[_B["operational"]] = 1.0 if b.get("operational", True) and not con_state else 0.0
            r[_B["working"]] = 1.0 if working else 0.0
            r[_B["constructing"]] = 1.0 if con_state else 0.0
            r[_B["disrupted"]] = 1.0 if b.get("disrupted") else 0.0
            r[_B["waiting_worker"]] = 1.0 if b.get("waiting_worker") else 0.0
            r[_B["queue_len"]] = len(b.get("queue", ())) / 5.0
            out = sum(requests.get(b["id"], {}).values()) if requests else 0
            need = self._inputs_of(b["kind"])
            r[_B["input_satisfaction"]] = 1.0 - min(1.0, out / need) if need else 1.0
            factor = 1.0
            if anycubes:
                from wizard_rts.regions import production_factor

                factor = production_factor(w, b)
            r[_B["outbreak_factor"]] = 1.0 - factor
            reason = IDLE_NONE
            if not working and not con_state:
                reason = STALL_REASON.get(stall.get("reason"), IDLE_NONE)
                if reason == IDLE_NONE and factor < 1.0:
                    reason = 4
            r[_B["idle_no_input"] + reason] = 1.0
            r[_B["dist_centre"]] = min(dist[i], 340.0) / 34.0 if np.isfinite(dist[i]) else 1.0
            r[_B["has_road"]] = 1.0 if b["id"] in fr.road_ids else 0.0
            row = kinds[i]
            r[_B["is_clinic"]] = ks[row, col["is_clinic"]]
            r[_B["nest_nearby"]] = 1.0 if near_nest[i] else 0.0
            r[_B["stall_minutes"]] = min(10.0, (fr.now_ms - int(stall["at_ms"])) / 60000.0) / 10.0 if stall and "at_ms" in stall else 0.0
            wids = b.get("worker_ids")
            if isinstance(wids, dict) and wids:
                r[_B["workers_fraction"]] = sum(1 for v in wids.values() if v) / len(wids)
            else:
                r[_B["workers_fraction"]] = 1.0
            r[_B["under_threat"]] = 1.0 if threat[i] else 0.0
            r[_B["is_store"]] = ks[row, col["is_centre"]]
            r[_B["construction_progress"]] = min(1.0, int(con_state.get("progress_ms", 0)) / BUILD_MS) if isinstance(con_state, dict) else 1.0
        np.clip(raw, -CLIP, CLIP, out=raw)
        return [b["id"] for b in fr.own_b], kinds, raw, sets

    # ------------------------------------------------------------------------------------------------------------------------ N2
    def settlement_rows(self, fr: Any, b_set: np.ndarray) -> tuple[np.ndarray, list[np.ndarray], np.ndarray, int, int]:
        w, ks, col = fr.world, fr.ks, fr.col
        n = len(fr.standing)
        raw = np.zeros((n, len(S.N2_RAW)), dtype=np.float32)
        members_all: list[np.ndarray] = []
        damaged = np.full(n, -1, dtype=np.int32)
        if n == 0:
            return raw, [], damaged, -1, -1
        rg = regions.state(w)
        hp = np.array([int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))) for b in fr.own_b], dtype=np.float64)
        clinic_xy = np.array([[b["tx"], b["ty"]] for b in fr.own_b if ks[fr.idx.get(b["kind"], 0), col["is_clinic"]] and b.get("operational")], dtype=np.float64).reshape(-1, 2)
        wmem = [m for m in fr.known_b if m["kind"] == "warehouse"]
        wm_xy = np.array([m["tile"] for m in wmem], dtype=np.float64).reshape(-1, 2)
        armed_xy = np.array([[u["tx"], u["ty"]] for u in fr.own_u if u.get("weapon")], dtype=np.float64).reshape(-1, 2)
        armed_str = np.array([self.strength(u) for u in fr.own_u if u.get("weapon")], dtype=np.float64)
        enemy_near = np.zeros(n)
        own_near = np.zeros(n)
        cubes_at = np.zeros(n)
        for j, cc in enumerate(fr.standing):
            rec = fr.srec[cc["id"]]
            mem = np.flatnonzero(b_set == j)
            members_all.append(mem)
            r = raw[j]
            stock = w.stocks.get(cc["id"], {})
            for k, ware in enumerate(S.KEY_WARES):
                r[k] = log5(stock.get(ware, 0))
            made = np.zeros(6)
            cons = np.zeros(6)
            for i in mem:
                v = fr.fl.get(fr.own_b[i]["id"])
                if v is not None:
                    made += v[:6]
                    cons += v[6:]
            base = len(S.KEY_WARES)
            for g in range(6):
                r[base + g] = log5(made[g])
                r[base + 6 + g] = log5(cons[g])
            r[_S["unrest"]] = float(rec.get("unrest", 0.0))
            r[_S["standing_vp"]] = 1.0
            r[_S["is_home"]] = 1.0 if rec.get("home") else 0.0
            r[_S["radius"]] = territory.radius_of(cc) / 34.0
            cube = 0
            nest_hp = 0.0
            if rg is not None:
                ri = rg.region_at(cc["tx"], cc["ty"])
                cube = self.known_cubes(fr, ri)
                nest_hp = max([m["hp"] for m in self.nest_memory.values() if rg.region_at(m["tile"][0], m["tile"][1]) == ri] + [0.0])
            cubes_at[j] = cube
            r[_S["region_cubes"]] = cube / 3.0
            r[_S["nest_hp"]] = nest_hp
            cxy = np.array([[cc["tx"], cc["ty"]]], dtype=np.float64)
            r[_S["own_clinics"]] = float((np.abs(clinic_xy - cxy).max(axis=1) <= 24).sum()) / 3.0 if len(clinic_xy) else 0.0
            if len(fr.e_xy):
                enemy_near[j] = fr.e_str[np.abs(fr.e_xy - cxy).max(axis=1) <= 40].sum()
            if len(armed_xy):
                own_near[j] = armed_str[np.abs(armed_xy - cxy).max(axis=1) <= 40].sum()
            r[_S["enemy_strength"]] = sq(enemy_near[j])
            r[_S["own_strength"]] = sq(own_near[j])
            d = cheb_to(cxy, wm_xy)[0]
            r[_S["dist_enemy_settlement"]] = min(d, 200.0) / 200.0 if np.isfinite(d) else 1.0
            r[_S["founded_minutes"]] = (fr.now_ms - int(rec.get("founded_ms", 0))) / 60000.0 / 240.0
            if len(mem):
                ops = sum(1 for i in mem if not fr.own_b[i].get("constructing") and fr.own_b[i].get("operational", True))
                r[_S["operational_fraction"]] = ops / len(mem)
                r[_S["constructing_count"]] = sum(1 for i in mem if fr.own_b[i].get("constructing")) / 10.0
                linked = sum(1 for i in mem if fr.own_b[i]["id"] in fr.road_ids or fr.own_b[i].get("command_center"))
                r[_S["connected_fraction"]] = linked / len(mem)
                r[_S["shortage_count"]] = sum(v for (bid, _g), v in fr.shortage_delta.items() if bid in {fr.own_b[i]["id"] for i in mem}) / 10.0
                damaged[j] = mem[int(np.argmin(hp[mem]))]
            else:
                r[_S["operational_fraction"]] = 1.0
                r[_S["connected_fraction"]] = 1.0
        np.clip(raw, -CLIP, CLIP, out=raw)
        # the most threatened settlement: visible enemy strength first, then catastrophe, then unrest; the weakest: the lowest production this window
        threat_key = [(enemy_near[j] - own_near[j], cubes_at[j], raw[j, _S["unrest"]], -j) for j in range(n)]
        s_threatened = int(max(range(n), key=lambda j: threat_key[j]))
        prod = raw[:, len(S.KEY_WARES):len(S.KEY_WARES) + 6].sum(axis=1)
        s_weakest = int(min(range(n), key=lambda j: (prod[j], raw[j, _S["operational_fraction"]], j)))
        return raw, members_all, damaged, s_threatened, s_weakest

    # ------------------------------------------------------------------------------------------------------------------------ N3
    def unit_rows(self, fr: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """Own units: [U, 20] raw rows, kind rows, armed mask, and the faction's total army strength."""
        w = fr.world
        n = len(fr.own_u)
        raw = np.zeros((n, len(S.N3_RAW)), dtype=np.float32)
        kinds = np.zeros(n, dtype=np.int32)
        armed = np.zeros(n, dtype=bool)
        if n == 0:
            return raw, kinds, armed, 0.0
        d_own = cheb_to(fr.o_xy, fr.cc_xy)
        d_enemy = cheb_to(fr.o_xy, fr.e_xy)
        rg = regions.state(w)
        total = 0.0
        for i, u in enumerate(fr.own_u):
            r = raw[i]
            kinds[i] = fr.idx.get("unit:" + u["kind"], 0)
            mhp = max(1, int(u.get("max_hp", u["hp"])))
            st = u.get("status", "idle")
            wpn = u.get("weapon")
            armed[i] = bool(wpn)
            s = self.strength(u)
            total += s
            r[_U["hp"]] = int(u["hp"]) / mhp
            r[_U["strength"]] = sq(s)
            r[_U["loco_foot"] + LOCO_COL.get(u.get("loco") or "foot", 0)] = 1.0
            r[_U["has_weapon"]] = 1.0 if wpn else 0.0
            wd = rules.weapon(wpn) if wpn else None
            r[_U["range"]] = float(wd.get("range", 0)) / 8.0 if wd else 0.0
            r[_U["is_founder"]] = 1.0 if territory.is_founder(u) else 0.0
            r[_U["carrying_cargo"]] = 1.0 if u.get("cargo") else 0.0
            r[_U["dist_own_centre"]] = min(d_own[i], 100.0) / 100.0 if np.isfinite(d_own[i]) else 1.0
            r[_U["dist_enemy"]] = min(d_enemy[i], 40.0) / 40.0 if np.isfinite(d_enemy[i]) else 1.0
            has_order = bool(u.get("order"))
            r[_U["engaged"]] = 1.0 if (u.get("target") is not None or st == "attacking") else 0.0
            r[_U["idle"]] = 1.0 if (st in ("idle", "waiting_route") and not has_order) else 0.0
            r[_U["moving"]] = 1.0 if st in ("moving", "ordered") else 0.0
            r[_U["region_cubes"]] = self.known_cubes(fr, rg.region_at(u["tx"], u["ty"])) / 3.0 if rg is not None else 0.0
            r[_U["speed"]] = (1000.0 / max(1, int(u.get("move_ms", 1000)))) / 5.0
            r[_U["has_order"]] = 1.0 if has_order else 0.0
            r[_U["weapon_ready"]] = 1.0 if int(u.get("cooldown_ms", 0)) <= 0 else 0.0
            r[_U["max_hp"]] = min(mhp / 50000.0, CLIP)
        np.clip(raw, -CLIP, CLIP, out=raw)
        return raw, kinds, armed, float(total)

    def enemy_rows(self, fr: Any) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        """Visible enemy units sorted by distance to the faction's nearest centre. Only what a unit shows from outside: kind, hit-point fraction, position
        (an enemy's orders, status and cargo are not observable and stay 0)."""
        w = fr.world
        order = np.argsort(finite_or(cheb_to(fr.e_xy, fr.cc_xy), 1e9), kind="stable") if len(fr.eu) else np.array([], dtype=np.int64)
        eu = [fr.eu[i] for i in order]
        raw = np.zeros((len(eu), len(S.N3_RAW)), dtype=np.float32)
        kinds = np.zeros(len(eu), dtype=np.int32)
        if not eu:
            return raw, kinds, eu
        exy = np.array([[u["tx"], u["ty"]] for u in eu], dtype=np.float64)
        d_own = cheb_to(exy, fr.cc_xy)
        d_foe = cheb_to(exy, fr.o_xy)  # for an enemy, "the enemy" is us
        rg = regions.state(w)
        for i, u in enumerate(eu):
            r = raw[i]
            kinds[i] = fr.idx.get("unit:" + u["kind"], 0)
            actor = rules.actor(u.get("definition", "")) or {}
            mhp = max(1, int(u.get("max_hp", actor.get("hp", 1000))))
            wpn = u.get("weapon")
            r[_U["hp"]] = int(u["hp"]) / mhp
            r[_U["strength"]] = sq(self.strength(u))
            r[_U["loco_foot"] + LOCO_COL.get(u.get("loco") or actor.get("locomotor") or "foot", 0)] = 1.0
            r[_U["has_weapon"]] = 1.0 if wpn else 0.0
            wd = rules.weapon(wpn) if wpn else None
            r[_U["range"]] = float(wd.get("range", 0)) / 8.0 if wd else 0.0
            r[_U["is_founder"]] = 1.0 if territory.is_founder(u) else 0.0
            r[_U["dist_own_centre"]] = min(d_own[i], 100.0) / 100.0 if np.isfinite(d_own[i]) else 1.0
            r[_U["dist_enemy"]] = min(d_foe[i], 40.0) / 40.0 if np.isfinite(d_foe[i]) else 1.0
            r[_U["region_cubes"]] = self.known_cubes(fr, rg.region_at(u["tx"], u["ty"])) / 3.0 if rg is not None else 0.0
            r[_U["speed"]] = (1000.0 / max(1, int(u.get("move_ms", 1000)))) / 5.0
            r[_U["max_hp"]] = min(mhp / 50000.0, CLIP)
        np.clip(raw, -CLIP, CLIP, out=raw)
        return raw, kinds, eu
