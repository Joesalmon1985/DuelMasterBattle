"""Candidate generation for the nine action heads (execution plan T2.3, design 4.4 and 4.5).

Scoring is learned (M3), candidate generation is mechanical: for each head this module lists the concrete commands the faction could issue now, each as the exact
payload `HybridEnv.apply` takes, plus the raw features of that candidate (widths in neuro/schema.py HEAD_RAW) and `refs`, the pointers into the `Observation` that
tell M3 which network outputs to gather for it (which settlement, which building rows, which squad, which offer, ...).

    H1 build         (kind, site) pairs per settlement          H6 draft       the open offers
    H2 roads/links   unconnected buildings, settlement links,   H7 trade/aid   (partner warehouse, give group, want group)
                     belts                                       H8 diplomacy   propose / accept / decline / break
    H3 produce       (factory, unit kind)                       H9 manage      demolish, dismantle, enhance, upgrade, convert
    H4 expand        (founder, site), deploy where it stands
    H5 military      (squad, target): enemy buildings, nests, defend, rally

RULES. The simulator is authoritative: nothing here changes the world, and a rejected candidate teaches the generator nothing (the controller reports it with
`note_rejection` and the key is withheld for 60 game seconds, nothing more). Candidates are built from the Observation and the faction's own state only, so they
cannot reveal what the faction has not seen: targets come from the visibility memory, trade partners from remembered or allied warehouses, expansion sites from
explored ground. Where a command depends on something hidden (a trade partner's stock, an enemy centre near a founding site) the candidate is offered anyway and
the simulator decides; those heads therefore have a lower acceptance rate by design. Where legality can be checked from the faction's own knowledge
(`check_placement` of a building, a unit's recipe, a road's endpoints) the candidate is checked before it is offered.
"""
from __future__ import annotations

from typing import Any

from neuro.cand_base import EXCLUDE_S, HEADS, Candidate, feat  # noqa: F401  (re-exported)
from neuro.cand_economy import EconomyCandidates
from neuro.cand_extra import ExtraCandidates
from neuro.cand_sites import SiteCandidates
from neuro.cand_war import WarCandidates
from neuro.observer import FactionObserver, Observation


class CandidateGenerator(SiteCandidates, EconomyCandidates, WarCandidates, ExtraCandidates):
    """Candidates of one faction. Use with the faction's FactionObserver: `gen.all(obs)` after `obs = observer.observe(game_s)`."""

    def __init__(self, env: Any, faction: str, observer: FactionObserver | None = None) -> None:
        self.env = env
        self.world = env.world if hasattr(env, "world") else env
        self.faction = faction
        self.observer = observer or FactionObserver(self.world, faction)
        self.excluded: dict[tuple, int] = {}
        self.rejections: dict[str, int] = {}
        self._site_cache: dict[tuple, tuple[int, list]] = {}
        self._kind_sig: tuple | None = None
        self._kinds: list[str] = []
        self.timings: dict[str, float] = {}

    # ------------------------------------------------------------------------------------------------------------------------ bookkeeping
    def on_events(self, events: list[dict]) -> None:
        self.observer.on_events(events)

    def note_rejection(self, cand: Candidate, reason: str, game_s: int) -> None:
        """The simulator refused this candidate: withhold its key for EXCLUDE_S game seconds (no learning, no heuristics)."""
        self.excluded[cand.key] = game_s + EXCLUDE_S
        self.rejections[reason] = self.rejections.get(reason, 0) + 1

    def _fresh(self, cands: list[Candidate], game_s: int) -> list[Candidate]:
        for k in [k for k, until in self.excluded.items() if until <= game_s]:
            del self.excluded[k]
        return [c for c in cands if c.key not in self.excluded]

    # ------------------------------------------------------------------------------------------------------------------------ all heads
    def all(self, obs: Observation | None = None, game_s: int | None = None) -> dict[str, list[Candidate]]:
        """Every head's candidates for this decision. Without `obs`, the generator observes first."""
        if obs is None:
            obs = self.observer.observe(int(game_s if game_s is not None else self.world.dmb.clock.get("game_ms", 0) // 1000))
        out = {
            "H1": self.build(obs), "H2": self.road(obs), "H3": self.produce(obs), "H4": self.expand(obs), "H5": self.military(obs),
            "H6": self.draft(obs), "H7": self.trade(obs), "H8": self.diplomacy(obs), "H9": self.manage(obs),
        }
        return {h: self._fresh(c, obs.game_s) for h, c in out.items()}
