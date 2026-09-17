"""Shared writer/audit policies referenced by scene manifests.

These are global rules. Scene manifests should cite them by id rather than
duplicating the same sentences across hundreds of scenes.
"""

from __future__ import annotations

WRITER_POLICIES: dict[str, str] = {
    "POLICY_KNOWLEDGE_BOUNDARY": (
        "No character may state knowledge outside their compiled knowledge boundary."
    ),
    "POLICY_ALLOWLISTED_EFFECTS": (
        "Do not add arbitrary script effects; outcomes must use allowlisted effect types."
    ),
    "POLICY_PRIVATE_FACT_REVEAL": (
        "Private facts may create subtext. They become spoken canon only when the "
        "manifest explicitly permits revelation or a validated effect has already exposed them."
    ),
    "POLICY_NO_QUEST_RESOLUTION_IN_INTRO": (
        "Do not resolve the character's principal quest or central contradiction in an introduction."
    ),
    "POLICY_RELATIONSHIP_NOT_EXPOSITION": (
        "At least one line or action must reveal relationship, attitude or pressure rather than pure exposition."
    ),
    "POLICY_HOUSE_ORDINARY_LIFE": (
        "A house scene should reveal at least one ordinary-life detail, one relationship, "
        "and one actionable affordance before or alongside any quest objective."
    ),
}

DEFAULT_POLICY_REFS = [
    "POLICY_KNOWLEDGE_BOUNDARY",
    "POLICY_ALLOWLISTED_EFFECTS",
    "POLICY_PRIVATE_FACT_REVEAL",
]
