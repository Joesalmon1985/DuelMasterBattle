"""Chronicle / HistoryService — factual era events with knowledge filtering (C11 / T105)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _bucket(state: Any) -> dict[str, Any]:
    hist = state.board.setdefault("history", {})
    if not isinstance(hist, dict):
        hist = {}
        state.board["history"] = hist
    events = hist.setdefault("events", [])
    if not isinstance(events, list):
        hist["events"] = []
        events = hist["events"]
    hist.setdefault("schema_version", 1)
    hist.setdefault("pins", {})
    return hist


@dataclass
class HistoryService:
    state: Any

    def record(
        self,
        *,
        kind: str,
        subject_ids: Sequence[str] | None = None,
        place_ids: Sequence[str] | None = None,
        cause_ids: Sequence[str] | None = None,
        parent_ids: Sequence[str] | None = None,
        summary: str,
        facts: Mapping[str, Any] | None = None,
        public: bool = True,
        knowledge_keys: Sequence[str] | None = None,
        transition_id: str | None = None,
    ) -> dict[str, Any]:
        hist = _bucket(self.state)
        event_id = self.state.ids.new("history")
        entry = {
            "id": event_id,
            "kind": kind,
            "summary": summary,
            "subject_ids": list(subject_ids or []),
            "place_ids": list(place_ids or []),
            "cause_ids": list(cause_ids or []),
            "parent_ids": list(parent_ids or []),
            "facts": dict(facts or {}),
            "public": bool(public),
            "knowledge_keys": list(knowledge_keys or []),
            "transition_id": transition_id,
            "turn": int(self.state.clock.get("turn") or 0),
            "game_ms": int(self.state.clock.get("game_ms") or 0),
            "era": str(self.state.clock.get("era") or self.state.board.get("era_id") or ""),
        }
        hist["events"].append(entry)
        return dict(entry)

    def pin_live_reference(self, referent_id: str, event_id: str) -> None:
        hist = _bucket(self.state)
        pins = hist.setdefault("pins", {})
        bucket = pins.setdefault(str(referent_id), [])
        if event_id not in bucket:
            bucket.append(event_id)

    def summarise_retired(self, event_ids: Sequence[str], *, summary: str) -> dict[str, Any]:
        return self.record(
            kind="summary",
            summary=summary,
            parent_ids=list(event_ids),
            public=True,
            facts={"retired_ids": list(event_ids)},
        )

    def query_known_history(self, *, debug: bool = False, viewer_id: str | None = None) -> list[dict[str, Any]]:
        """Player view respects knowledge; debug/developer sees all."""
        hist = _bucket(self.state)
        events = list(hist.get("events") or [])
        if debug:
            return [deepcopy(e) for e in events]
        known = set()
        knowledge = self.state.knowledge or {}
        # Known keys from player knowledge map + any revealed entity ids.
        for key, row in knowledge.items():
            known.add(str(key))
            if isinstance(row, dict):
                for sub in row.get("known_facts") or []:
                    known.add(str(sub))
        if viewer_id:
            known.add(str(viewer_id))
        out: list[dict[str, Any]] = []
        for event in events:
            if not event.get("public", True):
                continue
            keys = list(event.get("knowledge_keys") or [])
            if keys and not any(k in known for k in keys):
                # Also allow if any subject is known.
                subjects = list(event.get("subject_ids") or [])
                if not any(s in known for s in subjects):
                    continue
            out.append(deepcopy(event))
        return out

    def record_transition_receipt(self, receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Emit factual Chronicle rows from a committed era transition receipt."""
        tid = str(receipt.get("transition_id") or "")
        winner = str(receipt.get("winner_faction_id") or "")
        recorded: list[dict[str, Any]] = []
        recorded.append(
            self.record(
                kind="vp_threshold",
                subject_ids=[winner] if winner else [],
                summary=f"{winner or 'A faction'} reached 10 VP",
                facts={"winner_faction_id": winner, "next_era": receipt.get("next_era")},
                knowledge_keys=[winner] if winner else [],
                transition_id=tid,
                public=True,
            )
        )
        collapse = receipt.get("collapse") or {}
        collapsed_ids: list[str] = []
        if isinstance(collapse, dict):
            for row in collapse.get("collapsed") or []:
                if isinstance(row, dict) and row.get("faction_id"):
                    collapsed_ids.append(str(row["faction_id"]))
            for fid in collapse.get("collapsed_faction_ids") or []:
                collapsed_ids.append(str(fid))
        for fid in collapsed_ids:
            recorded.append(
                self.record(
                    kind="faction_collapsed",
                    subject_ids=[str(fid)],
                    summary=f"{fid} collapsed at era change",
                    facts={"faction_id": fid},
                    knowledge_keys=[str(fid)],
                    transition_id=tid,
                    parent_ids=[recorded[0]["id"]],
                )
            )
        for row in receipt.get("fission") or []:
            if not isinstance(row, dict):
                continue
            recorded.append(
                self.record(
                    kind="faction_fission",
                    subject_ids=list(row.get("successor_faction_ids") or []),
                    summary="Successor factions created",
                    facts=dict(row),
                    transition_id=tid,
                    parent_ids=[recorded[0]["id"]],
                )
            )
        for sid in receipt.get("core_settlement_ids") or []:
            recorded.append(
                self.record(
                    kind="historic_core",
                    subject_ids=[str(sid)],
                    place_ids=[str(sid)],
                    summary=f"{sid} chosen as Historic core",
                    facts={"settlement_id": sid},
                    knowledge_keys=[str(sid)],
                    transition_id=tid,
                    parent_ids=[recorded[0]["id"]],
                )
            )
        for sid in receipt.get("legacy_settlement_ids") or []:
            recorded.append(
                self.record(
                    kind="legacy_site",
                    subject_ids=[str(sid)],
                    place_ids=[str(sid)],
                    summary=f"{sid} retained as Prehistoric legacy site",
                    facts={"settlement_id": sid},
                    knowledge_keys=[str(sid)],
                    transition_id=tid,
                    parent_ids=[recorded[0]["id"]],
                )
            )
        continuity = receipt.get("continuity") or {}
        cont_receipt = continuity.get("receipt") if isinstance(continuity, dict) else None
        if not isinstance(cont_receipt, dict):
            cont_receipt = continuity if isinstance(continuity, dict) else {}
        displaced_ids = list(cont_receipt.get("displaced_person_ids") or [])
        if not displaced_ids:
            for row in cont_receipt.get("person_adaptations") or []:
                if isinstance(row, dict) and row.get("action") in {"displaced", "workplace_lost", "faction_collapsed"}:
                    displaced_ids.append(str(row.get("person_id")))
        for person_id in displaced_ids:
            recorded.append(
                self.record(
                    kind="person_displaced",
                    subject_ids=[str(person_id)],
                    summary=f"{person_id} displaced by era change",
                    facts={"person_id": person_id},
                    knowledge_keys=[str(person_id)],
                    transition_id=tid,
                    parent_ids=[recorded[0]["id"]],
                )
            )
            self.pin_live_reference(str(person_id), recorded[-1]["id"])
        return recorded
