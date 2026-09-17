"""Simultaneous seven-round technology draft (C12 / T041)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.rng import RngBank
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.technology.definitions import TechnologyCatalog
from sim.dmb.technology.research import TechnologyService


def _empty_draft() -> dict[str, Any]:
    return {
        "era": None,
        "pick_index": 0,
        "hands": {},
        "seat_order": [],
        "active": False,
        "last_snapshot": None,
        "picks_this_cycle": 0,
    }


@dataclass
class DraftService:
    state: WorldState
    catalog: TechnologyCatalog = field(default_factory=TechnologyCatalog)
    research: TechnologyService | None = None
    rng: RngBank | None = None

    def __post_init__(self) -> None:
        if not self.catalog.ids:
            self.catalog.load()
        if self.research is None:
            self.research = TechnologyService(self.state, catalog=self.catalog)
        if self.rng is None:
            self.rng = RngBank.from_dict(self.state.rng) if self.state.rng else RngBank()
            self.rng.ensure("tech_draft", seed=self.state.rng.get("seed", 0) if self.state.rng else 0)

    def draft_state(self) -> dict[str, Any]:
        data = self.state.tech_draft
        if not isinstance(data, dict):
            self.state.tech_draft = _empty_draft()
            data = self.state.tech_draft
        for key, default in _empty_draft().items():
            if key not in data:
                data[key] = deepcopy(default) if not isinstance(default, (int, type(None), bool)) else default
        return data

    def _pool_ids(self, era: str) -> list[str]:
        return [d.id for d in self.catalog.pool_for_era(era)]

    def _draw_card(self, era: str) -> dict[str, Any]:
        assert self.research is not None and self.rng is not None
        pool = self._pool_ids(era)
        idx = self.rng.draw_int("tech_draft", 0, len(pool) - 1)
        definition_id = pool[idx]
        return self.research.make_card_instance(definition_id)

    def deal(self, era: str, seat_order: list[str]) -> dict[str, Any]:
        """Deal seven cards with replacement to each faction at era start / redeal."""
        if not seat_order:
            raise TypeValidationError("seat_order required")
        draft = self.draft_state()
        hands: dict[str, list[dict[str, Any]]] = {}
        for faction_id in seat_order:
            hands[faction_id] = [self._draw_card(era) for _ in range(7)]
        draft.update(
            {
                "era": era,
                "pick_index": 0,
                "hands": hands,
                "seat_order": list(seat_order),
                "active": True,
                "last_snapshot": None,
                "picks_this_cycle": 0,
            }
        )
        self._persist_rng()
        return deepcopy(draft)

    def _persist_rng(self) -> None:
        assert self.rng is not None
        self.state.rng = self.rng.to_dict()

    def collect_choices(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """
        Freeze a common pre-draft snapshot and return the choice request.
        Choices must be resolved against this snapshot's hand IDs.
        """
        draft = self.draft_state()
        if not draft.get("active"):
            raise TypeValidationError("no active draft")
        frozen = {
            "era": draft["era"],
            "pick_index": int(draft["pick_index"]),
            "seat_order": list(draft["seat_order"]),
            "hands": {
                fid: [{"id": c["id"], "definition_id": c["definition_id"]} for c in cards]
                for fid, cards in draft["hands"].items()
            },
            "view": deepcopy(snapshot),
        }
        draft["last_snapshot"] = frozen
        return frozen

    def resolve_round(self, choices: dict[str, str]) -> dict[str, Any]:
        """
        choices: faction_id -> card_instance_id selected from current hand.
        Acquire all chosen, activate eligible, pass remaining hands clockwise.
        After seventh pick, redeal seven immediately.
        """
        assert self.research is not None
        draft = self.draft_state()
        if not draft.get("active"):
            raise TypeValidationError("no active draft")
        snapshot = draft.get("last_snapshot")
        if snapshot is None:
            raise TypeValidationError("collect_choices required before resolve_round")
        seat_order: list[str] = list(draft["seat_order"])
        if set(choices) != set(seat_order):
            raise TypeValidationError("choices must cover every seated faction exactly once")

        acquired: list[dict[str, Any]] = []
        # Select against snapshot hand IDs (common pre-draft view).
        selected_cards: dict[str, dict[str, Any]] = {}
        for faction_id in seat_order:
            pick_id = str(choices[faction_id])
            snap_hand = snapshot["hands"][faction_id]
            if pick_id not in {c["id"] for c in snap_hand}:
                raise TypeValidationError(f"stale or illegal pick {pick_id} for {faction_id}")
            live_hand: list[dict[str, Any]] = list(draft["hands"][faction_id])
            match = next((c for c in live_hand if c["id"] == pick_id), None)
            if match is None:
                raise TypeValidationError(f"pick {pick_id} missing from live hand")
            selected_cards[faction_id] = match

        for faction_id in seat_order:
            card = selected_cards[faction_id]
            receipt = self.research.acquire(faction_id, card)
            acquired.append(receipt)
            # Remove from hand before pass.
            draft["hands"][faction_id] = [c for c in draft["hands"][faction_id] if c["id"] != card["id"]]

        activations: dict[str, list[dict[str, Any]]] = {}
        for faction_id in seat_order:
            activations[faction_id] = self.research.activate_eligible(faction_id)

        # Pass remaining hands clockwise in stable seat order.
        if seat_order:
            old_hands = {fid: list(draft["hands"][fid]) for fid in seat_order}
            new_hands: dict[str, list[dict[str, Any]]] = {}
            n = len(seat_order)
            for i, faction_id in enumerate(seat_order):
                donor = seat_order[(i - 1) % n]  # receive from previous seat (clockwise pass)
                new_hands[faction_id] = old_hands[donor]
            draft["hands"] = new_hands

        draft["pick_index"] = int(draft["pick_index"]) + 1
        draft["picks_this_cycle"] = int(draft.get("picks_this_cycle", 0)) + 1
        draft["last_snapshot"] = None
        redealt = False
        if int(draft["pick_index"]) >= 7:
            self.deal(str(draft["era"]), seat_order)
            redealt = True
            draft = self.draft_state()
        self._persist_rng()
        return {
            "acquired": acquired,
            "activations": activations,
            "pick_index": int(draft["pick_index"]),
            "hands": {fid: [c["id"] for c in cards] for fid, cards in draft["hands"].items()},
            "hand_sizes": {fid: len(cards) for fid, cards in draft["hands"].items()},
            "redealt": redealt,
            "owned_counts": {
                fid: len(self.research.research_of(fid)["owned"]) for fid in seat_order
            },
        }

    def discard_for_era(self, reason: str = "era_interrupt") -> dict[str, Any]:
        """Era interruption discards remaining hands without old-era picks."""
        draft = self.draft_state()
        discarded = {
            fid: [c["id"] for c in cards] for fid, cards in dict(draft.get("hands") or {}).items()
        }
        draft.update(_empty_draft())
        draft["last_discard_reason"] = reason
        return {"discarded": discarded, "reason": reason}

    def auto_pick_first(self) -> dict[str, str]:
        """Deterministic helper: each faction picks the first card in hand order."""
        draft = self.draft_state()
        return {fid: cards[0]["id"] for fid, cards in draft["hands"].items() if cards}
