"""WorldState registries and immutable read views."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.types import TypeValidationError, WorldId


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass
class WorldState:
    world_id: WorldId
    world_version: int = 0
    ids: IdAllocator = field(default_factory=lambda: IdAllocator(WorldId("unset")))
    catalog_hash: str = ""
    clock: dict[str, Any] = field(
        default_factory=lambda: {
            "game_ms": 0,
            "residual_ms": 0,
            "turn": 0,
            "round": 0,
            "scheduled_faction_ids": [],
            "completed_seats": [],
            "active_faction_id": None,
            "pause_tokens": {},
            "clock_sequence": 0,
        }
    )
    player: dict[str, Any] = field(
        default_factory=lambda: {
            "node_id": "node:1",
            "area_id": "area.local",
            "position": [0, 0],
        }
    )
    board: dict[str, Any] = field(
        default_factory=lambda: {
            "nodes": {
                "node:1": {"id": "node:1", "exits": ["node:2"]},
                "node:2": {"id": "node:2", "exits": ["node:1"]},
            }
        }
    )
    factions: dict[str, Any] = field(default_factory=dict)
    settlements: dict[str, Any] = field(default_factory=dict)
    buildings: dict[str, Any] = field(default_factory=dict)
    people: dict[str, Any] = field(default_factory=dict)
    carts: dict[str, Any] = field(default_factory=dict)
    units: dict[str, Any] = field(default_factory=dict)
    stocks: dict[str, Any] = field(default_factory=dict)
    orders: dict[str, Any] = field(default_factory=dict)
    roads: dict[str, Any] = field(default_factory=dict)
    quests: dict[str, Any] = field(default_factory=dict)
    items: dict[str, Any] = field(default_factory=dict)
    leases: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    tombstones: dict[str, Any] = field(default_factory=dict)
    command_receipts: dict[str, Any] = field(default_factory=dict)
    definitions: dict[str, Any] = field(default_factory=dict)
    rng: dict[str, Any] = field(default_factory=dict)
    legacy_godot_world_tick_enabled: bool = False
    legacy_godot_world_save_enabled: bool = False

    def __post_init__(self) -> None:
        if self.ids.world_id == "unset":
            self.ids = IdAllocator(self.world_id)

    def read_view(self, scope: str = "player") -> Mapping[str, Any]:
        from sim.dmb.narrative.knowledge import filter_entity

        people = {}
        for entity_id, record in self.people.items():
            filtered = filter_entity(self, entity_id)
            # Presentation layout hints (not identity secrets).
            filtered = dict(filtered)
            filtered["node_id"] = record.get("node_id")
            filtered["grid"] = list(record.get("grid", []))
            people[entity_id] = filtered
        payload = {
            "world_id": self.world_id,
            "world_version": self.world_version,
            "clock": deepcopy(self.clock),
            "player": deepcopy(self.player),
            "board": {"nodes": deepcopy(self.board.get("nodes", {}))},
            "people": people,
            "scope": scope,
        }
        if scope == "debug":
            payload["leases"] = deepcopy(self.leases)
            payload["command_receipts"] = deepcopy(self.command_receipts)
            payload["knowledge_raw"] = deepcopy(self.knowledge)
        return _freeze(payload)

    def validate(self) -> list[str]:
        violations: list[str] = []
        nodes = self.board.get("nodes", {})
        node_id = self.player.get("node_id")
        if node_id not in nodes:
            violations.append(f"dangling player node_id {node_id!r}")
        for entity_id, record in self.people.items():
            if record.get("definition_id") and entity_id == record.get("definition_id"):
                violations.append(f"definition/instance collision {entity_id}")
            workplace = record.get("workplace_id")
            if workplace and workplace not in self.buildings and workplace not in self.tombstones:
                violations.append(f"dangling workplace {workplace}")
        for tomb_id, tomb in self.tombstones.items():
            if "kind" not in tomb or "display_name" not in tomb:
                violations.append(f"incomplete tombstone {tomb_id}")
        if self.legacy_godot_world_tick_enabled or self.legacy_godot_world_save_enabled:
            violations.append("legacy Godot world writers must remain disabled in migrated runtime")
        return violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "world_version": self.world_version,
            "ids": self.ids.to_dict(),
            "catalog_hash": self.catalog_hash,
            "clock": deepcopy(self.clock),
            "player": deepcopy(self.player),
            "board": deepcopy(self.board),
            "factions": deepcopy(self.factions),
            "settlements": deepcopy(self.settlements),
            "buildings": deepcopy(self.buildings),
            "people": deepcopy(self.people),
            "carts": deepcopy(self.carts),
            "units": deepcopy(self.units),
            "stocks": deepcopy(self.stocks),
            "orders": deepcopy(self.orders),
            "roads": deepcopy(self.roads),
            "quests": deepcopy(self.quests),
            "items": deepcopy(self.items),
            "leases": deepcopy(self.leases),
            "knowledge": deepcopy(self.knowledge),
            "tombstones": deepcopy(self.tombstones),
            "command_receipts": deepcopy(self.command_receipts),
            "definitions": deepcopy(self.definitions),
            "rng": deepcopy(self.rng),
            "legacy_godot_world_tick_enabled": False,
            "legacy_godot_world_save_enabled": False,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorldState":
        world_id = WorldId(str(payload["world_id"]))
        ids = IdAllocator.from_dict(payload["ids"], expected_world_id=world_id)
        state = cls(
            world_id=world_id,
            world_version=int(payload.get("world_version", 0)),
            ids=ids,
            catalog_hash=str(payload.get("catalog_hash", "")),
            clock=dict(payload.get("clock", {})),
            player=dict(payload.get("player", {})),
            board=dict(payload.get("board", {})),
            factions=dict(payload.get("factions", {})),
            settlements=dict(payload.get("settlements", {})),
            buildings=dict(payload.get("buildings", {})),
            people=dict(payload.get("people", {})),
            carts=dict(payload.get("carts", {})),
            units=dict(payload.get("units", {})),
            stocks=dict(payload.get("stocks", {})),
            orders=dict(payload.get("orders", {})),
            roads=dict(payload.get("roads", {})),
            quests=dict(payload.get("quests", {})),
            items=dict(payload.get("items", {})),
            leases=dict(payload.get("leases", {})),
            knowledge=dict(payload.get("knowledge", {})),
            tombstones=dict(payload.get("tombstones", {})),
            command_receipts=dict(payload.get("command_receipts", {})),
            definitions=dict(payload.get("definitions", {})),
            rng=dict(payload.get("rng", {})),
            legacy_godot_world_tick_enabled=False,
            legacy_godot_world_save_enabled=False,
        )
        violations = state.validate()
        if violations:
            raise TypeValidationError("; ".join(violations))
        return state
