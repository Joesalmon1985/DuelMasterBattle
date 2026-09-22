"""Semantic labels, inspection and available actions (C09 / G04 / T079)."""

from __future__ import annotations

from typing import Any, Mapping

from .knowledge import (
    KnowledgeFact,
    debug_projection,
    filter_entity,
    mint_token,
    player_projection,
    reveal,
)

INTERACTION_RANGE_TILES = 2.0

REQUIRED_KINDS = (
    "person",
    "building",
    "unit",
    "cart",
    "road",
    "item",
    "mechanism",
    "entrance",
    "hazard",
)

ARCHETYPE_LABELS = {
    "line": "Line",
    "skirmisher": "Skirmisher",
    "heavy": "Heavy",
}

FACTION_COLOUR = {
    "faction:red": "Red",
    "faction:blue": "Blue",
    "faction:a": "Local",
}

# Exact facts that must never appear in ordinary player semantic views.
HIDDEN_PLAYER_KEYS = frozenset(
    {
        "stocks",
        "stock",
        "economy",
        "production_rate",
        "army_strength",
        "unit_count",
        "formation_strength",
        "hidden_strength",
        "secret_inventory",
        "leases",
        "command_receipts",
        "rng",
        "knowledge_raw",
    }
)


def tile_distance(a: list[float] | tuple[float, ...] | None, b: list[float] | tuple[float, ...] | None) -> float | None:
    """Chebyshev distance in tile units; None if either pose is missing."""
    if a is None or b is None:
        return None
    if len(a) < 2 or len(b) < 2:
        return None
    return float(max(abs(float(a[0]) - float(b[0])), abs(float(a[1]) - float(b[1]))))


def in_interaction_range(
    wizard_pos: list[float] | tuple[float, ...] | None,
    target_pos: list[float] | tuple[float, ...] | None,
    *,
    range_tiles: float = INTERACTION_RANGE_TILES,
) -> bool:
    dist = tile_distance(wizard_pos, target_pos)
    if dist is None:
        return False
    return dist <= float(range_tiles)


def _strip_hidden(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in HIDDEN_PLAYER_KEYS}


class SemanticResolver:
    """Knowledge- and range-aware target view for the production bridge."""

    def __init__(self, world_state: Any, *, range_tiles: float = INTERACTION_RANGE_TILES):
        self.state = world_state
        self.range_tiles = float(range_tiles)

    def _player_node(self) -> str:
        return str((self.state.player or {}).get("node_id") or "")

    def _wizard_pos(self, local_poses: Mapping[str, Any] | None = None) -> list[float] | None:
        if local_poses and "wizard" in local_poses:
            pos = local_poses["wizard"]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return [float(pos[0]), float(pos[1])]
        pos = (self.state.player or {}).get("position")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return [float(pos[0]), float(pos[1])]
        return None

    def _board_bucket(self, name: str) -> dict[str, Any]:
        board = self.state.board if isinstance(self.state.board, dict) else {}
        bucket = board.get(name)
        return bucket if isinstance(bucket, dict) else {}

    def _record_for(self, entity_id: str) -> tuple[str, dict[str, Any]] | None:
        if entity_id in (self.state.units or {}):
            return "unit", self.state.units[entity_id]
        if entity_id in (self.state.buildings or {}):
            return "building", self.state.buildings[entity_id]
        if entity_id in (self.state.people or {}):
            return "person", self.state.people[entity_id]
        if entity_id in (self.state.carts or {}):
            return "cart", self.state.carts[entity_id]
        if entity_id in (self.state.roads or {}):
            return "road", self.state.roads[entity_id]
        if entity_id in (self.state.items or {}):
            item = self.state.items[entity_id]
            kind = str(item.get("kind") or "item")
            if kind == "mechanism":
                return "mechanism", item
            if kind in {"entrance", "exit", "door"}:
                return "entrance", item
            return "item", item
        for mech_id, mech in self._board_bucket("mechanisms").items():
            if mech_id == entity_id:
                return "mechanism", mech
        for ent_id, entrance in self._board_bucket("entrances").items():
            if ent_id == entity_id:
                return "entrance", entrance
        cubes = ((self.state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
        if entity_id in cubes:
            return "hazard", cubes[entity_id]
        # Hex id → active cube
        for cube in cubes.values():
            if str(cube.get("hex_id")) == entity_id and cube.get("active", True):
                return "hazard", cube
        return None

    def _target_pos(
        self,
        entity_id: str,
        record: dict[str, Any],
        kind: str,
        local_poses: Mapping[str, Any] | None = None,
    ) -> list[float] | None:
        if local_poses and entity_id in local_poses:
            pos = local_poses[entity_id]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return [float(pos[0]), float(pos[1])]
        pos = record.get("position") or record.get("grid")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return [float(pos[0]), float(pos[1])]
        if kind == "road":
            # Roads use edge midpoints when authored.
            mid = record.get("midpoint") or record.get("from_grid")
            if isinstance(mid, (list, tuple)) and len(mid) >= 2:
                return [float(mid[0]), float(mid[1])]
        if kind == "hazard":
            hid = str(record.get("hex_id") or "")
            anchors = (self.state.board or {}).get("hex_anchors") or {}
            anchor = anchors.get(hid) or {}
            grid = anchor.get("grid")
            if isinstance(grid, (list, tuple)) and len(grid) >= 2:
                return [float(grid[0]), float(grid[1])]
        return None

    def _target_node(self, record: dict[str, Any], kind: str) -> str:
        if kind == "hazard":
            return self._player_node()
        return str(
            record.get("node_id")
            or record.get("current_node")
            or record.get("home_node_id")
            or ""
        )

    def select(
        self,
        entity_id: str,
        *,
        local_poses: Mapping[str, Any] | None = None,
        expected_world_version: int | None = None,
    ) -> dict[str, Any]:
        """Select any visible/targetable entity; unknown identity stays targetable."""
        if expected_world_version is not None and int(expected_world_version) != int(self.state.world_version):
            return {
                "ok": False,
                "reason": "stale_world",
                "refresh": True,
                "entity_id": entity_id,
                "world_version": int(self.state.world_version),
                "label": "Outdated",
                "targetable": False,
            }
        classified = self._record_for(entity_id)
        if classified is None:
            # Stale / destroyed entity: still returns structured refresh feedback.
            return {
                "ok": False,
                "reason": "missing_entity",
                "refresh": True,
                "entity_id": entity_id,
                "world_version": int(self.state.world_version),
                "label": "Gone",
                "targetable": False,
            }
        kind, record = classified
        known = filter_entity(self.state, entity_id)
        unknown_identity = not bool(known.get("known")) and known.get("name") is None
        info = self.inspect(entity_id, local_poses=local_poses)
        payload = {
            "ok": True,
            "entity_id": entity_id,
            "kind": kind,
            "label": info.get("label"),
            "unknown_identity": unknown_identity,
            "targetable": True,
            "refresh": False,
            "world_version": int(self.state.world_version),
            "nearby": info.get("nearby"),
            "actions": self.available_actions(entity_id, local_poses=local_poses),
        }
        return _strip_hidden(payload)

    def label(self, entity_id: str, *, local_poses: Mapping[str, Any] | None = None) -> str:
        classified = self._record_for(entity_id)
        if classified is None:
            return "Unknown"
        kind, record = classified
        known = filter_entity(self.state, entity_id)
        known_name = known.get("name")
        fx = (self.state.board or {}).get("fx_battle") or {}
        labels = fx.get("labels") or {}
        if kind == "unit":
            person_id = record.get("person_id")
            person = self.state.people.get(person_id) if person_id else None
            person_name = None
            if person:
                person_name = person.get("name") or person.get("display_name")
            if entity_id in labels:
                public = str(labels[entity_id])
            else:
                fac = str(record.get("faction_id") or "")
                colour = FACTION_COLOUR.get(fac, fac.replace("faction:", "").title() or "Unit")
                arch = str(record.get("archetype") or "")
                arch_label = ARCHETYPE_LABELS.get(arch, arch.title() or "Soldier")
                public = f"{colour} {arch_label}".strip()
            known_person = filter_entity(self.state, str(person_id)) if person_id else {}
            display = known_name or known_person.get("name") or person_name or record.get("person_name")
            if display and " — " not in public:
                return f"{public} — {display}"
            return public
        if kind == "building":
            return str(record.get("label") or record.get("definition_id") or "Building")
        if kind == "hazard":
            hid = str(record.get("hex_id") or "")
            fxh = (self.state.board or {}).get("fx_hazard") or {}
            return str((fxh.get("hex_labels") or {}).get(hid) or f"Hazard {hid}")
        if kind == "person":
            if known_name:
                return str(known_name)
            if known.get("role"):
                return str(known["role"])
            return "Person"
        if kind == "cart":
            return str(record.get("label") or "Cart")
        if kind == "road":
            return str(record.get("label") or "Road")
        if kind == "item":
            if known_name:
                return str(known_name)
            return str(record.get("label") or record.get("definition_id") or "Item")
        if kind == "mechanism":
            return str(record.get("label") or "Mechanism")
        if kind == "entrance":
            if record.get("dungeon_id"):
                return str(record.get("label") or "Dungeon")
            return str(record.get("label") or "Door")
        return "Unknown"

    def inspect(
        self,
        entity_id: str,
        *,
        local_poses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        classified = self._record_for(entity_id)
        if classified is None:
            return {
                "ok": False,
                "reason": "unknown_target",
                "label": "Unknown",
                "refresh": True,
                "world_version": int(self.state.world_version),
            }
        kind, record = classified
        wizard_pos = self._wizard_pos(local_poses)
        target_pos = self._target_pos(entity_id, record, kind, local_poses)
        dist = tile_distance(wizard_pos, target_pos)
        nearby = in_interaction_range(wizard_pos, target_pos, range_tiles=self.range_tiles)
        same_node = self._target_node(record, kind) in {"", self._player_node()}
        known = filter_entity(self.state, entity_id)
        is_nearby = bool(nearby and same_node)
        payload = {
            "ok": True,
            "entity_id": entity_id,
            "kind": kind,
            "label": self.label(entity_id, local_poses=local_poses),
            "description": self._description(kind, record, entity_id, nearby=is_nearby),
            "same_node": same_node,
            "distance_tiles": dist,
            "nearby": is_nearby,
            "faction_id": record.get("faction_id"),
            "alive": record.get("alive", record.get("active", True)),
            "unknown_identity": not bool(known.get("known")) and known.get("name") is None,
            "world_version": int(self.state.world_version),
            "refresh": False,
        }
        return _strip_hidden(payload)

    def _description(self, kind: str, record: dict[str, Any], entity_id: str, *, nearby: bool = False) -> str:
        label = self.label(entity_id)
        if kind == "unit":
            hp = record.get("current_health")
            mx = record.get("max_health")
            if hp is not None and mx is not None:
                return f"{label}. Health {int(hp)}/{int(mx)}."
            return f"{label}."
        if kind == "hazard":
            return f"{label}. Catastrophe manifestation."
        if kind == "building":
            return f"{label}."
        if kind == "road":
            return f"{label}."
        if kind == "item":
            return f"{label}."
        if kind == "mechanism":
            if str(record.get("kind") or "") == "boulder" or str(entity_id).startswith("boulder:"):
                status = str(record.get("status") or "blocking")
                if status == "moved":
                    return str(
                        record.get("observe_near_moved")
                        or record.get("observe_near")
                        or "The boulder has been rolled clear of the path."
                    )
                if nearby:
                    return str(record.get("observe_near") or "It is far too heavy for John to move alone.")
                return str(record.get("observe_far") or "A large boulder blocks the path out of the village.")
            return f"{label}."
        if kind == "entrance":
            return f"{label}."
        if kind == "cart":
            return f"{label}."
        return f"{label}."

    def available_actions(
        self,
        entity_id: str,
        *,
        local_poses: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        info = self.inspect(entity_id, local_poses=local_poses)
        if not info.get("ok"):
            return []
        actions: list[dict[str, Any]] = [
            {"id": "observe", "label": "Observe", "requires_nearby": False},
        ]
        if not info.get("same_node"):
            return actions
        if not info.get("nearby"):
            return actions
        kind = info["kind"]
        if kind == "unit" and info.get("alive", True):
            actions.append({"id": "talk", "label": "Talk", "requires_nearby": True})
            actions.append(
                {
                    "id": "buff",
                    "label": "Buff…",
                    "requires_nearby": True,
                    "submenu": [
                        {"id": "buff_shield", "label": "Shield", "buff_kind": "shield"},
                        {"id": "buff_frequency", "label": "Attack speed", "buff_kind": "frequency"},
                        {"id": "buff_range", "label": "Range", "buff_kind": "range"},
                    ],
                }
            )
            actions.append({"id": "destroy", "label": "Destroy", "requires_nearby": True})
        elif kind in {"building", "cart"} and info.get("alive", True):
            actions.append({"id": "destroy", "label": "Destroy", "requires_nearby": True})
        elif kind == "person" and info.get("alive", True):
            actions.append({"id": "talk", "label": "Talk", "requires_nearby": True})
            # Combatant persons also expose magic verbs via linked unit when present.
            unit_id = (self.state.people.get(entity_id) or {}).get("unit_id")
            unit = self.state.units.get(unit_id) if unit_id else None
            if unit and unit.get("alive", True):
                actions.append(
                    {
                        "id": "buff",
                        "label": "Buff…",
                        "requires_nearby": True,
                        "submenu": [
                            {"id": "buff_shield", "label": "Shield", "buff_kind": "shield"},
                            {"id": "buff_frequency", "label": "Attack speed", "buff_kind": "frequency"},
                            {"id": "buff_range", "label": "Range", "buff_kind": "range"},
                        ],
                        "target_unit_id": unit_id,
                    }
                )
                actions.append(
                    {"id": "destroy", "label": "Destroy", "requires_nearby": True, "target_unit_id": unit_id}
                )
        elif kind == "hazard" and info.get("alive", True):
            actions.append({"id": "challenge", "label": "Challenge", "requires_nearby": True})
        elif kind == "item" and info.get("alive", True):
            actions.append({"id": "take", "label": "Take", "requires_nearby": True})
        elif kind == "mechanism" and info.get("alive", True):
            actions.append({"id": "use", "label": "Use", "requires_nearby": True})
        elif kind == "entrance" and info.get("alive", True):
            actions.append({"id": "enter", "label": "Enter", "requires_nearby": True})
        elif kind == "road":
            actions.append({"id": "inspect_road", "label": "Inspect", "requires_nearby": True})
        return actions

    def player_view(self, entity_id: str, *, local_poses: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Player-facing semantic payload with hidden economy/army facts stripped."""
        selected = self.select(entity_id, local_poses=local_poses)
        return _strip_hidden(selected)

    def kinds_supported(self) -> tuple[str, ...]:
        return REQUIRED_KINDS


__all__ = [
    "KnowledgeFact",
    "SemanticResolver",
    "INTERACTION_RANGE_TILES",
    "REQUIRED_KINDS",
    "HIDDEN_PLAYER_KEYS",
    "debug_projection",
    "filter_entity",
    "in_interaction_range",
    "mint_token",
    "player_projection",
    "reveal",
    "tile_distance",
]
