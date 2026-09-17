from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Iterable

from .profiles import CharacterProfile

RELATION_FIELDS = (
    ("ally", "Key_Ally", "Ally_Relationship", 3),
    ("rival", "Key_Rival", "Rival_Relationship", 5),
    ("cross_district", "Cross_District_Connection", "Cross_District_Relationship", 3),
    ("responsibility", "Dependent_or_Responsibility", "Dependency_Relationship", 4),
)

TIER_WEIGHT = {"Major": 3, "Supporting": 2, "Minor": 1}
MAX_RESPONSIBILITY_INDEGREE = 4
MIN_RESPONSIBILITY_TARGETS = 30


@dataclass(frozen=True)
class RelationshipEdge:
    relationship_id: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation_type: str
    source_description: str
    source_district: str
    target_district: str
    source_tier: str
    target_tier: str
    same_district: bool
    worldview_distance: int
    dramatic_weight: int
    reciprocity: str
    reverse_relation_types: str
    source_primary_worldview: str
    target_primary_worldview: str
    source_immediate_want: str
    target_immediate_want: str
    source_secret: str
    target_secret: str
    origin_event: str = ""
    shared_history: str = ""
    source_view_of_target: str = ""
    target_view_of_source: str = ""
    public_story: str = ""
    private_truth: str = ""
    current_tension: str = ""
    source_wants: str = ""
    target_wants: str = ""
    source_leverage: str = ""
    target_leverage: str = ""
    misunderstanding: str = ""
    reason_relationship_matters_now: str = ""
    breaking_point: str = ""
    repair_condition: str = ""
    reason_for_presence: str = ""
    contact_reason: str = ""


def _stable_id(source_id: str, target_id: str, relation_type: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{target_id}|{relation_type}".encode("utf-8")).hexdigest()[:10].upper()
    return f"REL_{digest}"


def _worldview_distance(a: CharacterProfile, b: CharacterProfile) -> int:
    return sum(abs(x - y) for x, y in zip(a.worldview_scores(), b.worldview_scores()))


def _reverse_types(source: CharacterProfile, target: CharacterProfile) -> list[str]:
    result: list[str] = []
    for rel_type, target_field, _, _ in RELATION_FIELDS:
        if target[target_field] == source.name:
            result.append(rel_type)
    return result


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    cut = text.find(". ")
    return text[: cut + 1] if cut != -1 else text


def _compose_history(source: CharacterProfile, target: CharacterProfile, rel_type: str, description: str) -> dict[str, str]:
    contact = source["Cross_District_Reason"] if rel_type == "cross_district" else rel_type.replace("_", " ")
    origin = _first_sentence(description) or (
        f"{source.name} and {target.name} were bound through {source['Village_Role'].lower()} work at {source['Home_or_Base']}."
    )
    if rel_type == "responsibility":
        source_view = (
            f"{source.name} tells {source['Self_Image']} while managing {target.name}: {source['Pressure_Behaviour']}"
        )
        target_view = (
            f"{target.name} experiences the duty as control because {target['Misjudges_Others_By']}"
        )
        public_story = f"{source.name} is simply looking after {target.name} as part of {source['Village_Role'].lower()} work."
        private_truth = description
        tension = f"{source['Immediate_Want']} collides with {target['Immediate_Want']}"
        presence = (
            f"{target.name} is here because {source.name} still carries the unpaid practical debt described in their history."
        )
    elif rel_type == "rival":
        source_view = f"{source['Relationship_Wound']} {source['Misjudges_Others_By']}"
        target_view = f"{target['Relationship_Wound']}"
        public_story = (
            f"{source.district} treats {source.name} and {target.name} as people who disagree about {source['Village_Role'].lower()} work."
        )
        private_truth = description
        tension = f"{source.name} needs {target.name} to be slightly wrong about {source['Secret']}"
        presence = f"{target.name} is present because the live dispute with {source.name} is already in motion."
    elif rel_type == "cross_district":
        source_view = (
            f"{source.name} keeps the {contact} unofficial so {source['Secret']} does not travel on a second district's books."
        )
        target_view = (
            f"{target.name} answers the {contact} because {target['Private_Need']}"
        )
        public_story = f"A routine {contact} between {source.district} and {target.district}."
        private_truth = description
        tension = f"The {contact} is due now, and neither can use an official route without exposing private facts."
        presence = (
            f"{target.name} has a concrete {contact} reason to be in {source.district}: {description}"
        )
    else:
        source_view = f"{source['Private_Need']} {source.name} uses {target.name} as the witness who has not yet become a judge."
        target_view = f"{target['Repair_Behaviour']}"
        public_story = f"{source.name} and {target.name} are known to work well together in {source.district}."
        private_truth = description
        tension = f"{source['Immediate_Want']} now requires {target.name}'s cover without giving {target.name} the whole of {source['Secret']}"
        presence = f"{target.name} is present as {source.name}'s working ally at {source.location}."

    return {
        "origin_event": origin,
        "shared_history": description,
        "source_view_of_target": source_view,
        "target_view_of_source": target_view,
        "public_story": public_story,
        "private_truth": private_truth,
        "current_tension": tension,
        "source_wants": source["Immediate_Want"],
        "target_wants": target["Immediate_Want"],
        "source_leverage": f"{source['Village_Role']} access at {source['Home_or_Base']}: {source['Social_Mask']}",
        "target_leverage": f"{target['Village_Role']} access at {target['Home_or_Base']}: {target['Specific_Regret']}",
        "misunderstanding": (
            f"{source.name} hears {target.name} through {source['Misjudges_Others_By']} "
            f"{target.name} hears {source.name} through {target['Misjudges_Others_By']}"
        ),
        "reason_relationship_matters_now": (
            f"{source['Immediate_Want']} cannot be finished without {target.name}, "
            f"and {source['Specific_Hope']} is already entangled with {target.name}."
        ),
        "breaking_point": (
            f"If {source['Secret']} becomes public through {target.name}, or if {target['Secret']} is used as a weapon, the relationship ends as working trust."
        ),
        "repair_condition": source["Repair_Behaviour"],
        "reason_for_presence": presence,
        "contact_reason": contact,
    }


def build_relationship_graph(profiles: Iterable[CharacterProfile]) -> list[RelationshipEdge]:
    profiles = list(profiles)
    by_name = {p.name: p for p in profiles}
    edges: list[RelationshipEdge] = []

    for source in profiles:
        for rel_type, target_field, description_field, base_weight in RELATION_FIELDS:
            target_name = source[target_field]
            if not target_name:
                continue
            target = by_name[target_name]
            reverse = _reverse_types(source, target)
            distance = _worldview_distance(source, target)
            tier_bonus = max(TIER_WEIGHT.get(source.tier, 1), TIER_WEIGHT.get(target.tier, 1))
            tension_bonus = 1 if rel_type in {"rival", "responsibility"} else 0
            worldview_bonus = 1 if distance >= 10 else 0
            dramatic_weight = base_weight + tier_bonus + tension_bonus + worldview_bonus
            history = _compose_history(source, target, rel_type, source[description_field])
            edges.append(
                RelationshipEdge(
                    relationship_id=_stable_id(source.id, target.id, rel_type),
                    source_id=source.id,
                    source_name=source.name,
                    target_id=target.id,
                    target_name=target.name,
                    relation_type=rel_type,
                    source_description=source[description_field],
                    source_district=source.district,
                    target_district=target.district,
                    source_tier=source.tier,
                    target_tier=target.tier,
                    same_district=source.district == target.district,
                    worldview_distance=distance,
                    dramatic_weight=dramatic_weight,
                    reciprocity="explicit" if reverse else "one_way",
                    reverse_relation_types="|".join(reverse),
                    source_primary_worldview=source["Primary_Worldview"],
                    target_primary_worldview=target["Primary_Worldview"],
                    source_immediate_want=source["Immediate_Want"],
                    target_immediate_want=target["Immediate_Want"],
                    source_secret=source["Secret"],
                    target_secret=target["Secret"],
                    **history,
                )
            )

    edges.sort(key=lambda e: (-e.dramatic_weight, e.source_id, e.target_id, e.relation_type))
    return edges


def write_relationship_csv(edges: Iterable[RelationshipEdge], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(edge) for edge in edges]
    if not rows:
        raise ValueError("No relationship edges to write")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_relationship_json(profiles: Iterable[CharacterProfile], edges: Iterable[RelationshipEdge], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles = list(profiles)
    edges = list(edges)
    payload = {
        "schema_version": "dmb-relationship-graph-v2",
        "nodes": [
            {
                "character_id": p.id,
                "display_name": p.name,
                "narrative_tier": p.tier,
                "district": p.district,
                "role": p["Village_Role"],
                "primary_worldview": p["Primary_Worldview"],
                "secondary_worldview": p["Secondary_Worldview"],
                "core_desire": p["Core_Desire"],
                "central_contradiction": p["Central_Contradiction"],
            }
            for p in profiles
        ],
        "edges": [asdict(edge) for edge in edges],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def edge_from_mapping(row: dict) -> RelationshipEdge:
    allowed = {item.name for item in fields(RelationshipEdge)}
    return RelationshipEdge(**{key: value for key, value in row.items() if key in allowed})
