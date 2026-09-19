"""Wizard destruction and support magic (C07 / T065–T066 / G04)."""

from __future__ import annotations

from typing import Any, Mapping

from sim.dmb.core.effects import apply_effect
from sim.dmb.narrative.semantic import INTERACTION_RANGE_TILES, in_interaction_range, tile_distance

ORDINARY_KINDS = {"unit", "person", "worker", "cart", "building"}
BUFF_KINDS = {"shield", "frequency", "range"}


class MagicService:
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

    def _target_pos(
        self,
        target_id: str,
        record: dict[str, Any],
        local_poses: Mapping[str, Any] | None = None,
    ) -> list[float] | None:
        if local_poses and target_id in local_poses:
            pos = local_poses[target_id]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return [float(pos[0]), float(pos[1])]
        pos = record.get("position") or record.get("grid")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return [float(pos[0]), float(pos[1])]
        return None

    def _classify(self, target_id: str) -> tuple[str, dict[str, Any]] | None:
        if target_id in (self.state.units or {}):
            return "unit", self.state.units[target_id]
        if target_id in (self.state.people or {}):
            person = self.state.people[target_id]
            kind = "worker" if person.get("role") in {"worker", "civilian"} or person.get("is_worker") else "person"
            return kind, person
        if target_id in (self.state.carts or {}):
            return "cart", self.state.carts[target_id]
        if target_id in (self.state.buildings or {}):
            return "building", self.state.buildings[target_id]
        return None

    def _locality_ok(
        self,
        target_id: str,
        record: dict[str, Any],
        *,
        local_poses: Mapping[str, Any] | None = None,
        require_range: bool = True,
    ) -> dict[str, Any] | None:
        """Return a rejection dict, or None when locality checks pass.

        Caller-supplied observed_ids never grant authority. Same-node membership
        and synchronised tile range are required for nearby actions.
        """
        target_node = str(
            record.get("node_id")
            or record.get("current_node")
            or record.get("home_node_id")
            or ""
        )
        if target_node and target_node != self._player_node():
            return {"ok": False, "reason": "remote_or_unobserved"}
        if not require_range:
            return None
        wizard_pos = self._wizard_pos(local_poses)
        target_pos = self._target_pos(target_id, record, local_poses)
        # When poses are unavailable (legacy unit tests), same-node alone stands.
        if wizard_pos is None or target_pos is None:
            return None
        if not in_interaction_range(wizard_pos, target_pos, range_tiles=self.range_tiles):
            return {
                "ok": False,
                "reason": "out_of_range",
                "distance_tiles": tile_distance(wizard_pos, target_pos),
                "range_tiles": self.range_tiles,
            }
        return None

    def validate_destroy(
        self,
        target_id: str,
        *,
        observed_local_ids: set[str] | None = None,
        command_id: str | None = None,
        local_poses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        # observed_local_ids is ignored for authority (G04); retained only for API compat.
        _ = observed_local_ids
        if target_id in {"wizard", "player"} or target_id == (self.state.player or {}).get("id"):
            return {"ok": False, "reason": "self_target"}
        if target_id.startswith("group:") or target_id.startswith("formation:"):
            return {"ok": False, "reason": "group_target"}
        classified = self._classify(target_id)
        if classified is None:
            if target_id.startswith("hazard:") or target_id.startswith("rival:"):
                return {"ok": False, "reason": "rival_duel_actor"}
            return {"ok": False, "reason": "unknown_target"}
        kind, record = classified
        if kind not in ORDINARY_KINDS and kind != "worker":
            return {"ok": False, "reason": "not_ordinary"}
        if record.get("is_wizard") or record.get("kind") == "wizard":
            return {"ok": False, "reason": "rival_duel_actor"}
        locality = self._locality_ok(target_id, record, local_poses=local_poses, require_range=True)
        if locality is not None:
            return locality
        return {
            "ok": True,
            "target_id": target_id,
            "target_kind": "worker" if kind == "worker" else kind,
            "allegiance": record.get("faction_id"),
            "command_id": command_id,
        }

    def destroy(
        self,
        target_id: str,
        *,
        observed_local_ids: set[str] | None = None,
        command_id: str | None = None,
        lease_id: str | None = None,
        local_poses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation = self.validate_destroy(
            target_id,
            observed_local_ids=observed_local_ids,
            command_id=command_id,
            local_poses=local_poses,
        )
        if not validation.get("ok"):
            return {"status": "rejected", **validation}
        if lease_id:
            lease = (getattr(self.state, "leases", {}) or {}).get(lease_id)
            if lease is not None:
                pending = lease.setdefault("pending_destructions", [])
                if command_id and any(p.get("command_id") == command_id for p in pending):
                    return {"status": "idempotent", "command_id": command_id, "pending": True}
                pending.append({"target_id": target_id, "command_id": command_id})
                return {"status": "pending_lease", "lease_id": lease_id, "target_id": target_id}

        kind = validation["target_kind"]
        effect_kind = {
            "unit": "destroy_unit",
            "person": "destroy_person",
            "worker": "destroy_person",
            "cart": "destroy_cart",
            "building": "destroy_building",
        }[kind]
        result = apply_effect(
            self.state,
            {
                "kind": effect_kind,
                "target_id": target_id,
                "command_id": command_id,
                "effect_id": command_id,
            },
        )
        return {"status": result.get("status"), "validation": validation, "result": result}

    def validate_buff(
        self,
        target_id: str,
        buff_kind: str,
        *,
        observed_local_ids: set[str] | None = None,
        local_poses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = observed_local_ids
        if buff_kind not in BUFF_KINDS:
            return {"ok": False, "reason": "unknown_buff"}
        unit = (self.state.units or {}).get(target_id)
        if unit is None or not unit.get("alive", True):
            return {"ok": False, "reason": "not_military_unit"}
        locality = self._locality_ok(target_id, unit, local_poses=local_poses, require_range=True)
        if locality is not None:
            return locality
        return {"ok": True, "target_id": target_id, "buff_kind": buff_kind}

    def apply_buff(
        self,
        target_id: str,
        buff_kind: str,
        *,
        observed_local_ids: set[str] | None = None,
        command_id: str | None = None,
        game_ms: int | None = None,
        frozen: bool = False,
        local_poses: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation = self.validate_buff(
            target_id,
            buff_kind,
            observed_local_ids=observed_local_ids,
            local_poses=local_poses,
        )
        if not validation.get("ok"):
            return {"status": "rejected", **validation}
        result = apply_effect(
            self.state,
            {
                "kind": "apply_buff",
                "target_id": target_id,
                "buff_kind": buff_kind,
                "command_id": command_id,
                "effect_id": command_id,
                "game_ms": int(game_ms if game_ms is not None else self.state.clock.get("game_ms", 0)),
                "frozen": frozen,
            },
        )
        return {"status": result.get("status"), "validation": validation, "result": result}
