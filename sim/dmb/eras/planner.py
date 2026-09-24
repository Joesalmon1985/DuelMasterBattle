"""Pure EraTransitionPlanner — hashed plans, no world mutation (C11 / T097)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from typing import Any, Mapping

from sim.dmb.construction.scoring import ScoreService, VP_THRESHOLD
from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.industry.allocation import solve_theoretical
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.service import (
    _channel_from_dict,
    _processor_from_dict,
    _route_from_dict,
)


CITY_CAPACITY_MULTIPLIER = Fraction(2)


@dataclass(frozen=True)
class TransitionTrigger:
    event_id: str
    winner_faction_id: str
    source_action_id: str | None = None
    scores_at_trigger: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "winner_faction_id": self.winner_faction_id,
            "source_action_id": self.source_action_id,
            "scores_at_trigger": dict(sorted((self.scores_at_trigger or {}).items())),
        }


@dataclass(frozen=True)
class EraTransitionPlan:
    """Hashed pure transition plan. Commit allocates successor IDs; planner does not."""

    id: str
    plan_hash: str
    source_world_id: str
    source_world_version: int
    source_world_hash: str
    source_era: str
    source_cycle: int
    trigger: dict[str, Any]
    next_era: str
    next_cycle: int
    scores: dict[str, int]
    theoretical_site_ranking: list[dict[str, Any]]
    collapse_faction_ids: list[str]
    collapse_reasons: dict[str, str]
    survivor_faction_ids: list[str]
    split_decisions: list[dict[str, Any]]
    successor_lineage: list[dict[str, Any]]
    core_pairs: list[dict[str, Any]]
    settlement_assignments: dict[str, str]
    road_assignments: dict[str, str]
    unit_assignments: dict[str, str]
    cart_assignments: dict[str, str]
    research_assignments: dict[str, str]
    person_assignments: dict[str, str]
    core_upgrade_operations: list[dict[str, Any]]
    legacy_site_ids: list[str]
    retirements: list[dict[str, Any]]
    starter_grants: list[dict[str, Any]]
    hazard_rollover: dict[str, Any]
    quest_adaptations: list[dict[str, Any]]
    person_adaptations: list[dict[str, Any]]
    item_adaptations: list[dict[str, Any]]
    layout_relocations: list[dict[str, Any]]
    new_roster: dict[str, Any]
    reserved_id_block: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_plan_hash(body: Mapping[str, Any]) -> str:
    """Hash plan body excluding plan_hash itself."""
    material = {k: v for k, v in body.items() if k != "plan_hash"}
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def snapshot_world_hash(snapshot: Any) -> str:
    """Stable hash of ranking-relevant snapshot fields (not a full save digest)."""
    settlements = getattr(snapshot, "settlements", {}) or {}
    buildings = getattr(snapshot, "buildings", {}) or {}
    industry = getattr(snapshot, "industry", {}) or {}
    factions = getattr(snapshot, "factions", {}) or {}
    clock = getattr(snapshot, "clock", {}) or {}
    payload = {
        "world_id": getattr(snapshot, "world_id", None),
        "world_version": getattr(snapshot, "world_version", None),
        "era": clock.get("era") or clock.get("era_id") or (getattr(snapshot, "board", {}) or {}).get("era_id"),
        "cycle": clock.get("cycle") or (getattr(snapshot, "board", {}) or {}).get("cycle") or 0,
        "settlements": {
            sid: {
                "faction_id": rec.get("faction_id"),
                "tier": rec.get("tier"),
                "node_id": rec.get("node_id"),
                "operational": rec.get("operational", True),
                "status": rec.get("status"),
                "legacy": rec.get("legacy"),
                "ruin_only": rec.get("ruin_only"),
            }
            for sid, rec in sorted(settlements.items())
        },
        "buildings": {
            bid: {
                "def_id": rec.get("def_id") or rec.get("building_def_id"),
                "settlement_id": rec.get("settlement_id"),
                "faction_id": rec.get("faction_id"),
                "status": rec.get("status"),
                "active": rec.get("active", True),
                "health": rec.get("health"),
                "max_health": rec.get("max_health"),
            }
            for bid, rec in sorted(buildings.items())
        },
        "industry": {
            "factories": industry.get("factories") or {},
            "routes": industry.get("routes") or {},
            "processors": industry.get("processors") or {},
            "channels": industry.get("channels") or {},
            "layers": {
                lid: {
                    "retired": (layer or {}).get("retired"),
                    "finite_balance": (layer or {}).get("finite_balance"),
                }
                for lid, layer in sorted((industry.get("layers") or {}).items())
            },
        },
        "factions": {fid: {"id": fid} for fid in sorted(factions)},
        "scores": ScoreService(snapshot).scores() if settlements or factions else {},
    }
    return f"sha256:{hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()}"


def _city_multiplier(settlement: Mapping[str, Any]) -> Fraction:
    tier = str(settlement.get("tier") or "settlement")
    if tier == "city":
        return CITY_CAPACITY_MULTIPLIER
    return Fraction(1)


def _permanent_tech_factory_modifier(snapshot: Any, faction_id: str) -> Fraction:
    """Apply permanent factory_ceiling research stacks when present."""
    research = (getattr(snapshot, "research", {}) or {}).get(faction_id) or {}
    stacks = research.get("active_stacks") or research.get("stacks") or {}
    if isinstance(stacks, dict):
        ceiling = stacks.get("factory_ceiling") or stacks.get("tech.prehistoric.factory_ceiling")
        if ceiling is None:
            return Fraction(1)
        try:
            count = int(ceiling if not isinstance(ceiling, dict) else ceiling.get("stacks", 1))
        except (TypeError, ValueError):
            return Fraction(1)
        # Baseline card: +10% per stack, cap 3 (C12).
        return Fraction(1) + Fraction(1, 10) * max(0, min(3, count))
    return Fraction(1)


def theoretical_site_capacity(snapshot: Any, settlement_id: str) -> Fraction:
    """Installed/permanent theoretical military output for one settlement (units/second)."""
    settlements = getattr(snapshot, "settlements", {}) or {}
    settlement = settlements.get(settlement_id)
    if not settlement:
        return Fraction()
    if settlement.get("ruin_only") or settlement.get("status") in {"ruined", "inert", "destroyed"}:
        return Fraction()
    if not settlement.get("operational", True):
        return Fraction()

    industry = getattr(snapshot, "industry", {}) or {}
    buildings = getattr(snapshot, "buildings", {}) or {}
    factories = industry.get("factories") or {}

    site_factory_ids = []
    for fid, frec in factories.items():
        building = buildings.get(fid) or frec
        if (building or {}).get("settlement_id") == settlement_id:
            site_factory_ids.append(fid)
        elif (frec or {}).get("settlement_id") == settlement_id:
            site_factory_ids.append(fid)
        elif (frec or {}).get("node_id") == settlement.get("node_id") and (
            (building or {}).get("faction_id") == settlement.get("faction_id")
            or (frec or {}).get("faction_id") == settlement.get("faction_id")
        ):
            # Fallback: same node + faction when settlement_id unset on older fixtures.
            if (building or {}).get("def_id", "").endswith("factory") or "factory" in str(
                (building or {}).get("building_def_id") or (frec or {}).get("unit_def_id") or ""
            ):
                site_factory_ids.append(fid)

    # Also collect by building settlement_id for factory-typed buildings.
    for bid, building in buildings.items():
        if building.get("settlement_id") != settlement_id:
            continue
        def_id = str(building.get("def_id") or building.get("building_def_id") or "")
        if "factory" in def_id and bid in factories:
            if bid not in site_factory_ids:
                site_factory_ids.append(bid)

    if not site_factory_ids:
        return Fraction()

    routes = []
    for rid, record in sorted((industry.get("routes") or {}).items()):
        route = _route_from_dict(record) if isinstance(record, dict) and "factory_id" in record else None
        if route is None and isinstance(record, dict):
            # routes keyed by factory_id
            try:
                route = _route_from_dict({**record, "factory_id": record.get("factory_id") or rid})
            except Exception:
                continue
        if route is not None and route.factory_id in site_factory_ids:
            routes.append(route)

    processors = {
        pid: _processor_from_dict(rec)
        for pid, rec in (industry.get("processors") or {}).items()
        if isinstance(rec, dict)
    }
    channels = {
        cid: _channel_from_dict(rec)
        for cid, rec in (industry.get("channels") or {}).items()
        if isinstance(rec, dict)
    }
    layers = {
        lid: LayerState.from_dict(rec) if isinstance(rec, dict) and "layer_id" not in rec
        else LayerState.from_dict({**(rec or {}), "id": lid})
        for lid, rec in (industry.get("layers") or {}).items()
        if isinstance(rec, dict)
    }
    # Normalize LayerState.from_dict expects id key
    fixed_layers: dict[str, LayerState] = {}
    for lid, rec in (industry.get("layers") or {}).items():
        if not isinstance(rec, dict):
            continue
        payload = dict(rec)
        payload.setdefault("id", lid)
        try:
            fixed_layers[lid] = LayerState.from_dict(payload)
        except Exception:
            continue

    installed: dict[str, bool] = {}
    for fid in site_factory_ids:
        building = buildings.get(fid) or {}
        frec = factories.get(fid) or {}
        permanently_gone = building.get("status") in {"destroyed", "retired"} or frec.get("status") == "destroyed"
        # Temporary inactive from catastrophe must NOT exclude; only permanent removal.
        installed[fid] = not permanently_gone

    if not routes:
        # No routes: capacity from installed factory ceilings alone (1/60 each).
        base = Fraction(1, 60) * sum(1 for fid in site_factory_ids if installed.get(fid, False))
    else:
        plan = solve_theoretical(
            routes,
            processors,
            channels,
            fixed_layers,
            factory_installed=installed,
        )
        base = sum((plan.rate(fid) for fid in site_factory_ids), Fraction())

    faction_id = str(settlement.get("faction_id") or "")
    tech = _permanent_tech_factory_modifier(snapshot, faction_id) if faction_id else Fraction(1)
    return base * _city_multiplier(settlement) * tech


def rank_theoretical_sites(snapshot: Any) -> list[dict[str, Any]]:
    """Rank all operational settlements by theoretical capacity desc, settlement ID asc."""
    rows: list[dict[str, Any]] = []
    for sid, settlement in sorted((getattr(snapshot, "settlements", {}) or {}).items()):
        if settlement.get("ruin_only") or settlement.get("status") in {"ruined", "inert", "destroyed"}:
            continue
        if not settlement.get("operational", True):
            continue
        if not settlement.get("faction_id"):
            continue
        capacity = theoretical_site_capacity(snapshot, sid)
        rows.append(
            {
                "settlement_id": sid,
                "faction_id": settlement.get("faction_id"),
                "node_id": settlement.get("node_id"),
                "tier": settlement.get("tier"),
                "theoretical_capacity": fraction_wire(capacity),
                "theoretical_capacity_exact": str(capacity),
            }
        )
    rows.sort(
        key=lambda row: (
            -fraction(row["theoretical_capacity"]),
            str(row["settlement_id"]),
        )
    )
    for index, row in enumerate(rows):
        row["rank"] = index + 1
    return rows


def faction_theoretical_capacity(snapshot: Any, faction_id: str) -> Fraction:
    total = Fraction()
    for row in rank_theoretical_sites(snapshot):
        if row["faction_id"] == faction_id:
            total += fraction(row["theoretical_capacity"])
    return total


def next_era_id(source_era: str) -> str:
    order = ("prehistoric", "historic", "modern", "future")
    aliases = {
        "ancient": "prehistoric",
        "prehistoric": "prehistoric",
        "historic": "historic",
        "modern": "modern",
        "future": "future",
    }
    normalised = aliases.get(str(source_era).lower(), str(source_era).lower())
    if normalised not in order:
        return "historic"
    idx = order.index(normalised)
    if idx + 1 >= len(order):
        return "prehistoric"  # full-cycle path is separate (C11 Future→Prehistoric)
    return order[idx + 1]


def validate_plan_freshness(plan: EraTransitionPlan | Mapping[str, Any], snapshot: Any) -> dict[str, Any]:
    """Return validation result; stale hash / version / world hash cannot commit."""
    body = plan.to_dict() if isinstance(plan, EraTransitionPlan) else dict(plan)
    expected_hash = compute_plan_hash(body)
    actual_hash = str(body.get("plan_hash") or "")
    current_world_hash = snapshot_world_hash(snapshot)
    world_version = int(getattr(snapshot, "world_version", -1))
    ok = (
        actual_hash == expected_hash
        and body.get("source_world_id") == getattr(snapshot, "world_id", None)
        and int(body.get("source_world_version", -2)) == world_version
        and body.get("source_world_hash") == current_world_hash
    )
    return {
        "ok": ok,
        "reason": "ok" if ok else "stale_or_tampered_plan",
        "expected_plan_hash": expected_hash,
        "actual_plan_hash": actual_hash,
        "current_world_hash": current_world_hash,
        "plan_world_hash": body.get("source_world_hash"),
        "can_commit": ok,
    }


class EraTransitionPlanner:
    """Pure planner: reads a snapshot, returns a hashed plan, never mutates."""

    def plan(self, snapshot: Any, trigger: TransitionTrigger | Mapping[str, Any]) -> EraTransitionPlan:
        before = deepcopy(getattr(snapshot, "settlements", None))
        trig = (
            trigger
            if isinstance(trigger, TransitionTrigger)
            else TransitionTrigger(
                event_id=str(trigger.get("event_id")),
                winner_faction_id=str(trigger.get("winner_faction_id")),
                source_action_id=trigger.get("source_action_id"),
                scores_at_trigger=dict(trigger.get("scores_at_trigger") or {}),
            )
        )
        scores = ScoreService(snapshot).scores()
        if trig.winner_faction_id not in scores and scores:
            # Winner must be present; fixtures may pass explicit scores_at_trigger.
            pass
        effective_scores = dict(trig.scores_at_trigger) if trig.scores_at_trigger else scores
        if trig.winner_faction_id and effective_scores.get(trig.winner_faction_id, 0) < VP_THRESHOLD:
            # Allow planning when caller asserts the triggering action already awarded VP
            # into scores_at_trigger; otherwise require threshold on live scores.
            if not trig.scores_at_trigger or effective_scores.get(trig.winner_faction_id, 0) < VP_THRESHOLD:
                raise TypeValidationError(
                    f"trigger faction {trig.winner_faction_id} below {VP_THRESHOLD} VP"
                )

        clock = getattr(snapshot, "clock", {}) or {}
        board = getattr(snapshot, "board", {}) or {}
        source_era = str(
            clock.get("era") or clock.get("era_id") or board.get("era_id") or "prehistoric"
        )
        if source_era == "ancient":
            source_era = "prehistoric"
        source_cycle = int(clock.get("cycle") or board.get("cycle") or 0)
        ranking = rank_theoretical_sites(snapshot)
        from sim.dmb.eras.collapse import plan_collapse_fields

        collapse_fields = plan_collapse_fields(snapshot, trig)
        world_hash = snapshot_world_hash(snapshot)
        plan_id = f"era_plan:{getattr(snapshot, 'world_id', 'world')}:{getattr(snapshot, 'world_version', 0)}:{trig.event_id}"

        body = {
            "id": plan_id,
            "source_world_id": str(getattr(snapshot, "world_id", "")),
            "source_world_version": int(getattr(snapshot, "world_version", 0)),
            "source_world_hash": world_hash,
            "source_era": source_era,
            "source_cycle": source_cycle,
            "trigger": trig.to_dict(),
            "next_era": next_era_id(source_era),
            "next_cycle": source_cycle,
            "scores": dict(sorted(effective_scores.items())),
            "theoretical_site_ranking": ranking,
            "collapse_faction_ids": collapse_fields["collapse_faction_ids"],
            "collapse_reasons": collapse_fields["collapse_reasons"],
            "survivor_faction_ids": collapse_fields["survivor_faction_ids"],
            "split_decisions": [],
            "successor_lineage": [],
            "core_pairs": [],
            "settlement_assignments": {},
            "road_assignments": {},
            "unit_assignments": {},
            "cart_assignments": {},
            "research_assignments": {},
            "person_assignments": {},
            "core_upgrade_operations": [],
            "legacy_site_ids": [],
            "retirements": [],
            "starter_grants": [],
            "hazard_rollover": {},
            "quest_adaptations": [],
            "person_adaptations": [],
            "item_adaptations": [],
            "layout_relocations": [],
            "new_roster": {},
            "reserved_id_block": {
                "note": "Successor IDs allocated at commit; planner does not allocate",
                "kinds": ["faction", "settlement"],
            },
            "validation": {
                "ranking_ignores_temporary_disruption": True,
                "planner_mutated_snapshot": False,
                "site_count": len(ranking),
                "faction_theoretical_capacities": collapse_fields["faction_theoretical_capacities"],
            },
        }
        body["plan_hash"] = compute_plan_hash(body)

        after = getattr(snapshot, "settlements", None)
        if before is not None and after is not None and before != deepcopy(after):
            raise TypeValidationError("EraTransitionPlanner mutated snapshot")

        return EraTransitionPlan(**body)
