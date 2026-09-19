"""Leased puzzle mechanism runtime (C10 / T089).

Python owns durable puzzle bindings, inventory interactions and finish effects.
Godot executes the whitelisted mechanism graph under an ACTIVE lease and submits
local pose / action updates. Checkpoint version is enforced on every mutation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.effects import apply_effects, validate_effects
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.player.inventory import InventoryService

PUZZLE_LEASE_KIND = "puzzle"
PUZZLE_SCHEMA_VERSION = 1
POSITION_EPSILON = 0.51  # tile-unit tolerance for pressure plates


def _pos(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    return [0.0, 0.0]


def _near(a: list[float], b: list[float], epsilon: float = POSITION_EPSILON) -> bool:
    return abs(a[0] - b[0]) <= epsilon and abs(a[1] - b[1]) <= epsilon


def fresh_mechanism_state(definition: dict[str, Any]) -> dict[str, Any]:
    """Authoritative initial local state for all mechanisms in a puzzle def."""
    mechs: dict[str, Any] = {}
    for mech in definition.get("mechanisms") or []:
        mid = str(mech["id"])
        kind = str(mech["kind"])
        record: dict[str, Any] = {
            "id": mid,
            "kind": kind,
            "active": False,
            "position": _pos(mech.get("position")),
        }
        if kind == "movable_box":
            record["position"] = _pos(mech.get("position") or mech.get("start_position"))
        if kind == "item_receptor":
            record["held_item_id"] = None
            record["accepts_definition_id"] = mech.get("accepts_definition_id")
            record["holds"] = bool(mech.get("holds", True))
            record["consumes"] = bool(mech.get("consumes", False))
        if kind == "sequence":
            record["progress"] = 0
            record["sequence"] = list(mech.get("sequence") or [])
        if kind in {"door", "gate", "timed_gate"}:
            record["open"] = False
            record["duration_game_ms"] = int(mech.get("duration_game_ms") or 0)
            record["opened_at_game_ms"] = None
        if kind == "switch":
            record["on"] = False
        mechs[mid] = record
    reset = dict(definition.get("reset_state") or {})
    for mid, patch in (reset.get("mechanisms") or {}).items():
        if mid in mechs and isinstance(patch, dict):
            mechs[mid].update(deepcopy(patch))
    return {
        "schema_version": int(definition.get("schema_version") or PUZZLE_SCHEMA_VERSION),
        "solved": False,
        "finish_applied": False,
        "mechanisms": mechs,
        "local_actors": {},
    }


@dataclass
class PuzzleService:
    state: WorldState

    def _puzzles(self) -> dict[str, Any]:
        return self.state.definitions.setdefault("puzzles", {})

    def register_definition(self, definition: dict[str, Any]) -> dict[str, Any]:
        pid = str(definition.get("id") or "")
        if not pid:
            raise TypeValidationError("puzzle definition requires id")
        if not definition.get("mechanisms"):
            raise TypeValidationError("puzzle definition requires mechanisms")
        if not (definition.get("solve_when") or {}).get("all"):
            raise TypeValidationError("puzzle definition requires solve_when.all")
        store = self._puzzles()
        store[pid] = deepcopy(definition)
        return dict(store[pid])

    def get_definition(self, puzzle_id: str) -> dict[str, Any]:
        definition = self._puzzles().get(puzzle_id)
        if definition is None:
            raise TypeValidationError(f"unknown puzzle {puzzle_id}")
        return dict(definition)

    def prepare_lease(
        self,
        puzzle_id: str,
        *,
        lease_id: str | None = None,
        area_id: str | None = None,
        bindings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        definition = self.get_definition(puzzle_id)
        # Reuse existing ACTIVE lease for the same puzzle.
        for existing in (self.state.leases or {}).values():
            if (
                isinstance(existing, dict)
                and existing.get("kind") == PUZZLE_LEASE_KIND
                and existing.get("state") == "ACTIVE"
                and existing.get("puzzle_id") == puzzle_id
            ):
                return {"status": "reused", "lease": dict(existing)}

        lid = lease_id or self.state.ids.new("lease")
        checkpoint = fresh_mechanism_state(definition)
        if bindings:
            checkpoint["bindings"] = deepcopy(bindings)
        record = {
            "id": lid,
            "lease_id": lid,
            "kind": PUZZLE_LEASE_KIND,
            "puzzle_id": puzzle_id,
            "area_id": area_id or definition.get("area_id"),
            "state": "ACTIVE",
            "version": 1,
            "checkpoint": checkpoint,
            "definition_schema_version": int(definition.get("schema_version") or 1),
        }
        self.state.leases[lid] = record
        return {"status": "started", "lease": dict(record)}

    def _require_lease(self, lease_id: str) -> dict[str, Any]:
        lease = (self.state.leases or {}).get(lease_id)
        if lease is None or lease.get("kind") != PUZZLE_LEASE_KIND:
            raise TypeValidationError(f"unknown puzzle lease {lease_id}")
        if lease.get("state") != "ACTIVE":
            raise TypeValidationError("puzzle lease not active")
        return lease

    def _enforce_version(self, lease: dict[str, Any], expected_version: int) -> None:
        current = int(lease.get("version") or 0)
        if int(expected_version) != current:
            raise TypeValidationError(
                f"mechanism checkpoint version mismatch: expected {expected_version}, have {current}"
            )

    def sync_local_pose(
        self,
        lease_id: str,
        *,
        expected_version: int,
        actor_id: str,
        position: list[float],
        kind: str = "actor",
    ) -> dict[str, Any]:
        lease = self._require_lease(lease_id)
        self._enforce_version(lease, expected_version)
        checkpoint = lease["checkpoint"]
        actors = checkpoint.setdefault("local_actors", {})
        actors[actor_id] = {"id": actor_id, "kind": kind, "position": _pos(position)}
        # Movable boxes are local actors that also update mechanism position.
        mech = (checkpoint.get("mechanisms") or {}).get(actor_id)
        if mech and mech.get("kind") == "movable_box":
            mech["position"] = _pos(position)
        self._refresh_pressure_plates(lease)
        lease["version"] = int(lease["version"]) + 1
        return {"status": "synced", "lease": dict(lease), "version": lease["version"]}

    def _refresh_pressure_plates(self, lease: dict[str, Any]) -> None:
        definition = self.get_definition(str(lease["puzzle_id"]))
        mech_defs = {str(m["id"]): m for m in definition.get("mechanisms") or []}
        checkpoint = lease["checkpoint"]
        mechanisms = checkpoint.get("mechanisms") or {}
        actors = list((checkpoint.get("local_actors") or {}).values())
        for mid, mech in mechanisms.items():
            if mech.get("kind") != "pressure_plate":
                continue
            plate_pos = _pos(mech.get("position") or mech_defs.get(mid, {}).get("position"))
            linked = mech_defs.get(mid, {}).get("linked_box")
            occupied = False
            for actor in actors:
                if linked and actor.get("id") != linked and actor.get("kind") != "movable_box":
                    # Prefer the linked box when authored; still allow exact id match.
                    if str(actor.get("id")) != str(linked):
                        continue
                if _near(_pos(actor.get("position")), plate_pos):
                    occupied = True
                    break
            # Also check movable_box mechanism positions directly.
            if not occupied:
                for other in mechanisms.values():
                    if other.get("kind") != "movable_box":
                        continue
                    if linked and str(other.get("id")) != str(linked):
                        continue
                    if _near(_pos(other.get("position")), plate_pos):
                        occupied = True
                        break
            mech["active"] = occupied
            mech["position"] = plate_pos

    def act(
        self,
        lease_id: str,
        *,
        expected_version: int,
        mechanism_id: str,
        action: str,
        item_id: str | None = None,
        holder_id: str = "player",
        game_ms: int | None = None,
    ) -> dict[str, Any]:
        lease = self._require_lease(lease_id)
        self._enforce_version(lease, expected_version)
        if lease["checkpoint"].get("solved"):
            return {"status": "already_solved", "lease": dict(lease), "version": lease["version"]}

        definition = self.get_definition(str(lease["puzzle_id"]))
        mech_defs = {str(m["id"]): m for m in definition.get("mechanisms") or []}
        if mechanism_id not in mech_defs:
            raise TypeValidationError(f"unknown mechanism {mechanism_id}")
        mech = lease["checkpoint"]["mechanisms"][mechanism_id]
        kind = str(mech["kind"])
        action = str(action)

        if kind == "switch" and action in {"toggle", "on", "off"}:
            if action in {"toggle", "on"} and not self._requirements_met(lease, mech_defs[mechanism_id]):
                raise TypeValidationError("switch requirements not met")
            if action == "toggle":
                mech["on"] = not bool(mech.get("on"))
            else:
                mech["on"] = action == "on"
            mech["active"] = bool(mech["on"])
        elif kind == "item_receptor" and action in {"place", "insert"}:
            self._place_in_receptor(mech, mech_defs[mechanism_id], item_id=item_id, holder_id=holder_id)
        elif kind == "item_receptor" and action == "take":
            self._take_from_receptor(mech, holder_id=holder_id)
        elif kind == "sequence" and action == "press":
            step = item_id  # reuse item_id field as sequence step token when provided
            if step is None:
                raise TypeValidationError("sequence press requires step id")
            seq = list(mech.get("sequence") or mech_defs[mechanism_id].get("sequence") or [])
            progress = int(mech.get("progress") or 0)
            if progress < len(seq) and str(seq[progress]) == str(step):
                mech["progress"] = progress + 1
            else:
                mech["progress"] = 0
            mech["active"] = int(mech["progress"]) >= len(seq) and len(seq) > 0
        elif kind in {"door", "gate"} and action in {"open", "close"}:
            if not self._requirements_met(lease, mech_defs[mechanism_id]):
                raise TypeValidationError("door requirements not met")
            mech["open"] = action == "open"
            mech["active"] = bool(mech["open"])
        elif kind == "timed_gate" and action == "open":
            if not self._requirements_met(lease, mech_defs[mechanism_id]):
                raise TypeValidationError("timed gate requirements not met")
            now = int(game_ms if game_ms is not None else self.state.clock.get("game_ms", 0))
            mech["open"] = True
            mech["active"] = True
            mech["opened_at_game_ms"] = now
        elif kind == "movable_box" and action == "push":
            # Client should prefer sync_local_pose; allow discrete nudge for tests.
            delta = _pos(mech_defs[mechanism_id].get("push_delta") or [1.0, 0.0])
            pos = _pos(mech.get("position"))
            mech["position"] = [pos[0] + delta[0], pos[1] + delta[1]]
            lease["checkpoint"].setdefault("local_actors", {})[mechanism_id] = {
                "id": mechanism_id,
                "kind": "movable_box",
                "position": list(mech["position"]),
            }
        elif kind == "pressure_plate":
            raise TypeValidationError("pressure plates follow local position; use sync_local_pose")
        else:
            raise TypeValidationError(f"unsupported action {action!r} for {kind}")

        self._refresh_pressure_plates(lease)
        self._refresh_timed_gates(lease, game_ms=game_ms)
        self._propagate_doors(lease, definition)
        solved_now = self._evaluate_solve(lease, definition)
        lease["version"] = int(lease["version"]) + 1
        result: dict[str, Any] = {
            "status": "acted",
            "mechanism_id": mechanism_id,
            "action": action,
            "solved_now": solved_now,
            "lease": dict(lease),
            "version": lease["version"],
        }
        if solved_now:
            finish = self.finish(lease_id, expected_version=lease["version"], command_id=None)
            result["finish"] = finish
            result["version"] = lease["version"]
            result["lease"] = dict(lease)
        return result

    def _place_in_receptor(
        self,
        mech: dict[str, Any],
        mech_def: dict[str, Any],
        *,
        item_id: str | None,
        holder_id: str,
    ) -> None:
        if mech.get("held_item_id"):
            raise TypeValidationError("receptor already holds an item")
        if not item_id:
            raise TypeValidationError("item_id required for receptor place")
        inv = InventoryService(self.state)
        item = inv._ensure_item(item_id)
        if item.get("holder_id") != holder_id:
            raise TypeValidationError("wrong owner")
        accepts = str(mech_def.get("accepts_definition_id") or mech.get("accepts_definition_id") or "")
        if accepts and str(item.get("definition_id")) != accepts:
            raise TypeValidationError("receptor rejects item definition")
        # Hold or consume the real inventory instance once.
        if mech_def.get("consumes") or mech.get("consumes"):
            item["alive"] = False
            item["quantity"] = 0
            item["holder_id"] = None
            item["container_id"] = None
            item["ground"] = None
            mech["held_item_id"] = item_id
            mech["consumed"] = True
        else:
            item["holder_id"] = None
            item["container_id"] = f"receptor:{mech['id']}"
            item["ground"] = None
            mech["held_item_id"] = item_id
            mech["consumed"] = False
        mech["active"] = True

    def _take_from_receptor(self, mech: dict[str, Any], *, holder_id: str) -> None:
        item_id = mech.get("held_item_id")
        if not item_id:
            raise TypeValidationError("receptor empty")
        if mech.get("consumed"):
            raise TypeValidationError("consumed item cannot be taken")
        inv = InventoryService(self.state)
        item = inv._ensure_item(str(item_id))
        if not item.get("alive", True):
            raise TypeValidationError("item destroyed")
        inv.pickup(str(item_id), holder_id=holder_id)
        mech["held_item_id"] = None
        mech["active"] = False

    def _requirements_met(self, lease: dict[str, Any], mech_def: dict[str, Any]) -> bool:
        required = list(mech_def.get("requires") or [])
        mechanisms = lease["checkpoint"].get("mechanisms") or {}
        for rid in required:
            other = mechanisms.get(str(rid)) or {}
            if not (other.get("active") or other.get("open") or other.get("on")):
                return False
        return True

    def _refresh_timed_gates(self, lease: dict[str, Any], *, game_ms: int | None) -> None:
        now = int(game_ms if game_ms is not None else self.state.clock.get("game_ms", 0))
        for mech in (lease["checkpoint"].get("mechanisms") or {}).values():
            if mech.get("kind") != "timed_gate":
                continue
            if not mech.get("open"):
                continue
            opened = mech.get("opened_at_game_ms")
            duration = int(mech.get("duration_game_ms") or 0)
            if opened is not None and duration > 0 and now - int(opened) >= duration:
                mech["open"] = False
                mech["active"] = False

    def _propagate_doors(self, lease: dict[str, Any], definition: dict[str, Any]) -> None:
        mechanisms = lease["checkpoint"].get("mechanisms") or {}
        for mech_def in definition.get("mechanisms") or []:
            mid = str(mech_def["id"])
            mech = mechanisms.get(mid)
            if mech is None or mech.get("kind") not in {"door", "gate"}:
                continue
            if mech_def.get("requires"):
                mech["open"] = self._requirements_met(lease, mech_def)
                mech["active"] = bool(mech["open"])

    def _evaluate_solve(self, lease: dict[str, Any], definition: dict[str, Any]) -> bool:
        if lease["checkpoint"].get("solved"):
            return False
        required = list((definition.get("solve_when") or {}).get("all") or [])
        mechanisms = lease["checkpoint"].get("mechanisms") or {}
        for mid in required:
            mech = mechanisms.get(str(mid)) or {}
            if not (mech.get("active") or mech.get("open") or mech.get("on")):
                return False
        lease["checkpoint"]["solved"] = True
        return True

    def finish(
        self,
        lease_id: str,
        *,
        expected_version: int,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply finish effects once. Duplicate finish is idempotent."""
        lease = self._require_lease(lease_id)
        self._enforce_version(lease, expected_version)
        checkpoint = lease["checkpoint"]
        if not checkpoint.get("solved"):
            raise TypeValidationError("puzzle not solved")
        finish_id = command_id or f"puzzle.finish:{lease.get('puzzle_id')}:{lease_id}"
        if checkpoint.get("finish_applied") or finish_id in (self.state.command_receipts or {}):
            return {
                "status": "idempotent",
                "finish_id": finish_id,
                "lease": dict(lease),
                "version": lease["version"],
            }
        definition = self.get_definition(str(lease["puzzle_id"]))
        effects = list(definition.get("finish_effects") or [])
        stamped = []
        for idx, effect in enumerate(effects):
            stamped_effect = dict(effect)
            stamped_effect["effect_id"] = (
                f"{finish_id}:{stamped_effect.get('effect_id') or idx}"
            )
            stamped.append(stamped_effect)
        if stamped:
            validate_effects(stamped)
            applied = apply_effects(self.state, stamped)
        else:
            applied = []
        checkpoint["finish_applied"] = True
        self.state.command_receipts[finish_id] = {
            "status": "applied",
            "puzzle_id": lease.get("puzzle_id"),
            "effects": applied,
        }
        lease["version"] = int(lease["version"]) + 1
        return {
            "status": "applied",
            "finish_id": finish_id,
            "effects": applied,
            "lease": dict(lease),
            "version": lease["version"],
        }

    def release(self, lease_id: str) -> dict[str, Any]:
        lease = (self.state.leases or {}).get(lease_id)
        if lease is None:
            return {"status": "missing"}
        lease["state"] = "RELEASED"
        return {"status": "released", "lease": dict(lease)}
