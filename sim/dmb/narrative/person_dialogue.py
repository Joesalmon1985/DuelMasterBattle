"""Person-facing talk context for ordinary settlement dialogue (G05).

Shared by DialogueResolver and overworld opening lines so Talk and ambient
text stay semantically consistent. Not a new ontology layer.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.world.settlement_layout import (
    activity_label,
    baseline_dialogue,
    public_occupation_for,
)


def person_talk_context(state: Any, person_id: str) -> dict[str, Any]:
    person = (state.people or {}).get(person_id) or {}
    workplace_id = str(person.get("workplace_id") or "")
    workplace = (state.buildings or {}).get(workplace_id) or {}
    occupation = public_occupation_for(person, workplace=workplace)
    activity = str(person.get("activity") or "idle")
    resource_label = None
    try:
        from sim.dmb.industry.projection import IndustryProjection

        for row in IndustryProjection(state).workers():
            if str(row.get("person_id")) == person_id:
                activity = str(row.get("activity") or activity)
                resource_label = row.get("resource_label")
                occupation = str(
                    row.get("public_occupation") or row.get("occupation") or occupation
                )
                break
    except Exception:
        pass
    role = str(person.get("role") or "villager")
    slot = str(workplace.get("slot_kind") or "")
    terrain = str(workplace.get("terrain") or "")
    workplace_label = str(workplace.get("label") or "") or None
    return {
        "person_id": person_id,
        "role": role,
        "occupation": occupation,
        "workplace_id": workplace_id or None,
        "workplace_kind": slot or None,
        "workplace_label": workplace_label,
        "terrain": terrain or None,
        "resource_label": str(resource_label) if resource_label else None,
        "activity": activity,
        "activity_label": activity_label(activity, resource_label=resource_label),
    }


def ordinary_opening_line(ctx: dict[str, Any], person: dict[str, Any] | None = None) -> str:
    """Short Talk greeting consistent with ambient baseline_dialogue."""
    person = person or {}
    role = str(ctx.get("role") or person.get("role") or "villager")
    if role == "soldier":
        return "I'm with the settlement's fighting force."
    if role == "leader":
        return "I keep an eye on what the settlement needs."
    lines = baseline_dialogue(
        person,
        occupation=str(ctx.get("occupation") or "Villager"),
        activity=str(ctx.get("activity") or "idle"),
        resource_label=ctx.get("resource_label"),
        workplace_label=ctx.get("workplace_label"),
    )
    return lines[0] if lines else "The settlement keeps us busy."


def occupation_answer_line(ctx: dict[str, Any]) -> str:
    """Truthful answer to 'What work do you do here?'"""
    occ = str(ctx.get("occupation") or "Villager")
    place = str(ctx.get("workplace_label") or "").strip()
    terrain = str(ctx.get("terrain") or "")
    resource = str(ctx.get("resource_label") or "").strip()
    role = str(ctx.get("role") or "")

    if role == "soldier":
        return "I'm with the settlement's fighting force."
    if role == "leader":
        return "I keep an eye on what the settlement needs."

    if "Woodcutter" in occ or terrain == "woodland":
        if resource:
            return f"I work the woodland edge. We bring {resource.lower()} back into the settlement."
        return "I work the woodland edge. We bring gathered goods back into the settlement."
    if "Miner" in occ or terrain == "ore_mountains":
        if resource:
            return f"I work the ridge. {resource} from here goes down to the works."
        return "I work the ridge. Material from here goes down to the works."
    if "Clay" in occ or terrain == "clay_mountains":
        return "I work the clay ground beyond the houses."
    if "Field" in occ or terrain == "fields":
        return "I work the fields at the edge of the settlement."
    if "Shepherd" in occ or terrain == "grazing_land":
        return "I work the pasture at the edge of the settlement."
    if "Works" in occ or ctx.get("workplace_kind") == "processor":
        if place:
            return f"I work at {place}. We combine what comes in from the surrounding land."
        return "I work at the hearth. We combine what comes in from the surrounding land."
    if "Factory" in occ or ctx.get("workplace_kind") == "factory":
        if place:
            return f"I work at {place}. Processed material comes here for the muster."
        return "I work at the muster yard. Processed material comes here for assembly."
    if "Storekeeper" in occ or ctx.get("workplace_kind") == "warehouse":
        if place:
            return f"I work at {place}, where goods are stored and dispatched."
        return "I work at the warehouse, where goods are stored and dispatched."
    if place:
        return f"I work at {place}."
    if occ and occ not in {"Villager", "Worker"}:
        return f"I'm a {occ.lower()} for the settlement."
    return "I've lived around here for some time."


def ordinary_talk_line(
    state: Any,
    person_id: str,
    *,
    line_id: str = "dialogue.person.ordinary",
) -> dict[str, Any]:
    ctx = person_talk_context(state, person_id)
    person = (state.people or {}).get(person_id) or {}
    text = ordinary_opening_line(ctx, person)
    return {
        "id": line_id,
        "scope": "normal",
        "speaker_role": str(ctx.get("role") or "worker"),
        "text": text,
        "fallback": "They nod.",
        "choices": [],
        "priority": "role_default",
        "context": ctx,
    }


def occupation_reply_line(state: Any, person_id: str) -> dict[str, Any]:
    ctx = person_talk_context(state, person_id)
    return {
        "id": "dialogue.boulder.occupation",
        "scope": "rockfall",
        "text": occupation_answer_line(ctx),
        "fallback": "They describe their ordinary work.",
        "choices": [],
        "context": ctx,
    }
