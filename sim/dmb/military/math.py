"""Shared combat damage and targeting oracles (C07 / T060).

Python and Godot share golden cases in content/fixtures/combat_math.json.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from sim.dmb.military.units import ERA_FACTORS, round_half_up

COVER_NONE = 0.0
COVER_PARTIAL = 0.25


def era_attack_factor(era: str) -> int:
    key = str(era or "prehistoric").lower()
    if key not in ERA_FACTORS:
        raise ValueError(f"unknown era {era!r}")
    return ERA_FACTORS[key]


def compute_damage(
    *,
    base_attack: float | int,
    era_factor: float | int = 1,
    attack_modifiers: float | int = 1.0,
    cover: float = 0.0,
    armour: float | int = 0,
) -> int:
    """Shared damage = max(1, round_half_up(base × era × mods × (1−cover) − armour))."""
    cover_f = float(cover)
    if abs(cover_f - COVER_NONE) > 1e-12 and abs(cover_f - COVER_PARTIAL) > 1e-12:
        raise ValueError(f"cover must be 0 or 0.25, got {cover!r}")
    raw = (
        float(base_attack)
        * float(era_factor)
        * float(attack_modifiers)
        * (1.0 - cover_f)
        - float(armour)
    )
    return max(1, round_half_up(raw))


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def in_range(
    attacker_pos: Sequence[float],
    target_pos: Sequence[float],
    range_tiles: float,
) -> bool:
    return distance(attacker_pos, target_pos) <= float(range_tiles) + 1e-9


def has_line_of_sight(
    attacker_pos: Sequence[float],
    target_pos: Sequence[float],
    blockers: Iterable[Mapping[str, Any]] | None = None,
) -> bool:
    """Axis-aligned segment vs axis-aligned blocker boxes (tile centres)."""
    if not blockers:
        return True
    ax, ay = float(attacker_pos[0]), float(attacker_pos[1])
    bx, by = float(target_pos[0]), float(target_pos[1])
    for block in blockers:
        if not block.get("blocks_los", True):
            continue
        if "min" in block and "max" in block:
            xmin, ymin = float(block["min"][0]), float(block["min"][1])
            xmax, ymax = float(block["max"][0]), float(block["max"][1])
        else:
            pos = block.get("position") or [block.get("x", 0), block.get("y", 0)]
            cx = float(pos[0])
            cy = float(pos[1])
            half = float(block.get("half", 0.45))
            xmin, xmax = cx - half, cx + half
            ymin, ymax = cy - half, cy + half
        if _point_in_aabb(ax, ay, xmin, ymin, xmax, ymax) or _point_in_aabb(
            bx, by, xmin, ymin, xmax, ymax
        ):
            continue
        if _segment_hits_aabb(ax, ay, bx, by, xmin, ymin, xmax, ymax):
            return False
    return True


def _point_in_aabb(x: float, y: float, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
    return xmin <= x <= xmax and ymin <= y <= ymax


def _segment_hits_aabb(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> bool:
    dx = x1 - x0
    dy = y1 - y0
    p = [-dx, dx, -dy, dy]
    q = [x0 - xmin, xmax - x0, y0 - ymin, ymax - y0]
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0:
                return False
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return False
    return True


def choose_target(
    attacker: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    hostiles: Mapping[str, set[str]] | None = None,
    blockers: Iterable[Mapping[str, Any]] | None = None,
    wizard_id: str | None = None,
) -> str | None:
    """Nearest, then lowest health, then ID. Requires range + LOS. Never wizard."""
    if not attacker.get("alive", True):
        return None
    attacker_id = str(attacker["id"])
    faction = str(attacker.get("faction_id") or "")
    pos = attacker.get("position") or [0.0, 0.0]
    range_tiles = float(attacker.get("range_tiles") or 1)
    eligible: list[tuple[float, int, str]] = []
    for cand in candidates:
        cid = str(cand["id"])
        if cid == attacker_id:
            continue
        if not cand.get("alive", True):
            continue
        if wizard_id and cid == wizard_id:
            continue
        if cand.get("kind") == "wizard" or cand.get("is_wizard"):
            continue
        other_faction = str(cand.get("faction_id") or "")
        if hostiles is not None:
            if other_faction not in hostiles.get(faction, set()):
                continue
        elif other_faction == faction:
            continue
        tpos = cand.get("position") or [0.0, 0.0]
        if not in_range(pos, tpos, range_tiles):
            continue
        if not has_line_of_sight(pos, tpos, blockers):
            continue
        dist = distance(pos, tpos)
        health = int(cand.get("current_health", 0))
        eligible.append((dist, health, cid))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1], row[2]))
    return eligible[0][2]


def gather_step_attacks(
    units: Mapping[str, Mapping[str, Any]],
    *,
    cover_by_target: Mapping[str, float] | None = None,
    hostiles: Mapping[str, set[str]] | None = None,
    blockers: Iterable[Mapping[str, Any]] | None = None,
    buildings: Mapping[str, Mapping[str, Any]] | None = None,
    attack_modifier: float = 1.0,
) -> tuple[dict[str, int], list[str]]:
    """Return (damage_by_target, attacker_ids_that_fired) from living-at-step-start."""
    cover_by_target = cover_by_target or {}
    living = {
        uid: u
        for uid, u in units.items()
        if u.get("alive", True) and int(u.get("current_health", 0)) > 0
    }
    targets: list[Mapping[str, Any]] = list(living.values())
    if buildings:
        for b in buildings.values():
            if b.get("alive", True) and int(b.get("current_health", b.get("health", 0))) > 0:
                targets.append(b)

    damages: dict[str, int] = {}
    fired: list[str] = []
    for uid in sorted(living):
        attacker = living[uid]
        if int(attacker.get("remaining_attack_cooldown_ms", 0)) > 0:
            continue
        tid = choose_target(attacker, targets, hostiles=hostiles, blockers=blockers)
        if tid is None:
            continue
        target = next(t for t in targets if str(t["id"]) == tid)
        cover = float(cover_by_target.get(tid, target.get("cover", COVER_NONE) or COVER_NONE))
        dmg = compute_damage(
            base_attack=attacker.get("base_attack", 0),
            era_factor=attacker.get("era_factor", 1),
            attack_modifiers=attack_modifier,
            cover=cover,
            armour=target.get("armour", 0),
        )
        damages[tid] = damages.get(tid, 0) + dmg
        fired.append(uid)
    return damages, fired


def gather_step_damage(
    units: Mapping[str, Mapping[str, Any]],
    *,
    cover_by_target: Mapping[str, float] | None = None,
    hostiles: Mapping[str, set[str]] | None = None,
    blockers: Iterable[Mapping[str, Any]] | None = None,
    buildings: Mapping[str, Mapping[str, Any]] | None = None,
    attack_modifier: float = 1.0,
) -> dict[str, int]:
    damages, _fired = gather_step_attacks(
        units,
        cover_by_target=cover_by_target,
        hostiles=hostiles,
        blockers=blockers,
        buildings=buildings,
        attack_modifier=attack_modifier,
    )
    return damages


def apply_simultaneous(
    units: dict[str, dict[str, Any]],
    damages: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Apply gathered damage; dead units stay marked for next-step exclusion."""
    events: list[dict[str, Any]] = []
    for tid, amount in sorted(damages.items()):
        unit = units.get(tid)
        if unit is None or not unit.get("alive", True):
            continue
        before = int(unit["current_health"])
        after = max(0, before - int(amount))
        unit["current_health"] = after
        killed = after <= 0
        if killed:
            unit["alive"] = False
            unit["status"] = "dead"
            unit["target_id"] = None
        events.append(
            {
                "unit_id": tid,
                "damage": int(amount),
                "health_before": before,
                "health_after": after,
                "killed": killed,
            }
        )
    return events


def resolve_combat_step(
    units: dict[str, dict[str, Any]],
    *,
    step_ms: int = 50,
    cover_by_target: Mapping[str, float] | None = None,
    hostiles: Mapping[str, set[str]] | None = None,
    blockers: Iterable[Mapping[str, Any]] | None = None,
    buildings: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cooldown decrement → gather from living-at-start → simultaneous apply → set cooldowns."""
    living_at_start = {
        uid: {
            **u,
            "remaining_attack_cooldown_ms": max(
                0, int(u.get("remaining_attack_cooldown_ms", 0)) - int(step_ms)
            ),
        }
        for uid, u in units.items()
        if u.get("alive", True) and int(u.get("current_health", 0)) > 0
    }
    for uid, snap in living_at_start.items():
        units[uid]["remaining_attack_cooldown_ms"] = snap["remaining_attack_cooldown_ms"]

    damages, fired = gather_step_attacks(
        living_at_start,
        cover_by_target=cover_by_target,
        hostiles=hostiles,
        blockers=blockers,
        buildings=buildings,
    )
    events = apply_simultaneous(units, damages)
    for uid in fired:
        unit = units.get(uid)
        if unit is None or not unit.get("alive", True):
            continue
        unit["remaining_attack_cooldown_ms"] = int(unit.get("period_ms") or 1000)
    return {"damages": damages, "events": events, "fired": fired}


class CombatMath:
    """Facade matching the C07 CombatMath public surface."""

    COVER_NONE = COVER_NONE
    COVER_PARTIAL = COVER_PARTIAL

    compute_damage = staticmethod(compute_damage)
    choose_target = staticmethod(choose_target)
    gather_step_damage = staticmethod(gather_step_damage)
    gather_step_attacks = staticmethod(gather_step_attacks)
    apply_simultaneous = staticmethod(apply_simultaneous)
    resolve_combat_step = staticmethod(resolve_combat_step)
    in_range = staticmethod(in_range)
    has_line_of_sight = staticmethod(has_line_of_sight)
    distance = staticmethod(distance)
    era_attack_factor = staticmethod(era_attack_factor)
    round_half_up = staticmethod(round_half_up)


# Documented golden cases (attack 15 into cover 0.25).
GOLDEN_PREHISTORIC_COVER = compute_damage(base_attack=15, era_factor=1, cover=0.25)  # 11
GOLDEN_HISTORIC_COVER = compute_damage(base_attack=15, era_factor=10, cover=0.25)  # 113
