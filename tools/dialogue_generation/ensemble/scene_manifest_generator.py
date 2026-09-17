from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .profiles import CharacterProfile
from .relationship_graph import RelationshipEdge

TIER_WEIGHT = {"Major": 3, "Supporting": 2, "Minor": 1}
ALLOWED_EFFECTS = [
    "knowledge",
    "relationship",
    "aspect",
    "quest_stage",
    "policy",
    "diplomatic",
    "item_transfer",
    "production_modifier",
    "conserved_stock_transfer",
    "hazard_treatment",
    "entity_relocation",
    "history_fact",
]


def _sid(seed: int, index: int, scene_type: str, primary_id: str) -> str:
    digest = hashlib.sha1(f"{seed}|{index}|{scene_type}|{primary_id}".encode("utf-8")).hexdigest()[:8].upper()
    return f"SCN_{index:03d}_{digest}"


def _pview(profile: CharacterProfile) -> dict:
    return {
        "character_id": profile.id,
        "display_name": profile.name,
        "role": profile["Village_Role"],
        "narrative_tier": profile.tier,
        "district": profile.district,
        "home_or_base": profile["Home_or_Base"],
        "voice": {
            "register": profile["Voice_Register"],
            "sentence_shape": profile["Sentence_Shape"],
            "vocabulary_domain": profile["Vocabulary_Domain"],
            "verbal_tic": profile["Verbal_Tic"],
            "humour_style": profile["Humour_Style"],
            "silence_behaviour": profile["Silence_Behaviour"],
        },
        "psychology": {
            "core_desire": profile["Core_Desire"],
            "immediate_want": profile["Immediate_Want"],
            "core_fear": profile["Core_Fear"],
            "shame_or_vulnerability": profile["Shame_or_Vulnerability"],
            "false_belief": profile["False_Belief"],
            "central_contradiction": profile["Central_Contradiction"],
            "moral_boundary": profile["Moral_Boundary"],
        },
        "knowledge": {
            "profile": profile["Knowledge_Profile"],
            "boundary": profile["Knowledge_Boundary"],
            "what_they_notice": profile["What_They_Notice"],
            "what_they_miss": profile["What_They_Miss"],
        },
        "private": {
            "secret": profile["Secret"],
            "protective_lie": profile["Protective_Lie"],
        },
        "worldview": {
            "primary": profile["Primary_Worldview"],
            "secondary": profile["Secondary_Worldview"],
        },
        "routine": profile["Daily_Routine"],
        "prized_object": profile["Prized_Object"],
        "canon_rule": profile["LLM_Canon_Rule"],
    }


def _relation_lookup(edges: list[RelationshipEdge]) -> dict[str, list[RelationshipEdge]]:
    result: dict[str, list[RelationshipEdge]] = defaultdict(list)
    for edge in edges:
        result[edge.source_id].append(edge)
        result[edge.target_id].append(edge)
    for values in result.values():
        values.sort(key=lambda e: (-e.dramatic_weight, e.relationship_id))
    return result


def _participant_ids(primary: CharacterProfile, rels: dict[str, list[RelationshipEdge]], by_id: dict[str, CharacterProfile], *, count: int, rng: random.Random) -> list[str]:
    ids = [primary.id]
    candidates: list[str] = []
    for edge in rels.get(primary.id, []):
        other = edge.target_id if edge.source_id == primary.id else edge.source_id
        if other != primary.id and other not in candidates:
            candidates.append(other)
    # Prefer meaningful graph links, but vary among the strongest six.
    top = candidates[:6]
    while top and len(ids) < count:
        pick = rng.choice(top)
        top.remove(pick)
        if pick not in ids:
            ids.append(pick)
    if len(ids) < count:
        same_district = [p.id for p in by_id.values() if p.district == primary.district and p.id not in ids]
        rng.shuffle(same_district)
        ids.extend(same_district[: count - len(ids)])
    return ids


def _relationship_context(participant_ids: list[str], edges: list[RelationshipEdge]) -> list[dict]:
    selected = set(participant_ids)
    result = []
    for edge in edges:
        if edge.source_id in selected and edge.target_id in selected:
            result.append({
                "relationship_id": edge.relationship_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "type": edge.relation_type,
                "description": edge.source_description,
                "reciprocity": edge.reciprocity,
                "reverse_relation_types": edge.reverse_relation_types.split("|") if edge.reverse_relation_types else [],
                "dramatic_weight": edge.dramatic_weight,
            })
    return result


def _scene_problem(scene_type: str, primary: CharacterProfile, related: list[CharacterProfile]) -> str:
    other = related[0].name if related else "another villager"
    if scene_type == "introduction":
        return (
            f"Introduce {primary.name} through ordinary work at {primary.location}, while a live obligation involving {other} "
            f"puts their central contradiction under mild pressure: {primary['Central_Contradiction']} "
            "The player must learn an actionable affordance without receiving a generic quest-terminal speech."
        )
    if scene_type == "relationship":
        return (
            f"A concrete disagreement between {primary.name} and {other} forces the relationship into the open. "
            f"The scene should make both positions intelligible and test {primary.name}'s contradiction: {primary['Central_Contradiction']}"
        )
    if scene_type == "quest":
        return f"{primary['Quest_Hook']} Complication: {primary['Quest_Complication']}"
    if scene_type == "secret_pressure":
        return (
            f"Events around {other} put pressure on something {primary.name} is protecting. The writer may dramatise the pressure, "
            "but must not reveal the private fact unless the manifest's reveal policy permits it."
        )
    if scene_type == "district_group":
        return (
            f"Several people in {primary.district} want incompatible practical outcomes from the same local situation. "
            f"Use {primary.name}'s immediate want as one pressure vector: {primary['Immediate_Want']}"
        )
    if scene_type == "consequence":
        return (
            f"Revisit {primary.name} after a meaningful prior outcome. Their behaviour must reflect: {primary['Post_Quest_State']} "
            "The scene is about changed relationships and memory, not replaying the original exposition."
        )
    raise ValueError(scene_type)


def _build_manifest(*, scene_id: str, scene_type: str, primary: CharacterProfile, participant_ids: list[str], by_id: dict[str, CharacterProfile], edges: list[RelationshipEdge], seed: int, ordinal: int) -> dict:
    participants = [by_id[i] for i in participant_ids]
    related = [p for p in participants if p.id != primary.id]
    reveal_secret = scene_type == "secret_pressure" and primary.tier in {"Major", "Supporting"}
    objectives = {p.id: p["Immediate_Want"] for p in participants}
    private_facts = {p.id: [p["Secret"], p["Protective_Lie"]] for p in participants}
    forbidden = [] if reveal_secret else [f"Do not explicitly reveal {primary.name}'s secret: {primary['Secret']}"]
    if scene_type == "introduction":
        forbidden.append("Do not resolve the character's principal quest or central contradiction in the introduction.")

    outcomes = [
        "player_gains_or_corrects_knowledge",
        "relationship_improves_or_worsens_for_a_specific_reason",
        "player_defers_or_redirects_the_issue_without_erasing_it",
    ]
    if scene_type == "quest":
        outcomes.extend(["quest_stage_advances", "alternate_solution_becomes_available"])
    if scene_type == "consequence":
        outcomes.append("prior_choice_is_acknowledged_without_repeating_the_old_scene")

    return {
        "schema_version": "dmb-scene-manifest-v1",
        "scene_id": scene_id,
        "scene_type": scene_type,
        "generation": {"seed": seed, "ordinal": ordinal},
        "location": primary.location,
        "district": primary.district,
        "primary_character_id": primary.id,
        "participant_ids": participant_ids,
        "participant_profiles": [_pview(p) for p in participants],
        "trigger": {
            "kind": {
                "introduction": "first_meaningful_contact",
                "relationship": "relationship_pressure",
                "quest": "cause_or_quest_stage",
                "secret_pressure": "private_fact_pressure",
                "district_group": "shared_local_pressure",
                "consequence": "prior_scene_receipt",
            }[scene_type],
            "must_be_true": ["all listed participants are present or validly reachable", "canonical game state matches the compiled packet"],
        },
        "dramatic_problem": _scene_problem(scene_type, primary, related),
        "character_objectives": objectives,
        "relationship_context": _relationship_context(participant_ids, edges),
        "knowledge_boundaries": {p.id: p["Knowledge_Boundary"] for p in participants},
        "private_facts_for_writer_only": private_facts,
        "reveal_policy": {
            "primary_secret_may_be_revealed": reveal_secret,
            "rule": "Private facts may create subtext. They become spoken canon only when this manifest explicitly permits revelation or a validated effect has already exposed them.",
        },
        "player_affordances": [
            "ask_for_evidence_or_clarification",
            "support_or_challenge_a_character_position",
            "use_relevant_known_fact_or_item_when_state_allows",
            "leave_or_defer_without_soft_locking_content",
        ],
        "possible_outcomes": outcomes,
        "allowed_effect_types": ALLOWED_EFFECTS,
        "forbidden_revelations": forbidden,
        "quest_material": {
            "hook": primary["Quest_Hook"],
            "complication": primary["Quest_Complication"],
            "alternate_solution": primary["Quest_Alternate_Solution"],
        },
        "puzzle_material": {
            "type": primary["Puzzle_Type"],
            "logic": primary["Puzzle_Logic"],
            "clue_source": primary["Puzzle_Clue_Source"],
            "failure_or_recovery": primary["Failure_or_Recovery"],
        },
        "scene_requirements": [
            primary["House_Content_Rule"],
            "At least one line or action must reveal relationship, attitude or pressure rather than pure exposition.",
            "No character may state knowledge outside their compiled knowledge boundary.",
            "Do not add arbitrary script effects; outcomes must use allowlisted effect types.",
        ],
        "coverage_tags": [scene_type, primary.tier.lower(), primary.district, primary["Village_Role"]],
    }


def generate_scene_manifests(profiles: Iterable[CharacterProfile], edges: Iterable[RelationshipEdge], *, target_scenes: int = 300, seed: int = 1337) -> list[dict]:
    profiles = list(profiles)
    edges = list(edges)
    if target_scenes < len(profiles):
        raise ValueError(f"target_scenes must be at least the character count ({len(profiles)})")

    rng = random.Random(seed)
    by_id = {p.id: p for p in profiles}
    rels = _relation_lookup(edges)
    manifests: list[dict] = []

    def add(scene_type: str, primary: CharacterProfile, participant_count: int) -> None:
        ordinal = len(manifests) + 1
        ids = _participant_ids(primary, rels, by_id, count=participant_count, rng=rng)
        manifests.append(
            _build_manifest(
                scene_id=_sid(seed, ordinal, scene_type, primary.id),
                scene_type=scene_type,
                primary=primary,
                participant_ids=ids,
                by_id=by_id,
                edges=edges,
                seed=seed,
                ordinal=ordinal,
            )
        )

    # Phase 1: every character is introduced in context, normally with one graph-linked NPC.
    for profile in sorted(profiles, key=lambda p: p.id):
        add("introduction", profile, 2)

    # Fixed 300-scene editorial mix. For other target sizes, these become ceilings and
    # the consequence phase fills any remaining budget.
    remaining = target_scenes - len(manifests)
    relationship_budget = min(65, max(0, remaining))

    # Phase 2: dramatise explicit high-value relationships without simply mirroring duplicate directed edges.
    seen_pairs: set[tuple[str, str]] = set()
    relationship_candidates: list[tuple[int, CharacterProfile]] = []
    for edge in edges:
        pair = tuple(sorted((edge.source_id, edge.target_id)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        primary = by_id[edge.source_id]
        relationship_candidates.append((edge.dramatic_weight, primary))
    relationship_candidates.sort(key=lambda item: (-item[0], item[1].id))
    for _, profile in relationship_candidates[:relationship_budget]:
        add("relationship", profile, 2 if profile.tier == "Minor" else 3)

    # Phase 3: quest scenes for all major/supporting characters while budget permits.
    quest_budget = min(64, max(0, target_scenes - len(manifests)))
    quest_pool = sorted((p for p in profiles if p.tier in {"Major", "Supporting"}), key=lambda p: (-TIER_WEIGHT[p.tier], p.id))
    for profile in quest_pool[:quest_budget]:
        add("quest", profile, 3)

    # Phase 4: a bounded set of secret/vulnerability pressure scenes. This deliberately
    # leaves room for place-based ensembles and consequence/revisit scenes.
    secret_budget = min(35, max(0, target_scenes - len(manifests)))
    secret_pool = sorted((p for p in profiles if p.tier in {"Major", "Supporting"}), key=lambda p: (-TIER_WEIGHT.get(p.tier, 1), p.id))
    # Shuffle within tier deterministically so the same subset is not always lowest-ID characters.
    majors = [p for p in secret_pool if p.tier == "Major"]
    supports = [p for p in secret_pool if p.tier == "Supporting"]
    rng.shuffle(majors)
    rng.shuffle(supports)
    chosen_secrets = majors + supports
    for profile in chosen_secrets[:secret_budget]:
        add("secret_pressure", profile, 3)

    # Phase 5: ensure every district gets two ensemble scenes before generic fill.
    by_district: dict[str, list[CharacterProfile]] = defaultdict(list)
    for profile in profiles:
        by_district[profile.district].append(profile)
    district_budget = min(len(by_district) * 2, max(0, target_scenes - len(manifests)))
    district_added = 0
    for district in sorted(by_district):
        for _ in range(2):
            if district_added >= district_budget or len(manifests) >= target_scenes:
                break
            pool = sorted(by_district[district], key=lambda p: (-TIER_WEIGHT.get(p.tier, 1), p.id))
            primary = rng.choice(pool[: min(5, len(pool))])
            add("district_group", primary, min(4, len(pool)))
            district_added += 1

    # Phase 6: fill remaining budget with consequence/revisit scenes distributed across the cast.
    coverage = Counter(m["primary_character_id"] for m in manifests)
    while len(manifests) < target_scenes:
        minimum = min(coverage.get(p.id, 0) for p in profiles)
        candidates = [p for p in profiles if coverage.get(p.id, 0) == minimum]
        candidates.sort(key=lambda p: (-TIER_WEIGHT.get(p.tier, 1), p.id))
        primary = rng.choice(candidates[: min(12, len(candidates))])
        add("consequence", primary, 2 if primary.tier == "Minor" else 3)
        coverage[primary.id] += 1

    return manifests[:target_scenes]


def write_manifests_jsonl(manifests: Iterable[dict], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for manifest in manifests:
            handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")


def write_manifests_json(manifests: Iterable[dict], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "dmb-scene-catalogue-v1", "scenes": list(manifests)}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
