"""Bounded legal action candidate generation and validation (C12 / T042)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sim.dmb.construction.orders import COSTS, ConstructionService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.stock import StockLedger


def _candidate(
    *,
    action_kind: str,
    faction_id: str,
    params: dict[str, Any],
    legal_version: int,
    cost: dict[str, int] | None = None,
    benefit: dict[str, Any] | None = None,
    explanation: str = "",
) -> dict[str, Any]:
    bound = {k: v for k, v in params.items() if v is not None}
    cid = action_kind + ":" + ":".join(f"{k}={bound[k]}" for k in sorted(bound))
    return {
        "id": cid,
        "action_kind": action_kind,
        "faction_id": faction_id,
        "params": bound,
        "legal_version": legal_version,
        "cost": dict(cost or {}),
        "benefit": dict(benefit or {}),
        "expiry_turn": None,
        "explanation": explanation,
    }


@dataclass
class LegalActionGenerator:
    state: WorldState
    construction: ConstructionService | None = None
    validators: dict[str, Callable[[dict[str, Any], dict[str, Any]], bool]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.construction is None:
            self.construction = ConstructionService(self.state)
        self.validators.setdefault("noop", self._validate_noop)
        self.validators.setdefault("construct", self._validate_construct)
        self.validators.setdefault("tech_pick", self._validate_tech_pick)
        self.validators.setdefault("diplomacy_propose", self._validate_diplomacy)
        self.validators.setdefault("trade_propose", self._validate_trade)
        self.validators.setdefault("military_move", self._validate_military_move)
        self.validators.setdefault("military_withdraw", self._validate_military_withdraw)
        self.validators.setdefault("military_objective", self._validate_military_objective)

    def enumerate(self, view: dict[str, Any], decision_kind: str) -> list[dict[str, Any]]:
        faction_id = str(view["faction_id"])
        version = int(view.get("legal_version") or self.state.world_version)
        candidates: list[dict[str, Any]] = []

        if decision_kind in {"seat", "construction", "all"}:
            candidates.extend(self._construction_candidates(faction_id, version, view))
        if decision_kind in {"seat", "technology", "all"}:
            candidates.extend(self._tech_candidates(faction_id, version, view))
        if decision_kind in {"seat", "diplomacy", "all"}:
            candidates.extend(self._diplomacy_candidates(faction_id, version, view))
        if decision_kind in {"seat", "trade", "all"}:
            candidates.extend(self._trade_candidates(faction_id, version, view))
        if decision_kind in {"seat", "military", "all"}:
            candidates.extend(self._military_candidates(faction_id, version, view))
            candidates.extend(self._military_objective_candidates(faction_id, version, view))


        # Always include a legal no-op when the seat cannot usefully act / as fallback.
        candidates.append(
            _candidate(
                action_kind="noop",
                faction_id=faction_id,
                params={"reason": "wait"},
                legal_version=version,
                explanation="legal no-op",
            )
        )

        # Deduplicate by id, sort for stable masks.
        by_id = {c["id"]: c for c in candidates}
        ordered = [by_id[k] for k in sorted(by_id)]
        for cand in ordered:
            if not self.validate_candidate(view, cand):
                raise TypeValidationError(f"generator emitted illegal candidate {cand['id']}")
        return ordered

    def validate_candidate(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        current = int(self.state.world_version)
        cand_ver = candidate.get("legal_version")
        view_ver = view.get("legal_version")
        if cand_ver is None or int(cand_ver) != current:
            return False
        if view_ver is None or int(view_ver) != current:
            return False
        if candidate.get("faction_id") != view.get("faction_id"):
            return False
        kind = str(candidate.get("action_kind"))
        validator = self.validators.get(kind)
        if validator is None:
            return False
        return bool(validator(view, candidate))

    def commit(self, view: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        """Revalidate at commit; reject stale without partial mutation."""
        before = self.state.world_version
        if not self.validate_candidate(view, candidate):
            raise TypeValidationError("stale or illegal candidate rejected")
        # Commit is a typed intent record for later policy/world wiring — no free resources.
        record = {
            "status": "accepted",
            "candidate_id": candidate["id"],
            "action_kind": candidate["action_kind"],
            "faction_id": candidate["faction_id"],
            "params": dict(candidate.get("params") or {}),
            "world_version": before,
        }
        commitments = self.state.factions.setdefault(str(candidate["faction_id"]), {}).setdefault(
            "commitments", []
        )
        commitments.append(record)
        return record

    def _validate_noop(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        return candidate.get("action_kind") == "noop"

    def _validate_construct(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        params = candidate.get("params") or {}
        action = str(params.get("action") or "")
        if action not in COSTS:
            return False
        assert self.construction is not None
        quote = self.construction.quote(
            action,
            faction_id=str(candidate["faction_id"]),
            store_id=str(params.get("store_id") or ""),
            target_node=params.get("target_node"),
            target_edge=tuple(params["target_edge"]) if params.get("target_edge") else None,
            target_building=params.get("target_building"),
        )
        return quote.get("status") in {"ok", "blocked"}  # blocked still enumerable for cargo scheduling

    def _validate_tech_pick(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        hand_ids = {c["id"] for c in (view.get("own") or {}).get("hand") or []}
        return str((candidate.get("params") or {}).get("card_instance_id") or "") in hand_ids

    def _validate_diplomacy(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        target = str((candidate.get("params") or {}).get("target_faction") or "")
        return bool(target) and target != view.get("faction_id") and target in self.state.factions

    def _validate_trade(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        params = candidate.get("params") or {}
        target = str(params.get("target_faction") or "")
        return bool(target) and target != view.get("faction_id") and target in self.state.factions

    def _validate_military_move(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        params = candidate.get("params") or {}
        formation_id = str(params.get("formation_id") or "")
        formations = getattr(self.state, "formations", {}) or {}
        formation = formations.get(formation_id)
        if formation is None:
            return False
        if str(formation.get("faction_id")) != view.get("faction_id"):
            return False
        active = self.state.clock.get("active_faction_id")
        if active is not None and str(active) != view.get("faction_id"):
            return False
        path = list(params.get("path") or [])
        if len(path) > 2:
            return False
        return True

    def _validate_military_withdraw(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        params = candidate.get("params") or {}
        formation_id = str(params.get("formation_id") or "")
        formations = getattr(self.state, "formations", {}) or {}
        formation = formations.get(formation_id)
        return formation is not None and str(formation.get("faction_id")) == view.get("faction_id")

    def _military_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        from sim.dmb.military.formations import FormationDirector

        out: list[dict[str, Any]] = []
        active = self.state.clock.get("active_faction_id")
        if active is not None and str(active) != faction_id:
            return out
        director = FormationDirector(self.state)
        for formation_id, formation in sorted((getattr(self.state, "formations", {}) or {}).items()):
            if str(formation.get("faction_id")) != faction_id:
                continue
            for objective in director.legal_objectives(formation_id, active_faction_id=faction_id):
                out.append(
                    _candidate(
                        action_kind="military_move",
                        faction_id=faction_id,
                        params={
                            "formation_id": formation_id,
                            "path": list(objective["path"]),
                            "node_id": objective["node_id"],
                        },
                        legal_version=version,
                        benefit={"edges": objective["edges"]},
                        explanation="strategic formation move ≤2 edges",
                    )
                )
            if formation.get("withdrawal_status") == "pending":
                out.append(
                    _candidate(
                        action_kind="military_withdraw",
                        faction_id=faction_id,
                        params={"formation_id": formation_id},
                        legal_version=version,
                        explanation="execute pending withdrawal on activation",
                    )
                )
        return out

    def _validate_military_objective(self, view: dict[str, Any], candidate: dict[str, Any]) -> bool:
        params = candidate.get("params") or {}
        objective = str(params.get("objective") or "")
        if objective not in {"defend", "assemble", "attack", "hold"}:
            return False
        formation_id = str(params.get("formation_id") or "")
        formation = (getattr(self.state, "formations", {}) or {}).get(formation_id)
        return formation is not None and str(formation.get("faction_id")) == view.get("faction_id")

    def _military_objective_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """defend/assemble/attack/hold using only observed strength (no fog peeking)."""
        out: list[dict[str, Any]] = []
        knowledge = (view.get("knowledge") or view.get("observed") or {})
        observed_enemy_nodes = set(knowledge.get("enemy_military_nodes") or [])
        # Never include unobserved enemy strength figures in benefits.
        for formation_id, formation in sorted((getattr(self.state, "formations", {}) or {}).items()):
            if str(formation.get("faction_id")) != faction_id:
                continue
            node_id = str(formation.get("node_id"))
            out.append(
                _candidate(
                    action_kind="military_objective",
                    faction_id=faction_id,
                    params={"formation_id": formation_id, "objective": "hold", "node_id": node_id},
                    legal_version=version,
                    benefit={"own_strength": int(formation.get("derived_strength") or 0)},
                    explanation="hold position",
                )
            )
            out.append(
                _candidate(
                    action_kind="military_objective",
                    faction_id=faction_id,
                    params={"formation_id": formation_id, "objective": "defend", "node_id": node_id},
                    legal_version=version,
                    benefit={"own_strength": int(formation.get("derived_strength") or 0)},
                    explanation="defend settlement",
                )
            )
            out.append(
                _candidate(
                    action_kind="military_objective",
                    faction_id=faction_id,
                    params={"formation_id": formation_id, "objective": "assemble", "node_id": node_id},
                    legal_version=version,
                    explanation="assemble reinforcements",
                )
            )
            for enemy_node in sorted(observed_enemy_nodes):
                out.append(
                    _candidate(
                        action_kind="military_objective",
                        faction_id=faction_id,
                        params={
                            "formation_id": formation_id,
                            "objective": "attack",
                            "node_id": enemy_node,
                        },
                        legal_version=version,
                        benefit={"target_observed": True},
                        explanation="attack observed enemy",
                    )
                )
        return out

    def _construction_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        assert self.construction is not None
        out: list[dict[str, Any]] = []
        # Prefer faction settlement store.
        store_id = None
        for settlement in self.state.settlements.values():
            if settlement.get("faction_id") == faction_id:
                wh = settlement.get("warehouse_id")
                store_id = settlement.get("store_id") or (f"store:{wh}" if wh else None) or settlement.get("id")
                break
        if not store_id:
            store_id = f"{faction_id}:store"
            StockLedger(self.state)  # ensure ledger exists
            self.state.stocks.setdefault(store_id, {})

        # Settlement targets: empty adjacent-ish nodes owned connection later; enumerate board nodes.
        nodes = list((self.state.board.get("nodes") or {}).keys())
        for node_id in nodes[:16]:
            legal, reason = self.construction.placement.can_settle(faction_id, str(node_id))
            if not legal and reason != "ok":
                continue
            quote = self.construction.quote(
                "settlement", faction_id=faction_id, store_id=str(store_id), target_node=str(node_id)
            )
            out.append(
                _candidate(
                    action_kind="construct",
                    faction_id=faction_id,
                    params={
                        "action": "settlement",
                        "store_id": store_id,
                        "target_node": node_id,
                    },
                    legal_version=version,
                    cost=dict(quote.get("required") or COSTS["settlement"]),
                    benefit={"vp_gain": 1},
                    explanation=str(quote.get("reason") or reason or "settlement"),
                )
            )
            if len(out) >= 8:
                break

        # Road edges from owned roads / settlements.
        endpoints = set()
        for s in self.state.settlements.values():
            if s.get("faction_id") == faction_id and s.get("node_id"):
                endpoints.add(str(s["node_id"]))
        for r in self.state.roads.values():
            if r.get("faction_id") == faction_id:
                endpoints.add(str(r.get("a")))
                endpoints.add(str(r.get("b")))
        edge_count = 0
        for a in list(endpoints)[:8]:
            node = (self.state.board.get("nodes") or {}).get(a) or {}
            exits = node.get("exits", [])
            dests = list(exits.keys()) if isinstance(exits, dict) else list(exits)
            for b in dests[:4]:
                quote = self.construction.quote(
                    "road",
                    faction_id=faction_id,
                    store_id=str(store_id),
                    target_edge=(str(a), str(b)),
                )
                out.append(
                    _candidate(
                        action_kind="construct",
                        faction_id=faction_id,
                        params={
                            "action": "road",
                            "store_id": store_id,
                            "target_edge": [str(a), str(b)],
                        },
                        legal_version=version,
                        cost=dict(quote.get("required") or COSTS["road"]),
                        benefit={"road": 1},
                        explanation=str(quote.get("reason") or "road"),
                    )
                )
                edge_count += 1
                if edge_count >= 8:
                    break
            if edge_count >= 8:
                break
        return out

    def _tech_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        out = []
        for card in (view.get("own") or {}).get("hand") or []:
            out.append(
                _candidate(
                    action_kind="tech_pick",
                    faction_id=faction_id,
                    params={"card_instance_id": card["id"], "definition_id": card.get("definition_id")},
                    legal_version=version,
                    explanation="draft pick",
                )
            )
        return out

    def _diplomacy_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        out = []
        for other in sorted(self.state.factions):
            if other == faction_id:
                continue
            for kind in ("alliance", "embargo", "peace"):
                out.append(
                    _candidate(
                        action_kind="diplomacy_propose",
                        faction_id=faction_id,
                        params={"target_faction": other, "proposal": kind},
                        legal_version=version,
                        explanation=f"propose {kind}",
                    )
                )
        return out

    def _trade_candidates(
        self, faction_id: str, version: int, view: dict[str, Any]
    ) -> list[dict[str, Any]]:
        out = []
        goods = ("timber", "brick", "wool", "grain", "ore")
        for other in sorted(self.state.factions):
            if other == faction_id:
                continue
            # Bounded small set; T045 expands escrow.
            for give in goods[:2]:
                for recv in goods[:2]:
                    if give == recv:
                        continue
                    out.append(
                        _candidate(
                            action_kind="trade_propose",
                            faction_id=faction_id,
                            params={
                                "target_faction": other,
                                "give": {give: 1},
                                "receive": {recv: 1},
                            },
                            legal_version=version,
                            explanation="bilateral trade probe",
                        )
                    )
                    if len(out) >= 16:
                        return out
        return out
