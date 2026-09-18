"""Bounded off-screen battle resolution (C07 / T062).

250 ms steps from checkpoint; freeze handoff buffs; no global time/industry.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping

from sim.dmb.military.math import resolve_combat_step
from sim.dmb.military.movement import StrategicMovement

STEP_MS = 250
MAX_SIM_MS = 120_000
WITHDRAW_THRESHOLD = 0.25


def _alive(units: Mapping[str, Mapping[str, Any]], faction: str | None = None) -> list[str]:
    out = []
    for uid, u in units.items():
        if not u.get("alive", True) or int(u.get("current_health", 0)) <= 0:
            continue
        if faction is not None and str(u.get("faction_id")) != faction:
            continue
        out.append(uid)
    return out


def _factions(units: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(u["faction_id"])
            for u in units.values()
            if u.get("alive", True) and u.get("faction_id") is not None
        }
    )


def _hostility_graph(factions: list[str]) -> dict[str, set[str]]:
    # Baseline: every faction hostile to every other.
    return {f: {o for o in factions if o != f} for f in factions}


def _approach(units: dict[str, dict[str, Any]], hostiles: dict[str, set[str]]) -> None:
    """Move attackers toward nearest hostile if out of range (simple step)."""
    living = [u for u in units.values() if u.get("alive", True) and int(u.get("current_health", 0)) > 0]
    for unit in living:
        faction = str(unit["faction_id"])
        enemies = [
            e
            for e in living
            if str(e["faction_id"]) in hostiles.get(faction, set()) and e["id"] != unit["id"]
        ]
        if not enemies:
            continue
        pos = unit.get("position") or [0.0, 0.0]
        rng = float(unit.get("range_tiles") or 1)
        nearest = min(
            enemies,
            key=lambda e: (
                math.hypot(
                    float(pos[0]) - float((e.get("position") or [0, 0])[0]),
                    float(pos[1]) - float((e.get("position") or [0, 0])[1]),
                ),
                int(e.get("current_health", 0)),
                str(e["id"]),
            ),
        )
        tpos = nearest.get("position") or [0.0, 0.0]
        dist = math.hypot(float(pos[0]) - float(tpos[0]), float(pos[1]) - float(tpos[1]))
        if dist <= rng + 1e-9:
            continue
        speed = float(unit.get("speed_tiles_per_s") or 2.0) * (STEP_MS / 1000.0)
        if dist <= 1e-9:
            continue
        dx = (float(tpos[0]) - float(pos[0])) / dist
        dy = (float(tpos[1]) - float(pos[1])) / dist
        step = min(speed, dist - rng)
        unit["position"] = [float(pos[0]) + dx * step, float(pos[1]) + dy * step]


def _side_health(units: Mapping[str, Mapping[str, Any]], faction: str) -> int:
    return sum(
        int(u.get("current_health", 0))
        for u in units.values()
        if str(u.get("faction_id")) == faction and u.get("alive", True)
    )


def _unreachable(units: dict[str, dict[str, Any]], hostiles: dict[str, set[str]]) -> bool:
    """True when living sides cannot reach each other within generous bounds."""
    living = [u for u in units.values() if u.get("alive", True) and int(u.get("current_health", 0)) > 0]
    if len(_factions({u["id"]: u for u in living})) < 2:
        return False
    for unit in living:
        faction = str(unit["faction_id"])
        enemies = [
            e for e in living if str(e["faction_id"]) in hostiles.get(faction, set())
        ]
        if not enemies:
            continue
        # If any enemy is within 50 tiles, reachable for approximation.
        pos = unit.get("position") or [0.0, 0.0]
        for e in enemies:
            tpos = e.get("position") or [0.0, 0.0]
            if math.hypot(float(pos[0]) - float(tpos[0]), float(pos[1]) - float(tpos[1])) < 50:
                return False
    return True


class OffscreenBattleResolver:
    def __init__(self, world_state: Any | None = None):
        self.state = world_state

    def resolve(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Deterministic bounded calculation; does not advance global clocks."""
        units = {
            uid: deepcopy(u)
            for uid, u in (snapshot.get("units") or {}).items()
        }
        buildings = {
            bid: deepcopy(b)
            for bid, b in (snapshot.get("buildings") or {}).items()
        }
        entry_health = dict(snapshot.get("entry_effective_health") or {})
        if not entry_health:
            for fac in _factions(units):
                entry_health[fac] = _side_health(units, fac)

        # Freeze buffs active at handoff (retain original expiry metadata).
        frozen_buffs: dict[str, list[dict[str, Any]]] = {}
        for uid, unit in units.items():
            buffs = deepcopy(unit.get("buffs") or [])
            for buff in buffs:
                buff["frozen"] = True
            unit["buffs"] = buffs
            frozen_buffs[uid] = buffs

        factions = _factions(units)
        hostiles = _hostility_graph(factions)
        cover_by_target = dict(snapshot.get("cover_by_target") or {})
        blockers = list(snapshot.get("blockers") or [])

        sim_ms = 0
        steps = 0
        material_version = int(snapshot.get("material_change_version") or 0)
        outcome = "ongoing"
        withdrawals: list[dict[str, Any]] = []

        while sim_ms < MAX_SIM_MS:
            living_factions = [f for f in factions if _alive(units, f)]
            if len(living_factions) <= 1:
                outcome = "victory" if living_factions else "wipe"
                break
            if _unreachable(units, hostiles):
                outcome = "stalemate"
                break

            # Withdrawal check per side below 25% entry health.
            for fac in list(living_factions):
                entry = int(entry_health.get(fac) or 0)
                if entry <= 0:
                    continue
                if _side_health(units, fac) / entry < WITHDRAW_THRESHOLD:
                    retreat = snapshot.get("withdrawal_targets", {}).get(fac)
                    if retreat:
                        withdrawals.append(
                            {
                                "faction_id": fac,
                                "status": "pending",
                                "withdrawal_target": retreat,
                                "immediate_move": False,
                            }
                        )
                        # Remove withdrawing side from further fighting this resolve.
                        for uid in _alive(units, fac):
                            units[uid]["alive"] = True  # stay alive
                            units[uid]["withdrawing"] = True
                        outcome = "withdrawal"
                        break
            if outcome == "withdrawal":
                break

            _approach(units, hostiles)
            # Exclude withdrawing from attacks.
            fighting = {
                uid: u
                for uid, u in units.items()
                if not u.get("withdrawing") and u.get("alive", True)
            }
            result = resolve_combat_step(
                fighting,
                step_ms=STEP_MS,
                cover_by_target=cover_by_target,
                hostiles=hostiles,
                blockers=blockers,
                buildings=buildings,
            )
            # Mirror fighting state back.
            for uid, u in fighting.items():
                units[uid] = u
            # Apply building damage from simultaneous pool if buildings targeted.
            for bid, amount in (result.get("damages") or {}).items():
                if bid in buildings:
                    b = buildings[bid]
                    before = int(b.get("current_health", b.get("health", 0)))
                    after = max(0, before - int(amount))
                    b["current_health"] = after
                    b["health"] = after
                    if after <= 0:
                        b["alive"] = False

            sim_ms += STEP_MS
            steps += 1
        else:
            outcome = "stalemate"

        # Restore buff metadata (frozen flag) without accruing Game Time.
        for uid, buffs in frozen_buffs.items():
            if uid in units:
                units[uid]["buffs"] = buffs

        casualties = []
        for uid, u in units.items():
            orig = (snapshot.get("units") or {}).get(uid) or {}
            if orig.get("alive", True) and not u.get("alive", True):
                casualties.append(uid)
            elif int(orig.get("current_health", 0)) != int(u.get("current_health", 0)):
                casualties.append(uid)

        return {
            "outcome": outcome,
            "sim_ms": sim_ms,
            "steps": steps,
            "units": units,
            "buildings": buildings,
            "casualties": sorted(set(casualties)),
            "withdrawals": withdrawals,
            "entry_effective_health": entry_health,
            "material_change_version": material_version,
            "global_time_advanced": False,
            "industry_accrued": False,
            "reinforcements_accrued": False,
            "stalemate_bound_ms": MAX_SIM_MS,
        }

    def commit_to_world(self, outcome: Mapping[str, Any], *, battle_id: str | None = None) -> dict[str, Any]:
        """Apply resolved unit/building health once onto WorldState."""
        if self.state is None:
            raise RuntimeError("no world state")
        applied = []
        for uid, patch in (outcome.get("units") or {}).items():
            unit = self.state.units.get(uid)
            if unit is None:
                continue
            for key in (
                "current_health",
                "alive",
                "status",
                "position",
                "remaining_attack_cooldown_ms",
                "target_id",
                "shield_remaining",
                "buffs",
                "withdrawing",
            ):
                if key in patch:
                    unit[key] = deepcopy(patch[key])
            if not unit.get("alive", True):
                unit["status"] = "dead"
                unit["current_health"] = 0
            applied.append(uid)
        for bid, patch in (outcome.get("buildings") or {}).items():
            building = self.state.buildings.get(bid)
            if building is None:
                continue
            for key in ("current_health", "health", "alive"):
                if key in patch:
                    building[key] = deepcopy(patch[key])
        if battle_id and battle_id in (getattr(self.state, "battles", {}) or {}):
            battle = self.state.battles[battle_id]
            battle["state"] = outcome.get("outcome")
            battle["last_offscreen"] = {
                "outcome": outcome.get("outcome"),
                "sim_ms": outcome.get("sim_ms"),
                "material_change_version": outcome.get("material_change_version"),
            }
        # Withdrawal intents via StrategicMovement (no immediate move).
        mover = StrategicMovement(self.state)
        for w in outcome.get("withdrawals") or []:
            # Find a formation for faction at battle node if present.
            fac = w.get("faction_id")
            for fid, formation in (getattr(self.state, "formations", {}) or {}).items():
                if formation.get("faction_id") == fac:
                    formation["withdrawal_target"] = w.get("withdrawal_target")
                    formation["withdrawal_status"] = "pending"
                    mover.revalidate_withdrawal(fid)
        return {"applied_units": applied, "outcome": outcome.get("outcome")}
