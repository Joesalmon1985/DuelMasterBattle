"""Shared helpers of the observer: events, windows of per-faction counters, memories of nests and regions, geometry (neuro/observer.py)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro import vision
from wizard_rts import construction as con
from wizard_rts import regions, tech
from wizard_rts.ai_plus import strength_of

EVENT_CATEGORIES = ("lost_building", "lost_units", "enemy_near", "shortage", "draft", "outbreak", "era", "relation", "caravan_lost", "other")


def log5(n: float) -> float:
    """log1p(n) / 5: the scale used for counts and stocks (a stock of 150 is about 1)."""
    return math.log1p(max(0.0, float(n))) / 5.0


def sq(strength: float) -> float:
    """A strength feature: strength / 1000, compressed above 2 (2 + ln(v / 2)) so that armies of 5,000 and 25,000 stay distinguishable inside the +-5 clip."""
    v = max(0.0, float(strength)) / 1000.0
    return v if v <= 2.0 else 2.0 + math.log(v / 2.0)


def cheb_to(points: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Chebyshev distance of each point to the nearest target; inf when there is no target."""
    if len(targets) == 0 or len(points) == 0:
        return np.full(len(points), np.inf)
    return np.abs(points[:, None, :] - targets[None, :, :]).max(axis=2).min(axis=1)


def finite_or(a: np.ndarray, default: float) -> np.ndarray:
    return np.where(np.isfinite(a), a, default)


class WorldMixin:
    world: Any
    faction: str

    # ------------------------------------------------------------------------------------------------------------------------ events
    def on_events(self, events: list[dict]) -> None:
        """Count the faction's own trigger events since the last observation (design 5.2). Other factions' events are ignored."""
        me = self.faction
        reg_cache: dict[str, bool] = {}
        for e in events:
            k = e.get("kind")
            if k in ("building_destroyed", "settlement_destroyed", "catastrophe_destroyed") and e.get("faction") == me:
                self.event_counts[0] += 1
            elif k in ("unit_killed", "unit_lost") and e.get("faction") == me:
                self.event_counts[1] += 1
            elif k == "shortage" and e.get("faction") == me:
                self.event_counts[3] += 1
            elif k == "draft_offer" and e.get("faction") == me:
                self.event_counts[4] += 1
            elif k in ("outbreak", "outbreak_cube"):
                rid = e.get("region", "")
                if rid not in reg_cache:
                    reg_cache[rid] = self._own_region(rid)
                if reg_cache[rid]:
                    self.event_counts[5] += 1
            elif k == "era_advanced":
                self.event_counts[6] += 1
            elif k == "relation_changed" and me in (e.get("a"), e.get("b")):
                self.event_counts[7] += 1
            elif k == "caravan_lost" and e.get("faction") == me:
                self.event_counts[8] += 1
                who = self._owner_of(e.get("by", ""))
                if who:
                    self.caravans_lost[who] = self.caravans_lost.get(who, 0) + 1
            elif k in ("card_drafted", "deploy_rejected") and e.get("faction") == me:
                self.event_counts[9] += 1

    def _owner_of(self, entity_id: str) -> str:
        e = self.world.units.get(entity_id) or self.world.buildings.get(entity_id)
        return e["faction_name"] if e and e.get("faction_name") and e["faction_name"] != self.faction else ""

    def _own_region(self, rid: str) -> bool:
        s = regions.state(self.world)
        if s is None or not rid.startswith("region:"):
            return False
        try:
            q, r = (int(x) for x in rid[len("region:"):].split(","))
        except ValueError:
            return False
        i = s.index.get((q, r))
        if i is None:
            return False
        key = (self.world.economy_quanta // 50, len(self.world.buildings))
        if getattr(self, "_own_regions_key", None) != key:
            self._own_regions_key = key
            self._own_regions = {s.region_at(b["tx"], b["ty"]) for b in self.world.buildings.values() if b["faction_name"] == self.faction and "hp" in b}
        return i in self._own_regions

    # ------------------------------------------------------------------------------------------------------------------------ windows
    @staticmethod
    def _window_delta(hist: Any, now_s: int, window: int) -> tuple[Any, float]:
        """The oldest snapshot not older than `window` seconds before now (and the seconds it covers); (None, 0) when there is none yet."""
        for t, snap in hist:
            if 0 < now_s - t <= window:
                return snap, float(now_s - t)
        return None, 0.0

    def _flow_snapshot(self, own_b: list[dict]) -> dict[str, np.ndarray]:
        """Cumulative made/consumed totals per ware group ([made 6, consumed 6]) for the faction ("_f") and per building."""
        w = self.world
        out: dict[str, np.ndarray] = {}
        tot = np.zeros(12, dtype=np.float64)
        fl = w.__dict__.get("ware_flow", {}).get(self.faction, {})
        for k, kind in enumerate(("made", "consumed")):
            for ware, n in fl.get(kind, {}).items():
                g = F.group_of(ware)
                if g is not None:
                    tot[k * 6 + g] += n
        out["_f"] = tot
        per = w.__dict__.get("ware_flow_b", {})
        for b in own_b:
            rec = per.get(b["id"])
            if rec:
                v = np.zeros(12, dtype=np.float64)
                for k, kind in enumerate(("made", "consumed")):
                    for ware, n in rec[kind].items():
                        g = F.group_of(ware)
                        if g is not None:
                            v[k * 6 + g] += n
                out[b["id"]] = v
        return out

    @staticmethod
    def _flow_delta(now: dict[str, np.ndarray], old: dict[str, np.ndarray] | None, scale: float) -> dict[str, np.ndarray]:
        """Production and consumption over the window, scaled to a full 5 minutes (zeros until the observer has a window of at least 10 s)."""
        if old is None or scale == 0.0:
            return {k: np.zeros(12) for k in now}
        return {k: np.maximum(v - old.get(k, 0.0), 0.0) * scale for k, v in now.items()}

    def _shortage_snapshot(self, own_b: list[dict]) -> dict[tuple[str, str], int]:
        mine = {b["id"] for b in own_b}
        return {k: v for k, v in self.world.shortages.items() if k[0] in mine}

    # ------------------------------------------------------------------------------------------------------------------------ memories
    def _update_nests(self, nests: list[dict], game_s: int) -> None:
        """Nests seen are remembered (position, hit points); one that is gone when its place is seen again is forgotten."""
        for r in nests:
            self.nest_memory[r["id"]] = {"tile": tuple(r["tile"]), "hp": r["hp"], "seen_s": game_s}
        for nid in sorted(self.nest_memory):
            m = self.nest_memory[nid]
            b = self.world.buildings.get(nid)
            if (b is None or int(b.get("hp", 0)) <= 0) and vision.visible(self.world, self.faction, m["tile"][0], m["tile"][1]):
                del self.nest_memory[nid]

    def _centroids(self, s: Any) -> np.ndarray:
        """[R, 2] mean tile (x, y) of every region (static per map)."""
        if self._region_centroids is None or len(self._region_centroids) != len(s.axials):
            tab = np.asarray(s.table, dtype=np.int64)
            n = len(s.axials)
            ys, xs = np.divmod(np.arange(tab.size), s.w)
            cnt = np.maximum(np.bincount(tab, minlength=n), 1)
            self._region_centroids = np.stack([np.bincount(tab, weights=xs, minlength=n) / cnt, np.bincount(tab, weights=ys, minlength=n) / cnt], axis=1)
        return self._region_centroids

    # ------------------------------------------------------------------------------------------------------------------------ small facts
    @staticmethod
    def strength(u: dict) -> float:
        """Fighting value of a unit (the same measure the heuristic AI uses: sqrt(HP) x DPS x range factor)."""
        return strength_of(u.get("definition", ""), int(u.get("hp", 1))) if u.get("weapon") else 0.0

    def known_cubes(self, fr: Any, region: int) -> int:
        """Outbreak cubes in a region as this faction knows them: the live count if the region is in sight, else the last count it saw (0 if never seen)."""
        rg = regions.state(fr.world)
        if rg is None:
            return 0
        if region in fr.vis_regions:
            return int(rg.cubes[region])
        return int(self.region_memory.get(region, (0, "", 0))[0])

    def unlocked_groups(self) -> np.ndarray:
        """Per ware group: 1.0 if at least one building kind that produces it is unlocked for the faction (the static chain table x its cards)."""
        w, f = self.world, self.faction
        sig = (len(w.tech.get(f, {}).get("cards", [])), int(getattr(w, "era_index", 0)))
        if sig != self._unlock_sig:
            ks, idx = F.kind_static(), F.kind_index()
            col = {c: i for i, c in enumerate(S.KIND_STATIC_COLUMNS)}
            cols = [col["produces_" + g] for g in S.GROUP_NAMES]
            out = np.zeros(S.N_GROUPS, dtype=np.float32)
            for kind in sorted(con.full_menu()):
                row = idx.get(kind, 0)
                if row and ks[row, col["is_unit"]] == 0 and out.min() < 1.0 and tech.kind_allowed(w, f, kind):
                    out = np.maximum(out, ks[row, cols])
            self._unlock_sig, self._unlock_cache = sig, out
        return self._unlock_cache
