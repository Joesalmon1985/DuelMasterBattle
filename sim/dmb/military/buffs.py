"""Timed military buffs and shield stacks (C07)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.military.units import round_half_up

BUFF_DURATION_MS = 30_000
SHIELD_FRACTION = 0.25
FREQUENCY_BONUS = 0.25
RANGE_BONUS = 1

# Additive caps relative to baseline / max HP.
SHIELD_CAP_MULT = 2
FREQUENCY_CAP_MULT = 3
RANGE_EXTRA_CAP = 4

BUFF_KINDS = ("shield", "frequency", "range")


class BuffService:
    def __init__(self, world_state: Any):
        self.state = world_state

    def apply(
        self,
        unit_id: str,
        kind: str,
        *,
        game_ms: int,
        command_id: str | None = None,
        frozen: bool = False,
    ) -> dict[str, Any]:
        if kind not in BUFF_KINDS:
            raise ValueError(f"unknown buff kind {kind!r}")
        unit = self.state.units[unit_id]
        if not unit.get("alive", True):
            raise ValueError(f"unit {unit_id} is not alive")
        # Idempotent receipt: same command_id grants no second stack.
        if command_id:
            for existing in unit.get("buffs") or []:
                if existing.get("command_id") == command_id:
                    return deepcopy(existing)
        effect_id = self.state.ids.new("effect")
        max_hp = int(unit["max_health"])
        shield_points = 0
        if kind == "shield":
            shield_points = round_half_up(max_hp * SHIELD_FRACTION)
            capped = max_hp * SHIELD_CAP_MULT
            room = max(0, capped - int(unit.get("shield_remaining", 0)))
            shield_points = min(shield_points, room)
            unit["shield_remaining"] = int(unit.get("shield_remaining", 0)) + shield_points
        buff = {
            "id": effect_id,
            "kind": kind,
            "unit_id": unit_id,
            "applied_game_ms": int(game_ms),
            "expires_game_ms": int(game_ms) + BUFF_DURATION_MS,
            "remaining_ms": BUFF_DURATION_MS,
            "shield_points": shield_points,
            "shield_remaining": shield_points,
            "command_id": command_id,
            "frozen": bool(frozen),
        }
        unit.setdefault("buffs", []).append(buff)
        return deepcopy(buff)

    def tick(self, *, game_ms: int, paused: bool = False) -> list[str]:
        """Expire buffs by Game Time; pause/duel freezes remaining duration."""
        expired: list[str] = []
        if paused:
            return expired
        for unit in self.state.units.values():
            if not unit.get("alive", True):
                continue
            kept: list[dict[str, Any]] = []
            for buff in list(unit.get("buffs") or []):
                if buff.get("frozen"):
                    kept.append(buff)
                    continue
                if int(game_ms) >= int(buff["expires_game_ms"]):
                    expired.append(buff["id"])
                    if buff["kind"] == "shield":
                        remove = int(buff.get("shield_remaining", 0))
                        unit["shield_remaining"] = max(
                            0, int(unit.get("shield_remaining", 0)) - remove
                        )
                    continue
                buff["remaining_ms"] = max(0, int(buff["expires_game_ms"]) - int(game_ms))
                kept.append(buff)
            unit["buffs"] = kept
        return expired

    def set_frozen(self, frozen: bool) -> None:
        for unit in self.state.units.values():
            for buff in unit.get("buffs") or []:
                buff["frozen"] = bool(frozen)

    def absorb_damage(self, unit_id: str, amount: int) -> int:
        """Consume earliest-expiry shields first; return HP damage remaining."""
        unit = self.state.units[unit_id]
        remaining = max(0, int(amount))
        shields = sorted(
            [b for b in (unit.get("buffs") or []) if b["kind"] == "shield" and int(b.get("shield_remaining", 0)) > 0],
            key=lambda b: (int(b["expires_game_ms"]), b["id"]),
        )
        for buff in shields:
            if remaining <= 0:
                break
            available = int(buff["shield_remaining"])
            take = min(available, remaining)
            buff["shield_remaining"] = available - take
            unit["shield_remaining"] = max(0, int(unit.get("shield_remaining", 0)) - take)
            remaining -= take
        return remaining

    def modifiers(self, unit_id: str) -> dict[str, float | int]:
        unit = self.state.units[unit_id]
        frequency = 1.0
        extra_range = 0
        for buff in unit.get("buffs") or []:
            if buff["kind"] == "frequency":
                frequency += FREQUENCY_BONUS
            elif buff["kind"] == "range":
                extra_range += RANGE_BONUS
        frequency = min(frequency, float(FREQUENCY_CAP_MULT))
        extra_range = min(extra_range, RANGE_EXTRA_CAP)
        return {
            "attack_frequency_mult": frequency,
            "extra_range": extra_range,
            "shield_remaining": int(unit.get("shield_remaining", 0)),
        }
