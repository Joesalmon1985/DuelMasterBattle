"""Quest state machine and invalidation (C10 / T083)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.effects import apply_effects
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

QUEST_STATUSES = (
    "offered",
    "active",
    "suspended",
    "completed",
    "resolved_by_world",
    "failed_with_consequence",
)

ALLOWED_TRANSITIONS = {
    "offered": {"active", "resolved_by_world", "failed_with_consequence", "suspended"},
    "active": {"suspended", "completed", "resolved_by_world", "failed_with_consequence"},
    "suspended": {"active", "completed", "resolved_by_world", "failed_with_consequence"},
    "completed": set(),
    "resolved_by_world": set(),
    "failed_with_consequence": set(),
}

RUNTIME_SCHEMA_VERSION = 1


@dataclass
class QuestService:
    state: WorldState

    def get(self, quest_id: str) -> dict[str, Any]:
        quest = self.state.quests.get(quest_id)
        if quest is None:
            raise TypeValidationError(f"unknown quest {quest_id}")
        return quest

    def offer(self, quest_id: str) -> dict[str, Any]:
        quest = self.get(quest_id)
        quest["status"] = "offered"
        quest.setdefault("schema_version", RUNTIME_SCHEMA_VERSION)
        return dict(quest)

    def accept(self, quest_id: str) -> dict[str, Any]:
        return self._transition(quest_id, "active")

    def suspend(self, quest_id: str, *, reason: str) -> dict[str, Any]:
        quest = self._transition(quest_id, "suspended")
        self.state.quests[quest_id]["suspend_reason"] = reason
        return dict(self.state.quests[quest_id])

    def choose_branch(
        self,
        quest_id: str,
        branch_id: str,
        *,
        effects: list[dict[str, Any]] | None = None,
        choice_id: str | None = None,
    ) -> dict[str, Any]:
        quest = self.get(quest_id)
        if quest.get("status") not in {"offered", "active", "suspended"}:
            raise TypeValidationError("quest not choosable")
        # Simultaneous choices reward once via choice_id / effect_id receipts.
        choice_key = choice_id or f"{quest_id}:{branch_id}"
        receipts = list(quest.get("effect_receipts") or [])
        if choice_key in receipts:
            return {"status": "idempotent", "quest": dict(quest), "choice_id": choice_key}
        applied = {"ok": True, "applied": []}
        if effects:
            applied = apply_effects(self.state, effects)
            if not applied.get("ok"):
                return {"status": "aborted", "quest": dict(quest), "effects": applied}
        quest["branch"] = branch_id
        receipts.append(choice_key)
        quest["effect_receipts"] = receipts
        if applied.get("applied"):
            for item in applied["applied"]:
                eid = item.get("effect_id")
                if eid and eid not in quest["effect_receipts"]:
                    quest["effect_receipts"].append(eid)
        return {"status": "chosen", "quest": dict(quest), "effects": applied}

    def evaluate(self, quest_id: str, *, world_signals: dict[str, Any] | None = None) -> dict[str, Any]:
        """Advance/invalidate from world signals. Era flag alone never completes/cancels."""
        quest = self.get(quest_id)
        signals = dict(world_signals or {})
        # Era flag alone is insufficient.
        if set(signals.keys()) <= {"era_id", "era_flag", "full_cycle"}:
            return {"status": "unchanged", "quest": dict(quest), "reason": "era_flag_alone"}

        if signals.get("world_repaired") or signals.get("cause_cleared_by_world"):
            if quest.get("status") in {"offered", "active", "suspended"}:
                self._transition(quest_id, "resolved_by_world")
                self.state.quests[quest_id]["resolution"] = "world_fix_first"
                return {"status": "resolved_by_world", "quest": dict(self.state.quests[quest_id])}

        if signals.get("target_destroyed") or signals.get("site_destroyed"):
            branch = (quest.get("invalid_target_branch") or signals.get("declared_branch") or "loss")
            if quest.get("status") in {"offered", "active", "suspended"}:
                self._transition(quest_id, "failed_with_consequence")
                self.state.quests[quest_id]["branch"] = branch
                self.state.quests[quest_id]["resolution"] = "target_destroyed"
                return {"status": "failed_with_consequence", "quest": dict(self.state.quests[quest_id])}

        if signals.get("stakeholder_dead"):
            if quest.get("status") in {"offered", "active"}:
                self.suspend(quest_id, reason="stakeholder_dead")
                return {"status": "suspended", "quest": dict(self.state.quests[quest_id])}

        if signals.get("output_confirmed") and signals.get("intervention"):
            if quest.get("status") in {"active", "suspended"}:
                self._transition(quest_id, "completed")
                self.state.quests[quest_id]["resolution"] = signals.get("intervention")
                return {"status": "completed", "quest": dict(self.state.quests[quest_id])}

        if signals.get("advance_stage") is not None:
            stage = int(signals["advance_stage"])
            stages = int(quest.get("stage_count") or 4)
            if stage < 0 or stage >= stages:
                raise TypeValidationError("stage out of graph range")
            quest["stage"] = stage
            if quest.get("status") == "offered" and stage > 0:
                self._transition(quest_id, "active")
            return {"status": "stage", "quest": dict(quest)}

        return {"status": "unchanged", "quest": dict(quest)}

    def apply_outcome(self, quest_id: str, outcome: str, *, effects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if outcome not in {"completed", "resolved_by_world", "failed_with_consequence"}:
            raise TypeValidationError(f"invalid outcome {outcome}")
        if effects:
            applied = apply_effects(self.state, effects)
            if not applied.get("ok"):
                return {"status": "aborted", "effects": applied}
        quest = self._transition(quest_id, outcome)
        return {"status": outcome, "quest": quest}

    def _transition(self, quest_id: str, to_status: str) -> dict[str, Any]:
        quest = self.get(quest_id)
        current = str(quest.get("status") or "offered")
        if to_status == current:
            return dict(quest)
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if to_status not in allowed:
            raise TypeValidationError(f"illegal transition {current} -> {to_status}")
        quest["status"] = to_status
        return dict(quest)
