"""Policy assignment, commitments and recorded replay (C12 / T043)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.legal import LegalActionGenerator
from sim.dmb.ai.observation import ObservationBuilder
from sim.dmb.construction.orders import ConstructionService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.director import LogisticsService
from sim.dmb.logistics.stock import StockLedger


@dataclass
class PolicyService:
    state: WorldState
    brain: HeuristicBrain = field(default_factory=HeuristicBrain)
    observations: ObservationBuilder | None = None
    legal: LegalActionGenerator | None = None
    construction: ConstructionService | None = None
    director: LogisticsService | None = None

    def __post_init__(self) -> None:
        if self.observations is None:
            self.observations = ObservationBuilder(self.state)
        if self.legal is None:
            self.legal = LegalActionGenerator(self.state)
        if self.construction is None:
            self.construction = ConstructionService(self.state)
        if self.director is None:
            self.director = LogisticsService(self.state)

    def _policy_bucket(self, faction_id: str) -> dict[str, Any]:
        faction = self.state.factions.setdefault(faction_id, {"id": faction_id})
        policy = faction.setdefault(
            "policy",
            {
                "brain": "heuristic",
                "assignments": [],
                "selections": [],
                "cargo_schedules": [],
            },
        )
        return policy

    def assign_brain(self, faction_id: str, brain_name: str = "heuristic") -> None:
        bucket = self._policy_bucket(faction_id)
        bucket["brain"] = brain_name
        bucket["assignments"].append(
            {"brain": brain_name, "turn": int(self.state.clock.get("turn", 0))}
        )

    def activate(self, faction_id: str, *, decision_kind: str = "seat") -> dict[str, Any]:
        """One seat activation: observe, enumerate, choose ≤1 construct + ≤1 proposal."""
        assert self.observations is not None and self.legal is not None
        obs = self.observations.build(faction_id, decision_kind)
        candidates = self.legal.enumerate(obs, decision_kind)
        choice = self.brain.choose_activation(obs, candidates)
        by_id = {c["id"]: c for c in candidates}
        applied: list[dict[str, Any]] = []
        for cid in choice["selected_ids"]:
            cand = by_id[cid]
            result = self._apply_candidate(obs, cand)
            applied.append(result)
        record = {
            "faction_id": faction_id,
            "turn": int(self.state.clock.get("turn", 0)),
            "decision_kind": decision_kind,
            "observation_schema": obs.get("schema"),
            "legal_version": obs.get("legal_version"),
            "candidate_ids": [c["id"] for c in candidates],
            "selected_ids": list(choice["selected_ids"]),
            "primary_id": choice["primary_id"],
            "applied": applied,
        }
        self._policy_bucket(faction_id)["selections"].append(deepcopy(record))
        return record

    def _apply_candidate(self, obs: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        assert self.legal is not None and self.construction is not None
        # Revalidate; stale rejects without partial mutation.
        commit = self.legal.commit(obs, candidate)
        kind = candidate.get("action_kind")
        params = candidate.get("params") or {}
        if kind == "construct":
            return self._apply_construct(candidate, params)
        if kind == "noop":
            return {"status": "noop", "commit": commit}
        # Trade/diplomacy proposals recorded as commitments; execution in T044/T045.
        return {"status": "proposed", "commit": commit, "candidate_id": candidate["id"]}

    def _apply_construct(self, candidate: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        assert self.construction is not None and self.director is not None
        action = str(params.get("action"))
        faction_id = str(candidate["faction_id"])
        store_id = str(params.get("store_id"))
        target_node = params.get("target_node")
        target_edge = params.get("target_edge")
        edge = tuple(target_edge) if isinstance(target_edge, (list, tuple)) else None
        quote = self.construction.quote(
            action,
            faction_id=faction_id,
            store_id=store_id,
            target_node=target_node,
            target_edge=edge,
        )
        if quote.get("status") == "ok":
            order = self.construction.reserve_order(
                action,
                faction_id=faction_id,
                store_id=store_id,
                target_node=target_node,
                target_edge=edge,
            )
            return {"status": "reserved", "order": order, "candidate_id": candidate["id"]}
        # Unaffordable: schedule cargo for missing goods (no free resources).
        missing = dict(quote.get("missing") or quote.get("required") or {})
        schedule = {
            "faction_id": faction_id,
            "action": action,
            "store_id": store_id,
            "missing": missing,
            "candidate_id": candidate["id"],
            "turn": int(self.state.clock.get("turn", 0)),
            "director": "cargo_intent",
        }
        # Record haul intent against idle carts when a source store exists; never invent stock.
        idle = self.director.idle_carts(faction_id) if self.director else []
        schedule["idle_carts"] = list(idle)
        self._policy_bucket(faction_id)["cargo_schedules"].append(schedule)
        pending = self.state.orders.setdefault(
            f"pending:{candidate['id']}",
            {
                "id": f"pending:{candidate['id']}",
                "status": "awaiting_cargo",
                "faction_id": faction_id,
                "action": action,
                "store_id": store_id,
                "target_node": target_node,
                "target_edge": list(edge) if edge else None,
                "missing": missing,
            },
        )
        schedule["pending_order_id"] = pending["id"]
        return {"status": "cargo_scheduled", "schedule": schedule, "candidate_id": candidate["id"]}

    def replay_selection(self, faction_id: str, selection_index: int = -1) -> dict[str, Any]:
        """Return the recorded selection for replay; does not re-score."""
        selections = self._policy_bucket(faction_id).get("selections") or []
        if not selections:
            raise TypeValidationError("no recorded selections")
        return deepcopy(selections[selection_index])

    def choose_recorded_or_live(
        self,
        faction_id: str,
        candidates: list[dict[str, Any]],
        *,
        recorded_primary_id: str | None,
    ) -> str:
        """Replay uses recorded selection even if heuristic ranking would differ."""
        if recorded_primary_id is not None:
            ids = {c["id"] for c in candidates}
            if recorded_primary_id not in ids:
                raise TypeValidationError("recorded selection not in candidate list")
            return recorded_primary_id
        obs = {"own": {"vp": 0}, "public": {}, "faction_id": faction_id}
        return self.brain.choose(obs, candidates)
