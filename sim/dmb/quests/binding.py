"""Quest binding to real causes and living stakeholders (C10 / T082)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.quests.causes import CauseTracker


BINDING_SCHEMA_VERSION = 1


@dataclass
class QuestBinder:
    state: WorldState
    causes: CauseTracker | None = None

    def __post_init__(self) -> None:
        if self.causes is None:
            self.causes = CauseTracker(self.state)

    def _templates(self) -> dict[str, Any]:
        return self.state.definitions.setdefault("quest_templates", {})

    def register_template(self, template: dict[str, Any]) -> dict[str, Any]:
        tid = str(template.get("id") or "")
        if not tid:
            raise TypeValidationError("template requires id")
        record = deepcopy(template)
        record.setdefault("schema_version", BINDING_SCHEMA_VERSION)
        self._templates()[tid] = record
        return dict(record)

    def eligible_templates(self, cause: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cause_kind = str(cause.get("cause_kind") or "")
        for template in self._templates().values():
            pred = template.get("required_cause") or template.get("required_cause_predicate") or {}
            kinds = pred.get("kinds") or pred.get("cause_kinds") or []
            if kinds and cause_kind not in kinds:
                continue
            if pred.get("cause_kind") and pred.get("cause_kind") != cause_kind:
                continue
            out.append(dict(template))
        return out

    def bind(self, template: dict[str, Any] | str, cause: dict[str, Any] | str) -> dict[str, Any]:
        """Bind template+cause to a QuestInstance without fabricating dead stakeholders."""
        if isinstance(template, str):
            template = self._templates().get(template) or {}
        if isinstance(cause, str):
            assert self.causes is not None
            found = self.causes.get(cause)
            if found is None:
                raise TypeValidationError(f"unknown cause {cause}")
            cause = found
        if not template or not cause:
            raise TypeValidationError("bind requires template and cause")
        template_id = str(template["id"])
        cause_id = str(cause["id"])
        affected = str(cause.get("affected_entity_id") or "")

        # Dedupe active quest by template/cause/affected.
        for quest in self.state.quests.values():
            if (
                quest.get("template_id") == template_id
                and quest.get("cause_id") == cause_id
                and quest.get("affected_entity_id") == affected
                and quest.get("status") in {"offered", "active", "suspended"}
            ):
                return {"status": "deduped", "quest": dict(quest)}

        stakeholder_id = cause.get("stakeholder_id") or self._resolve_stakeholder(template, cause)
        if stakeholder_id:
            person = self.state.people.get(str(stakeholder_id))
            if person is None or not person.get("alive", True) or person.get("status") == "dead":
                raise TypeValidationError(
                    "missing stakeholder cannot be fabricated as the same dead person"
                )

        site_id = cause.get("site_id") or (template.get("binding") or {}).get("site_id")
        quest_id = self.state.ids.new("quest")
        instance = {
            "id": quest_id,
            "schema_version": BINDING_SCHEMA_VERSION,
            "template_id": template_id,
            "template_version": template.get("version", 1),
            "cause_id": cause_id,
            "occurrence_key": cause.get("occurrence_key"),
            "affected_entity_id": affected,
            "stakeholder_id": stakeholder_id,
            "site_id": site_id,
            "status": "offered",
            "stage": 0,
            "branch": None,
            "bindings": {
                "stakeholder_id": stakeholder_id,
                "site_id": site_id,
                "affected_entity_id": affected,
            },
            "effect_receipts": [],
            "history_refs": [],
        }
        self.state.quests[quest_id] = instance
        return {"status": "bound", "quest": dict(instance)}

    def _resolve_stakeholder(self, template: dict[str, Any], cause: dict[str, Any]) -> str | None:
        binding = template.get("binding") or {}
        explicit = binding.get("stakeholder_id") or cause.get("stakeholder_id")
        if explicit:
            return str(explicit)
        role = binding.get("stakeholder_role")
        workplace = cause.get("affected_entity_id")
        if role or workplace:
            for person_id, person in self.state.people.items():
                if not person.get("alive", True):
                    continue
                if workplace and person.get("workplace_id") == workplace:
                    return person_id
                if role and person.get("role") == role:
                    return person_id
        return None
