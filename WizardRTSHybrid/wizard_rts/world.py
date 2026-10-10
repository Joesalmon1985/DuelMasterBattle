"""One authoritative hybrid world.

Python owns entities, stocks, clocks, and duel outcomes. Godot only presents
this snapshot and sends pose, advance, interact, and resolve commands.
Crossing a hex updates the player hex and does not advance game time.
"""

from __future__ import annotations

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
from wizard_rts.economy import PROVENANCE as ECONOMY_PROVENANCE  # noqa: E402
from wizard_rts.economy import SCHEDULE_PROVENANCE  # noqa: E402
from wizard_rts.widelands_stock import EconomyTotals  # noqa: E402
from wizard_rts.economy import economy_quantum  # noqa: E402
from wizard_rts.military import MOVEMENT_PROVENANCE  # noqa: E402
from wizard_rts.military import PROVENANCE as MILITARY_PROVENANCE  # noqa: E402
from wizard_rts.military import military_quantum  # noqa: E402

WORLD_ID = "hybrid.world"


class HybridWorld:
    def __init__(self, seed: int = 507) -> None:
        self.seed = int(seed)
        self.dmb = WorldState(world_id=WorldId(WORLD_ID))
        self.clock = ClockService(self.dmb.clock)
        self.buildings: dict[str, dict[str, Any]] = {}
        self.carriers: dict[str, dict[str, Any]] = {}
        self.units: dict[str, dict[str, Any]] = {}
        self.roads: dict[str, list[tuple[int, int]]] = {}
        self.stocks: dict[str, dict[str, int]] = {}
        self.economy_totals = EconomyTotals()
        self.blocked: set[tuple[int, int]] = set()
        self.events: list[dict[str, Any]] = []
        self.economy_quanta = 0
        self.military_quanta = 0
        self.stats = {"deliver": 0, "blocked": 0, "move": 0, "attack": 0, "destroyed": 0, "produce": 0}
        self.hazard_id = ""
        self.hazard_tile: tuple[int, int] | None = None
        self.player = {"tx": 0, "ty": 0, "facing": "down"}
        self._layout()

    def tile_in_map(self, tx: int, ty: int) -> bool:
        return tile_in_map(tx, ty)

    def tile_blocked_for_carrier(self, tile: tuple[int, int]) -> bool:
        if self.hazard_tile is None or not self._hazard_active():
            return False
        return tile == self.hazard_tile

    def _hazard_active(self) -> bool:
        cube = (self.dmb.hazards.get("catastrophe", {}).get("cubes") or {}).get(self.hazard_id)
        return bool(cube and cube.get("active", True))

    def _layout(self) -> None:
        red = self._place_faction("Red", 2, 2)
        blue = self._place_faction("Blue", 6, 3)
        # Stand just east of the red settlement so the town is in frame at
        # playable zoom. Hex (2, 3)'s center is a full hex away and hides it.
        start = self._stand_near(red["road"])
        self.player = {"tx": start[0], "ty": start[1], "facing": "up"}
        self._place_hazard(red["road"])
        self.events.append({"kind": "layout", "factions": [red["faction"], blue["faction"]]})

    def _place_faction(self, name: str, q: int, r: int) -> dict[str, Any]:
        faction_id = str(self.dmb.ids.new("faction"))
        center = hex_center_tile(q, r)
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
        self.buildings[processor]["warehouse_id"] = warehouse
        road_tiles = _path(producer_tile, warehouse_tile) + _path(warehouse_tile, processor_tile)[1:]
        road_id = f"road:{faction_id}"
        self.roads[road_id] = road_tiles
        self._place_showcase(faction_id, name, q, r, center, set(road_tiles))
        carrier_id = str(self.dmb.ids.new("cart"))
        self.carriers[carrier_id] = {
            "id": carrier_id,
            "faction": faction_id,
            "faction_name": name,
            "kind": "carrier",
            "label": f"{name} carrier",
            "tx": road_tiles[0][0],
            "ty": road_tiles[0][1],
            "index": 0,
            "road_id": road_id,
            "producer_id": producer,
            "warehouse_id": warehouse,
            "cargo": None,
            "status": "idle",
            "definition": "widelands.carrier",
            "facing": "e",
        }
        self.stocks[carrier_id] = {}
        unit_tile = self._offset_owned(q, r, center, 0, 3)
        self._unit(faction_id, name, "soldier", "Soldier", "widelands.soldier", unit_tile)
        infantry_tile = self._free_in_hex(q, r, center, 1, 4, set())
        self._unit(faction_id, name, "infantry", "Rifleman", "openra.e1", infantry_tile)
        tank_tile = self._free_in_hex(q, r, center, -2, 4, set())
        self._unit(faction_id, name, "tank", "Tank", "openra.3tnk", tank_tile)
        return {"faction": faction_id, "road": road_tiles, "warehouse": warehouse}

    def _place_showcase(
        self,
        faction_id: str,
        name: str,
        q: int,
        r: int,
        center: tuple[int, int],
        road: set[tuple[int, int]],
    ) -> None:
        """Real buildings from both games, sharing this faction's hex."""
        specs = (
            ("mine", "widelands.coalmine", "Mine", -12, 5),
            ("tavern", "widelands.tavern", "Tavern", -10, -8),
            ("farm", "widelands.farm", "Farm", 1, -11),
            ("barracks", "openra.barracks", "Barracks", 11, -6),
            ("vehicle_factory", "openra.weap", "War factory", 12, 7),
            ("refinery", "openra.proc", "Refinery", -12, -3),
            ("defense", "openra.gun", "Turret", 5, 9),
        )
        for kind, definition, label, dx, dy in specs:
            tile = self._free_in_hex(q, r, center, dx, dy, road)
            self._building(faction_id, name, kind, tile, label, definition)
        self._place_scenery(faction_id, name, center, road)

    def _place_scenery(
        self,
        faction_id: str,
        name: str,
        center: tuple[int, int],
        road: set[tuple[int, int]],
    ) -> None:
        trees = ((-9, -1), (-9, 1), (-8, 3), (-5, -7), (8, -6), (-2, -8))
        for dx, dy in trees:
            tile = (center[0] + dx, center[1] + dy)
            if not tile_in_map(*tile) or tile in self.blocked or tile in road:
                continue
            self._building(faction_id, name, "tree", tile, "Beech", "widelands.beech", block=False)
        for dx, dy in ((-7, 5), (8, 2)):
            tile = (center[0] + dx, center[1] + dy)
            if not tile_in_map(*tile) or tile in self.blocked or tile in road:
                continue
            self._building(faction_id, name, "rock", tile, "Rocks", "widelands.rocks", block=False)

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
            "hp": 12,
            "alive": True,
            "facing": "s",
            "status": "idle",
        }
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
        self.buildings[building_id] = record
        self.stocks[building_id] = {}
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
        if tile in self.blocked or tile in avoid or not tile_in_map(*tile):
            return False
        return True

    def _tile_open(self, q: int, r: int, tile: tuple[int, int], avoid: set[tuple[int, int]]) -> bool:
        if tile in self.blocked or tile in avoid:
            return False
        return tile_to_hex(*tile) == (q, r)

    def _stand_near(self, road: list[tuple[int, int]]) -> tuple[int, int]:
        blocked = self.blocked
        road_set = set(road)
        for tile in ((100, 50), (102, 52), (98, 54), (104, 48), (96, 56)):
            east = (tile[0] + 1, tile[1])
            if tile in blocked or tile in road_set or east in blocked:
                continue
            if tile_in_map(*tile) and tile_in_map(*east):
                return tile
        return hex_center_tile(2, 3)

    def _offset_owned(self, q: int, r: int, center: tuple[int, int], dx: int, dy: int) -> tuple[int, int]:
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

    def set_pose(self, tx: int, ty: int, facing: str = "down") -> dict[str, Any]:
        game_ms = int(self.dmb.clock.get("game_ms", 0))
        tile = (int(tx), int(ty))
        if not tile_in_map(*tile):
            return {"status": "rejected", "reason": "outside_map", "snapshot": self.snapshot()}
        if tile in self.blocked:
            return {"status": "rejected", "reason": "blocked", "snapshot": self.snapshot()}
        previous = tile_to_hex(self.player["tx"], self.player["ty"])
        self.player = {"tx": tile[0], "ty": tile[1], "facing": str(facing or "down")}
        current = tile_to_hex(tile[0], tile[1])
        if current != previous:
            self.events.append({"kind": "hex_cross", "from": list(previous), "to": list(current)})
        assert int(self.dmb.clock.get("game_ms", 0)) == game_ms
        return {"status": "ok", "snapshot": self.snapshot()}

    def advance(self, ms: int, sequence: int) -> dict[str, Any]:
        quanta = self.clock.request_advance(int(ms), int(sequence))
        for _ in range(quanta):
            economy_quantum(self)
            military_quantum(self)
            if self.economy_quanta % 30 == 0:
                self.events.append({"kind": "ai_economy", "game_ms": int(self.dmb.clock.get("game_ms", 0))})
        return {"status": "ok", "quanta": quanta, "snapshot": self.snapshot()}

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
        ids = list(self.buildings) + list(self.carriers) + list(self.units)
        if self.hazard_id:
            ids.append(self.hazard_id)
        return sorted(ids)

    def _player_near_hazard(self) -> bool:
        if self.hazard_tile is None:
            return False
        dx = abs(self.player["tx"] - self.hazard_tile[0])
        dy = abs(self.player["ty"] - self.hazard_tile[1])
        return dx + dy <= 1

    def snapshot(self) -> dict[str, Any]:
        q, r = tile_to_hex(self.player["tx"], self.player["ty"])
        entities = []
        for building in self.buildings.values():
            entities.append(_entity_row(building))
        for carrier in self.carriers.values():
            row = _entity_row(carrier)
            row["cargo"] = carrier["cargo"]
            row["status"] = carrier["status"]
            entities.append(row)
        for unit in self.units.values():
            row = _entity_row(unit)
            row["hp"] = unit["hp"]
            row["alive"] = unit["alive"]
            entities.append(row)
        if self.hazard_tile and self._hazard_active():
            entities.append(
                {
                    "id": self.hazard_id,
                    "kind": "hazard",
                    "faction": "",
                    "label": "Magical hazard",
                    "tx": self.hazard_tile[0],
                    "ty": self.hazard_tile[1],
                    "alive": True,
                }
            )
        return {
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
            "entity_ids": self.entity_ids(),
            "provenance": {
                "economy_stock": ECONOMY_PROVENANCE,
                "economy_schedule": SCHEDULE_PROVENANCE,
                "military_damage": MILITARY_PROVENANCE,
                "military_movement": MOVEMENT_PROVENANCE,
            },
            "economy_totals": dict(self.economy_totals.totals),
            "map": {"q": 20, "r": 20},
            "neighbor_sample": neighbors(q, r),
            "in_map": in_map(q, r),
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
