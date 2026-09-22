"""Chronicle compaction with pinned live references (C11 / T128)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sim.dmb.history.chronicle import HistoryService, _bucket


@dataclass
class ChronicleCompaction:
    state: Any

    def compute_pins(self) -> dict[str, list[str]]:
        """Pin events referenced by live people, quests, items, relationships, legacy."""
        hist = _bucket(self.state)
        pins: dict[str, list[str]] = dict(hist.get("pins") or {})
        live_referents: list[str] = []
        for pid, person in (self.state.people or {}).items():
            if person.get("alive", True):
                live_referents.append(str(pid))
                for ref in person.get("history_refs") or []:
                    live_referents.append(str(ref))
        live_referents.extend(str(qid) for qid in (self.state.quests or {}))
        for item in (getattr(self.state, "items", {}) or {}).values():
            if isinstance(item, dict):
                live_referents.append(str(item.get("id") or ""))
        legacy = (self.state.board.get("legacy") or {})
        for bucket in ("relics", "scars", "contamination"):
            live_referents.extend(str(k) for k in (legacy.get(bucket) or {}))

        events = list(hist.get("events") or [])
        by_id = {e["id"]: e for e in events if isinstance(e, dict) and e.get("id")}
        for referent in live_referents:
            if not referent:
                continue
            for event in events:
                subjects = set(event.get("subject_ids") or []) | set(event.get("place_ids") or [])
                if referent in subjects or referent in (event.get("facts") or {}):
                    bucket = pins.setdefault(referent, [])
                    if event["id"] not in bucket:
                        bucket.append(event["id"])
            # Also keep quest source events.
            if referent in (self.state.quests or {}):
                quest = self.state.quests[referent]
                source = quest.get("source_event_id") or quest.get("history_event_id")
                if source and source in by_id:
                    bucket = pins.setdefault(referent, [])
                    if source not in bucket:
                        bucket.append(source)
        hist["pins"] = pins
        return pins

    def compact_retired(self, *, keep_recent: int = 50) -> dict[str, Any]:
        """Compact unpinned retired detail; pinned events remain resolvable."""
        hist = _bucket(self.state)
        pins = self.compute_pins()
        pinned_ids = {eid for ids in pins.values() for eid in ids}
        events = list(hist.get("events") or [])
        kept: list[dict[str, Any]] = []
        compacted: list[str] = []
        for event in events:
            eid = event.get("id")
            if eid in pinned_ids or event.get("kind") in {"cycle_reseed", "era_transition", "summary"}:
                kept.append(event)
                continue
            if event.get("retired") and eid not in pinned_ids:
                compacted.append(str(eid))
                continue
            kept.append(event)
        # Always retain trailing recent window.
        if len(kept) > keep_recent:
            head, tail = kept[:-keep_recent], kept[-keep_recent:]
            for event in head:
                if event.get("id") not in pinned_ids and event.get("kind") not in {
                    "cycle_reseed",
                    "era_transition",
                    "summary",
                }:
                    compacted.append(str(event.get("id")))
                else:
                    tail.insert(0, event)
            kept = tail
        if compacted:
            HistoryService(self.state).summarise_retired(compacted, summary=f"compacted:{len(compacted)}")
        hist["events"] = kept
        hist["compacted_count"] = int(hist.get("compacted_count") or 0) + len(compacted)
        return {"compacted": compacted, "kept": len(kept), "pins": pins}
