"""Diplomacy relations, proposals and transit permissions (C12 / T044)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

# Default: neutral and trade-permitted.
REL_NEUTRAL = "neutral"
REL_WAR = "war"
REL_ALLIANCE = "alliance"
REL_EMBARGO = "embargo"


def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


@dataclass
class DiplomacyService:
    state: WorldState

    def _store(self) -> dict[str, Any]:
        bucket = self.state.diplomacy
        if not isinstance(bucket, dict):
            self.state.diplomacy = {"relations": {}, "proposals": {}, "history": []}
            bucket = self.state.diplomacy
        bucket.setdefault("relations", {})
        bucket.setdefault("proposals", {})
        bucket.setdefault("history", [])
        return bucket

    def relation(self, a: str, b: str) -> str:
        if a == b:
            return REL_ALLIANCE
        key = _pair_key(a, b)
        entry = self._store()["relations"].get(key)
        if not entry:
            return REL_NEUTRAL
        return str(entry.get("status") or REL_NEUTRAL)

    def trade_permitted(self, a: str, b: str) -> bool:
        rel = self.relation(a, b)
        return rel not in {REL_WAR, REL_EMBARGO}

    def transit_permitted(self, traveler: str, road_owner: str) -> bool:
        if traveler == road_owner:
            return True
        if road_owner in {None, "shared"}:
            return True
        rel = self.relation(traveler, str(road_owner))
        if rel == REL_ALLIANCE:
            return True
        if rel in {REL_WAR, REL_EMBARGO}:
            return False
        # Neutral default: own/shared only (no foreign transit without alliance).
        return False

    def declare_war(self, attacker: str, defender: str, *, cause: str = "attack") -> dict[str, Any]:
        """Attack establishes war."""
        return self._set_relation(attacker, defender, REL_WAR, cause=cause)

    def set_embargo(self, a: str, b: str) -> dict[str, Any]:
        return self._set_relation(a, b, REL_EMBARGO, cause="embargo")

    def _set_relation(self, a: str, b: str, status: str, *, cause: str) -> dict[str, Any]:
        store = self._store()
        key = _pair_key(a, b)
        prev = deepcopy(store["relations"].get(key))
        entry = {
            "a": a,
            "b": b,
            "status": status,
            "cause": cause,
            "turn": int(self.state.clock.get("turn", 0)),
        }
        store["relations"][key] = entry
        store["history"].append({"kind": "relation", "previous": prev, "current": deepcopy(entry)})
        # Mirror onto faction records for observations.
        for fid, other in ((a, b), (b, a)):
            faction = self.state.factions.setdefault(fid, {"id": fid})
            relations = faction.setdefault("relations", {})
            relations[other] = status
        return entry

    def propose(
        self,
        proposer: str,
        target: str,
        proposal: str,
        *,
        proposal_id: str | None = None,
    ) -> dict[str, Any]:
        store = self._store()
        pid = proposal_id or f"proposal:{proposer}:{target}:{proposal}:{len(store['proposals'])}"
        if pid in store["proposals"]:
            # Duplicate proposal id → one effect only (return existing).
            return deepcopy(store["proposals"][pid])
        # Content-duplicate: same proposer/target/kind still open → reuse.
        for existing in store["proposals"].values():
            if (
                existing.get("proposer") == proposer
                and existing.get("target") == target
                and existing.get("proposal") == proposal
                and existing.get("status") == "pending"
            ):
                return deepcopy(existing)
        record = {
            "id": pid,
            "proposer": proposer,
            "target": target,
            "proposal": proposal,
            "status": "pending",
            "turn": int(self.state.clock.get("turn", 0)),
        }
        store["proposals"][pid] = record
        store["history"].append({"kind": "propose", "proposal": deepcopy(record)})
        return deepcopy(record)

    def respond(self, proposal_id: str, *, accept: bool) -> dict[str, Any]:
        store = self._store()
        prop = store["proposals"].get(proposal_id)
        if prop is None:
            raise TypeValidationError(f"unknown proposal {proposal_id}")
        if prop.get("status") != "pending":
            # Duplicate response — one relationship effect already applied.
            return deepcopy(prop)
        prop["status"] = "accepted" if accept else "rejected"
        if accept and prop.get("proposal") == "alliance":
            self._set_relation(prop["proposer"], prop["target"], REL_ALLIANCE, cause="alliance_accepted")
        elif accept and prop.get("proposal") == "embargo":
            self._set_relation(prop["proposer"], prop["target"], REL_EMBARGO, cause="embargo_accepted")
        elif accept and prop.get("proposal") == "peace":
            self._set_relation(prop["proposer"], prop["target"], REL_NEUTRAL, cause="peace_accepted")
        store["history"].append({"kind": "respond", "proposal": deepcopy(prop)})
        return deepcopy(prop)

    def accept_alliance_if_common_threat(self, a: str, b: str, observed_hostiles: set[str]) -> dict[str, Any] | None:
        """Alliance accepted when both share an observed hostile and no conflicting commitment."""
        if not observed_hostiles:
            return None
        if self.relation(a, b) in {REL_WAR, REL_EMBARGO}:
            return None
        prop = self.propose(a, b, "alliance")
        return self.respond(prop["id"], accept=True)
