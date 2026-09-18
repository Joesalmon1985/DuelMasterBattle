"""Wizard destruction and support magic (C07 / T065–T066)."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.effects import apply_effect

ORDINARY_KINDS = {"unit", "person", "worker", "cart", "building"}
BUFF_KINDS = {"shield", "frequency", "range"}


class MagicService:
    def __init__(self, world_state: Any):
        self.state = world_state

    def _player_node(self) -> str:
        return str((self.state.player or {}).get("node_id") or "")

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

    def validate_destroy(
        self,
        target_id: str,
        *,
        observed_local_ids: set[str] | None = None,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        if target_id in {"wizard", "player"} or target_id == (self.state.player or {}).get("id"):
            return {"ok": False, "reason": "self_target"}
        if target_id.startswith("group:") or target_id.startswith("formation:"):
            return {"ok": False, "reason": "group_target"}
        classified = self._classify(target_id)
        if classified is None:
            # Rival wizard / hazard actors require duels.
            if target_id.startswith("hazard:") or target_id.startswith("rival:"):
                return {"ok": False, "reason": "rival_duel_actor"}
            return {"ok": False, "reason": "unknown_target"}
        kind, record = classified
        if kind not in ORDINARY_KINDS and kind != "worker":
            return {"ok": False, "reason": "not_ordinary"}
        if record.get("is_wizard") or record.get("kind") == "wizard":
            return {"ok": False, "reason": "rival_duel_actor"}
        # Local observation: same strategic node as wizard.
        target_node = str(
            record.get("node_id")
            or record.get("current_node")
            or record.get("home_node_id")
            or ""
        )
        if observed_local_ids is not None and target_id not in observed_local_ids:
            return {"ok": False, "reason": "remote_or_unobserved"}
        if observed_local_ids is None and target_node and target_node != self._player_node():
            return {"ok": False, "reason": "remote_or_unobserved"}
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
    ) -> dict[str, Any]:
        validation = self.validate_destroy(
            target_id, observed_local_ids=observed_local_ids, command_id=command_id
        )
        if not validation.get("ok"):
            return {"status": "rejected", **validation}
        # Leased targets become pending encounter commands.
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
    ) -> dict[str, Any]:
        if buff_kind not in BUFF_KINDS:
            return {"ok": False, "reason": "unknown_buff"}
        unit = (self.state.units or {}).get(target_id)
        if unit is None or not unit.get("alive", True):
            return {"ok": False, "reason": "not_military_unit"}
        if observed_local_ids is not None and target_id not in observed_local_ids:
            return {"ok": False, "reason": "remote_or_unobserved"}
        if observed_local_ids is None and str(unit.get("node_id")) != self._player_node():
            return {"ok": False, "reason": "remote_or_unobserved"}
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
    ) -> dict[str, Any]:
        validation = self.validate_buff(
            target_id, buff_kind, observed_local_ids=observed_local_ids
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
