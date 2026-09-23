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

# Optional neural brain registry: policy_id -> artifact path (pinned, local only).
_NEURAL_ARTIFACTS: dict[str, str] = {}
_NEURAL_CACHE: dict[str, Any] = {}


def register_neural_artifact(policy_id: str, artifact_path: str) -> None:
    """Pin a local inference artifact for a policy id (no network fetch)."""
    _NEURAL_ARTIFACTS[policy_id] = artifact_path
    _NEURAL_CACHE.pop(policy_id, None)


def load_policy_manifest(path: str | None = None) -> dict[str, Any]:
    """Load content/policies/manifest.json if present."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    manifest_path = Path(path) if path else root / "godot_project" / "content" / "policies" / "manifest.json"
    if not manifest_path.is_file():
        return {"policies": []}
    import json

    return json.loads(manifest_path.read_text(encoding="utf-8"))


@dataclass
class PolicyService:
    state: WorldState
    brain: Any = field(default_factory=HeuristicBrain)
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
                "policy_id": "heuristic",
                "assignments": [],
                "selections": [],
                "cargo_schedules": [],
            },
        )
        return policy

    def assign_brain(self, faction_id: str, brain_name: str = "heuristic") -> None:
        bucket = self._policy_bucket(faction_id)
        bucket["brain"] = brain_name
        bucket["policy_id"] = brain_name
        bucket["assignments"].append(
            {"brain": brain_name, "turn": int(self.state.clock.get("turn", 0))}
        )

    def resolve_brain(self, faction_id: str) -> Any:
        """Resolve per-faction brain; neural failures fall back inside NeuralBrain."""
        bucket = self._policy_bucket(faction_id)
        name = str(bucket.get("brain") or bucket.get("policy_id") or "heuristic")
        if name in {"heuristic", "scripted"}:
            return self.brain if name == "heuristic" else self.brain
        # Neural / named policy artifact.
        if name not in _NEURAL_CACHE:
            artifact = _NEURAL_ARTIFACTS.get(name)
            if artifact is None:
                # Try manifest.
                for entry in load_policy_manifest().get("policies") or []:
                    if entry.get("id") == name and entry.get("artifact"):
                        artifact = entry["artifact"]
                        break
            if artifact:
                from pathlib import Path

                from sim.dmb.ai.neural import NeuralBrain

                root = Path(__file__).resolve().parents[3]
                path = Path(artifact)
                if not path.is_file():
                    path = root / artifact
                brain = NeuralBrain(artifact_path=path, policy_id=name)
                _NEURAL_CACHE[name] = brain
            else:
                _NEURAL_CACHE[name] = HeuristicBrain()
        return _NEURAL_CACHE[name]

    def activate(self, faction_id: str, *, decision_kind: str = "seat") -> dict[str, Any]:
        """One seat activation: observe, enumerate, choose ≤1 construct + ≤1 proposal."""
        assert self.observations is not None and self.legal is not None
        cargo_retries = self._retry_pending_cargo(faction_id)
        obs = self.observations.build(faction_id, decision_kind)
        candidates = self.legal.enumerate(obs, decision_kind)
        brain = self.resolve_brain(faction_id)
        if hasattr(brain, "choose_activation"):
            choice = brain.choose_activation(obs, candidates)
        else:
            cid = brain.choose(obs, candidates)
            choice = {"primary_id": cid, "selected_ids": [cid]}
        by_id = {c["id"]: c for c in candidates}
        applied: list[dict[str, Any]] = list(cargo_retries)
        selected_ids = list(choice.get("selected_ids") or [])
        illegal = [cid for cid in selected_ids if cid not in by_id]
        if illegal:
            # Illegal/stale neural output → best legal heuristic; no partial neural action.
            choice = HeuristicBrain().choose_activation(obs, candidates)
            selected_ids = list(choice["selected_ids"])
            applied.append({"status": "neural_illegal_fallback", "rejected_ids": illegal})
        for cid in selected_ids:
            applied.append(self._apply_candidate(obs, by_id[cid]))
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
            "source": choice.get("source") or str(self._policy_bucket(faction_id).get("brain")),
            "policy_id": self._policy_bucket(faction_id).get("policy_id"),
            "inference_ms": choice.get("inference_ms"),
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
        if kind == "diplomacy_propose":
            from sim.dmb.ai.diplomacy import DiplomacyService

            dip = DiplomacyService(self.state)
            target = str(params.get("target_faction"))
            proposal = str(params.get("proposal") or "alliance")
            result = dip.propose(str(candidate["faction_id"]), target, proposal)
            return {"status": "diplomacy", "commit": commit, "result": result}
        if kind == "trade_propose":
            from sim.dmb.logistics.stock import StockLedger
            from sim.dmb.logistics.trade import TradeService

            # Only propose when both sides have stock at known warehouses; never invent goods.
            ledger = StockLedger(self.state)
            trade = TradeService(self.state, ledger=ledger)
            give = dict(params.get("give") or {})
            receive = dict(params.get("receive") or {})
            proposer = str(candidate["faction_id"])
            counter = str(params.get("target_faction"))
            p_store = self._primary_store(proposer)
            c_store = self._primary_store(counter)
            if not p_store or not c_store:
                return {"status": "trade_skipped", "reason": "missing_store", "commit": commit}
            try:
                contract = trade.propose(
                    proposer,
                    counter,
                    give=give,
                    receive=receive,
                    proposer_store=p_store,
                    counterparty_store=c_store,
                )
            except TypeValidationError as exc:
                return {"status": "trade_blocked", "reason": str(exc), "commit": commit}
            return {"status": "trade_proposed", "commit": commit, "contract": contract}
        if kind == "military_move":
            from sim.dmb.military.movement import StrategicMovement

            mover = StrategicMovement(self.state)
            fid = str(params.get("formation_id") or "")
            path = list(params.get("path") or params.get("nodes") or [])
            faction_id = str(candidate.get("faction_id") or "")
            if not fid or len(path) < 1:
                return {"status": "military_move_skipped", "reason": "missing_path", "commit": commit}
            try:
                result = mover.activate(
                    fid,
                    path,
                    active_faction_id=faction_id,
                    turn=int(self.state.clock.get("turn", 0)),
                )
            except Exception as exc:  # pragma: no cover - defensive
                return {"status": "military_move_blocked", "reason": str(exc), "commit": commit}
            return {"status": "military_moved", "commit": commit, "result": result}
        if kind == "military_objective":
            from sim.dmb.military.formations import FormationDirector

            director = FormationDirector(self.state)
            fid = str(params.get("formation_id") or "")
            objective = str(params.get("objective") or "")
            if not fid or not objective:
                return {"status": "military_objective_skipped", "commit": commit}
            try:
                formation = director.get(fid)
                formation["objective"] = objective
                if params.get("node_id"):
                    formation["objective_node_id"] = str(params.get("node_id"))
            except Exception as exc:  # pragma: no cover
                return {"status": "military_objective_blocked", "reason": str(exc), "commit": commit}
            return {
                "status": "military_objective_set",
                "commit": commit,
                "formation_id": fid,
                "objective": objective,
            }
        if kind == "military_withdraw":
            from sim.dmb.military.formations import FormationDirector

            director = FormationDirector(self.state)
            fid = str(params.get("formation_id") or "")
            if not fid:
                return {"status": "military_withdraw_skipped", "commit": commit}
            try:
                result = director.mark_withdrawal(fid)
            except Exception as exc:  # pragma: no cover
                return {"status": "military_withdraw_blocked", "reason": str(exc), "commit": commit}
            return {"status": "military_withdrawn", "commit": commit, "result": result}
        return {"status": "proposed", "commit": commit, "candidate_id": candidate["id"]}

    def _primary_store(self, faction_id: str) -> str | None:
        for settlement in self.state.settlements.values():
            if settlement.get("faction_id") != faction_id:
                continue
            wh = settlement.get("warehouse_id")
            if wh:
                return f"store:{wh}"
        return None

    def _faction_stores(self, faction_id: str) -> list[str]:
        out: list[str] = []
        for settlement in self.state.settlements.values():
            if settlement.get("faction_id") != faction_id or settlement.get("staging"):
                continue
            wh = settlement.get("warehouse_id")
            if wh:
                out.append(f"store:{wh}")
        return out

    def _store_node(self, store_id: str) -> str | None:
        bid = store_id.split("store:", 1)[-1]
        building = self.state.buildings.get(bid) or {}
        node = building.get("node_id")
        return str(node) if node else None

    def _find_source_store(
        self,
        faction_id: str,
        missing: dict[str, int],
        *,
        destination_store: str,
    ) -> str | None:
        """Find a same-faction warehouse that can cover all missing goods."""
        assert self.director is not None and self.director.ledger is not None
        ledger = self.director.ledger
        for store_id in self._faction_stores(faction_id):
            if store_id == destination_store:
                continue
            if all(ledger.available(store_id, good) >= qty for good, qty in missing.items()):
                return store_id
        return None

    def _assign_cargo_haul(
        self,
        *,
        faction_id: str,
        destination_store: str,
        missing: dict[str, int],
        pending_id: str,
    ) -> dict[str, Any] | None:
        """Reserve at a source warehouse and assign an idle cart via LogisticsService."""
        assert self.director is not None and self.director.ledger is not None
        source = self._find_source_store(faction_id, missing, destination_store=destination_store)
        if not source:
            return None
        idle = self.director.idle_carts(faction_id)
        if not idle:
            return None
        cart_id = idle[0]
        source_node = self._store_node(source)
        dest_node = self._store_node(destination_store)
        if not source_node or not dest_node:
            return None
        try:
            reservation = self.director.ledger.reserve(
                pending_id,
                {k: int(v) for k, v in missing.items()},
                store_id=source,
            )
        except TypeValidationError:
            return None
        assigned = self.director.assign(
            cart_id,
            source=source_node,
            target=dest_node,
            destination_store=destination_store,
            reservation_id=str(reservation.get("id") or ""),
        )
        return {"cart_id": cart_id, "source": source, "assign": assigned, "reservation": reservation}

    def _retry_pending_cargo(self, faction_id: str) -> list[dict[str, Any]]:
        """When goods arrive, convert awaiting_cargo pending orders into real reservations."""
        assert self.construction is not None
        applied: list[dict[str, Any]] = []
        for oid, order in list((self.state.orders or {}).items()):
            if not str(oid).startswith("pending:"):
                continue
            if order.get("status") != "awaiting_cargo":
                continue
            if str(order.get("faction_id") or "") != faction_id:
                continue
            action = str(order.get("action") or "")
            store_id = str(order.get("store_id") or "")
            target_node = order.get("target_node")
            edge_raw = order.get("target_edge")
            edge = tuple(edge_raw) if isinstance(edge_raw, (list, tuple)) and len(edge_raw) == 2 else None
            quote = self.construction.quote(
                action,
                faction_id=faction_id,
                store_id=store_id,
                target_node=target_node,
                target_edge=edge,
            )
            if quote.get("status") != "ok":
                missing = dict(quote.get("missing") or {})
                if missing and quote.get("reason") == "insufficient_local_goods":
                    haul = self._assign_cargo_haul(
                        faction_id=faction_id,
                        destination_store=store_id,
                        missing=missing,
                        pending_id=str(oid),
                    )
                    if haul:
                        applied.append({"status": "cargo_assigned", "pending": oid, "haul": haul})
                continue
            reserved = self.construction.reserve_order(
                action,
                faction_id=faction_id,
                store_id=store_id,
                target_node=target_node,
                target_edge=edge,
            )
            order["status"] = "superseded"
            applied.append({"status": "pending_reserved", "pending": oid, "order": reserved})
        return applied

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
        # Only schedule cargo when local goods are the blocker — never for placement illegality.
        if quote.get("reason") != "insufficient_local_goods":
            return {
                "status": "construct_blocked",
                "reason": quote.get("reason"),
                "quote": quote,
                "candidate_id": candidate["id"],
            }
        missing = dict(quote.get("missing") or {})
        schedule = {
            "faction_id": faction_id,
            "action": action,
            "store_id": store_id,
            "missing": missing,
            "candidate_id": candidate["id"],
            "turn": int(self.state.clock.get("turn", 0)),
            "director": "cargo_intent",
        }
        idle = self.director.idle_carts(faction_id) if self.director else []
        schedule["idle_carts"] = list(idle)
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
        haul = self._assign_cargo_haul(
            faction_id=faction_id,
            destination_store=store_id,
            missing=missing,
            pending_id=str(pending["id"]),
        )
        if haul:
            schedule["haul"] = haul
            self._policy_bucket(faction_id)["cargo_schedules"].append(schedule)
            return {"status": "cargo_assigned", "schedule": schedule, "candidate_id": candidate["id"]}
        self._policy_bucket(faction_id)["cargo_schedules"].append(schedule)
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
