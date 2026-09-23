"""Local neural inference with legal heuristic fallback (C12 / T147).

Loads pinned inference weights + schema only. Training dependencies are not
required at runtime. Wrong schema / timeout / exception → legal heuristic,
never a partial neural action or free extra resources.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.ai.heuristic import HeuristicBrain
from training.environment import schema_hash
from training.model import CandidateScorer

# p95 target 20 ms (C14). Soft deadline for a single choose call.
INFERENCE_DEADLINE_MS = 20.0
# Documented personality bias for family-specialised trained policies (C14 diversity).
FAMILY_LOGIT_BIAS = 2.5
FAMILY_KIND = {
    "build": {"construct"},
    "trade": {"trade_propose", "diplomacy_propose"},
    "war": {"military_move", "military_objective", "military_withdraw"},
    "other": set(),
}


@dataclass
class NeuralBrain:
    """Pinned local candidate scorer; same choose contract as HeuristicBrain."""

    artifact_path: Path
    model: CandidateScorer | None = None
    load_error: str | None = None
    fallback: HeuristicBrain = field(default_factory=HeuristicBrain)
    last_inference_ms: float = 0.0
    last_source: str = "uninitialized"
    force_fail: bool = False
    policy_id: str = "neural"
    prefer_family: str | None = None

    def __post_init__(self) -> None:
        self.artifact_path = Path(self.artifact_path)
        try:
            self.model = CandidateScorer.load(self.artifact_path, expect_schema_hash=schema_hash())
            if not self.model.trained:
                self.load_error = "artifact_not_marked_trained"
                self.model = None
            else:
                prov = getattr(self.model, "provenance", None) or {}
                if isinstance(prov, dict) and prov.get("prefer_family"):
                    self.prefer_family = str(prov.get("prefer_family"))
        except Exception as exc:  # noqa: BLE001 — fallback is the contract
            self.load_error = str(exc)
            self.model = None

    def choose(self, observation: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
        result = self.choose_activation(observation, candidates)
        return str(result["primary_id"])

    def choose_activation(
        self, observation: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        started = time.perf_counter()
        source = "heuristic_fallback"
        primary: str | None = None
        try:
            if self.force_fail:
                raise RuntimeError("forced_inference_failure")
            if self.model is None:
                raise RuntimeError(self.load_error or "model_unavailable")
            # Score only supplied candidates — never emit arbitrary IDs.
            ranked = self.model.score_candidates(observation, candidates)
            if self.prefer_family and self.prefer_family in FAMILY_KIND:
                kinds = FAMILY_KIND[self.prefer_family]
                by_id = {c["id"]: c for c in candidates}
                boosted: list[tuple[str, float]] = []
                for cid, score in ranked:
                    cand = by_id.get(cid) or {}
                    ak = str(cand.get("action_kind") or "")
                    bonus = FAMILY_LOGIT_BIAS if ak in kinds else 0.0
                    boosted.append((cid, float(score) + bonus))
                ranked = boosted
            ranked.sort(key=lambda x: (-x[1], x[0]))
            primary = ranked[0][0]
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.last_inference_ms = elapsed_ms
            if elapsed_ms > INFERENCE_DEADLINE_MS:
                raise TimeoutError(f"inference_deadline_ms={elapsed_ms:.3f}")
            # Deterministic dual-slot selection mirroring heuristic structure,
            # but ordered by neural scores.
            by_id = {c["id"]: c for c in candidates}
            score_order = [by_id[cid] for cid, _ in ranked if cid in by_id]
            choice = self._select_slots(score_order)
            source = "neural"
            self.last_source = source
            choice["inference_ms"] = elapsed_ms
            choice["source"] = source
            choice["policy_id"] = self.policy_id
            if self.prefer_family:
                choice["prefer_family"] = self.prefer_family
            return choice
        except Exception:
            # No partial neural action — full heuristic replacement within same seat budget.
            choice = self.fallback.choose_activation(observation, candidates)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.last_inference_ms = elapsed_ms
            self.last_source = "heuristic_fallback"
            choice["inference_ms"] = elapsed_ms
            choice["source"] = "heuristic_fallback"
            choice["policy_id"] = self.policy_id
            choice["fallback_reason"] = self.load_error or "inference_error_or_timeout"
            return choice

    @staticmethod
    def _select_slots(ranked: list[dict[str, Any]]) -> dict[str, Any]:
        primary = None
        construction = None
        proposal = None
        tech = None
        noop = None
        primary_kinds = {
            "construct",
            "military_move",
            "military_objective",
            "military_withdraw",
            "hazard_treat",
            "tech_pick",
        }
        for cand in ranked:
            kind = cand.get("action_kind")
            if kind in primary_kinds and primary is None:
                primary = cand
            if kind == "construct" and construction is None:
                construction = cand
            elif kind in {"trade_propose", "diplomacy_propose"} and proposal is None:
                proposal = cand
            elif kind == "tech_pick" and tech is None:
                tech = cand
            elif kind == "noop" and noop is None:
                noop = cand
        selected = [c for c in (primary, proposal) if c is not None]
        if tech is not None and primary is not tech and tech not in selected:
            selected.append(tech)
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
