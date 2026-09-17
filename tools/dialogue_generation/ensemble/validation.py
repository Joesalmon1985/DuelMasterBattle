from __future__ import annotations

from collections import Counter
from typing import Iterable

from .profiles import CharacterProfile
from .relationship_graph import RelationshipEdge


def validate_ensemble(profiles: Iterable[CharacterProfile], edges: Iterable[RelationshipEdge], manifests: Iterable[dict]) -> dict:
    profiles = list(profiles)
    edges = list(edges)
    manifests = list(manifests)
    ids = {p.id for p in profiles}
    errors: list[str] = []
    warnings: list[str] = []

    if len(ids) != len(profiles):
        errors.append("Duplicate Character_ID detected")

    for edge in edges:
        if edge.source_id not in ids or edge.target_id not in ids:
            errors.append(f"Broken relationship reference: {edge.relationship_id}")
        if edge.source_id == edge.target_id:
            errors.append(f"Self relationship is not permitted: {edge.relationship_id}")

    scene_ids = [m.get("scene_id") for m in manifests]
    if len(scene_ids) != len(set(scene_ids)):
        errors.append("Duplicate scene_id detected")

    scene_primary = Counter(m.get("primary_character_id") for m in manifests)
    scene_participation = Counter(pid for m in manifests for pid in m.get("participant_ids", []))
    missing_primary = sorted(ids.difference(scene_primary))
    missing_participation = sorted(ids.difference(scene_participation))
    if missing_primary:
        errors.append(f"Characters with no primary scene: {missing_primary}")
    if missing_participation:
        errors.append(f"Characters never appearing in any scene: {missing_participation}")

    intro_ids = {m.get("primary_character_id") for m in manifests if m.get("scene_type") == "introduction"}
    missing_intros = sorted(ids.difference(intro_ids))
    if missing_intros:
        errors.append(f"Characters without introduction scene: {missing_intros}")

    for manifest in manifests:
        participants = manifest.get("participant_ids", [])
        if not participants:
            errors.append(f"Scene has no participants: {manifest.get('scene_id')}")
        unknown = sorted(set(participants).difference(ids))
        if unknown:
            errors.append(f"Scene {manifest.get('scene_id')} has unknown participants {unknown}")
        if manifest.get("primary_character_id") not in participants:
            errors.append(f"Scene {manifest.get('scene_id')} omits primary character from participants")
        if not manifest.get("dramatic_problem"):
            errors.append(f"Scene {manifest.get('scene_id')} lacks dramatic_problem")
        if not manifest.get("knowledge_boundaries"):
            errors.append(f"Scene {manifest.get('scene_id')} lacks knowledge boundaries")

    edge_out = Counter(edge.source_id for edge in edges)
    for profile in profiles:
        if edge_out[profile.id] < 4:
            warnings.append(f"{profile.id} has only {edge_out[profile.id]} authored outgoing relationships")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "characters": len(profiles),
            "relationship_edges": len(edges),
            "scenes": len(manifests),
            "scene_types": dict(Counter(m.get("scene_type") for m in manifests)),
            "min_primary_scenes_per_character": min(scene_primary.values()) if scene_primary else 0,
            "max_primary_scenes_per_character": max(scene_primary.values()) if scene_primary else 0,
            "min_total_scene_appearances_per_character": min(scene_participation.values()) if scene_participation else 0,
            "max_total_scene_appearances_per_character": max(scene_participation.values()) if scene_participation else 0,
        },
    }
