"""Deterministic heuristic faction brain (C12 / T043)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Lexicographic priority tiers (lower = more urgent).
PRIORITY = {
    "catastrophe": 0,
    "win_vp": 1,
    "restore_core": 2,
    "expand": 3,  # city/settlement/road/legacy
    "extra": 4,  # processor / military (military deferred)
    "trade": 5,
    "diplomacy": 6,
    "tech_pick": 7,
    "noop": 9,
}


def _construction_utility(candidate: dict[str, Any], observation: dict[str, Any]) -> int:
    """C12 tunable integer utility for construction candidates."""
    benefit = candidate.get("benefit") or {}
    params = candidate.get("params") or {}
    vp_gain = int(benefit.get("vp_gain") or (2 if params.get("action") == "city" else 0))
    if params.get("action") == "settlement":
        vp_gain = int(benefit.get("vp_gain") or 1)
    new_goods = int(benefit.get("new_catan_good_types") or 0)
    pips = int(benefit.get("target_best_pips") or 0)
    milli = int(benefit.get("additional_milliunits_per_second") or 0)
    cart_trips = int(benefit.get("required_cart_edge_trips") or 0)
    new_roads = int(benefit.get("new_road_edges_needed") or (1 if params.get("action") == "road" else 0))
    return (
        1000 * vp_gain
        + 100 * new_goods
        + 20 * pips
        + 10 * milli
        - 5 * cart_trips
        - 10 * new_roads
    )


def _tier(candidate: dict[str, Any], observation: dict[str, Any]) -> int:
    kind = str(candidate.get("action_kind"))
    params = candidate.get("params") or {}
    own_vp = int((observation.get("own") or {}).get("vp") or 0)
    if kind == "construct":
        action = str(params.get("action") or "")
        if (observation.get("public") or {}).get("catastrophe"):
            if action in {"repair", "replacement_cart"}:
                return PRIORITY["catastrophe"]
        vp_gain = int((candidate.get("benefit") or {}).get("vp_gain") or 0)
        if action == "city":
            vp_gain = max(vp_gain, 2)
        if action == "settlement":
            vp_gain = max(vp_gain, 1)
        if own_vp + vp_gain >= 10:
            return PRIORITY["win_vp"]
        if action in {"repair", "replacement_cart", "processor"} and "missing" in str(
            candidate.get("explanation") or ""
        ):
            return PRIORITY["restore_core"]
        if action in {"city", "settlement", "road", "legacy_upgrade"}:
            return PRIORITY["expand"]
        if action == "processor":
            return PRIORITY["extra"]
        return PRIORITY["expand"]
    if kind == "trade_propose":
        return PRIORITY["trade"]
    if kind == "diplomacy_propose":
        return PRIORITY["diplomacy"]
    if kind == "tech_pick":
        return PRIORITY["tech_pick"]
    if kind == "noop":
        return PRIORITY["noop"]
    return 8


@dataclass
class HeuristicBrain:
    """Deterministic scoring / ties; baseline policy. Does not mutate world state."""

    def score(self, observation: dict[str, Any], candidate: dict[str, Any]) -> tuple[int, int, str]:
        tier = _tier(candidate, observation)
        utility = 0
        if candidate.get("action_kind") == "construct":
            utility = _construction_utility(candidate, observation)
        elif candidate.get("action_kind") == "trade_propose":
            # Prefer trades that cover observed construction shortages on shorter routes.
            benefit = candidate.get("benefit") or {}
            utility = (
                10 * int(benefit.get("shortage_goods_covered") or 0)
                - int(benefit.get("route_length") or 0)
            )
        elif candidate.get("action_kind") == "tech_pick":
            # Prefer first stable id among hand (definition id as weak signal).
            utility = 0
        # Sort key: lower tier better, higher utility better, then stable id.
        return (tier, -utility, str(candidate["id"]))

    def choose(self, observation: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
        if not candidates:
            raise RuntimeError("no candidates")
        ranked = sorted(candidates, key=lambda c: self.score(observation, c))
        # Apply one-construction + one-proposal allowance at activation selection:
        # choose the best overall; PolicyService enforces the dual-slot commit set.
        return str(ranked[0]["id"])

    def choose_activation(
        self, observation: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Select ≤1 construction and ≤1 proposal (trade/diplomacy), plus optional tech."""
        ranked = sorted(candidates, key=lambda c: self.score(observation, c))
        construction = None
        proposal = None
        tech = None
        noop = None
        for cand in ranked:
            kind = cand.get("action_kind")
            if kind == "construct" and construction is None:
                construction = cand
            elif kind in {"trade_propose", "diplomacy_propose"} and proposal is None:
                proposal = cand
            elif kind == "tech_pick" and tech is None:
                tech = cand
            elif kind == "noop" and noop is None:
                noop = cand
        selected = [c for c in (construction, proposal, tech) if c is not None]
        if not selected and noop is not None:
            selected = [noop]
        elif not selected and ranked:
            selected = [ranked[0]]
        return {
            "primary_id": selected[0]["id"] if selected else ranked[0]["id"],
            "selected_ids": [c["id"] for c in selected],
            "construction_id": construction["id"] if construction else None,
            "proposal_id": proposal["id"] if proposal else None,
            "tech_id": tech["id"] if tech else None,
        }
