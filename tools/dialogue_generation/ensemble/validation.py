from __future__ import annotations

from collections import Counter
from typing import Iterable

from .profiles import CharacterProfile
from .quality import _unexplained_off_district
from .relationship_graph import MAX_RESPONSIBILITY_INDEGREE, MIN_RESPONSIBILITY_TARGETS, RelationshipEdge

DEPTH_REQUIRED = (
    "Formative_Event",
    "Self_Image",
    "Private_Need",
    "Social_Mask",
    "Specific_Regret",
    "Specific_Hope",
    "Relationship_Wound",
    "Pressure_Behaviour",
    "Repair_Behaviour",
    "Misjudges_Others_By",
    "Cross_District_Reason",
)


def validate_ensemble(profiles: Iterable[CharacterProfile], edges: Iterable[RelationshipEdge], manifests: Iterable[dict]) -> dict:
    profiles = list(profiles)
    edges = list(edges)
    manifests = list(manifests)
    ids = {p.id for p in profiles}
    by_id = {p.id: p for p in profiles}
    errors: list[str] = []
    warnings: list[str] = []

    if len(ids) != len(profiles):
        errors.append("Duplicate Character_ID detected")

    for profile in profiles:
        for field in DEPTH_REQUIRED:
            if not profile[field].strip():
                errors.append(f"{profile.id} missing required profile field {field}")

    rel_ids = [edge.relationship_id for edge in edges]
    if len(rel_ids) != len(set(rel_ids)):
        errors.append("Duplicate relationship_id detected")

    resp_in = Counter()
    for edge in edges:
        if edge.source_id not in ids or edge.target_id not in ids:
            errors.append(f"Broken relationship reference: {edge.relationship_id}")
        if edge.source_id == edge.target_id:
            errors.append(f"Self relationship is not permitted: {edge.relationship_id}")
        if edge.relation_type == "cross_district":
            if edge.source_district == edge.target_district or edge.same_district:
                errors.append(
                    f"cross_district relationship {edge.relationship_id} joins same-district characters "
                    f"{edge.source_name} and {edge.target_name}"
                )
            if not (edge.contact_reason or "").strip():
                warnings.append(f"{edge.relationship_id} has no contact_reason")
        if edge.relation_type == "responsibility":
            resp_in[edge.target_id] += 1
        if not (edge.shared_history or edge.source_description or "").strip():
            errors.append(f"{edge.relationship_id} lacks character-specific history")

    if len({cid for cid in resp_in}) < MIN_RESPONSIBILITY_TARGETS:
        errors.append(
            f"Responsibility targets ({len(resp_in)}) below minimum {MIN_RESPONSIBILITY_TARGETS}"
        )
    over = {cid: count for cid, count in resp_in.items() if count > MAX_RESPONSIBILITY_INDEGREE}
    if over:
        named = {by_id[cid]["Responsibility_Indegree_Override_Reason"] for cid in over if by_id[cid]["Responsibility_Indegree_Override_Reason"]}
        if len(named) < len(over):
            errors.append(f"Responsibility indegree exceeds {MAX_RESPONSIBILITY_INDEGREE} without override: {over}")

    scene_ids = [m.get("scene_id") for m in manifests]
    if len(scene_ids) != len(set(scene_ids)):
        errors.append("Duplicate scene_id detected")
    scene_id_set = set(scene_ids)

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

    for profile in profiles:
        if scene_primary[profile.id] < 2:
            errors.append(f"{profile.id} has fewer than 2 primary scenes")
        if scene_participation[profile.id] < 4:
            errors.append(f"{profile.id} appears in fewer than 4 scenes")

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

        unexplained = _unexplained_off_district(manifest, by_id)
        if unexplained and manifest.get("scene_type") in {"introduction", "district_group", "consequence"}:
            errors.append(
                f"Scene {manifest.get('scene_id')} has unexplained off-district participants {unexplained}"
            )

        if manifest.get("scene_type") == "consequence":
            trigger = manifest.get("trigger") or {}
            pred = trigger.get("required_scene_id")
            outcome = trigger.get("required_outcome_id")
            effects = trigger.get("required_effects") or []
            if trigger.get("kind") != "prior_scene_receipt":
                errors.append(f"Consequence {manifest.get('scene_id')} lacks prior_scene_receipt trigger")
            if not pred or pred not in scene_id_set:
                errors.append(f"Consequence {manifest.get('scene_id')} references missing predecessor {pred!r}")
            elif pred == manifest.get("scene_id"):
                errors.append(f"Consequence {manifest.get('scene_id')} binds to itself")
            if not outcome:
                errors.append(f"Consequence {manifest.get('scene_id')} lacks required_outcome_id")
            if not effects:
                errors.append(f"Consequence {manifest.get('scene_id')} lacks required_effects")
            else:
                for effect in effects:
                    target = effect.get("target")
                    if target and target not in ids:
                        errors.append(f"Consequence {manifest.get('scene_id')} effect target {target} is not a character")

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
            "responsibility_targets": len(resp_in),
            "max_responsibility_indegree": max(resp_in.values()) if resp_in else 0,
        },
    }
