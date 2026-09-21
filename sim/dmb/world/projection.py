"""Stable local village projection (C09 / T078).

Durable layout anchors and overrides live on the world board. Disposable views
bind current living entity IDs without rerolling people or inventing authority.
"""

from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

LAYOUT_SCHEMA_VERSION = 3  # Full-board LocalArea: fixed 48×48, geography + road/trail exits
BASE_SIZE = 48
GROW_STEP = 16
FOOTPRINT = (3, 3)

# Keep settlement_layout version in sync for settlement anchors written elsewhere.
from sim.dmb.world import settlement_layout as _settlement_layout

_settlement_layout.LAYOUT_SCHEMA_VERSION = LAYOUT_SCHEMA_VERSION


def _stable_rng(seed_material: str) -> random.Random:
    digest = hashlib.sha256(seed_material.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big", signed=False))


def _in_bounds(x: int, y: int, width: int, height: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def _cells_for_footprint(origin: tuple[int, int], footprint: tuple[int, int]) -> set[tuple[int, int]]:
    ox, oy = origin
    fw, fh = footprint
    return {(ox + dx, oy + dy) for dx in range(fw) for dy in range(fh)}


def _bfs_reachable(
    width: int,
    height: int,
    blocked: set[tuple[int, int]],
    start: tuple[int, int],
    goals: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    if start in blocked or not _in_bounds(*start, width, height):
        return set()
    pending = [start]
    seen = {start}
    found: set[tuple[int, int]] = set()
    while pending:
        x, y = pending.pop(0)
        if (x, y) in goals:
            found.add((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not _in_bounds(nx, ny, width, height):
                continue
            if (nx, ny) in blocked or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            pending.append((nx, ny))
    return found


@dataclass
class LocalProjectionService:
    state: WorldState

    def _store(self) -> dict[str, Any]:
        board = self.state.board
        if not isinstance(board, dict):
            self.state.board = {}
            board = self.state.board
        return board.setdefault("local_projections", {})

    def layout_record(self, node_id: str) -> dict[str, Any] | None:
        rec = self._store().get(node_id)
        return dict(rec) if isinstance(rec, dict) else None

    def ensure_layout(
        self,
        node_id: str,
        *,
        seed: str | int | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create durable layout once from node seed; later calls reuse saved anchors."""
        store = self._store()
        existing = store.get(node_id)
        if isinstance(existing, dict) and existing.get("schema_version") == LAYOUT_SCHEMA_VERSION:
            self._ensure_capacity(existing, manifest or self._default_manifest(node_id))
            self._apply_manifest_bindings(existing, manifest)
            self._bind_topology_exits(existing, node_id)
            store[node_id] = existing
            return dict(existing)

        node_seed = seed if seed is not None else f"{self.state.world_id}:{node_id}"
        width = BASE_SIZE
        height = BASE_SIZE
        centre = [width // 2, height // 2]
        record: dict[str, Any] = {
            "schema_version": LAYOUT_SCHEMA_VERSION,
            "node_id": node_id,
            "seed": str(node_seed),
            "width": width,
            "height": height,
            "centre": centre,
            "buildings": {},
            "people_anchors": {},
            "cart_anchors": {},
            "unit_anchors": {},
            "objects": {},
            "exits": [],
            "destroyed_ids": [],
            "overrides": {},
            "edits": [],
            "geography": [],
            "kind": self._derive_node_kind(node_id),
        }
        self._generate_geography(record, node_id)
        self._place_settlement_buildings(record, node_id)
        self._ensure_capacity(record, manifest or self._default_manifest(node_id))
        self._apply_manifest_bindings(record, manifest)
        self._bind_topology_exits(record, node_id)
        store[node_id] = record
        return dict(record)

    def project_node(self, node_id: str) -> dict[str, Any]:
        """Production entry: ensure + project any strategic node."""
        return self.project(node_id)

    def _derive_node_kind(self, node_id: str) -> str:
        for s in (self.state.settlements or {}).values():
            if s.get("node_id") == node_id and not s.get("staging") and s.get("operational", True):
                tier = str(s.get("tier") or "settlement")
                return "city" if tier == "city" else "settlement"
        if self._incident_roads(node_id):
            return "road"
        return "wilderness"

    def _incident_roads(self, node_id: str) -> list[dict[str, Any]]:
        out = []
        for road in (self.state.roads or {}).values():
            if road.get("status") != "built":
                continue
            if node_id in {str(road.get("a")), str(road.get("b"))}:
                out.append(road)
        return out

    def _road_to_neighbour(self, node_id: str, other: str) -> dict[str, Any] | None:
        for road in self._incident_roads(node_id):
            ends = {str(road.get("a")), str(road.get("b"))}
            if other in ends:
                return road
        return None

    def _generate_geography(self, record: dict[str, Any], node_id: str) -> None:
        """Deterministic terrain patches from touching hexes — persisted with the layout."""
        from sim.dmb.world.settlement_layout import hex_sector, perimeter_anchor

        board_topo = self.state.board.get("topology") or {}
        hex_terrain = self.state.board.get("hex_terrain") or {}
        touching = list(self.state.board.get("node_hexes", {}).get(node_id) or [])
        rng = _stable_rng(f"{record.get('seed')}:geo")
        width = int(record["width"])
        height = int(record["height"])
        patches: list[dict[str, Any]] = []
        # Reconstruct a minimal HexBoard-like API via topology dict if needed.
        try:
            from sim.dmb.world.board import HexBoard

            board = HexBoard.from_dict(board_topo) if board_topo.get("hexes") else None
        except Exception:
            board = None
        for hid in touching:
            terrain = str(hex_terrain.get(hid) or "fields")
            if board is not None:
                try:
                    sector = hex_sector(board, node_id, str(hid))
                except Exception:
                    sector = rng.choice(
                        ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
                    )
            else:
                sector = rng.choice(
                    ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
                )
            anchor = perimeter_anchor(width, height, sector, footprint=(6, 5), margin=2)
            tile = {"woodland": "T", "ore_mountains": "r", "clay_mountains": "r", "fields": ",", "grazing_land": ",", "desert": "."}.get(
                terrain, "."
            )
            patches.append(
                {
                    "hex_id": str(hid),
                    "terrain": terrain,
                    "sector": sector,
                    "grid": list(anchor["grid"]),
                    "footprint": list(anchor["footprint"]),
                    "tile": tile,
                }
            )
        record["geography"] = patches

    def _place_settlement_buildings(self, record: dict[str, Any], node_id: str) -> None:
        """If this node has a settlement, place buildings via spatial grammar."""
        has_settlement = any(
            s.get("node_id") == node_id and not s.get("staging") for s in (self.state.settlements or {}).values()
        )
        if not has_settlement:
            return
        from sim.dmb.world.board import HexBoard
        from sim.dmb.world.settlement_layout import build_village_layout_sites

        board_topo = self.state.board.get("topology") or {}
        try:
            board = HexBoard.from_dict(board_topo)
        except Exception:
            return
        node_buildings = {
            str(bid): b
            for bid, b in (self.state.buildings or {}).items()
            if b.get("node_id") == node_id and b.get("active", True)
        }
        anchors, sites = build_village_layout_sites(
            board=board,
            node_id=node_id,
            buildings=node_buildings,
            width=int(record["width"]),
            height=int(record["height"]),
        )
        record["buildings"] = anchors
        # Sync industry layout site grids for worker paths.
        by_node = self.state.board.setdefault("fx_industry_by_node", {})
        if node_id in by_node:
            # Merge grids into existing site rows.
            by_id = {str(s["id"]): s for s in sites}
            merged = []
            for site in (by_node[node_id].get("layout") or {}).get("sites") or []:
                extra = by_id.get(str(site.get("id"))) or {}
                row = dict(site)
                if extra:
                    row.update(
                        {
                            "grid": extra.get("grid", site.get("grid")),
                            "entrance": extra.get("entrance", site.get("entrance")),
                            "approach": extra.get("approach", site.get("approach")),
                            "footprint": extra.get("footprint", site.get("footprint")),
                            "sector": extra.get("sector"),
                            "presentation": extra.get("presentation"),
                        }
                    )
                merged.append(row)
            by_node[node_id]["layout"] = {"sites": merged or sites}
            if str((self.state.player or {}).get("node_id") or "") == node_id:
                self.state.board["fx_industry"] = dict(by_node[node_id])

    def save_override(self, node_id: str, override: dict[str, Any]) -> dict[str, Any]:
        record = self._store().get(node_id)
        if not isinstance(record, dict):
            raise TypeValidationError(f"no layout for node {node_id}")
        overrides = dict(record.get("overrides") or {})
        key = str(override.get("entity_id") or override.get("id") or "")
        if not key:
            raise TypeValidationError("override requires entity_id")
        overrides[key] = deepcopy(override)
        record["overrides"] = overrides
        edits = list(record.get("edits") or [])
        edits.append({"kind": "override", "entity_id": key})
        record["edits"] = edits
        self._store()[node_id] = record
        return dict(record)

    def mark_destroyed(self, node_id: str, entity_id: str) -> dict[str, Any]:
        record = self._store().get(node_id)
        if not isinstance(record, dict):
            raise TypeValidationError(f"no layout for node {node_id}")
        destroyed = list(record.get("destroyed_ids") or [])
        if entity_id not in destroyed:
            destroyed.append(entity_id)
        record["destroyed_ids"] = destroyed
        for bucket in ("buildings", "people_anchors", "cart_anchors", "unit_anchors", "objects"):
            bucket_map = dict(record.get(bucket) or {})
            bucket_map.pop(entity_id, None)
            record[bucket] = bucket_map
        self._store()[node_id] = record
        return dict(record)

    def project(
        self,
        node_id: str,
        manifest: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Disposable view: durable anchors + live bindings; never rerolls people."""
        layout = self.ensure_layout(node_id, manifest=manifest)
        destroyed = set(layout.get("destroyed_ids") or [])
        buildings_view = []
        for building_id, anchor in sorted((layout.get("buildings") or {}).items()):
            if building_id in destroyed:
                continue
            if building_id not in self.state.buildings:
                continue
            if not self.state.buildings[building_id].get("active", True):
                continue
            buildings_view.append(
                {
                    "id": building_id,
                    "grid": list(anchor.get("grid") or []),
                    "footprint": list(anchor.get("footprint") or list(FOOTPRINT)),
                    "entrance": list(anchor.get("entrance") or []),
                    "approach": list(anchor.get("approach") or []),
                    "definition_id": self.state.buildings[building_id].get("definition_id"),
                }
            )
        people_view = []
        for person_id, anchor in sorted((layout.get("people_anchors") or {}).items()):
            if person_id in destroyed:
                continue
            person = self.state.people.get(person_id)
            if person is None or not person.get("alive", True):
                continue
            people_view.append(
                {
                    "id": person_id,
                    "grid": list(anchor.get("grid") or person.get("grid") or []),
                    "role": person.get("role"),
                    "workplace_id": person.get("workplace_id"),
                }
            )
        carts_view = []
        for cart_id, anchor in sorted((layout.get("cart_anchors") or {}).items()):
            if cart_id in destroyed or cart_id not in self.state.carts:
                continue
            carts_view.append({"id": cart_id, "grid": list(anchor.get("grid") or [])})
        units_view = []
        for unit_id, anchor in sorted((layout.get("unit_anchors") or {}).items()):
            if unit_id in destroyed or unit_id not in self.state.units:
                continue
            units_view.append({"id": unit_id, "grid": list(anchor.get("grid") or [])})

        # Live people on this node (anchors + anyone currently located here).
        people_ids = {str(p["id"]) for p in people_view}
        for person_id, person in (self.state.people or {}).items():
            if person_id in people_ids or person_id in destroyed:
                continue
            if not person.get("alive", True) or person.get("node_id") != node_id:
                continue
            people_view.append(
                {
                    "id": person_id,
                    "grid": list(person.get("grid") or layout.get("centre") or [24, 24]),
                    "role": person.get("role"),
                    "workplace_id": person.get("workplace_id"),
                }
            )
        # Live carts / units at this node.
        for cart_id, cart in (self.state.carts or {}).items():
            if cart_id in destroyed:
                continue
            if str(cart.get("current_node") or cart.get("node_id") or "") != node_id:
                continue
            if any(c["id"] == cart_id for c in carts_view):
                continue
            carts_view.append({"id": cart_id, "grid": list(layout.get("centre") or [24, 24])})
        for unit_id, unit in (self.state.units or {}).items():
            if unit_id in destroyed or unit.get("status") == "dead":
                continue
            if str(unit.get("node_id") or "") != node_id:
                continue
            if any(u["id"] == unit_id for u in units_view):
                continue
            units_view.append({"id": unit_id, "grid": list(layout.get("centre") or [24, 24])})

        exits = [dict(e) for e in layout.get("exits") or []]
        reachable = self.exits_reachable(layout)
        view = {
            "schema_version": LAYOUT_SCHEMA_VERSION,
            "node_id": node_id,
            "seed": layout.get("seed"),
            "width": int(layout["width"]),
            "height": int(layout["height"]),
            "centre": list(layout.get("centre") or []),
            "kind": layout.get("kind") or self._derive_node_kind(node_id),
            "geography": list(layout.get("geography") or []),
            "buildings": buildings_view,
            "people": people_view,
            "carts": carts_view,
            "units": units_view,
            "exits": exits,
            "exits_reachable": sorted(reachable),
            "destroyed_ids": sorted(destroyed),
            "knowledge_scope": sorted((knowledge or {}).keys()) if knowledge else [],
            "overrides": deepcopy(layout.get("overrides") or {}),
        }
        return view

    def exits_reachable(self, layout: dict[str, Any]) -> list[str]:
        width = int(layout["width"])
        height = int(layout["height"])
        centre = tuple(layout.get("centre") or [width // 2, height // 2])
        blocked: set[tuple[int, int]] = set()
        for building_id, anchor in (layout.get("buildings") or {}).items():
            if building_id in set(layout.get("destroyed_ids") or []):
                continue
            grid = anchor.get("grid") or [0, 0]
            footprint = tuple(anchor.get("footprint") or FOOTPRINT)
            cells = _cells_for_footprint((int(grid[0]), int(grid[1])), (int(footprint[0]), int(footprint[1])))
            entrance = anchor.get("entrance")
            if entrance:
                cells.discard((int(entrance[0]), int(entrance[1])))
            approach = anchor.get("approach")
            if approach:
                cells.discard((int(approach[0]), int(approach[1])))
            blocked |= cells
        goals = {
            (int(e["grid"][0]), int(e["grid"][1])): str(e["id"])
            for e in layout.get("exits") or []
            if e.get("grid")
        }
        reached_cells = _bfs_reachable(width, height, blocked, (int(centre[0]), int(centre[1])), set(goals))
        return [goals[cell] for cell in sorted(reached_cells)]

    def _bind_topology_exits(self, record: dict[str, Any], node_id: str) -> None:
        """Bind one exit per topology neighbour; mark constructed roads vs trails."""
        width = int(record.get("width") or BASE_SIZE)
        height = int(record.get("height") or BASE_SIZE)
        node = (self.state.board.get("nodes") or {}).get(node_id) or {}
        exits_map = node.get("exits") or {}
        # Fall back to topology adjacency if exits not wired yet.
        if not isinstance(exits_map, dict) or not exits_map:
            topo = self.state.board.get("topology") or {}
            try:
                from sim.dmb.world.board import HexBoard

                board = HexBoard.from_dict(topo)
                from sim.dmb.world.fx_village_world import wire_topology_travel

                wire_topology_travel(self.state, board, home_node_id=node_id, width=width, height=height)
                node = (self.state.board.get("nodes") or {}).get(node_id) or {}
                exits_map = node.get("exits") or {}
            except Exception:
                exits_map = {}
        grids = {
            "north": [width // 2, 1],
            "south": [width // 2, height - 2],
            "east": [width - 2, height // 2],
            "west": [1, height // 2],
        }
        bound: list[dict[str, Any]] = []
        used_dirs: set[str] = set()
        for to_node, link in sorted((exits_map or {}).items()):
            direction = str((link or {}).get("direction") or "north")
            if direction not in grids or direction in used_dirs:
                for cand in ("north", "east", "south", "west"):
                    if cand not in used_dirs:
                        direction = cand
                        break
            used_dirs.add(direction)
            road = self._road_to_neighbour(node_id, str(to_node))
            is_road = road is not None and str(road.get("status")) == "built"
            dest_rec = (self.state.board.get("nodes") or {}).get(str(to_node)) or {}
            dest_label = str(dest_rec.get("label") or "")
            known = bool(dest_rec.get("settlement_id") or dest_label not in {"", "Wilderness"})
            if is_road and known and dest_label and dest_label != "Wilderness":
                label = f"Road to {dest_label}"
            elif is_road:
                label = f"{direction.title()} road"
            elif known and dest_label and dest_label != "Wilderness":
                label = f"Path to {dest_label}"
            else:
                label = f"Path {direction}"
            bound.append(
                {
                    "id": f"exit.{direction}.{to_node.replace(':', '_')}",
                    "grid": list(grids[direction]),
                    "direction": direction,
                    "to": str(to_node),
                    "to_node": str(to_node),
                    "from_node": str(node_id),
                    "label": label,
                    "dest_label": dest_label or "Wilderness",
                    "passage": "road" if is_road else "trail",
                    "interactive": True,
                    "quiet_label": True,
                }
            )
        record["exits"] = bound

    def _apply_manifest_bindings(self, record: dict[str, Any], manifest: dict[str, Any] | None) -> None:
        if not manifest:
            # Bind any live buildings/people already on this node.
            manifest = self._default_manifest(record["node_id"])
        destroyed = set(record.get("destroyed_ids") or [])
        rng = _stable_rng(f"{record.get('seed')}:place")
        buildings = dict(record.get("buildings") or {})
        for building_id in manifest.get("building_ids") or []:
            if building_id in destroyed or building_id in buildings:
                continue
            if building_id not in self.state.buildings:
                continue
            origin = self._next_open_origin(record, buildings, rng)
            fw, fh = FOOTPRINT
            entrance = [origin[0] + fw // 2, origin[1] + fh]
            approach = [entrance[0], entrance[1] + 1]
            buildings[building_id] = {
                "grid": list(origin),
                "footprint": [fw, fh],
                "entrance": entrance,
                "approach": approach,
            }
        record["buildings"] = buildings

        people = dict(record.get("people_anchors") or {})
        for person_id in manifest.get("person_ids") or []:
            if person_id in destroyed or person_id in people:
                continue
            person = self.state.people.get(person_id)
            if person is None or not person.get("alive", True):
                continue
            workplace = person.get("workplace_id")
            if workplace and workplace in buildings:
                approach = list(buildings[workplace].get("approach") or buildings[workplace]["grid"])
                people[person_id] = {"grid": approach, "workplace_id": workplace}
            else:
                people[person_id] = {"grid": list(record.get("centre") or [24, 24])}
        record["people_anchors"] = people

        carts = dict(record.get("cart_anchors") or {})
        for cart_id in manifest.get("cart_ids") or []:
            if cart_id in destroyed or cart_id in carts or cart_id not in self.state.carts:
                continue
            carts[cart_id] = {"grid": [int(record["centre"][0]) + 2, int(record["centre"][1])]}
        record["cart_anchors"] = carts

        units = dict(record.get("unit_anchors") or {})
        for unit_id in manifest.get("unit_ids") or []:
            if unit_id in destroyed or unit_id in units or unit_id not in self.state.units:
                continue
            units[unit_id] = {"grid": [int(record["centre"][0]) - 2, int(record["centre"][1])]}
        record["unit_anchors"] = units

    def _default_manifest(self, node_id: str) -> dict[str, Any]:
        building_ids = [
            bid
            for bid, b in self.state.buildings.items()
            if b.get("node_id") == node_id and b.get("active", True)
        ]
        person_ids = [
            pid
            for pid, p in self.state.people.items()
            if p.get("node_id") == node_id and p.get("alive", True)
        ]
        cart_ids = [
            cid for cid, c in self.state.carts.items() if c.get("node_id") == node_id
        ]
        unit_ids = [
            uid for uid, u in self.state.units.items() if u.get("node_id") == node_id
        ]
        return {
            "building_ids": building_ids,
            "person_ids": person_ids,
            "cart_ids": cart_ids,
            "unit_ids": unit_ids,
        }

    def _ensure_capacity(self, record: dict[str, Any], manifest: dict[str, Any] | None) -> None:
        """Ordinary strategic nodes stay at the canonical LocalArea size (BASE_SIZE)."""
        record["width"] = BASE_SIZE
        record["height"] = BASE_SIZE
        centre = [BASE_SIZE // 2, BASE_SIZE // 2]
        record["centre"] = centre
        # Do not expand — pack within the standard footprint.
        _ = manifest

    def _next_open_origin(
        self,
        record: dict[str, Any],
        buildings: dict[str, Any],
        rng: random.Random,
    ) -> tuple[int, int]:
        width = int(record["width"])
        height = int(record["height"])
        occupied: set[tuple[int, int]] = set()
        for anchor in buildings.values():
            grid = anchor.get("grid") or [0, 0]
            footprint = tuple(anchor.get("footprint") or FOOTPRINT)
            occupied |= _cells_for_footprint((int(grid[0]), int(grid[1])), (int(footprint[0]), int(footprint[1])))
        # Prefer deterministic row-major strip south of centre; rng only breaks ties.
        centre = record.get("centre") or [width // 2, height // 2]
        candidates: list[tuple[int, int]] = []
        for y in range(int(centre[1]) + 2, height - 6, 5):
            for x in range(4, width - 6, 5):
                cells = _cells_for_footprint((x, y), FOOTPRINT)
                if cells.isdisjoint(occupied) and all(_in_bounds(cx, cy, width, height) for cx, cy in cells):
                    candidates.append((x, y))
        if not candidates:
            # Expand once more if packing failed.
            record["width"] = width + GROW_STEP
            record["height"] = height + GROW_STEP
            return self._next_open_origin(record, buildings, rng)
        # Stable pick: first candidate (seeded order already row-major). Touch rng for seed binding.
        _ = rng.random()
        return candidates[0]
