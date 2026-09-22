"""Persistent cause detection (C10 / T082).

Stable occurrence IDs — not one ID per visit. Dedupe by template/cause/
affected entity while the occurrence is active.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from sim.dmb.core.state import WorldState


CAUSE_SCHEMA_VERSION = 1


def _occurrence_key(template_id: str, cause_kind: str, affected_entity_id: str) -> str:
    material = f"{template_id}|{cause_kind}|{affected_entity_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"causeocc:{digest}"


@dataclass
class CauseTracker:
    state: WorldState

    def _store(self) -> dict[str, Any]:
        causes = self.state.definitions.setdefault("causes", {})
        causes.setdefault("schema_version", CAUSE_SCHEMA_VERSION)
        causes.setdefault("active", {})
        causes.setdefault("resolved", {})
        causes.setdefault("index", {})  # occurrence_key -> cause_id
        return causes

    def active_causes(self) -> list[dict[str, Any]]:
        store = self._store()
        return [dict(v) for v in store["active"].values() if v.get("active")]

    def observe_changes(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ingest real world events; return newly created or refreshed causes."""
        created: list[dict[str, Any]] = []
        for event in events:
            out = self._observe_one(dict(event))
            if out is not None:
                created.append(out)
        return created

    def _observe_one(self, event: dict[str, Any]) -> dict[str, Any] | None:
        kind = str(event.get("kind") or event.get("cause_kind") or "")
        if not kind:
            return None
        affected = str(event.get("affected_entity_id") or event.get("entity_id") or "")
        template_id = str(event.get("template_id") or f"template.{kind}")
        if not affected:
            return None
        store = self._store()
        key = _occurrence_key(template_id, kind, affected)
        existing_id = store["index"].get(key)
        if existing_id and existing_id in store["active"] and store["active"][existing_id].get("active"):
            # Same template/cause/affected while active → no duplicate.
            rec = store["active"][existing_id]
            rec["last_event"] = deepcopy(event)
            return {"status": "deduped", "cause": dict(rec)}

        # New occurrence after prior resolution gets a fresh cause ID.
        cause_id = self.state.ids.new("cause")
        record = {
            "id": cause_id,
            "occurrence_key": key,
            "template_id": template_id,
            "cause_kind": kind,
            "affected_entity_id": affected,
            "stakeholder_id": event.get("stakeholder_id"),
            "site_id": event.get("site_id"),
            "active": True,
            "event": deepcopy(event),
            "created_game_ms": int((self.state.clock or {}).get("game_ms") or 0),
        }
        store["active"][cause_id] = record
        store["index"][key] = cause_id
        return {"status": "created", "cause": dict(record)}

    def resolve(self, cause_id: str, *, reason: str = "resolved") -> dict[str, Any]:
        store = self._store()
        rec = store["active"].get(cause_id)
        if rec is None:
            return {"status": "missing", "cause_id": cause_id}
        rec = dict(rec)
        rec["active"] = False
        rec["resolved_reason"] = reason
        store["active"].pop(cause_id, None)
        store["resolved"][cause_id] = rec
        # Keep index pointing at resolved id until a new occurrence replaces it.
        return {"status": "resolved", "cause": rec}

    def get(self, cause_id: str) -> dict[str, Any] | None:
        store = self._store()
        if cause_id in store["active"]:
            return dict(store["active"][cause_id])
        if cause_id in store["resolved"]:
            return dict(store["resolved"][cause_id])
        return None
