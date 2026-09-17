from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
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
        "schema_version": "dmb-relationship-graph-v1",
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
