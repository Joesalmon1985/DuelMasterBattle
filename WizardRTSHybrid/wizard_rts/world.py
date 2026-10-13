"""One authoritative hybrid world.

Python owns entities, stocks, clocks, and duel outcomes. Godot only presents
this snapshot and sends pose, advance, interact, and resolve commands.
Crossing a hex updates the player hex and does not advance game time.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sim.dmb.adventure.duels import HazardDuelService  # noqa: E402
from sim.dmb.core.state import WorldState  # noqa: E402
from sim.dmb.core.types import WorldId  # noqa: E402
from sim.dmb.hazards.service import CatastropheService  # noqa: E402
from sim.dmb.player.visits import VisitService  # noqa: E402
from sim.dmb.time.clock import ClockService  # noqa: E402

from wizard_rts.coords import hex_center_tile, in_map, neighbors, tile_in_map, tile_to_hex  # noqa: E402
from wizard_rts import grid, mapgen, terrain as terrain_mod  # noqa: E402
from wizard_rts.economy import PROVENANCE as ECONOMY_PROVENANCE  # noqa: E402
from wizard_rts.economy import SCHEDULE_PROVENANCE  # noqa: E402
from wizard_rts.widelands_stock import EconomyTotals  # noqa: E402
from wizard_rts.economy import economy_quantum  # noqa: E402
from wizard_rts.logistics import add_road, logistics_quantum  # noqa: E402
from wizard_rts import rules
from wizard_rts import tribes
from wizard_rts.animals import spawn_animal
from wizard_rts.programs_data import RESOURCE_PER_NODE, ROCK_AMOUNT, START_WARES
from wizard_rts.workers import forestry_quantum, new_id, plant_tree, find_path, TreeDict  # noqa: E402
from wizard_rts.military import MOVEMENT_PROVENANCE  # noqa: E402
from wizard_rts.military import PROVENANCE as MILITARY_PROVENANCE  # noqa: E402
from wizard_rts.military import init_unit, military_quantum, order_attack, order_move, order_stop
from wizard_rts.lifecycle import begin_destruction, lifecycle_quantum
from wizard_rts import disruption, feed, history, nests, regions, settlements, society, story, tech, trade, vp
from wizard_rts.industry import sim as industry
from wizard_rts.ai import ai_quantum
from wizard_rts import construction as con  # noqa: E402
from wizard_rts import diagnostics, territory  # noqa: E402
from wizard_rts.openra_damage import damage_versus, inflict_damage, warhead_damage  # noqa: E402

WORLD_ID = "hybrid.world"

# building size each showcase kind needs on the terrain (Widelands buildcaps: small/medium/big/mine)
SHOWCASE_SIZE = {
    "mine": "mine", "ironmine": "mine", "smelter": "medium", "smithy": "medium", "quarry": "small",
    "tavern": "medium", "farm": "big", "bakery": "medium", "hunter": "small", "well": "small",
    "barracks": "medium", "vehicle_factory": "big", "defense": "small",
}
SHOWCASE_RES = {"mine": "coal", "ironmine": "iron"}
MIN_MINE_DEPOSIT = 150

# name, axial hex of the capital, display colour (hex RGB)
FACTIONS = (
    ("Red", (2, 2), "#d63a3a"),
    ("Blue", (6, 3), "#3a6ad6"),
    ("Green", (10, 4), "#3fae49"),
    ("Yellow", (3, 7), "#e0c63a"),
    ("Purple", (8, 8), "#8e4ad0"),
    ("Orange", (13, 7), "#e8892e"),
)


class EventLog(list):
    """The bounded event window. Every AI decision event is also counted per faction (fstats), so long runs keep exact totals
    after old events have been trimmed away."""

    def __init__(self, world: Any) -> None:
        super().__init__()
        self._world = world
        self.total = 0  # every event ever appended: a reader of the bounded window knows how many are new since it last looked

    def append(self, e: dict) -> None:  # type: ignore[override]
        kind = e.get("kind", "")
        if kind.startswith("ai_") and e.get("faction"):
            self._world.fstat(e["faction"], kind)
        if kind == "ai_attack" and e.get("faction") and e.get("of"):
            trade.note_hostility(self._world, e["faction"], e["of"])  # an attack ends any peace for trade
        if kind in feed.KINDS:
            feed.capture(self._world, e)
        self.total = getattr(self, "total", 0) + 1
        super().append(e)


PRIMITIVE_SHOWCASE = ("quarry", "hunter", "well")  # with the producer, sawmill and ranger every start has: D15 "bare-bones Widelands facilities"


class HybridWorld:
    def __init__(self, seed: int = 507, minimal: bool = False, terrain: bool | None = None, map_size: str = "standard",
                 profile: str | None = None, start_perm: list[int] | None = None) -> None:
        """terrain=True builds the square-grid Widelands-derived map; terrain=False is the legacy flat world.

        None reads HYBRID_TERRAIN (default "1"). The legacy world stays available so the
        pre-terrain tests and a flat bench keep working (DECISIONS D5).
        """
        if terrain is None:
            terrain = os.environ.get("HYBRID_TERRAIN", "1") != "0"
        self.profile = profile or ("test_minimal" if minimal else "test_showcase")  # tech.PROFILES; the server defaults to "campaign"
        tech.profile_flags(self.profile)
        self.start_perm = list(start_perm) if start_perm else None  # S07: which homeland each faction (in FACTIONS order) starts on
        self.cycle_pending = False
        self.era_index = 0
        self.draft_interval_ms = tech.DRAFT_INTERVAL_MS
        self.terrain: terrain_mod.TerrainGrid | None = mapgen.generate(int(seed), map_size) if terrain else None
        self.map_size = map_size
        self.move_dirs = grid.DIRS4 if terrain else grid.DIRS8
        self.seed = int(seed)
        self.dmb = WorldState(world_id=WorldId(WORLD_ID))
        self.clock = ClockService(self.dmb.clock)
        self.buildings: dict[str, dict[str, Any]] = {}
        self.carriers: dict[str, dict[str, Any]] = {}
        self.units: dict[str, dict[str, Any]] = {}
        self.roads: dict[str, list[tuple[int, int]]] = {}
        self.road_tile_set: set[tuple[int, int]] = set()
        self.road_edges: dict[str, tuple[str, str]] = {}
        self.adjacency: dict[str, list[tuple[str, str]]] = {}
        self.node_wares: dict[str, list[dict[str, Any]]] = {}
        self.shortages: dict[tuple[str, str], int] = {}
        self.recipe_requests: dict[str, dict[str, int]] = {}
        self.rocks: dict[str, dict[str, Any]] = {}
        self.animals: dict[str, dict[str, Any]] = {}
        self.projectiles: list[dict[str, Any]] = []
        self.effects: list[dict[str, Any]] = []
        self.ai_enabled = os.environ.get("HYBRID_AI", "1") != "0"
        self.ai_factions: set[str] | None = None  # None: the built-in AI plays every faction; a set restricts it (training agents play the rest)
        self.resources: dict[tuple[int, int], dict[str, int]] = {}
        self.trees: dict[str, dict[str, Any]] = TreeDict()
        self.tree_tiles: dict[tuple[int, int], str] = {}
        self.workers: dict[str, dict[str, Any]] = {}
        self.reserved_tiles: set[tuple[int, int]] = set()
        self.counters: dict[str, int] = {}
        self.rng = random.Random(int(seed))
        self.time_scale = 1
        self.path_searches = 0
        self.join_searches = 0
        self.carrier_respawn: dict[str, int] = {}  # road id -> ms until a new carrier walks out (logistics.carrier_quantum)
        self.cc_ids: dict[str, None] = {}  # warehouses = command centres, in creation order (a dict, not a set: string hashes are salted per process and would make runs differ)
        self.cc_buffer = territory.BUFFER  # extra tiles between two command centres' build areas
        self.faction_info: dict[str, dict[str, str]] = {}
        self.controlled_faction = ""
        self.stocks: dict[str, dict[str, int]] = {}
        self.economy_totals = EconomyTotals()
        self.blocked: set[tuple[int, int]] = set()
        self.events: list[dict[str, Any]] = EventLog(self)
        self.economy_quanta = 0
        self.military_quanta = 0
        self.fstats: dict[str, dict[str, float]] = {}
        self.layout_notes: list[str] = []  # what the opening layout could not place on this map
        self.stats = {"deliver": 0, "blocked": 0, "move": 0, "attack": 0, "destroyed": 0, "produce": 0}
        self.hazard_id = ""
        self.hazard_tile: tuple[int, int] | None = None
        self.player = {"tx": 0, "ty": 0, "facing": "down"}
        self._pending_links: list[tuple[str, str]] = []
        if minimal:
            self._layout_minimal()
        else:
            self._layout()
        tech.init_world(self)
        industry.init_world(self)
        vp.era_state(self)

    def tile_in_map(self, tx: int, ty: int) -> bool:
        """True where a ground unit, worker, carrier or road may be. With terrain: inside the grid and on land."""
        if self.terrain is not None:
            return self.terrain.ground(tx, ty)
        return tile_in_map(tx, ty)

    def state_hash(self) -> str:
        """SHA-1 of the canonical snapshot plus the live terrain layers: identical seed and commands give identical hashes."""
        import hashlib
        import json

        h = hashlib.sha1(json.dumps(self.snapshot(), sort_keys=True, default=str).encode())
        if self.terrain is not None:
            h.update(self.terrain.state_hash().encode())
        return h.hexdigest()

    def tile_speed(self, loco: str | None, x: int, y: int) -> int:
        """Percent speed of this locomotor on a tile (0 = cannot enter). OpenRA Locomotor.TerrainSpeeds over our terrain classes."""
        t = self.terrain
        if t is None:
            return 100 if (tile_in_map(x, y) and loco not in ("naval", "lcraft")) else 0
        if not (0 <= x < t.w and 0 <= y < t.h):
            return 0
        i = y * t.w + x
        pct = rules.speed_table(loco or "foot")[t.cls[i]]
        if pct and t.cls[i] != terrain_mod.WATER and (x, y) in self.road_tile_set:
            pct = max(pct, rules.road_speed(loco or "foot"))
        return pct

    def tile_in_bounds(self, tx: int, ty: int) -> bool:
        if self.terrain is not None:
            return self.terrain.in_bounds(tx, ty)
        return tile_in_map(tx, ty)

    # ---- terrain-backed resources (legacy worlds keep the dict) ----------
    def resource_nodes(self, center: tuple[int, int], radius: int, res: str) -> list[tuple[int, int]]:
        if self.terrain is not None:
            return self.terrain.nodes_with(center[0], center[1], radius, res)
        return [
            (tx, ty) for (tx, ty), amounts in self.resources.items()
            if max(abs(tx - center[0]), abs(ty - center[1])) <= radius and amounts.get(res, 0) > 0
        ]

    def resource_amount(self, node: tuple[int, int], res: str) -> int:
        if self.terrain is not None:
            return self.terrain.amount(node[0], node[1], res)
        return self.resources.get(node, {}).get(res, 0)

    def resource_total(self, center: tuple[int, int], radius: int, res: str) -> int:
        if self.terrain is not None:
            return self.terrain.total(center[0], center[1], radius, res)
        return sum(self.resources.get((center[0] + dx, center[1] + dy), {}).get(res, 0)
                   for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1))

    def take_resource(self, node: tuple[int, int], res: str, n: int = 1) -> int:
        if self.terrain is not None:
            return self.terrain.take(node[0], node[1], res, n)
        have = self.resources.get(node, {}).get(res, 0)
        got = min(have, n)
        if got:
            self.resources[node][res] = have - got
        return got

    def tile_info(self, tx: int, ty: int) -> dict[str, Any]:
        """What the terrain says about one node (God Mode inspector, tests)."""
        t = self.terrain
        if t is None:
            return {"status": "ok", "terrain": "legacy", "ground": tile_in_map(tx, ty)}
        if not t.in_bounds(tx, ty):
            return {"status": "rejected", "reason": "outside_map"}
        res, amt = t.resource(tx, ty)
        d = t.terrain_def(tx, ty)
        i = ty * t.w + tx
        return {
            "status": "ok", "terrain": t.terrain_name(tx, ty), "is": d["is"], "height": t.height[i],
            "ground": t.ground(tx, ty), "swim": t.swimmable(tx, ty), "build": t.build_cap_name(tx, ty),
            "resource": res, "amount": amt, "depth": t.depth[i], "water_component": t.water_comp[i],
            "tree": self.tree_tiles.get((tx, ty), ""), "road": (tx, ty) in self.road_tile_set,
            "fertility": t.environment(tx, ty)[1],
        }

    def resource_region(self, x0: int, y0: int, x1: int, y1: int, limit: int = 20000) -> list[list[int]]:
        """[x, y, kind, amount] for every node with a deposit or fish in the rectangle (live amounts)."""
        t = self.terrain
        if t is None:
            return []
        out: list[list[int]] = []
        for y in range(max(0, y0), min(t.h, y1 + 1)):
            for x in range(max(0, x0), min(t.w, x1 + 1)):
                i = y * t.w + x
                if t.res_kind[i] in (1, 2, 3, 4, 5) and t.res_amt[i] > 0:
                    out.append([x, y, t.res_kind[i], t.res_amt[i]])
                    if len(out) >= limit:
                        return out
        return out

    def terrain_free_sites(self, size: str, within=lambda p: True):
        """Yield free tiles where a building of this size could stand (test and AI helper)."""
        t = self.terrain
        for y in range(t.h):
            for x in range(t.w):
                p = (x, y)
                if within(p) and t.can_build(x, y, size) and p not in self.blocked and p not in self.tree_tiles and p not in self.road_tile_set:
                    yield p

    def can_build(self, tile: tuple[int, int], size: str) -> bool:
        """Terrain says a building of this size may stand here (always true on the legacy flat world)."""
        if self.terrain is None:
            return tile_in_map(*tile)
        return self.terrain.can_build(tile[0], tile[1], size)

    def damage_building(
        self,
        building_id: str,
        raw_damage: int,
        target_types: list[str],
        versus: dict[str, int] | None = None,
        by: str = "",
    ) -> int:
        """One shared hit. A weapon that does not list the target type deals nothing."""
        building = self.buildings.get(building_id)
        if building is None or building.get("target_type") not in target_types:
            return 0
        if int(building.get("hp", 0)) <= 0:
            return 0
        if by:
            building["last_hit_by"] = by
            sh = self.units.get(by) or self.buildings.get(by)
            if sh is not None:
                trade.note_hostility(self, sh.get("faction_name", ""), building.get("faction_name", ""))  # who dealt the last blow (a blight nest credits the faction that cleared a cube)
        versus_percent = damage_versus(versus or {}, [str(building.get("armor", ""))])
        applied = warhead_damage(int(raw_damage), [], versus_percent)
        before = int(building["hp"])
        building["hp"] = inflict_damage(before, int(building["max_hp"]), applied)
        if before > 0 and int(building["hp"]) <= 0:
            begin_destruction(self, building)
            self.stats["destroyed"] += 1
            self.stats["buildings_lost"] = self.stats.get("buildings_lost", 0) + 1
            self.effects.append({"t": "explosion", "x1": building["tx"], "y1": building["ty"], "x2": building["tx"], "y2": building["ty"], "ttl_ms": 2500, "keep": 3, "p": ""})
            self.events.append({"kind": "building_destroyed", "id": building_id, "faction": building["faction_name"]})
            vp.on_destroyed(self, building, by)
            self.fstat(building["faction_name"], "building_losses")
            shooter = self.units.get(by) or self.buildings.get(by)
            if shooter is not None:
                self.fstat(shooter["faction_name"], "nest_kills" if building.get("kind") == "blight_nest" else "building_kills")  # a nest is no war
        return before - int(building["hp"])

    def status_text(self, b: dict[str, Any]) -> str:
        """Why a building is doing what it is doing, in plain words (God Mode inspector)."""
        now = int(self.dmb.clock.get("game_ms", 0))
        if int(b.get("hp", 1)) <= 0:
            return "destroyed"
        site = b.get("constructing")
        if site:
            stock = self.stocks.get(b["id"], {})
            need = ["%s %d" % (g, n - int(stock.get(g, 0))) for g, n in site["cost"].items() if int(stock.get(g, 0)) < n]
            if not self.adjacency.get(b["id"]) and b["kind"] != "warehouse":
                return "Under construction: needs a road to receive " + ", ".join(need) if need else "Under construction"
            return "Under construction: waiting for " + ", ".join(need) if need else "Building (%d%%)" % int(100 * site["progress_ms"] / 20_000)
        if b["kind"].startswith("mdy:"):
            text = industry.status_text(self, b)
            if b["kind"] == "mdy:conveyor":
                return "Conveyor run: %d tiles" % len(b.get("line", {}).get("tiles", []))
            return text or "Idle"
        if b["kind"] not in ("warehouse", "ranger", "defense") and not self.adjacency.get(b["id"]) and b.get("operational", True):
            return "No road: goods cannot arrive or leave"
        if b.get("queue"):
            head = b["queue"][0]
            return "Recruiting %s (%s)" % (head["unit"], head["state"] if head["state"] != "waiting" else "waiting for goods")
        if b.get("disrupted"):
            d = b["disrupted"]
            need = ", ".join("%s %d" % (g, n) for g, n in d["repair"].items())
            stock = self.stocks.get(b["id"], {})
            if any(int(stock.get(g, 0)) < n for g, n in d["repair"].items()):
                return "Closed: %s. Waiting for repair wares (%s)" % (d["label"], need)
            return "Closed: %s. Repair %d%%" % (d["label"], int(100 * int(d["progress_ms"]) / max(1, int(d["repair_ms"]))))
        if b.get("working"):
            return "Working"
        stall = b.get("stall")
        if stall and now - int(stall["at_ms"]) < 45_000:
            texts = {"inputs": "Stopped: " + stall["detail"], "worker": "Stopped: its worker found " + (stall["detail"] or "no work"), "not_needed": "Idle: " + stall["detail"]}
            return texts.get(stall["reason"], "Stopped: " + stall["reason"])
        if b.get("worker_ids") is not None and any(r not in self.workers for r in b["worker_ids"].values()):
            return "Waiting for a worker"
        return "Working" if b.get("waiting_worker") else "Idle"

    def note_produced(self, faction: str, entity: str) -> None:
        """Count a completed building or produced unit by entity id (`wl:...`, `barracks`, `unit:tank`) with the time of the first one.
        Kept outside the snapshot: it feeds the inspector and the content reports and must not change the state hash."""
        rec = self.__dict__.setdefault("entity_stats", {}).setdefault(faction, {}).setdefault(entity, {"count": 0, "first_ms": int(self.dmb.clock.get("game_ms", 0))})
        rec["count"] += 1

    def fstat(self, faction: str, key: str, amount: float = 1) -> None:
        """Per-faction counters (kills, losses): the reward signals of the training interface and a battle report."""
        d = self.fstats.setdefault(faction, {})
        d[key] = d.get(key, 0) + amount

    def tile_blocked_for_carrier(self, tile: tuple[int, int]) -> bool:
        if self.hazard_tile is None or not self._hazard_active():
            return False
        return tile == self.hazard_tile

    def _hazard_active(self) -> bool:
        cube = (self.dmb.hazards.get("catastrophe", {}).get("cubes") or {}).get(self.hazard_id)
        return bool(cube and cube.get("active", True))

    def _layout_minimal(self) -> None:
        """One faction with a warehouse and nothing else: an isolated bench for single-building tests."""
        name, (q, r), color = FACTIONS[0]
        faction_id = str(self.dmb.ids.new("faction"))
        centre = self._home_center(q, r)
        warehouse = self._building(faction_id, name, "warehouse", centre, "Warehouse", "widelands.warehouse")
        self.faction_info[name] = {"id": faction_id, "name": name, "color": color}
        self.player = {"tx": centre[0] + 20, "ty": centre[1], "facing": "up"}

    def _layout(self) -> None:
        placed = [self._place_faction(name, q, r) for name, (q, r), _color in FACTIONS]
        red, blue = placed[0], placed[1]
        for (name, _hex, color), info in zip(FACTIONS, placed):
            self.faction_info[name] = {"id": info["faction"], "name": name, "color": color, "tribe": tribes.FACTION_TRIBES.get(name, "barbarians")}
        for name, bid in self._pending_links:
            wh = con.faction_warehouse(self, name)
            res = con.build_road(self, name, bid, wh["id"])
            assert res["status"] == "ok", res
        if self.terrain is not None:
            self._plant_features()
        # Stand just east of the red settlement so the town is in frame at
        # playable zoom. Hex (2, 3)'s center is a full hex away and hides it.
        start = self._stand_near(red["road"])
        self.player = {"tx": start[0], "ty": start[1], "facing": "up"}
        self._place_hazard(red["road_a"])
        self.events.append({"kind": "layout", "factions": [red["faction"], blue["faction"]]})

    def _home_center(self, q: int, r: int) -> tuple[int, int]:
        if self.terrain is not None:
            idx = [f[1] for f in FACTIONS].index((q, r))
            if self.start_perm:
                idx = self.start_perm[idx]
            return tuple(self.terrain.starts[idx])
        return hex_center_tile(q, r)

    def _place_faction(self, name: str, q: int, r: int) -> dict[str, Any]:
        faction_id = str(self.dmb.ids.new("faction"))
        center = self._home_center(q, r)
        warehouse_tile = center
        producer_tile = self._offset_owned(q, r, center, -4, 0)
        processor_tile = self._offset_owned(q, r, center, 4, 1)
        warehouse = self._building(
            faction_id, name, "warehouse", warehouse_tile, "Warehouse", "widelands.warehouse"
        )
        producer = self._building(
            faction_id, name, "producer", producer_tile, "Lumberjack", "widelands.lumberjack"
        )
        processor = self._building(
            faction_id, name, "processor", processor_tile, "Sawmill", "widelands.sawmill"
        )
        road_a = _path(producer_tile, warehouse_tile)
        road_b = _path(warehouse_tile, processor_tile)
        road_tiles = road_a + road_b[1:]
        add_road(self, faction_id, name, producer, warehouse, road_a)
        add_road(self, faction_id, name, warehouse, processor, road_b)
        from wizard_rts.economy import produce

        stock = dict(START_WARES)
        for good, n in tribes.starter_stock(tribes.FACTION_TRIBES.get(name, "barbarians")).items():
            stock[good] = max(stock.get(good, 0), n)
        stock.update({"recruit": 8, "carrier": 8})
        for good, n in stock.items():
            produce(self, warehouse, good, n)
        ranger_tile = self._free_in_hex(q, r, center, -6, 3, set(road_tiles))
        self._building(faction_id, name, "ranger", ranger_tile, "Ranger's hut", "widelands.rangers_hut")
        if self.terrain is None:
            self._plant_forest(producer_tile, set(road_tiles))
        primitive_start = tech.PROFILES[self.profile]["primitive_start"]
        self._place_showcase(faction_id, name, q, r, center, set(road_tiles), only=PRIMITIVE_SHOWCASE if primitive_start else None)
        unit_tile = self._offset_owned(q, r, center, 0, 3)
        self._unit(faction_id, name, "soldier", "Soldier", "widelands.soldier", unit_tile)
        if primitive_start:  # D15: a bare-bones start, no OpenRA units until the cards for them are drafted
            return {"faction": faction_id, "road": road_tiles, "road_a": road_a, "warehouse": warehouse}
        infantry_tile = self._free_in_hex(q, r, center, 1, 4, set())
        self._unit(faction_id, name, "infantry", "Rifleman", "openra.e1", infantry_tile)
        tank_tile = self._free_in_hex(q, r, center, -2, 4, set())
        self._unit(faction_id, name, "tank", "Tank", "openra.3tnk", tank_tile)
        return {"faction": faction_id, "road": road_tiles, "road_a": road_a, "warehouse": warehouse}

    def _plant_forest(self, around: tuple[int, int], avoid: set[tuple[int, int]]) -> None:
        """A mixed-age forest. Persistent ids, staggered growth timers."""
        stages = ["old"] * 14 + ["mature"] * 4 + ["pole"] * 3 + ["sapling"] * 2
        for stage in stages:
            for _ in range(30):
                tile = (around[0] + self.rng.randint(-8, 8), around[1] + self.rng.randint(-8, 8))
                if tile in avoid or tile == around or not self._tile_open_anywhere(tile, set()):
                    continue
                if tile in self.tree_tiles:
                    continue
                tree_id = plant_tree(self, tile, stage)
                self.trees[tree_id]["timer_ms"] = int(self.trees[tree_id]["timer_ms"] * (0.2 + 0.8 * self.rng.random()))
                break

    def _place_showcase(
        self,
        faction_id: str,
        name: str,
        q: int,
        r: int,
        center: tuple[int, int],
        road: set[tuple[int, int]],
        only: tuple[str, ...] | None = None,
    ) -> None:
        """Real buildings from both games, sharing this faction's hex. `only` restricts the kinds (the primitive campaign start)."""
        specs = (
            ("mine", "widelands.coalmine", "Coal mine", -12, 5),
            ("ironmine", "widelands.ironmine", "Iron mine", -12, -3),
            ("smelter", "widelands.smelting_works", "Smelting works", -9, -5),
            ("smithy", "widelands.ax_workshop", "Ax workshop", 6, -8),
            ("quarry", "widelands.quarry", "Quarry", -4, 9),
            ("tavern", "widelands.tavern", "Tavern", -10, -8),
            ("farm", "widelands.farm", "Farm", 1, -11),
            ("bakery", "widelands.bakery", "Bakery", -6, -10),
            ("hunter", "widelands.hunters_hut", "Hunter's hut", -14, 2),
            ("well", "widelands.well", "Well", 4, -5),
            ("barracks", "openra.barracks", "Barracks", 11, -6),
            ("vehicle_factory", "openra.weap", "War factory", 12, 7),
            ("defense", "openra.gun", "Turret", 5, 9),
        )
        for kind, definition, label, dx, dy in specs:
            if only is not None and kind not in only:
                continue
            if self.terrain is not None:
                try:
                    tile = self._site(center, dx, dy, SHOWCASE_SIZE[kind], road, SHOWCASE_RES.get(kind), extra=con.GROUND_FOOTPRINT.get(kind))
                except RuntimeError as exc:  # an imported map may have no deposit or space within reach of this start
                    self.layout_notes.append(f"{name}: no {kind} ({exc})")
                    continue
            else:
                tile = self._free_in_hex(q, r, center, dx, dy, road)
            bid = self._building(faction_id, name, kind, tile, label, definition)
            if self.terrain is not None and kind in con.GROUND_FOOTPRINT:
                fp = [list(tile)] + [[tile[0] + ox, tile[1] + oy] for ox, oy in con.GROUND_FOOTPRINT[kind]]
                self.buildings[bid]["ground_footprint"] = fp
                self.blocked.update((int(a), int(b)) for a, b in fp)
            if kind in ("barracks", "vehicle_factory", "mine", "ironmine", "smelter", "smithy", "quarry",
                        "farm", "tavern", "bakery", "hunter", "well"):
                self._pending_links.append((name, bid))
            if self.terrain is None:
                if kind in ("mine", "ironmine"):
                    self._seed_resource(tile, "coal" if kind == "mine" else "iron")
                if kind == "well":
                    self._seed_resource(tile, "water")
        if self.terrain is not None:
            return  # the generated map carries its own game (terrain.features["animals"], planted with the forests)
        self._place_scenery(faction_id, name, center, road)
        for res, (dx, dy) in (("gold", (-8, -12)), ("stones", (7, 11))):
            self._seed_resource(self._free_in_hex(q, r, center, dx, dy, road), res)
        for k in range(8):
            for _ in range(20):
                tile = (center[0] + self.rng.randint(-16, 16), center[1] + self.rng.randint(-14, 14))
                if tile_to_hex(*tile) == (q, r) and tile_in_map(*tile) and tile not in self.blocked and tile not in road and tile not in self.tree_tiles:
                    spawn_animal(self, tile, "deer" if k % 3 else "bunny")
                    break

    def _site(self, center: tuple[int, int], dx: int, dy: int, size: str | None, avoid: set, res: str | None = None, max_r: int = 45, extra: list | None = None) -> tuple[int, int]:
        """Nearest free tile to center+(dx, dy) where terrain allows this building size (None: any ground).

        A mine needs a deposit of `res` within the programme radius under it.
        """
        px, py = center[0] + dx, center[1] + dy
        t = self.terrain
        reach = self._reach_from(center)
        for r in range(0, max_r + 1):
            for tile in grid.ring(px, py, r):
                if tile not in reach:
                    continue
                if tile in self.blocked or tile in avoid or tile in self.tree_tiles or tile in self.road_tile_set:
                    continue
                if size is None:
                    if not self.tile_in_map(*tile):
                        continue
                elif not t.can_build(tile[0], tile[1], size):
                    continue
                if res is not None and t.total(tile[0], tile[1], 2, res) < MIN_MINE_DEPOSIT:
                    continue
                if extra and not all(
                    t.ground(tile[0] + ox, tile[1] + oy) and (tile[0] + ox, tile[1] + oy) not in self.blocked
                    and (tile[0] + ox, tile[1] + oy) not in avoid and (tile[0] + ox, tile[1] + oy) not in self.tree_tiles
                    and (tile[0] + ox, tile[1] + oy) not in self.road_tile_set and t.can_build(tile[0] + ox, tile[1] + oy, "small")
                    for ox, oy in extra
                ):
                    continue
                return tile
        raise RuntimeError(f"no {size} site near {(px, py)}" + (f" with {res}" if res else ""))

    def _reach_from(self, centre: tuple[int, int], limit: int = 58) -> dict[tuple[int, int], int]:
        """Ground tiles within `limit` steps of centre (static terrain only), so a site can always be reached by road."""
        cache = self.__dict__.setdefault("_reach_cache", {})
        if centre in cache:
            return cache[centre]
        dist = {centre: 0}
        frontier = [centre]
        t = self.terrain
        while frontier:
            nxt = []
            for x, y in frontier:
                d = dist[(x, y)] + 1
                if d > limit:
                    continue
                for dx, dy in grid.DIRS4:
                    n = (x + dx, y + dy)
                    if n not in dist and t.ground(*n):
                        dist[n] = d
                        nxt.append(n)
            frontier = nxt
        cache[centre] = dist
        return dist

    def _spawn_wildlife(self, center: tuple[int, int], road: set) -> None:
        for k in range(8):
            for _ in range(30):
                tile = (center[0] + self.rng.randint(-18, 18), center[1] + self.rng.randint(-16, 16))
                if self.tile_in_map(*tile) and tile not in self.blocked and tile not in road and tile not in self.tree_tiles:
                    spawn_animal(self, tile, "deer" if k % 3 else "bunny")
                    break

    def _plant_features(self) -> None:
        """Turn the generator's tree and rock data into persistent world objects."""
        occupied = self.blocked | self.road_tile_set
        caps = [tuple(h["capital"]) for h in self.terrain.meta.get("homes", [])] if isinstance(self.terrain.meta, dict) else []
        for x, y, species, stage in self.terrain.features["trees"]:
            tile = (x, y)
            if tile in occupied or tile in self.tree_tiles or not self.tile_in_map(x, y):
                continue
            if self._thinned(tile, caps):
                continue
            tree_id = plant_tree(self, tile, stage, species)
            self.trees[tree_id]["timer_ms"] = int(self.trees[tree_id]["timer_ms"] * (0.2 + 0.8 * self.rng.random()))
        for x, y, species in self.terrain.features.get("animals", []):
            tile = (x, y)
            if tile in occupied or tile in self.tree_tiles or not self.tile_in_map(x, y):
                continue
            spawn_animal(self, tile, species)
        for x, y in self.terrain.features["rocks"]:
            tile = (x, y)
            if tile in occupied or tile in self.tree_tiles or not self.tile_in_map(x, y):
                continue
            rock_id = new_id(self, "rock")
            self.rocks[rock_id] = {
                "id": rock_id, "class": "rock", "kind": "rock", "definition": "widelands.rocks",
                "tx": x, "ty": y, "amount": ROCK_AMOUNT, "reserved_by": "",
            }

    @staticmethod
    def _thinned(tile: tuple[int, int], capitals: list[tuple[int, int]]) -> bool:
        """Owner playtest (12 Oct 2026): settlement woods were overcrowded. Two in five trees of the homeland woods 12 to 26 tiles from a
        capital are not planted; the settlement core and the lumberjack grove keep the generator's layout.
        Decided per tile by a hash, so the map generator's own random stream (and every other feature) is unchanged."""
        import zlib

        for cx, cy in capitals:
            d2 = (tile[0] - cx) ** 2 + (tile[1] - cy) ** 2
            if d2 > 26 * 26:
                continue
            if d2 < 144:
                return False  # the core of the settlement (and the lumberjack grove) keeps the generator's layout
            return zlib.crc32(f"thin:{tile[0]},{tile[1]}".encode()) % 5 < 2
        return False

    def _seed_resource(self, around: tuple[int, int], resource: str) -> None:
        """A 5 by 5 resource field centred on the mine (the programme radius is 2)."""
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                node = (around[0] + dx, around[1] + dy)
                self.resources.setdefault(node, {})[resource] = RESOURCE_PER_NODE[resource]

    def _place_scenery(
        self,
        faction_id: str,
        name: str,
        center: tuple[int, int],
        road: set[tuple[int, int]],
    ) -> None:
        scatter = []
        for _ in range(18):  # a quarry field big enough for a long game
            scatter.append((self.rng.randint(-9, -1), self.rng.randint(6, 13)))
        for dx, dy in ((-7, 8), (-8, 11), (-6, 12), (-1, 12), (-10, 9), (8, 2), *scatter):
            tile = (center[0] + dx, center[1] + dy)
            if not tile_in_map(*tile) or tile in self.blocked or tile in road or tile in self.tree_tiles:
                continue
            rock_id = new_id(self, "rock")
            self.rocks[rock_id] = {
                "id": rock_id, "class": "rock", "kind": "rock", "definition": "widelands.rocks",
                "tx": tile[0], "ty": tile[1], "amount": ROCK_AMOUNT, "reserved_by": "",
            }

    def _unit(
        self,
        faction_id: str,
        name: str,
        kind: str,
        label: str,
        definition: str,
        tile: tuple[int, int],
    ) -> str:
        unit_id = str(self.dmb.ids.new("unit"))
        self.units[unit_id] = {
            "id": unit_id,
            "faction": faction_id,
            "faction_name": name,
            "kind": kind,
            "label": f"{name} {label}",
            "definition": definition,
            "tx": tile[0],
            "ty": tile[1],
            "alive": True,
            "facing": "s",
            "status": "idle",
        }
        init_unit(self.units[unit_id])
        return unit_id

    def _building(
        self,
        faction_id: str,
        name: str,
        kind: str,
        tile: tuple[int, int],
        label: str,
        definition: str = "",
        block: bool = True,
    ) -> str:
        building_id = str(self.dmb.ids.new("building"))
        record: dict[str, Any] = {
            "id": building_id,
            "faction": faction_id,
            "faction_name": name,
            "kind": kind,
            "label": f"{name} {label}",
            "tx": tile[0],
            "ty": tile[1],
        }
        if definition:
            record["definition"] = definition
        if kind == "warehouse":
            self.cc_ids[building_id] = None
            record["command_center"] = True  # a warehouse is the faction's immobile command centre: it sets the build area
            record["territory"] = territory.HOME_RADIUS
        if kind not in ("tree", "rock"):
            r = rules.actor(definition) if definition.startswith("openra.") else None
            # OpenRA buildings take their rules HP; Widelands buildings have none, so 500 HP (50000) is hybrid-defined. A home warehouse
            # (the capital, the faction's last stand) holds 2000 HP: at 500 a Prehistoric band razed a capital in seconds (12 Oct 2026)
            record["hp"] = record["max_hp"] = int(r["hp"]) if r else (200_000 if kind == "warehouse" else 50_000)
            record["target_type"] = "structure"
            record["armor"] = (r["armor"] if r else "Wood") or "Wood"
            if kind == "warehouse" and not r:
                record["armor"] = "Concrete"  # a capital is stone-built: Prehistoric clubs and spears barely scratch it, siege weapons can take it
            record["operational"] = True
        self.buildings[building_id] = record
        self.stocks[building_id] = {}
        if kind == "warehouse":
            settlements.register(self, record)
        if block:
            self.blocked.add(tile)
        return building_id

    def _free_in_hex(
        self,
        q: int,
        r: int,
        center: tuple[int, int],
        dx: int,
        dy: int,
        avoid: set[tuple[int, int]],
    ) -> tuple[int, int]:
        if self.terrain is not None:
            return self._site(center, dx, dy, "small", avoid)
        preferred = (center[0] + dx, center[1] + dy)
        if self._tile_open_anywhere(preferred, avoid):
            return preferred
        for radius in range(1, 14):
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    cand = (center[0] + ox, center[1] + oy)
                    if self._tile_open_anywhere(cand, avoid):
                        return cand
        raise RuntimeError(f"no free tile in hex {(q, r)}")

    def _tile_open_anywhere(self, tile: tuple[int, int], avoid: set[tuple[int, int]]) -> bool:
        if tile in self.blocked or tile in avoid or not self.tile_in_map(*tile):
            return False
        return True

    def _tile_open(self, q: int, r: int, tile: tuple[int, int], avoid: set[tuple[int, int]]) -> bool:
        if tile in self.blocked or tile in avoid:
            return False
        return tile_to_hex(*tile) == (q, r)

    def _stand_near(self, road: list[tuple[int, int]]) -> tuple[int, int]:
        blocked = self.blocked
        road_set = set(road)
        if self.terrain is not None:
            cx, cy = self.terrain.starts[0]
            return self._site((cx, cy), 17, 2, None, road_set)
        for tile in ((100, 50), (102, 52), (98, 54), (104, 48), (96, 56)):
            east = (tile[0] + 1, tile[1])
            if tile in blocked or tile in road_set or east in blocked:
                continue
            if tile_in_map(*tile) and tile_in_map(*east):
                return tile
        return hex_center_tile(2, 3)

    def _offset_owned(self, q: int, r: int, center: tuple[int, int], dx: int, dy: int) -> tuple[int, int]:
        if self.terrain is not None:
            return self._site(center, dx, dy, "small", set())
        tile = (center[0] + dx, center[1] + dy)
        if tile_to_hex(*tile) == (q, r) and tile not in self.blocked:
            return tile
        for radius in range(1, 12):
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    cand = (center[0] + ox, center[1] + oy)
                    if cand in self.blocked:
                        continue
                    if tile_to_hex(*cand) == (q, r):
                        return cand
        raise RuntimeError(f"no free tile in hex {(q, r)}")

    def _place_hazard(self, road: list[tuple[int, int]]) -> None:
        tile = road[len(road) // 2]
        q, r = tile_to_hex(*tile)
        hex_id = f"hex:{q},{r}"
        added = CatastropheService(self.dmb).add_cube(hex_id, "demon")
        self.hazard_id = str(added["cube"]["id"])
        self.hazard_tile = tile

    WALKABLE_TREE_STAGES = ("sapling", "felled", "stump")

    def tree_solid(self, tree: dict[str, Any]) -> bool:
        """A grown tree is solid; saplings, stumps, felled trunks, fields, crops and bushes are not."""
        if not tree or tree.get("stage") in self.WALKABLE_TREE_STAGES or tree.get("species") == "wheat":
            return False
        if "imm" in tree:
            from wizard_rts import imm

            attrs = imm.attributes(tree) if hasattr(imm, "attributes") else []
            return "tree" in attrs or "normal_tree" in attrs
        return True

    def solid_for_wizard(self, tile: tuple[int, int]) -> bool:
        """True where a standing tree or a rock stands (the wizard walks round them, as Godot's local movement does)."""
        tid = self.tree_tiles.get(tile)
        if tid is not None and self.tree_solid(self.trees.get(tid, {})):
            return True
        idx = self.__dict__.get("_rock_index")
        if idx is None or idx[0] != len(self.rocks):
            idx = self._rock_index = (len(self.rocks), {(int(r["tx"]), int(r["ty"])) for r in self.rocks.values()})
        return tile in idx[1]

    def set_pose(self, tx: int, ty: int, facing: str = "down", snapshot: bool = True) -> dict[str, Any]:
        game_ms = int(self.dmb.clock.get("game_ms", 0))
        tile = (int(tx), int(ty))
        if not self.tile_in_map(*tile):
            return {"status": "rejected", "reason": "outside_map", "snapshot": self.snapshot() if snapshot else None}
        if tile in self.blocked:
            return {"status": "rejected", "reason": "blocked", "snapshot": self.snapshot() if snapshot else None}
        if self.solid_for_wizard(tile):  # P1.1: a standing tree or a rock is solid; saplings, stumps and cleared tiles are not
            return {"status": "rejected", "reason": "obstacle", "snapshot": self.snapshot() if snapshot else None}
        previous = tile_to_hex(self.player["tx"], self.player["ty"])
        self.player = {"tx": tile[0], "ty": tile[1], "facing": str(facing or "down")}
        current = tile_to_hex(tile[0], tile[1])
        if current != previous:
            self.events.append({"kind": "hex_cross", "from": list(previous), "to": list(current)})
        assert int(self.dmb.clock.get("game_ms", 0)) == game_ms
        return {"status": "ok", "snapshot": self.snapshot() if snapshot else None}

    def advance(self, ms: int, sequence: int, snapshot: bool = True, tree_sync: bool | None = None) -> dict[str, Any]:
        quanta = self.clock.request_advance(int(ms) * int(self.time_scale), int(sequence))
        for _ in range(quanta):
            forestry_quantum(self)
            economy_quantum(self)
            logistics_quantum(self)
            con.construction_quantum(self)
            industry.industry_quantum(self)
            story.story_quantum(self)
            vp.vp_quantum(self)
            regions.regions_quantum(self)
            nests.nest_quantum(self)
            trade.trade_quantum(self)
            disruption.disruption_quantum(self)
            society.society_quantum(self)
            history.history_quantum(self)
            con.recruitment_quantum(self)
            lifecycle_quantum(self)
            territory.deploy_quantum(self)
            tech.tech_quantum(self)
            diagnostics.watch_quantum(self)
            if self.ai_enabled:
                ai_quantum(self)
            military_quantum(self)
            if self.economy_quanta % 30 == 0:
                self.events.append({"kind": "ai_economy", "game_ms": int(self.dmb.clock.get("game_ms", 0))})
        return {"status": "ok", "quanta": quanta, "snapshot": self.snapshot(tree_sync=tree_sync) if snapshot else None}

    def set_speed(self, scale: int) -> dict[str, Any]:
        self.time_scale = max(1, min(int(scale), 60))
        return {"status": "ok", "time_scale": self.time_scale, "snapshot": self.snapshot()}

    # ---- commands shared by God Mode and AI -------------------------------
    def control(self, faction: str) -> dict[str, Any]:
        if faction and faction not in self.faction_info:
            return {"status": "rejected", "reason": "unknown_faction"}
        self.controlled_faction = faction
        self.events.append({"kind": "control", "faction": faction})
        return {"status": "ok", "snapshot": self.snapshot()}

    def _effects_for_snapshot(self) -> list[dict[str, Any]]:
        out = [dict(e) for e in self.effects]
        for e in self.effects:
            e["keep"] = max(0, int(e.get("keep", 0)) - 1)
        return out

    def _guard(self, faction: str) -> dict[str, Any] | None:
        if faction not in self.faction_info:
            return {"status": "rejected", "reason": "unknown_faction"}
        return None

    def build(self, faction: str, kind: str, tx: int, ty: int) -> dict[str, Any]:
        out = self._guard(faction) or con.place_building(self, faction, kind, tx, ty)
        out["snapshot"] = self.snapshot()
        return out

    def road(self, faction: str, a: str, b: str) -> dict[str, Any]:
        out = self._guard(faction) or con.build_road(self, faction, a, b)
        out["snapshot"] = self.snapshot()
        return out

    def queue(self, building: str, unit_kind: str) -> dict[str, Any]:
        out = con.queue_unit(self, building, unit_kind)
        out["snapshot"] = self.snapshot()
        return out

    def cancel(self, building: str, index: int) -> dict[str, Any]:
        out = con.cancel_queue(self, building, index)
        out["snapshot"] = self.snapshot()
        return out

    def move(self, units: list[str], tx: int, ty: int, attack_move: bool = False) -> dict[str, Any]:
        out = order_move(self, [str(u) for u in units], tx, ty, attack_move)
        out["snapshot"] = self.snapshot()
        return out

    def stop(self, units: list[str]) -> dict[str, Any]:
        out = order_stop(self, [str(u) for u in units])
        out["snapshot"] = self.snapshot()
        return out

    def rally(self, building: str, tx: int, ty: int) -> dict[str, Any]:
        b = self.buildings.get(building)
        if b is None or b["kind"] not in con.RECIPES or not self.tile_in_map(int(tx), int(ty)):
            return {"status": "rejected", "reason": "no_rally", "snapshot": self.snapshot()}
        b["rally"] = [int(tx), int(ty)]
        return {"status": "ok", "snapshot": self.snapshot()}

    def demolish(self, building: str) -> dict[str, Any]:
        b = self.buildings.get(building)
        if b is None or "hp" not in b:
            return {"status": "rejected", "reason": "no_building", "snapshot": self.snapshot()}
        if b["kind"] == "warehouse":
            return {"status": "rejected", "reason": "cannot_demolish_warehouse", "snapshot": self.snapshot()}
        self.damage_building(building, 10**9, ["structure"], {})
        return {"status": "ok", "snapshot": self.snapshot()}

    def belt(self, faction: str, tiles: list, end_dir: int | None = None) -> dict[str, Any]:
        from wizard_rts.industry import commands as ind_commands

        out = ind_commands.place_belt(self, faction, tiles, end_dir)
        out["snapshot"] = self.snapshot()
        return out

    def upgrade(self, faction: str, building: str, to_kind: str) -> dict[str, Any]:
        from wizard_rts.industry import commands as ind_commands

        out = ind_commands.upgrade_mine(self, faction, str(building), str(to_kind))
        out["snapshot"] = self.snapshot()
        return out

    def configure(self, faction: str, building: str, key: str, value: Any) -> dict[str, Any]:
        from wizard_rts.industry import commands as ind_commands

        out = ind_commands.configure(self, faction, str(building), str(key), value)
        out["snapshot"] = self.snapshot()
        return out

    def draft(self, faction: str, card_id: str) -> dict[str, Any]:
        out = tech.draft(self, faction, str(card_id))
        out["snapshot"] = self.snapshot()
        return out

    def grant_card(self, faction: str, card_id: str) -> dict[str, Any]:
        out = tech.grant(self, faction, str(card_id))
        out["snapshot"] = self.snapshot()
        return out

    def fire(self, target_id: str) -> dict[str, Any]:
        from wizard_rts import magic

        out = magic.fire(self, str(target_id))
        out["snapshot"] = self.snapshot()
        return out

    def deploy(self, unit_id: str) -> dict[str, Any]:
        out = territory.deploy(self, str(unit_id))
        out["snapshot"] = self.snapshot()
        return out

    def order(self, unit_id: str, target_id: str) -> dict[str, Any]:
        result = order_attack(self, str(unit_id), str(target_id))
        result["snapshot"] = self.snapshot()
        return result

    def interact(self) -> dict[str, Any]:
        if not self._hazard_active():
            return {"status": "rejected", "reason": "no_hazard", "snapshot": self.snapshot()}
        if not self._player_near_hazard():
            return {"status": "rejected", "reason": "too_far", "snapshot": self.snapshot()}
        q, r = tile_to_hex(*self.hazard_tile) if self.hazard_tile else (0, 0)
        node_id = f"hex:{q},{r}"
        VisitService(self.dmb).arrive(node_id, "travel", int(self.dmb.clock.get("turn", 0)))
        started = HazardDuelService(self.dmb).begin(self.hazard_id)
        if started.get("status") != "started":
            return {"status": "rejected", "reason": started.get("reason", started.get("status")), "snapshot": self.snapshot()}
        return {
            "status": "started",
            "payload": {"public": started["public"], "duel": started["duel"]},
            "snapshot": self.snapshot(),
        }

    def resolve(self, duel_id: str, success: bool, command_id: str | None = None) -> dict[str, Any]:
        before_ids = self.entity_ids()
        pose = dict(self.player)
        stocks_before = {k: dict(v) for k, v in self.stocks.items()}
        result = HazardDuelService(self.dmb).resolve(
            str(duel_id),
            success=bool(success),
            command_id=command_id or f"hybrid:{duel_id}",
        )
        if result.get("status") != "idempotent":
            self.events.append({"kind": "duel_resolved", "success": bool(success), "result": result.get("status")})
        after_ids = self.entity_ids()
        assert before_ids == after_ids
        assert self.player == pose
        if result.get("status") == "idempotent":
            assert self.stocks == stocks_before
        return {"status": result.get("status"), "result": result, "snapshot": self.snapshot()}

    def entity_ids(self) -> list[str]:
        ids = list(self.buildings) + list(self.carriers) + list(self.units) + list(self.workers) + list(self.trees) + list(self.rocks) + list(self.animals)
        if self.hazard_id:
            ids.append(self.hazard_id)
        return sorted(ids)

    def _player_near_hazard(self) -> bool:
        if self.hazard_tile is None:
            return False
        dx = abs(self.player["tx"] - self.hazard_tile[0])
        dy = abs(self.player["ty"] - self.hazard_tile[1])
        return dx + dy <= 1

    def tree_delta(self, full: bool) -> dict[str, Any]:
        """Trees changed since the last delta sent (one client). Trees are 90 % of the snapshot and change rarely, so the
        Godot client asks for them as a delta and rebuilds the full list locally; the simulation is unchanged."""
        sent = self.__dict__.setdefault("_tree_sent", {})
        if full:
            sent.clear()
        upsert = []
        for tree_id, tree in self.trees.items():
            sig = (tree["definition"], tree["stage"])
            if sent.get(tree_id) != sig:
                sent[tree_id] = sig
                upsert.append({"id": tree_id, "class": "tree", "kind": "tree", "definition": tree["definition"], "stage": tree["stage"], "tx": tree["tx"], "ty": tree["ty"],
                               "solid": self.tree_solid(tree)})
        for rock_id, rock in self.rocks.items():
            sig = ("rock", rock["amount"])
            if sent.get(rock_id) != sig:
                sent[rock_id] = sig
                upsert.append(self._rock_row(rock))
        removed = [i for i in sent if i not in self.trees and i not in self.rocks]
        for i in removed:
            del sent[i]
        return {"full": bool(full), "upsert": upsert, "removed": removed}

    @staticmethod
    def _rock_row(rock: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": rock["id"], "class": "rock", "kind": "rock", "definition": rock["definition"],
            "tx": rock["tx"], "ty": rock["ty"], "alive": True, "faction": "", "label": "Rocks", "amount": rock["amount"],
        }

    def snapshot(self, tree_sync: bool | None = None) -> dict[str, Any]:
        """tree_sync None: trees inline (tests, headless). False: a client that wants everything now (sends a full delta).
        True: a client that applies deltas."""
        q, r = tile_to_hex(self.player["tx"], self.player["ty"])
        entities = []
        for building in self.buildings.values():
            row = _entity_row(building)
            row["class"] = "building" if "hp" in building else "scenery"
            if building.get("working"):
                row["working"] = True
            if "hp" in building:
                row["status_text"] = self.status_text(building)
            if building["kind"] == "warehouse":
                row["territory"] = territory.radius_of(building)
                row["outpost"] = bool(building.get("outpost"))
            if building.get("destroyed"):
                row["destroyed"] = True
                row["ruin_ms"] = int(building.get("ruin_ms", 0))
            if building.get("mdy") is not None:
                row["mdy"] = industry.row(self, building)
            elif building["kind"] == "mdy:conveyor" and building.get("line"):
                row["line_tiles"] = len(building["line"]["tiles"])
                row["line_live"] = bool(building.get("line_live"))
            if building["kind"] in ("mine", "ironmine", "well"):
                res = {"mine": "coal", "ironmine": "iron", "well": "water"}[building["kind"]]
                row["deposit_left"] = self.resource_total((building["tx"], building["ty"]), 2, res)
                row["inexhaustible"] = terrain_mod.is_mineral(res)  # D22: the figure is the site's richness, not a stock that runs out
            if building.get("kind") == "blight_nest":
                row["nest_cubes"] = int(building.get("nest_cubes", 1))
                row["region"] = building.get("nest", "")
            if building.get("disrupted"):
                d = building["disrupted"]
                row["disrupted"] = {"cause": d["cause"], "label": d["label"], "since_ms": d["since_ms"], "repair": dict(d["repair"]),
                                    "progress": round(int(d["progress_ms"]) / max(1, int(d["repair_ms"])), 2)}
            entities.append(row)
        for carrier in self.carriers.values():
            row = _entity_row(carrier)
            row["class"] = "carrier"
            row["cargo"] = carrier["cargo"]['good'] if carrier["cargo"] else ""
            row["status"] = carrier["status"]
            row["move_ms"] = 100 * 5  # a carrier takes one tile per five logistics quanta (logistics_quantum)
            entities.append(row)
        if tree_sync is None:
            for tree in self.trees.values():
                entities.append(
                    {
                        "id": tree["id"], "class": "tree", "kind": "tree", "definition": tree["definition"], "stage": tree["stage"],
                        "tx": tree["tx"], "ty": tree["ty"],
                    }
                )
        if tree_sync is None:
            for rock in self.rocks.values():
                entities.append(self._rock_row(rock))
        entities.extend(story.entity_rows(self))
        entities.extend(regions.entity_rows(self))
        for animal in self.animals.values():
            row = {
                "id": animal["id"], "class": "animal", "kind": "animal", "definition": animal["definition"],
                "tx": animal["tx"], "ty": animal["ty"], "alive": True, "faction": "", "label": animal["species"].title(),
                "facing": animal["facing"], "status": animal["status"],
            }
            row["move_ms"] = 1500
            if animal["next"] is not None:
                row["next_tx"], row["next_ty"] = animal["next"]
                row["move_progress"] = min(1.0, animal["progress_ms"] / 1500.0)
            entities.append(row)
        for worker in self.workers.values():
            row = _entity_row(worker)
            row["class"] = "worker"
            row["role"] = worker["role"]
            row["anim"] = worker["anim"]
            row["carrying"] = worker["carrying"]
            row["status"] = worker["status"]
            row["inside"] = (
                worker["anim"] == "idle"
                and not worker["path"]
                and (worker["tx"], worker["ty"]) == (self.buildings[worker["building"]]["tx"], self.buildings[worker["building"]]["ty"])
            )
            row["move_ms"] = 600
            row["move_progress"] = min(1.0, worker["progress_ms"] / 600.0) if worker["path"] else 0.0
            if worker["path"]:
                row["next_tx"], row["next_ty"] = worker["path"][0]
            entities.append(row)
        for unit in self.units.values():
            row = _entity_row(unit)
            row["class"] = "unit"
            if unit.get("cargo"):
                row["unit_cargo"] = dict(unit["cargo"])
            if unit.get("deploying_ms"):
                row["deploying_ms"] = int(unit["deploying_ms"])
            row["hp"] = unit["hp"]
            row["max_hp"] = unit["max_hp"]
            row["alive"] = unit["alive"]
            if unit.get("order"):
                row["order"] = dict(unit["order"])
            entities.append(row)
        if self.hazard_tile and self._hazard_active():
            entities.append(
                {
                    "id": self.hazard_id,
                    "class": "hazard",
                    "kind": "hazard",
                    "faction": "",
                    "label": "Magical hazard",
                    "tx": self.hazard_tile[0],
                    "ty": self.hazard_tile[1],
                    "alive": True,
                }
            )
        out_tree = {} if tree_sync is None else {"tree_delta": self.tree_delta(full=not tree_sync)}
        return {
            **out_tree,
            "world_id": WORLD_ID,
            "seed": self.seed,
            "game_ms": int(self.dmb.clock.get("game_ms", 0)),
            "clock_sequence": int(self.dmb.clock.get("clock_sequence", 0)),
            "paused": bool(self.dmb.clock.get("pause_tokens")),
            "player": {"tx": self.player["tx"], "ty": self.player["ty"], "facing": self.player["facing"], "hex": [q, r]},
            "entities": entities,
            "stocks": {k: dict(v) for k, v in self.stocks.items()},
            "blocked": [list(tile) for tile in sorted(self.blocked)],
            "roads": {rid: [list(tile) for tile in tiles] for rid, tiles in self.roads.items()},
            "hazard_active": self._hazard_active(),
            "hazard_id": self.hazard_id,
            "entity_ids": self.entity_ids() if tree_sync is None else [],
            "provenance": {
                "economy_stock": ECONOMY_PROVENANCE,
                "economy_schedule": SCHEDULE_PROVENANCE,
                "military_damage": MILITARY_PROVENANCE,
                "military_movement": MOVEMENT_PROVENANCE,
            },
            "effects": self._effects_for_snapshot(),
            "stats": dict(self.stats),
            "recent_events": [dict(e) for e in self.events[-30:] if e["kind"].startswith(("ai_", "unit_produced", "building_destroyed", "destroyed", "construction", "recruit"))],
            "time_scale": self.time_scale,
            "factions": list(self.faction_info.values()),
            "controlled_faction": self.controlled_faction,
            "economy_totals": dict(self.economy_totals.totals),
            "map": ({"q": 20, "r": 20} if self.terrain is None else {"w": self.terrain.w, "h": self.terrain.h, "static_hash": self.terrain.static_hash()}),
            "neighbor_sample": neighbors(q, r),
            "in_map": in_map(q, r),
            "tech": tech.snapshot(self),
            "industry": industry.snapshot(self),
            "story": story.snapshot(self),
            "era": vp.snapshot(self),
            "history": history.snapshot(self),
            "overview": feed.overview(self),
            "feed": feed.snapshot(self),
            "ai_notes": {k: list(v[-4:]) for k, v in self.__dict__.get("ai_notes", {}).items()},
            "regions": regions.snapshot(self),
        }


def _entity_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "kind": row["kind"],
        "faction": row.get("faction", ""),
        "faction_name": row.get("faction_name", ""),
        "label": row.get("label", row["kind"]),
        "tx": int(row["tx"]),
        "ty": int(row["ty"]),
        "alive": True,
    }
    if row.get("definition"):
        out["definition"] = row["definition"]
    if row.get("facing"):
        out["facing"] = row["facing"]
    if row.get("status"):
        out["status"] = row["status"]
    if "hp" in row:
        out["hp"] = int(row["hp"])
        out["max_hp"] = int(row.get("max_hp", row["hp"]))
    if row.get("target_type"):
        out["target_type"] = row["target_type"]
    if row.get("rally"):
        out["rally"] = list(row["rally"])
    if row.get("tribe_fallback"):
        out["tribe_fallback"] = True
    if row.get("ground_footprint"):
        out["ground_footprint"] = row["ground_footprint"]
    if row.get("footprint"):
        out["footprint"] = row["footprint"]
        out["anchor"] = row["anchor"]
    if row.get("loco"):
        out["loco"] = row["loco"]
    if "cloaked" in row:
        out["cloaked"] = bool(row["cloaked"])
    if "operational" in row:
        out["operational"] = bool(row["operational"])
    if row.get("constructing"):
        site = row["constructing"]
        out["constructing"] = {"cost": site["cost"], "progress_ms": site["progress_ms"]}
    if row.get("queue") is not None:
        out["queue"] = [dict(i) for i in row["queue"]]
    if row.get("order"):
        out["order"] = dict(row["order"])
    if row.get("path"):
        nxt = row["path"][0]
        out["next_tx"], out["next_ty"] = int(nxt[0]), int(nxt[1])
        out["move_ms"] = int(row.get("move_ms", 760))
        out["move_progress"] = min(1.0, row.get("progress_ms", 0) / max(1, row.get("move_ms", 760)))
    return out


def _path(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    cursor = start
    out = [cursor]
    for _ in range(80):
        if cursor == goal:
            return out
        dx = goal[0] - cursor[0]
        dy = goal[1] - cursor[1]
        if abs(dx) >= abs(dy) and dx != 0:
            cursor = (cursor[0] + (1 if dx > 0 else -1), cursor[1])
        else:
            cursor = (cursor[0], cursor[1] + (1 if dy > 0 else -1))
        out.append(cursor)
    return out
