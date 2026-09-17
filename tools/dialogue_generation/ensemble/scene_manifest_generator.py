from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .policies import DEFAULT_POLICY_REFS
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
NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def _sid(seed: int, index: int, scene_type: str, primary_id: str) -> str:
    digest = hashlib.sha1(f"{seed}|{index}|{scene_type}|{primary_id}".encode("utf-8")).hexdigest()[:8].upper()
    return f"SCN_{index:03d}_{digest}"


def _pview(profile: CharacterProfile, presence_reason: str = "") -> dict:
    return {
        "character_id": profile.id,
        "display_name": profile.name,
        "role": profile["Village_Role"],
        "narrative_tier": profile.tier,
        "district": profile.district,
        "home_or_base": profile["Home_or_Base"],
        "presence_reason": presence_reason,
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
            "formative_event": profile["Formative_Event"],
            "self_image": profile["Self_Image"],
            "private_need": profile["Private_Need"],
            "social_mask": profile["Social_Mask"],
            "specific_regret": profile["Specific_Regret"],
            "specific_hope": profile["Specific_Hope"],
            "pressure_behaviour": profile["Pressure_Behaviour"],
            "repair_behaviour": profile["Repair_Behaviour"],
            "misjudges_others_by": profile["Misjudges_Others_By"],
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


def _edge_between(rels: dict[str, list[RelationshipEdge]], a: str, b: str) -> RelationshipEdge | None:
    for edge in rels.get(a, []):
        other = edge.target_id if edge.source_id == a else edge.source_id
        if other == b:
            return edge
    return None


def _presence_reason(primary: CharacterProfile, other: CharacterProfile, edge: RelationshipEdge | None) -> str:
    if other.district == primary.district:
        if other["Home_or_Base"] == primary["Home_or_Base"]:
            return f"Works at {primary['Home_or_Base']} with {primary.name}."
        return f"Resident/worker in {primary.district}, present for ordinary {other['Village_Role'].lower()} business."
    if edge is None:
        return ""
    return edge.reason_for_presence or (
        f"{other.name} has a {edge.contact_reason or edge.relation_type} reason to be in {primary.district}: {edge.origin_event}"
    )


def _same_place(primary: CharacterProfile, other: CharacterProfile) -> bool:
    return other["Home_or_Base"] == primary["Home_or_Base"] or other.location == primary.location


def _participant_ids(
    primary: CharacterProfile,
    rels: dict[str, list[RelationshipEdge]],
    by_id: dict[str, CharacterProfile],
    *,
    count: int,
    rng: random.Random,
    scene_type: str,
    forced: list[str] | None = None,
) -> list[str]:
    ids = [primary.id]
    for pid in forced or []:
        if pid in by_id and pid not in ids:
            ids.append(pid)
        if len(ids) >= count:
            return ids[:count]

    neighbours: list[str] = []
    for edge in rels.get(primary.id, []):
        other = edge.target_id if edge.source_id == primary.id else edge.source_id
        if other != primary.id and other not in neighbours:
            neighbours.append(other)

    same_district = [p.id for p in by_id.values() if p.district == primary.district and p.id not in ids]
    same_place = [pid for pid in same_district if _same_place(primary, by_id[pid])]
    local_neighbours = [pid for pid in neighbours if by_id[pid].district == primary.district]
    explained_outsiders = [
        pid for pid in neighbours
        if by_id[pid].district != primary.district and _presence_reason(primary, by_id[pid], _edge_between(rels, primary.id, pid))
    ]

    if scene_type in {"introduction", "district_group"}:
        pools = [same_place, local_neighbours, same_district]
        if scene_type == "district_group":
            pools.append(explained_outsiders)
    elif scene_type == "consequence":
        pools = [forced or [], local_neighbours, explained_outsiders, same_district]
    else:
        pools = [local_neighbours, same_place, explained_outsiders, same_district]

    for pool in pools:
        available = [pid for pid in pool if pid not in ids]
        rng.shuffle(available)
        for pid in available:
            if scene_type in {"introduction", "district_group"} and by_id[pid].district != primary.district:
                if not _presence_reason(primary, by_id[pid], _edge_between(rels, primary.id, pid)):
                    continue
            ids.append(pid)
            if len(ids) >= count:
                return ids
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
                "origin_event": edge.origin_event,
                "shared_history": edge.shared_history,
                "public_story": edge.public_story,
                "private_truth": edge.private_truth,
                "current_tension": edge.current_tension,
                "reason_for_presence": edge.reason_for_presence,
                "contact_reason": edge.contact_reason,
                "reciprocity": edge.reciprocity,
                "reverse_relation_types": edge.reverse_relation_types.split("|") if edge.reverse_relation_types else [],
                "dramatic_weight": edge.dramatic_weight,
            })
    return result


def _scene_problem(scene_type: str, primary: CharacterProfile, related: list[CharacterProfile], predecessor: dict | None) -> str:
    other = related[0] if related else None
    other_name = other.name if other else "a neighbour in " + primary.district
    if scene_type == "introduction":
        reason = ""
        if other and other.district != primary.district:
            reason = f" {other.name} is not local; their presence must be justified by the compiled reason_for_presence."
        return (
            f"Introduce {primary.name} through ordinary {primary['Village_Role'].lower()} work at {primary.location}. "
            f"{other_name} puts pressure on {primary['Central_Contradiction']} {reason} "
            f"The player should leave with one actionable affordance, not a quest-terminal speech."
        )
    if scene_type == "relationship":
        return (
            f"A concrete disagreement between {primary.name} and {other_name} forces their shared history into the open: "
            f"{primary['Relationship_Wound']} Test {primary['Central_Contradiction']}"
        )
    if scene_type == "quest":
        return f"{primary['Quest_Hook']} Complication: {primary['Quest_Complication']}"
    if scene_type == "secret_pressure":
        return (
            f"Events around {other_name} press on {primary['Secret']}. Dramatise the pressure through {primary['Pressure_Behaviour']} "
            "Do not reveal the private fact unless the reveal policy permits it."
        )
    if scene_type == "district_group":
        names = ", ".join(p.name for p in related[:3]) or other_name
        return (
            f"A live practical conflict in {primary.district} at {primary.location} gives {names} incompatible outcomes. "
            f"{primary.name}'s vector is: {primary['Immediate_Want']} Outsiders may appear only with compiled presence reasons."
        )
    if scene_type == "consequence":
        pred = predecessor["scene_id"] if predecessor else "a prior scene"
        return (
            f"Revisit {primary.name} after {pred}. Behaviour must reflect {primary['Post_Quest_State']} "
            "Show changed relationships and memory; do not replay the original exposition."
        )
    raise ValueError(scene_type)


def _names_in_text(text: str, by_name: dict[str, CharacterProfile]) -> list[str]:
    found: list[str] = []
    for name, profile in by_name.items():
        if name and name in (text or ""):
            found.append(profile.id)
    return found


def _policy_refs(scene_type: str) -> list[str]:
    refs = list(DEFAULT_POLICY_REFS)
    refs.append("POLICY_RELATIONSHIP_NOT_EXPOSITION")
    if scene_type == "introduction":
        refs.append("POLICY_NO_QUEST_RESOLUTION_IN_INTRO")
    if scene_type in {"introduction", "consequence"}:
        refs.append("POLICY_HOUSE_ORDINARY_LIFE")
    return refs


def _scene_requirements(scene_type: str, primary: CharacterProfile, related: list[CharacterProfile], predecessor: dict | None) -> list[str]:
    reqs = []
    if scene_type == "introduction" and related and related[0].district != primary.district:
        reqs.append(f"Justify {related[0].name}'s presence from compiled reason_for_presence; do not treat them as a random visitor.")
    if scene_type == "district_group":
        reqs.append(f"Keep the argument about {primary.district}, not a touring party of unrelated specialists.")
    if scene_type == "quest":
        reqs.append("The alternate solution must remain available and change who trusts the player even if the material result is similar.")
    if scene_type == "consequence":
        pred = predecessor["scene_id"] if predecessor else "the bound predecessor"
        reqs.append(f"Open from the state left by {pred}; do not re-explain that scene.")
        reqs.append("If a named relationship change is the point, that person must be present, discussed from known state, or shown through a causally connected proxy.")
    if scene_type == "secret_pressure":
        reqs.append("Keep the secret in subtext unless reveal_policy.primary_secret_may_be_revealed is true.")
    return reqs


def _quest_material(primary: CharacterProfile) -> dict:
    return {
        "hook": primary["Quest_Hook"],
        "complication": primary["Quest_Complication"],
        "alternate_solution": primary["Quest_Alternate_Solution"],
        "primary_solution": (
            f"Follow {primary.name}'s {primary['Village_Role'].lower()} work at {primary['Home_or_Base']} until "
            f"{primary['Secret']} is checkable, then decide who pays the cost described in the complication."
        ),
        "player_does": f"Inspect {primary['Home_or_Base']} and test {primary['Village_Role'].lower()} claims against physical traces.",
        "enabler": f"{primary['Key_Ally']}'s {primary['Puzzle_Clue_Source'] or 'knowledge'} and the prized object: {primary['Prized_Object']}",
        "who_benefits": primary["Dependent_or_Responsibility"] or primary["Key_Ally"],
        "who_pays": primary["Key_Rival"],
        "relationship_after": primary["Post_Quest_State"],
    }


def _build_manifest(
    *,
    scene_id: str,
    scene_type: str,
    primary: CharacterProfile,
    participant_ids: list[str],
    by_id: dict[str, CharacterProfile],
    edges: list[RelationshipEdge],
    rels: dict[str, list[RelationshipEdge]],
    seed: int,
    ordinal: int,
    predecessor: dict | None = None,
) -> dict:
    participants = [by_id[i] for i in participant_ids]
    related = [p for p in participants if p.id != primary.id]
    reveal_secret = scene_type == "secret_pressure" and primary.tier in {"Major", "Supporting"}
    objectives = {p.id: p["Immediate_Want"] for p in participants}
    private_facts = {p.id: [p["Secret"], p["Protective_Lie"]] for p in participants}
    forbidden = [] if reveal_secret else [f"Do not explicitly reveal {primary.name}'s secret: {primary['Secret']}"]
    presence_reasons = {}
    for p in participants:
        if p.id == primary.id:
            presence_reasons[p.id] = f"Primary: this is {primary.name}'s scene at {primary.location}."
            continue
        reason = _presence_reason(primary, p, _edge_between(rels, primary.id, p.id))
        if not reason and predecessor and p.id in predecessor.get("participant_ids", []):
            reason = (
                f"Causally present because they shared predecessor {predecessor['scene_id']} "
                f"({predecessor.get('scene_type')}) with {primary.name}."
            )
        presence_reasons[p.id] = reason

    outcomes = [
        "player_gains_or_corrects_knowledge",
        "relationship_improves_or_worsens_for_a_specific_reason",
        "player_defers_or_redirects_the_issue_without_erasing_it",
    ]
    if scene_type == "quest":
        outcomes.extend(["quest_stage_advances", "alternate_solution_becomes_available"])
    if scene_type == "consequence":
        outcomes.append("prior_choice_is_acknowledged_without_repeating_the_old_scene")

    if scene_type == "consequence" and predecessor:
        pred_primary = predecessor["primary_character_id"]
        trigger = {
            "kind": "prior_scene_receipt",
            "required_scene_id": predecessor["scene_id"],
            "required_outcome_id": "OUTCOME_RELATIONSHIP_OR_QUEST_CHANGE",
            "required_effects": [
                {
                    "type": "relationship",
                    "target": pred_primary if pred_primary != primary.id else (related[0].id if related else primary.id),
                    "minimum_state": 1,
                }
            ],
            "must_be_true": [
                "canonical game state matches the compiled packet",
                f"scene {predecessor['scene_id']} has already resolved",
            ],
        }
    else:
        trigger = {
            "kind": {
                "introduction": "first_meaningful_contact",
                "relationship": "relationship_pressure",
                "quest": "cause_or_quest_stage",
                "secret_pressure": "private_fact_pressure",
                "district_group": "shared_local_pressure",
                "consequence": "prior_scene_receipt",
            }[scene_type],
            "must_be_true": ["all listed participants are present or validly reachable", "canonical game state matches the compiled packet"],
        }

    return {
        "schema_version": "dmb-scene-manifest-v2",
        "scene_id": scene_id,
        "scene_type": scene_type,
        "generation": {"seed": seed, "ordinal": ordinal},
        "location": primary.location,
        "district": primary.district,
        "primary_character_id": primary.id,
        "participant_ids": participant_ids,
        "presence_reasons": presence_reasons,
        "participant_profiles": [_pview(p, presence_reasons.get(p.id, "")) for p in participants],
        "trigger": trigger,
        "dramatic_problem": _scene_problem(scene_type, primary, related, predecessor),
        "character_objectives": objectives,
        "relationship_context": _relationship_context(participant_ids, edges),
        "knowledge_boundaries": {p.id: p["Knowledge_Boundary"] for p in participants},
        "private_facts_for_writer_only": private_facts,
        "reveal_policy": {
            "primary_secret_may_be_revealed": reveal_secret,
            "policy_ref": "POLICY_PRIVATE_FACT_REVEAL",
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
        "quest_material": _quest_material(primary),
        "puzzle_material": {
            "type": primary["Puzzle_Type"],
            "logic": primary["Puzzle_Logic"],
            "clue_source": primary["Puzzle_Clue_Source"],
            "failure_or_recovery": primary["Failure_or_Recovery"],
        },
        "policy_refs": _policy_refs(scene_type),
        "scene_requirements": _scene_requirements(scene_type, primary, related, predecessor),
        "coverage_tags": [scene_type, primary.tier.lower(), primary.district, primary["Village_Role"]],
    }


def _pick_predecessor(primary: CharacterProfile, manifests: list[dict], by_name: dict[str, CharacterProfile]) -> dict | None:
    named = set(_names_in_text(primary["Post_Quest_State"], by_name)) | {primary.id}
    ranked: list[tuple[int, dict]] = []
    for manifest in manifests:
        if manifest["scene_type"] == "consequence":
            continue
        participants = set(manifest["participant_ids"])
        if primary.id not in participants and not (named & participants):
            continue
        score = 0
        if manifest["scene_type"] == "quest":
            score += 5
        elif manifest["scene_type"] == "relationship":
            score += 4
        elif manifest["scene_type"] == "secret_pressure":
            score += 3
        if primary.id == manifest["primary_character_id"]:
            score += 3
        if primary.id in participants:
            score += 2
        if named & participants:
            score += 2
        ranked.append((score, manifest))
    ranked.sort(key=lambda item: (-item[0], item[1]["scene_id"]))
    return ranked[0][1] if ranked else (manifests[0] if manifests else None)


def generate_scene_manifests(profiles: Iterable[CharacterProfile], edges: Iterable[RelationshipEdge], *, target_scenes: int = 300, seed: int = 1337) -> list[dict]:
    profiles = list(profiles)
    edges = list(edges)
    if target_scenes < len(profiles):
        raise ValueError(f"target_scenes must be at least the character count ({len(profiles)})")

    rng = random.Random(seed)
    by_id = {p.id: p for p in profiles}
    by_name = {p.name: p for p in profiles}
    rels = _relation_lookup(edges)
    manifests: list[dict] = []

    def add(scene_type: str, primary: CharacterProfile, participant_count: int, predecessor: dict | None = None, forced: list[str] | None = None) -> None:
        ordinal = len(manifests) + 1
        ids = _participant_ids(
            primary, rels, by_id, count=participant_count, rng=rng, scene_type=scene_type, forced=forced,
        )
        manifests.append(
            _build_manifest(
                scene_id=_sid(seed, ordinal, scene_type, primary.id),
                scene_type=scene_type,
                primary=primary,
                participant_ids=ids,
                by_id=by_id,
                edges=edges,
                rels=rels,
                seed=seed,
                ordinal=ordinal,
                predecessor=predecessor,
            )
        )

    for profile in sorted(profiles, key=lambda p: p.id):
        add("introduction", profile, 2)

    remaining = target_scenes - len(manifests)
    relationship_budget = min(65, max(0, remaining))
    seen_pairs: set[tuple[str, str]] = set()
    relationship_candidates: list[tuple[int, CharacterProfile]] = []
    for edge in edges:
        pair = tuple(sorted((edge.source_id, edge.target_id)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        relationship_candidates.append((edge.dramatic_weight, by_id[edge.source_id]))
    relationship_candidates.sort(key=lambda item: (-item[0], item[1].id))
    for _, profile in relationship_candidates[:relationship_budget]:
        add("relationship", profile, 2 if profile.tier == "Minor" else 3)

    quest_budget = min(64, max(0, target_scenes - len(manifests)))
    quest_pool = sorted((p for p in profiles if p.tier in {"Major", "Supporting"}), key=lambda p: (-TIER_WEIGHT[p.tier], p.id))
    for profile in quest_pool[:quest_budget]:
        add("quest", profile, 3)

    secret_budget = min(35, max(0, target_scenes - len(manifests)))
    secret_pool = sorted((p for p in profiles if p.tier in {"Major", "Supporting"}), key=lambda p: (-TIER_WEIGHT.get(p.tier, 1), p.id))
    majors = [p for p in secret_pool if p.tier == "Major"]
    supports = [p for p in secret_pool if p.tier == "Supporting"]
    rng.shuffle(majors)
    rng.shuffle(supports)
    for profile in (majors + supports)[:secret_budget]:
        add("secret_pressure", profile, 3)

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

    coverage = Counter(m["primary_character_id"] for m in manifests)
    while len(manifests) < target_scenes:
        minimum = min(coverage.get(p.id, 0) for p in profiles)
        candidates = [p for p in profiles if coverage.get(p.id, 0) == minimum]
        candidates.sort(key=lambda p: (-TIER_WEIGHT.get(p.tier, 1), p.id))
        primary = rng.choice(candidates[: min(12, len(candidates))])
        predecessor = _pick_predecessor(primary, manifests, by_name)
        forced: list[str] = []
        if predecessor:
            forced.extend(pid for pid in predecessor["participant_ids"] if pid != primary.id)
        forced.extend(_names_in_text(primary["Post_Quest_State"], by_name))
        add("consequence", primary, 2 if primary.tier == "Minor" else 3, predecessor=predecessor, forced=forced)
        coverage[primary.id] += 1

    _ensure_appearance_floor(manifests, profiles, by_id, rels, edges)
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
    payload = {"schema_version": "dmb-scene-catalogue-v2", "scenes": list(manifests)}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rebuild_participants(manifest: dict, participant_ids: list[str], by_id: dict[str, CharacterProfile], rels, edges, predecessor=None) -> None:
    primary = by_id[manifest["primary_character_id"]]
    related = [by_id[pid] for pid in participant_ids if pid != primary.id]
    presence_reasons = {}
    for pid in participant_ids:
        profile = by_id[pid]
        if pid == primary.id:
            presence_reasons[pid] = f"Primary: this is {primary.name}'s scene at {primary.location}."
            continue
        reason = _presence_reason(primary, profile, _edge_between(rels, primary.id, pid))
        if not reason and predecessor and pid in predecessor.get("participant_ids", []):
            reason = f"Causally present because they shared predecessor {predecessor['scene_id']} with {primary.name}."
        if not reason and profile.district == primary.district:
            reason = f"Resident/worker in {primary.district}, added to restore appearance coverage."
        presence_reasons[pid] = reason
    manifest["participant_ids"] = participant_ids
    manifest["presence_reasons"] = presence_reasons
    manifest["participant_profiles"] = [_pview(by_id[pid], presence_reasons.get(pid, "")) for pid in participant_ids]
    manifest["character_objectives"] = {pid: by_id[pid]["Immediate_Want"] for pid in participant_ids}
    manifest["knowledge_boundaries"] = {pid: by_id[pid]["Knowledge_Boundary"] for pid in participant_ids}
    manifest["private_facts_for_writer_only"] = {pid: [by_id[pid]["Secret"], by_id[pid]["Protective_Lie"]] for pid in participant_ids}
    manifest["relationship_context"] = _relationship_context(participant_ids, edges)
    related_profiles = [by_id[pid] for pid in participant_ids if pid != primary.id]
    manifest["dramatic_problem"] = _scene_problem(manifest["scene_type"], primary, related_profiles, predecessor)
    manifest["scene_requirements"] = _scene_requirements(manifest["scene_type"], primary, related, predecessor)


def _ensure_appearance_floor(manifests: list[dict], profiles: list[CharacterProfile], by_id: dict[str, CharacterProfile], rels, edges) -> None:
    floor = 4
    by_name = {p.name: p for p in profiles}

    def appearances() -> Counter:
        return Counter(pid for m in manifests for pid in m["participant_ids"])

    counts = appearances()
    needy = sorted((p for p in profiles if counts[p.id] < floor), key=lambda p: (counts[p.id], p.id))
    for profile in needy:
        needed = floor - counts[profile.id]
        candidates = [
            m for m in manifests
            if m["district"] == profile.district
            and profile.id not in m["participant_ids"]
            and m["scene_type"] in {"district_group", "relationship", "quest", "secret_pressure", "consequence"}
        ]
        candidates.sort(key=lambda m: (0 if m["scene_type"] == "district_group" else 1, m["scene_id"]))
        for manifest in candidates:
            if needed <= 0:
                break
            current = list(manifest["participant_ids"])
            surplus = [pid for pid in current[1:] if appearances()[pid] > floor + 2]
            if surplus:
                surplus.sort(key=lambda pid: (-appearances()[pid], pid))
                current[current.index(surplus[0])] = profile.id
            elif len(current) < 4 and manifest["scene_type"] in {"district_group", "quest", "secret_pressure", "consequence"}:
                current.append(profile.id)
            else:
                continue
            pred = None
            if manifest["scene_type"] == "consequence":
                pred = next((m for m in manifests if m["scene_id"] == (manifest.get("trigger") or {}).get("required_scene_id")), None)
            _rebuild_participants(manifest, current, by_id, rels, edges, predecessor=pred)
            needed -= 1
            counts = appearances()

