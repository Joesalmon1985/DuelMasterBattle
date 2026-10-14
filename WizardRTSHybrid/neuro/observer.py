"""Per-decision feature assembly (execution plan T2.2): everything the neural controller may know about one faction, as float32 arrays.

`FactionObserver(world, faction)` is owned by one controller (one seat). `observe(game_s)` returns an `Observation`: the raw feature rows of every network
(widths in neuro/schema.py), the id lists and index pointers that let M3 route network outputs (which building belongs to which settlement, the most damaged
building of each settlement, the most threatened settlement, the nearest enemy units, ...) and the context the candidate generator reuses.

INFORMATION RULES (the hidden-information contract, tested in tests/test_neuro_features.py):
  * the faction's own state is read directly;
  * other factions are seen only through neuro/vision.py: units in sight now, the memory of buildings seen earlier (which may be stale), regions in sight;
  * public facts every faction is shown: the VP table, the era, the outbreak counters and limit, whether a faction has collapsed, the schedule of the next
    outbreak cube, and the cube count of regions the faction has seen (remembered by this observer);
  * production, consumption, kills and losses come from per-faction counters (wizard_rts/flow.py, fstats), never from the world's global counters;
  * events are used only for the faction's own trigger counts.
CACHING. Static per-building data (kind row, settlement assignment, distance to its centre) is cached by building id and invalidated when the faction's set of
command centres changes; the unlocked-kind table is cached by card count and era; per-decision work is vectorised with numpy where that is cheap. Window
counters (5 minutes of production, 10 of kills) come from snapshots kept by the observer.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro import vision
from neuro.obs_crisis import CrisisMixin
from neuro.obs_entities import EntitiesMixin
from neuro.obs_strategy import StrategyMixin
from neuro.obs_world import WorldMixin, EVENT_CATEGORIES
from wizard_rts import territory

WINDOW_S = 300  # production, consumption and shortage window
FIGHT_WINDOW_S = 600  # kills and losses window
CURE_WINDOW_S = 1200


@dataclass
class Frame:
    """Everything computed once per decision and shared by the sections."""
    world: Any
    me: str
    game_s: int
    now_ms: int
    own_b: list[dict]
    own_u: list[dict]
    ccs: list[dict]
    standing: list[dict]
    srec: dict[str, dict | None]
    cc_xy: np.ndarray
    known_b: list[dict]
    nests: list[dict]
    vis_regions: set[int]
    eu: list[dict]  # visible enemy units, sorted by id
    e_xy: np.ndarray
    e_str: np.ndarray
    o_xy: np.ndarray
    road_ids: set[str]
    fl: dict[str, np.ndarray]
    fd: dict[str, float]
    cured: float
    shortage_delta: dict[tuple[str, str], int]
    ks: np.ndarray
    idx: dict[str, int]
    col: dict[str, int]
    scratch: dict[str, Any] = field(default_factory=dict)


@dataclass
class Observation:
    faction: str
    game_s: int
    # own buildings (N1)
    b_ids: list[str]
    b_kind: np.ndarray
    b_raw: np.ndarray
    b_settlement: np.ndarray  # index into s_ids, -1 when the faction has no settlement
    # settlements (N2)
    s_ids: list[str]
    s_centre: list[str]
    s_raw: np.ndarray
    s_members: list[np.ndarray]  # building rows of each settlement
    s_damaged: np.ndarray  # building row of the most damaged member of each settlement (-1 when none)
    s_threatened: int  # index of the most threatened settlement (-1 when none)
    s_weakest: int  # index of the settlement with the lowest production (-1 when none)
    # own units (N3) and visible enemy units (sorted by distance to the faction's nearest centre)
    u_ids: list[str]
    u_kind: np.ndarray
    u_raw: np.ndarray
    u_armed: np.ndarray
    e_ids: list[str]
    e_kind: np.ndarray
    e_raw: np.ndarray
    e_faction: list[str]
    # network-level raw vectors
    n4_raw: np.ndarray
    n5_raw: np.ndarray
    n6_raw: np.ndarray
    n7_raw: np.ndarray
    n8_raw: np.ndarray
    n10_raw: np.ndarray
    n12_raw: np.ndarray
    # expansion, cards, diplomacy, catastrophe
    expansion_sites: list[tuple[int, int]]
    card_ids: list[str]
    card_raw: np.ndarray
    n13_slots: np.ndarray
    n13_factions: list[str]
    n13_pressure: float
    n14_regions: np.ndarray
    n14_global: np.ndarray
    n14_worst: np.ndarray
    extra: dict[str, Any] = field(default_factory=dict)  # context for candidates.py (centres, memory rows, ...)

    def arrays(self) -> dict[str, np.ndarray]:
        return {k: v for k, v in self.__dict__.items() if isinstance(v, np.ndarray)}


class FactionObserver(EntitiesMixin, StrategyMixin, CrisisMixin, WorldMixin):
    """Features of one faction. Construct once per seat; call `on_events` with the event stream and `observe` once per decision."""

    def __init__(self, world: Any, faction: str) -> None:
        self.world = world
        self.faction = faction
        self.last_obs_s = 0
        self.event_counts = np.zeros(len(EVENT_CATEGORIES), dtype=np.float32)
        self.caravans_lost: dict[str, int] = {}
        self.region_memory: dict[int, tuple[int, str, int]] = {}  # region -> (cubes, kind, last seen game second)
        self.nest_memory: dict[str, dict[str, Any]] = {}
        self.flow_hist: deque = deque(maxlen=128)
        self.fight_hist: deque = deque(maxlen=128)
        self.short_hist: deque = deque(maxlen=128)
        self._static: dict[str, tuple] = {}
        self._static_sig: tuple = ()
        self._unlock_sig: tuple | None = None
        self._unlock_cache = np.zeros(S.N_GROUPS, dtype=np.float32)
        self._region_centroids: np.ndarray | None = None
        self._input_total: dict[str, int] = {}
        self.timings: dict[str, float] = {}

    # ------------------------------------------------------------------------------------------------------------------------ the frame
    def _frame(self, game_s: int) -> Frame:
        w, me = self.world, self.faction
        ks, idx = F.kind_static(), F.kind_index()
        col = {c: i for i, c in enumerate(S.KIND_STATIC_COLUMNS)}
        own_b = sorted((b for b in w.buildings.values() if b["faction_name"] == me and "hp" in b and int(b["hp"]) > 0 and not b.get("destroyed")), key=lambda b: b["id"])
        own_u = sorted((u for u in w.units.values() if u["faction_name"] == me and u.get("alive", True) and not u.get("inside")), key=lambda u: u["id"])
        ccs = sorted(territory.command_centers(w, me), key=lambda c: c["id"])
        srec = {c["id"]: w.dmb.settlements.get(c.get("settlement_id", "")) for c in ccs}
        standing = [c for c in ccs if srec[c["id"]] is not None and srec[c["id"]]["state"] == "standing"]
        seen = vision.seen_enemies(w, me)
        nests = [r for r in seen["buildings"] if not r["faction"]]
        self._update_nests(nests, game_s)
        eu = [w.units[r["id"]] for r in sorted(seen["units"], key=lambda r: r["id"]) if r["id"] in w.units]
        # windows of per-faction counters
        flow_now = self._flow_snapshot(own_b)
        self.flow_hist.append((game_s, flow_now))
        old, span = self._window_delta(self.flow_hist, game_s, WINDOW_S)
        scale = WINDOW_S / span if old is not None and span >= 10 else 0.0
        fl = self._flow_delta(flow_now, old, scale)
        fs = w.fstats.get(me, {})
        fight_now = {k: float(fs.get(k, 0)) for k in ("kill_value", "loss_value", "building_kills", "building_losses", "cubes_cured")}
        self.fight_hist.append((game_s, fight_now))
        fold, _ = self._window_delta(self.fight_hist, game_s, FIGHT_WINDOW_S)
        fd = {k: (fight_now[k] - fold[k]) if fold is not None else 0.0 for k in fight_now}
        cold, _ = self._window_delta(self.fight_hist, game_s, CURE_WINDOW_S)
        cured = (fight_now["cubes_cured"] - cold["cubes_cured"]) if cold is not None else 0.0
        short_now = self._shortage_snapshot(own_b)
        self.short_hist.append((game_s, short_now))
        sold, _ = self._window_delta(self.short_hist, game_s, WINDOW_S)
        shortage_delta = {k: max(0, v - sold.get(k, 0)) for k, v in short_now.items()} if sold is not None else {}
        road_ids = {i for a, c in (e for e in w.road_edges.values()) for i in (a, c)}
        return Frame(
            world=w, me=me, game_s=game_s, now_ms=int(w.dmb.clock.get("game_ms", 0)), own_b=own_b, own_u=own_u, ccs=ccs, standing=standing, srec=srec,
            cc_xy=np.array([[c["tx"], c["ty"]] for c in ccs], dtype=np.float64).reshape(-1, 2), known_b=vision.known_enemy_buildings(w, me), nests=nests,
            vis_regions=vision.visible_regions(w, me), eu=eu, e_xy=np.array([[u["tx"], u["ty"]] for u in eu], dtype=np.float64).reshape(-1, 2),
            e_str=np.array([self.strength(u) for u in eu], dtype=np.float64), o_xy=np.array([[u["tx"], u["ty"]] for u in own_u], dtype=np.float64).reshape(-1, 2),
            road_ids=road_ids, fl=fl, fd=fd, cured=cured, shortage_delta=shortage_delta, ks=ks, idx=idx, col=col)

    # ------------------------------------------------------------------------------------------------------------------------ observe
    def observe(self, game_s: int) -> Observation:
        fr = self._frame(game_s)
        b_ids, b_kind, b_raw, b_set = self.building_rows(fr)
        s_raw, s_members, s_damaged, s_threatened, s_weakest = self.settlement_rows(fr, b_set)
        u_raw, u_kind, u_armed, own_strength = self.unit_rows(fr)
        e_raw, e_kind, e_sorted = self.enemy_rows(fr)
        n4, groups_stock = self.n4_economy(fr)
        n5 = self.n5_logistics(fr)
        n6 = self.n6_military(fr, u_armed, own_strength)
        n7, sites = self.n7_expansion(fr, own_strength)
        card_ids, card_raw = self.cards(fr)
        n8 = self.n8_technology(fr, len(card_ids))
        n10 = self.n10_war(fr, own_strength)
        n13, n13_factions, n13_pressure = self.n13_diplomacy(fr)
        n14r, n14g, worst = self.n14_catastrophe(fr)
        n12 = self.n12_context(fr, groups_stock, own_strength, len(fr.standing))
        self.last_obs_s = game_s
        self.event_counts[:] = 0
        obs = Observation(
            faction=self.faction, game_s=game_s, b_ids=b_ids, b_kind=b_kind, b_raw=b_raw, b_settlement=b_set, s_ids=[fr.srec[c["id"]]["id"] for c in fr.standing],
            s_centre=[c["id"] for c in fr.standing], s_raw=s_raw, s_members=s_members, s_damaged=s_damaged, s_threatened=s_threatened, s_weakest=s_weakest,
            u_ids=[u["id"] for u in fr.own_u], u_kind=u_kind, u_raw=u_raw, u_armed=u_armed, e_ids=[u["id"] for u in e_sorted], e_kind=e_kind, e_raw=e_raw,
            e_faction=[u["faction_name"] for u in e_sorted], n4_raw=n4, n5_raw=n5, n6_raw=n6, n7_raw=n7, n8_raw=n8, n10_raw=n10, n12_raw=n12, expansion_sites=sites,
            card_ids=card_ids, card_raw=card_raw, n13_slots=n13, n13_factions=n13_factions, n13_pressure=n13_pressure, n14_regions=n14r, n14_global=n14g,
            n14_worst=worst,
            extra={"frame": fr, "ccs": fr.ccs, "known_buildings": fr.known_b, "nests": fr.nests, "own_buildings": fr.own_b, "own_units": fr.own_u,
                   "enemy_units": e_sorted, "vis_regions": fr.vis_regions, "now_ms": fr.now_ms})
        for name, a in obs.arrays().items():
            if not np.isfinite(a).all():
                raise FloatingPointError(f"non-finite feature in {name} for {self.faction}")
        return obs
