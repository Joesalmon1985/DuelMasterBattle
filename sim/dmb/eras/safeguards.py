"""Sole-faction and zero-faction recovery safeguards (C11 / T102)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sim.dmb.core.types import TypeValidationError
from sim.dmb.eras.fission import node_distance, plan_fission
from sim.dmb.world.board import HexBoard


def active_faction_ids(state: Any) -> list[str]:
    active: list[str] = []
    for fid, faction in sorted((getattr(state, "factions", {}) or {}).items()):
        if faction.get("status") in {"collapsed", "succeeded", "dissolved"}:
            continue
        if faction.get("operational") is False and faction.get("status") != "active":
            continue
        centres = [
            s
            for s in (getattr(state, "settlements", {}) or {}).values()
            if s.get("faction_id") == fid
            and s.get("operational", True)
            and not s.get("ruin_only")
            and not s.get("staging")
        ]
        if centres or faction.get("status") == "active":
            if centres:
                active.append(fid)
    return active


def dissolve_factions_without_centres(state: Any) -> list[str]:
    """Ordinary play: factions with no centres dissolve (not Game Over)."""
    dissolved: list[str] = []
    for fid, faction in list((getattr(state, "factions", {}) or {}).items()):
        if faction.get("status") in {"collapsed", "succeeded", "dissolved"}:
            continue
        centres = [
            s
            for s in state.settlements.values()
            if s.get("faction_id") == fid
            and s.get("operational", True)
            and not s.get("ruin_only")
            and not s.get("staging")
        ]
        if centres:
            continue
        faction["status"] = "dissolved"
        faction["operational"] = False
        faction["dissolve_reason"] = "no_centres"
        dissolved.append(fid)
    return dissolved


def sole_era_starter_ids(state: Any) -> list[str]:
    clock = getattr(state, "clock", {}) or {}
    started = list(clock.get("started_faction_ids") or [])
    if clock.get("sole_era_starter"):
        return started or active_faction_ids(state)
    if len(started) == 1:
        return started
    return []


def mark_mandatory_fission(state: Any, faction_id: str) -> None:
    clock = state.clock
    mandatory = list(clock.get("mandatory_split_ids") or [])
    if faction_id not in mandatory:
        mandatory.append(faction_id)
    clock["mandatory_split_ids"] = mandatory
    clock["sole_era_starter"] = True
    if not clock.get("started_faction_ids"):
        clock["started_faction_ids"] = [faction_id]
    faction = state.factions.setdefault(faction_id, {"id": faction_id})
    faction["mandatory_fission"] = True


def plan_undersized_mandatory_split(
    snapshot: Any,
    *,
    parent_faction_id: str,
    successor_faction_ids: Sequence[str],
) -> dict[str, Any]:
    """2/3/1-site mandatory split rules — never manufacture four duplicate centres."""
    sites = [
        {"settlement_id": sid, **rec}
        for sid, rec in sorted((getattr(snapshot, "settlements", {}) or {}).items())
        if rec.get("faction_id") == parent_faction_id
        and rec.get("operational", True)
        and not rec.get("ruin_only")
    ]
    successors = list(successor_faction_ids)
    if len(successors) != 2:
        raise TypeValidationError("mandatory split needs two successor ids")

    if len(sites) >= 4:
        return plan_fission(
            snapshot,
            parent_faction_id=parent_faction_id,
            successor_faction_ids=successors,
            split=True,
        )

    if len(sites) == 0:
        raise TypeValidationError("cannot split faction with zero sites")

    if len(sites) == 1:
        # Seed a second core at nearest legal empty node (or one-time distance exception).
        seed = propose_emergency_seed_node(snapshot, sites[0]["node_id"])
        return {
            "parent_faction_id": parent_faction_id,
            "split": True,
            "undersized": True,
            "site_count": 1,
            "successor_faction_ids": successors,
            "core_pairs": [
                {
                    "successor_faction_id": successors[0],
                    "core_settlement_ids": [sites[0]["settlement_id"]],
                    "parent_faction_id": parent_faction_id,
                },
                {
                    "successor_faction_id": successors[1],
                    "core_settlement_ids": [],
                    "seed_node_id": seed["node_id"],
                    "distance_exception": seed.get("distance_exception", False),
                    "parent_faction_id": parent_faction_id,
                },
            ],
            "settlement_assignments": {sites[0]["settlement_id"]: successors[0]},
            "seed_operations": [seed],
            "road_assignments": {},
            "unit_assignments": {},
            "cart_assignments": {},
            "research_assignments": {s: parent_faction_id for s in successors},
            "person_assignments": {},
            "sibling_relation": {"status": "neutral", "trade_permitted": True},
        }

    # 2 or 3 sites: each successor gets at least one existing core; extras by rank/distance.
    ranked = sorted(sites, key=lambda s: str(s["settlement_id"]))
    core_pairs = [
        {
            "successor_faction_id": successors[0],
            "core_settlement_ids": [ranked[0]["settlement_id"]],
            "parent_faction_id": parent_faction_id,
        },
        {
            "successor_faction_id": successors[1],
            "core_settlement_ids": [ranked[1]["settlement_id"]],
            "parent_faction_id": parent_faction_id,
        },
    ]
    assignments = {
        ranked[0]["settlement_id"]: successors[0],
        ranked[1]["settlement_id"]: successors[1],
    }
    if len(ranked) == 3:
        # Assign extra to nearest of the two cores.
        board = HexBoard.from_dict((getattr(snapshot, "board", {}) or {}).get("topology") or {})
        extra = ranked[2]
        d0 = node_distance(board, str(extra["node_id"]), str(ranked[0]["node_id"]))
        d1 = node_distance(board, str(extra["node_id"]), str(ranked[1]["node_id"]))
        pick = successors[0] if (d0, ranked[0]["settlement_id"]) <= (d1, ranked[1]["settlement_id"]) else successors[1]
        assignments[extra["settlement_id"]] = pick
        for pair in core_pairs:
            if pair["successor_faction_id"] == pick:
                pair["core_settlement_ids"].append(extra["settlement_id"])
    return {
        "parent_faction_id": parent_faction_id,
        "split": True,
        "undersized": True,
        "site_count": len(sites),
        "successor_faction_ids": successors,
        "core_pairs": core_pairs,
        "settlement_assignments": assignments,
        "seed_operations": [],
        "road_assignments": {},
        "unit_assignments": {},
        "cart_assignments": {},
        "research_assignments": {s: parent_faction_id for s in successors},
        "person_assignments": {},
        "sibling_relation": {"status": "neutral", "trade_permitted": True},
    }


def propose_emergency_seed_node(snapshot: Any, origin_node: str) -> dict[str, Any]:
    """Nearest legal empty node; one-time exception if none distance-legal."""
    board = HexBoard.from_dict((getattr(snapshot, "board", {}) or {}).get("topology") or {})
    occupied = {
        str(s.get("node_id"))
        for s in (getattr(snapshot, "settlements", {}) or {}).values()
        if s.get("node_id") and not s.get("ruin_only")
    }
    candidates: list[tuple[int, str]] = []
    for nid in board.nodes:
        if nid in occupied or nid == origin_node:
            continue
        dist = node_distance(board, origin_node, nid)
        # Normal placement prefers distance >= 2 from existing settlement.
        candidates.append((dist, nid))
    if not candidates:
        raise TypeValidationError("invariant_violation: no empty node for emergency seed")
    candidates.sort()
    legal = [c for c in candidates if c[0] >= 2]
    if legal:
        dist, node_id = legal[0]
        return {"node_id": node_id, "distance": dist, "distance_exception": False}
    # Explicit one-time exception: nearest empty node even if adjacent.
    dist, node_id = candidates[0]
    return {"node_id": node_id, "distance": dist, "distance_exception": True}


@dataclass
class RecoveryService:
    state: Any

    def ensure_factions_for_world_turn(self) -> dict[str, Any]:
        """On World Turn with zero active factions, seed two via recovery (not Game Over)."""
        dissolved = dissolve_factions_without_centres(self.state)
        active = active_faction_ids(self.state)
        if active:
            return {"active": active, "dissolved": dissolved, "seeded": []}
        seeded = self.seed_two_factions()
        return {"active": active_faction_ids(self.state), "dissolved": dissolved, "seeded": seeded}

    def seed_two_factions(self) -> list[str]:
        board = HexBoard.from_dict((self.state.board or {}).get("topology") or {})
        occupied = {
            str(s.get("node_id"))
            for s in self.state.settlements.values()
            if s.get("node_id") and not s.get("ruin_only")
        }
        empties = [nid for nid in board.nodes if nid not in occupied]
        if len(empties) < 2:
            raise TypeValidationError("cannot seed two factions: insufficient empty nodes")
        # Prefer well-separated nodes.
        best_pair = None
        best_dist = -1
        for i, a in enumerate(empties):
            for b in empties[i + 1 :]:
                d = node_distance(board, a, b)
                if d > best_dist:
                    best_dist = d
                    best_pair = (a, b)
        assert best_pair is not None
        seeded: list[str] = []
        for node_id in best_pair:
            fid = self.state.ids.new("faction")
            sid = self.state.ids.new("settlement")
            self.state.factions[fid] = {
                "id": fid,
                "status": "active",
                "operational": True,
                "recovery_seeded": True,
            }
            self.state.settlements[sid] = {
                "id": sid,
                "node_id": node_id,
                "faction_id": fid,
                "tier": "settlement",
                "operational": True,
                "recovery_seeded": True,
                "ruin_only": False,
            }
            seeded.append(fid)
        # Preserve displaced living people / quests / cargo — do not touch them.
        self.state.clock["started_faction_ids"] = list(seeded)
        self.state.clock["sole_era_starter"] = False
        scheduled = list(self.state.clock.get("scheduled_faction_ids") or [])
        for fid in seeded:
            if fid not in scheduled:
                scheduled.append(fid)
        self.state.clock["scheduled_faction_ids"] = scheduled
        return seeded
