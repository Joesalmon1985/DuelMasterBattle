"""Hazard deck draw/discard (C08 / T069)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.core.rng import RngBank


class HazardDeck:
    def __init__(self, state: Any, *, hex_ids: list[str] | None = None, stream: str = "catastrophe"):
        self.state = state
        self.stream = stream
        cat = state.hazards.setdefault(
            "catastrophe",
            {
                "deck": [],
                "discard": [],
                "cursor": 0,
                "era_outbreaks": 0,
                "lifetime_outbreaks": 0,
                "placement_ordinal": 0,
                "era_start_turn": int(state.clock.get("turn", 0)),
                "draws_this_era": 0,
                "cubes": {},
                "propagation_event_id": None,
                "visited_outbreaks": [],
            },
        )
        cat.setdefault("deck", [])
        cat.setdefault("discard", [])
        cat.setdefault("cubes", {})
        cat.setdefault("visited_outbreaks", [])
        cat.setdefault("era_outbreaks", 0)
        cat.setdefault("lifetime_outbreaks", 0)
        cat.setdefault("placement_ordinal", 0)
        cat.setdefault("cursor", 0)
        if hex_ids is not None and not cat.get("deck") and not cat.get("discard"):
            rng = RngBank.from_dict(state.rng) if state.rng else RngBank()
            order = list(hex_ids)
            cat["deck"] = rng.shuffle(self.stream, order)
            state.rng = rng.to_dict()

    @property
    def data(self) -> dict[str, Any]:
        return self.state.hazards["catastrophe"]

    def draw(self, count: int) -> list[str]:
        cat = self.data
        drawn: list[str] = []
        for _ in range(int(count)):
            if not cat["deck"]:
                self._reshuffle()
            if not cat["deck"]:
                break
            drawn.append(cat["deck"].pop(0))
        cat["cursor"] = int(cat.get("cursor", 0)) + len(drawn)
        return drawn

    def discard(self, hex_ids: list[str]) -> None:
        self.data["discard"].extend(list(hex_ids))

    def _reshuffle(self) -> None:
        cat = self.data
        if not cat["discard"]:
            return
        rng = RngBank.from_dict(self.state.rng) if self.state.rng else RngBank()
        order = list(cat["discard"])
        cat["discard"] = []
        cat["deck"] = rng.shuffle(self.stream, order)
        self.state.rng = rng.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.data)
