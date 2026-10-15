"""Observer sections for diplomacy (N13), catastrophe (N14) and the faction context (N12) (neuro/observer.py). Field lists: neuro/schema.py."""
from __future__ import annotations

from typing import Any

import numpy as np

from neuro import schema as S
from neuro.obs_strategy import named
from neuro.obs_world import EVENT_CATEGORIES, cheb_to, log5, sq
from wizard_rts import diplomacy, history, regions, trade, vp

CLIP = 5.0


class CrisisMixin:
    world: Any
    faction: str

    # ------------------------------------------------------------------------------------------------------------------------ N13
    def n13_diplomacy(self, fr: Any) -> tuple[np.ndarray, list[str], float]:
        """[8, 16] relation slots, the factions they describe, and the world's cooperation pressure (public). Slots are sorted known-before-unknown,
        then by distance to the faction's nearest centre, then by name; a faction that has collapsed sorts last."""
        w, me = fr.world, fr.me
        hist = history.state(w)["faction"]
        totals = vp.totals(w)
        offers = list(w.__dict__.get("offers", {}).values())
        rg = regions.state(w)
        rows = []
        for n in sorted(w.faction_info):
            if n == me:
                continue
            mem = [m for m in fr.known_b if m["faction_name"] == n]
            mxy = np.array([m["tile"] for m in mem], dtype=np.float64).reshape(-1, 2)
            dist = float(cheb_to(mxy, fr.cc_xy).min()) if len(mem) and len(fr.cc_xy) else np.inf
            collapsed = hist.get(n, {}).get("state") == "collapsed"
            rows.append((collapsed, not mem, dist if np.isfinite(dist) else 1e9, n, mem, dist))
        rows.sort(key=lambda r: r[:4])
        slots = np.zeros((S.N_DIPLO_SLOTS, len(S.N13_SLOT)), dtype=np.float32)
        names: list[str] = []
        for i, (collapsed, unknown, _k, n, mem, dist) in enumerate(rows[:S.N_DIPLO_SLOTS]):
            names.append(n)
            state = diplomacy.state_of(w, me, n)
            rel = w.__dict__.get("relations", {}).get(diplomacy._key(me, n), {})
            until = int(rel.get("until_ms", 0))
            strength = float(sum(s for u, s in zip(fr.eu, fr.e_str) if u["faction_name"] == n))
            cubes = 0
            if rg is not None:
                cubes = sum(self.region_memory.get(r, (0, "", 0))[0] for r in {rg.region_at(m["tile"][0], m["tile"][1]) for m in mem})
            slots[i] = named(S.N13_SLOT, len(S.N13_SLOT), **{
                f"rel_{state}": 1.0,
                "offer_from_them": float(any(o["from"] == n and o["to"] == me for o in offers)), "offer_to_them": float(any(o["from"] == me and o["to"] == n for o in offers)),
                "truce_minutes_left": max(0, until - fr.now_ms) / 60000.0 / 15.0 if until else 0.0,
                "trades_done": trade.partners_traded(w, me, n) / 5.0, "caravans_lost": self.caravans_lost.get(n, 0) / 5.0,
                "their_vp": totals.get(n, 0) / 10.0, "their_strength": sq(strength),
                "their_distance": min(dist, 200.0) / 200.0 if np.isfinite(dist) else 1.0, "their_pressure": cubes / 6.0,
                "collapsed": float(collapsed), "known": 0.0 if unknown else 1.0,
                "known_settlements": sum(1 for m in mem if m["kind"] == "warehouse") / 8.0})
        return slots, names, float(diplomacy.pressure(w))

    # ------------------------------------------------------------------------------------------------------------------------ N14
    def n14_catastrophe(self, fr: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """[R, 10] region rows, the 8 raw globals and the indices of the three worst visible regions (-1 padded). A region's cube count is the last one this
        faction saw (remembered); regions it has never seen show 0 cubes and visible = 0."""
        w, me = fr.world, fr.me
        s = regions.state(w)
        if s is None:
            return np.zeros((0, len(S.N14_REGION)), dtype=np.float32), np.zeros(len(S.N14_GLOBAL), dtype=np.float32), np.full(3, -1, dtype=np.int32)
        for i in sorted(fr.vis_regions):
            self.region_memory[i] = (s.cubes[i], s.kind[i], fr.game_s)
        kinds = [k["id"] for k in regions.config()["kinds"]]
        cen = self._centroids(s)
        d_own = np.minimum(cheb_to(cen, fr.cc_xy), 200.0) / 200.0 if len(fr.cc_xy) else np.ones(len(cen))
        own_set = {s.region_at(c["tx"], c["ty"]) for c in fr.standing}
        clinic_regions: set[int] = set()
        for b in fr.own_b:
            if fr.ks[fr.idx.get(b["kind"], 0), fr.col["is_clinic"]] and b.get("operational") and not b.get("constructing"):
                clinic_regions.update(regions._regions_near(w, s, b["tx"], b["ty"]))
        nest_hp: dict[int, float] = {}
        for m in self.nest_memory.values():
            i = s.region_at(m["tile"][0], m["tile"][1])
            nest_hp[i] = max(nest_hp.get(i, 0.0), float(m["hp"]))
        rows = np.zeros((len(s.axials), len(S.N14_REGION)), dtype=np.float32)
        kcol = {n: j for j, n in enumerate(S.N14_REGION)}
        cubes_known = 0
        for i in range(len(s.axials)):
            cubes, kind, _seen = self.region_memory.get(i, (0, "", 0))
            cubes_known += cubes
            r = rows[i]
            r[kcol["cubes"]] = cubes / 3.0
            if cubes and kind in kinds:
                r[kcol["kind_0"] + min(kinds.index(kind), 3)] = 1.0
            r[kcol["own_settlement"]] = 1.0 if i in own_set else 0.0
            r[kcol["own_clinic"]] = 1.0 if i in clinic_regions else 0.0
            r[kcol["nest_hp"]] = nest_hp.get(i, 0.0)
            r[kcol["visible"]] = 1.0 if i in fr.vis_regions else 0.0
            r[kcol["dist_own"]] = d_own[i]
        np.clip(rows, -CLIP, CLIP, out=rows)
        vis = sorted(fr.vis_regions, key=lambda i: (-s.cubes[i], i))
        worst = np.full(3, -1, dtype=np.int32)
        for k, i in enumerate(vis[:3]):
            worst[k] = i
        stock = self.own_stock(fr)
        total = int(getattr(w, "loss_outbreaks_total", regions.const("loss_outbreaks")))
        per_era = int(getattr(w, "loss_outbreaks_per_era", regions.config()["constants"].get("loss_outbreaks_per_era", total)))
        clinics = sum(1 for b in fr.own_b if fr.ks[fr.idx.get(b["kind"], 0), fr.col["is_clinic"]] and b.get("operational") and not b.get("constructing"))
        g = named(S.N14_GLOBAL, 8, outbreaks=s.outbreaks / max(1, total), era_outbreaks=s.era_outbreaks.get(int(getattr(w, "era_index", 0)), 0) / max(1, per_era),
                  minutes_to_cube=max(0, s.next_cube_ms - fr.now_ms) / 60000.0 / 10.0, cured_recently=fr.cured / 5.0, clinics=clinics / 5.0,
                  rations=stock.get("ration", 0) / 50.0, water=stock.get("water", 0) / 50.0, cubes_total=cubes_known / 20.0)
        return rows, g, worst

    # ------------------------------------------------------------------------------------------------------------------------ N12
    def n12_context(self, fr: Any, groups_stock: np.ndarray, own_strength: float, n_settlements: int) -> np.ndarray:
        w, me = fr.world, fr.me
        s = regions.state(w)
        total = int(getattr(w, "loss_outbreaks_total", regions.const("loss_outbreaks")))
        per_era = int(getattr(w, "loss_outbreaks_per_era", regions.config()["constants"].get("loss_outbreaks_per_era", total)))
        era = int(getattr(w, "era_index", 0))
        totals = vp.totals(w)
        own = vp.faction_vp(w, me)
        vals: dict[str, float] = {
            "minutes": fr.game_s / 60.0 / 240.0, "minutes_since_decision": min(1.0, (fr.game_s - self.last_obs_s) / 60.0 / 5.0),
            "outbreaks": (s.outbreaks / max(1, total)) if s else 0.0, "era_outbreaks": (s.era_outbreaks.get(era, 0) / max(1, per_era)) if s else 0.0,
            "own_vp": own / 10.0, "vp_gap": (max(totals.values(), default=0) - own) / 10.0, "settlements": n_settlements / 8.0, "strength": sq(own_strength)}
        for i in range(len(EVENT_CATEGORIES)):
            vals[f"event_{i}"] = min(float(self.event_counts[i]), 3.0) / 3.0
        for i in range(4):
            vals[f"era_{i}"] = float(era == i)
        for g, n in enumerate(S.GROUP_NAMES):
            vals[f"stock_group_{n}"] = float(groups_stock[g])
        return named(S.N12_RAW, 28, **vals)
