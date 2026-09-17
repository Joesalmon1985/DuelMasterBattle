"""Repeatable quality analysis for ensemble profiles, relationships and scenes."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .policies import DEFAULT_POLICY_REFS
from .profiles import CharacterProfile
from .relationship_graph import RelationshipEdge

PSYCH_FIELDS = (
    "Core_Desire",
    "Immediate_Want",
    "Core_Fear",
    "Shame_or_Vulnerability",
    "False_Belief",
    "Central_Contradiction",
    "Moral_Boundary",
    "Secret",
    "Protective_Lie",
    "Post_Quest_State",
)

DEPTH_FIELDS = (
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
)

TEMPLATE_PHRASES = (
    "this link exists so quests can leave",
    "in a way that can produce care, control, resentment or sacrifice",
    "sees the part of",
    "preferred explanation of events",
    "without inventing a stranger",
    "a non-confrontational route should exist",
    "being publicly exposed as less competent than their role requires",
    "to protect the part of village life they understand best",
    "wants a missing object, record or resource recovered",
)

NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
GENERIC_REQUIREMENT_RE = re.compile(
    r"No character may state knowledge outside|Do not add arbitrary script effects|At least one line or action must reveal relationship",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _mask_names(text: str, names: Iterable[str]) -> str:
    masked = text or ""
    for name in sorted(set(names), key=len, reverse=True):
        if name:
            masked = re.sub(re.escape(name), "{NAME}", masked)
    masked = NAME_RE.sub("{NAME}", masked)
    return _norm(masked)


def _near_duplicates(values: list[str], *, threshold: float = 0.84, limit: int = 25) -> list[dict[str, Any]]:
    items = [(i, values[i], _norm(values[i])) for i in range(len(values)) if values[i].strip()]
    found: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for i, raw_a, a in items:
        for j, raw_b, b in items:
            if j <= i or not a or a == b:
                continue
            if abs(len(a) - len(b)) > max(40, int(0.35 * max(len(a), len(b)))):
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= threshold:
                pair = (i, j)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                found.append({"left": raw_a, "right": raw_b, "similarity": round(ratio, 3)})
                if len(found) >= limit:
                    return found
    return found


def _field_duplication(profiles: list[CharacterProfile], field: str) -> dict[str, Any]:
    values = [p[field].strip() for p in profiles]
    nonempty = [v for v in values if v]
    counts = Counter(nonempty)
    repeats = [{"value": value, "count": count} for value, count in counts.most_common() if count > 1]
    return {
        "field": field,
        "populated": len(nonempty),
        "unique": len(set(nonempty)),
        "most_repeated": repeats[:8],
        "repeat_count": len(repeats),
        "near_duplicates": _near_duplicates(nonempty),
    }


def _profile_quality(profiles: list[CharacterProfile]) -> dict[str, Any]:
    majors = [p for p in profiles if p.tier == "Major"]
    flags: list[str] = []
    psych = [_field_duplication(profiles, field) for field in PSYCH_FIELDS]
    depth_present = [field for field in DEPTH_FIELDS if any(p[field].strip() for p in profiles)]
    depth = [_field_duplication(profiles, field) for field in depth_present]

    def _major_ident(field: str) -> list[str]:
        counts = Counter(p[field].strip() for p in majors if p[field].strip())
        return [value for value, count in counts.items() if count > 1]

    for field in ("Central_Contradiction", "Core_Fear", "False_Belief"):
        shared = _major_ident(field)
        if shared:
            flags.append(f"Major characters share identical {field}: {shared[:5]}")

    def _cap(field: str, cap: int) -> None:
        counts = Counter(p[field].strip() for p in profiles if p[field].strip())
        offenders = {value: count for value, count in counts.items() if count > cap}
        if offenders:
            flags.append(f"{field} exceeds cap {cap}: {list(offenders.items())[:5]}")

    _cap("Central_Contradiction", 3)
    _cap("Core_Fear", 4)
    _cap("False_Belief", 4)

    pasteable = []
    occupation_tokens = {p["Village_Role"].split("/")[0].strip().lower() for p in profiles}
    for profile in profiles:
        blob = " ".join(profile[field] for field in PSYCH_FIELDS + DEPTH_FIELDS)
        specific = any(
            token and token in blob.lower()
            for token in (
                profile["Village_Role"].split("/")[0].strip().lower(),
                profile["Home_or_Base"].lower(),
                profile.district.split("&")[0].strip().lower(),
            )
        )
        if not specific:
            pasteable.append(profile.id)
    if pasteable:
        flags.append(f"Characters whose psychology lacks occupation/place specificity: {pasteable[:12]}")

    return {
        "character_count": len(profiles),
        "major_count": len(majors),
        "psychological_fields": psych,
        "depth_fields": depth,
        "missing_depth_fields": [field for field in DEPTH_FIELDS if field not in depth_present],
        "occupation_token_count": len(occupation_tokens),
        "flags": flags,
    }


def _relationship_quality(profiles: list[CharacterProfile], edges: list[RelationshipEdge]) -> dict[str, Any]:
    by_id = {p.id: p for p in profiles}
    type_counts = Counter(e.relation_type for e in edges)
    outgoing = Counter(e.source_id for e in edges)
    incoming = Counter(e.target_id for e in edges)
    resp_in = Counter(e.target_id for e in edges if e.relation_type == "responsibility")
    resp_targets = sorted(resp_in)
    reciprocity = Counter(e.reciprocity for e in edges)
    flagged: list[str] = []

    xd_same = []
    xd_true = 0
    for edge in edges:
        if edge.relation_type != "cross_district":
            continue
        if edge.source_district == edge.target_district or edge.same_district:
            xd_same.append(
                {
                    "relationship_id": edge.relationship_id,
                    "source": edge.source_name,
                    "target": edge.target_name,
                    "district": edge.source_district,
                }
            )
        else:
            xd_true += 1

    descriptions = [getattr(edge, "source_description", "") or getattr(edge, "shared_history", "") for edge in edges]
    desc_counts = Counter(_norm(d) for d in descriptions if d.strip())
    exact_desc_repeats = [{"value": value, "count": count} for value, count in desc_counts.most_common() if count > 1]
    names = [p.name for p in profiles]
    masked_desc = Counter(_mask_names(d, names) for d in descriptions if d.strip())
    pattern_repeats = [{"pattern": pat, "count": n} for pat, n in masked_desc.most_common(12) if n > 1]

    lacking_history = []
    for edge in edges:
        blob = " ".join(
            str(getattr(edge, field, "") or "")
            for field in (
                "source_description",
                "origin_event",
                "shared_history",
                "private_truth",
                "reason_for_presence",
                "reason_relationship_matters_now",
            )
        ).lower()
        if any(phrase in blob for phrase in TEMPLATE_PHRASES) or len(blob.strip()) < 80:
            lacking_history.append(edge.relationship_id)

    hubs = [
        {"character_id": cid, "name": by_id[cid].name if cid in by_id else cid, "incoming": incoming[cid], "outgoing": outgoing[cid]}
        for cid, _ in incoming.most_common(8)
    ]
    max_resp = max(resp_in.values()) if resp_in else 0
    if len(resp_targets) < 30:
        flagged.append(f"Only {len(resp_targets)} distinct responsibility targets (need >= 30)")
    over = {cid: n for cid, n in resp_in.items() if n > 4}
    if over:
        flagged.append(f"Responsibility indegree exceeds 4 without counting overrides: {over}")

    degrees = {
        p.id: {
            "name": p.name,
            "tier": p.tier,
            "district": p.district,
            "incoming": incoming[p.id],
            "outgoing": outgoing[p.id],
            "responsibility_indegree": resp_in[p.id],
        }
        for p in profiles
    }

    return {
        "edge_count": len(edges),
        "counts_by_type": dict(type_counts),
        "reciprocity": dict(reciprocity),
        "distinct_responsibility_targets": len(resp_targets),
        "responsibility_targets": resp_targets,
        "max_responsibility_indegree": max_resp,
        "responsibility_indegree": dict(resp_in),
        "cross_district_true": xd_true,
        "cross_district_same_district_failures": xd_same,
        "exact_description_repeats": exact_desc_repeats[:10],
        "masked_description_patterns": pattern_repeats,
        "relationships_lacking_specific_history": lacking_history,
        "hubs": hubs,
        "degrees": degrees,
        "flags": flagged + ([f"{len(xd_same)} cross_district edges join same-district characters"] if xd_same else []),
    }


def _unexplained_off_district(manifest: dict, by_id: dict[str, CharacterProfile]) -> list[str]:
    district = manifest.get("district")
    unexplained: list[str] = []
    reasons = manifest.get("presence_reasons") or {}
    for pid in manifest.get("participant_ids", []):
        profile = by_id.get(pid)
        if profile is None:
            continue
        if profile.district == district:
            continue
        reason = reasons.get(pid) or next(
            (
                p.get("presence_reason")
                for p in manifest.get("participant_profiles", [])
                if p.get("character_id") == pid
            ),
            "",
        )
        if not str(reason).strip():
            unexplained.append(pid)
    return unexplained


def _scene_quality(profiles: list[CharacterProfile], edges: list[RelationshipEdge], manifests: list[dict]) -> dict[str, Any]:
    by_id = {p.id: p for p in profiles}
    names = [p.name for p in profiles]
    type_counts = Counter(m.get("scene_type") for m in manifests)
    primary = Counter(m.get("primary_character_id") for m in manifests)
    appearances = Counter(pid for m in manifests for pid in m.get("participant_ids", []))
    off_by_type: dict[str, int] = Counter()
    unexplained: list[dict[str, Any]] = []
    intro_outsiders: list[str] = []
    district_outsiders: list[str] = []
    problems = []
    hooks = []
    alts = []
    reqs = []
    generic_req_scenes = 0
    consequence_missing = []
    consequence_valid = 0
    scene_ids = {m.get("scene_id") for m in manifests}

    for manifest in manifests:
        scene_type = manifest.get("scene_type")
        unexplained_ids = _unexplained_off_district(manifest, by_id)
        if unexplained_ids:
            off_by_type[scene_type] += 1
            unexplained.append({"scene_id": manifest.get("scene_id"), "scene_type": scene_type, "ids": unexplained_ids})
            if scene_type == "introduction":
                intro_outsiders.append(manifest.get("scene_id"))
            if scene_type == "district_group":
                district_outsiders.append(manifest.get("scene_id"))
        problems.append(manifest.get("dramatic_problem") or "")
        quest = manifest.get("quest_material") or {}
        hooks.append(quest.get("hook") or "")
        alts.append(quest.get("alternate_solution") or "")
        for req in manifest.get("scene_requirements") or []:
            reqs.append(req)
            if GENERIC_REQUIREMENT_RE.search(str(req)):
                generic_req_scenes += 1
                break
        if scene_type == "consequence":
            trigger = manifest.get("trigger") or {}
            pred = trigger.get("required_scene_id")
            outcome = trigger.get("required_outcome_id")
            effects = trigger.get("required_effects") or []
            if not pred or pred not in scene_ids or not outcome or not effects:
                consequence_missing.append(manifest.get("scene_id"))
            else:
                consequence_valid += 1

    def _repeat_table(values: list[str], *, mask: bool = False) -> list[dict[str, Any]]:
        seq = [_mask_names(v, names) if mask else _norm(v) for v in values if v.strip()]
        counts = Counter(seq)
        return [{"value": value, "count": count} for value, count in counts.most_common(12) if count > 1]

    minor_ids = {p.id for p in profiles if p.tier == "Minor"}
    major_ids = {p.id for p in profiles if p.tier == "Major"}
    major_appear = [appearances[i] for i in major_ids]
    minor_flags = []
    if major_appear:
        major_median = sorted(major_appear)[len(major_appear) // 2]
        for pid in minor_ids:
            if appearances[pid] > 3 * max(1, major_median):
                minor_flags.append({"character_id": pid, "appearances": appearances[pid], "major_median": major_median})

    isolated = []
    by_district = defaultdict(list)
    for profile in profiles:
        by_district[profile.district].append(profile.id)
    edge_pairs = {(e.source_id, e.target_id) for e in edges} | {(e.target_id, e.source_id) for e in edges}
    for district, ids in by_district.items():
        for pid in ids:
            if not any((pid, other) in edge_pairs for other in ids if other != pid):
                isolated.append({"character_id": pid, "district": district})

    flags = []
    if unexplained:
        flags.append(f"{len(unexplained)} scenes have unexplained off-district participants")
    if consequence_missing:
        flags.append(f"{len(consequence_missing)} consequence scenes lack valid predecessor bindings")
    if generic_req_scenes:
        flags.append(f"{generic_req_scenes} scenes still duplicate global writer-policy text")

    return {
        "scene_count": len(manifests),
        "scenes_by_type": dict(type_counts),
        "primary_scenes_by_character": dict(primary),
        "appearances_by_character": dict(appearances),
        "off_district_unexplained_by_type": dict(off_by_type),
        "unexplained_off_district_scenes": unexplained,
        "introduction_unexplained_outsiders": intro_outsiders,
        "district_group_unexplained_outsiders": district_outsiders,
        "repeated_dramatic_problem_patterns": _repeat_table(problems, mask=True),
        "repeated_quest_hooks": _repeat_table(hooks, mask=True),
        "repeated_alternate_solutions": _repeat_table(alts, mask=True),
        "repeated_scene_requirements": _repeat_table(reqs, mask=True)[:8],
        "generic_policy_requirement_scenes": generic_req_scenes,
        "consequence_valid_bindings": consequence_valid,
        "consequence_missing_or_invalid": consequence_missing,
        "minor_overrepresentation": minor_flags,
        "district_isolates": isolated,
        "policy_refs_expected": DEFAULT_POLICY_REFS,
        "flags": flags,
    }


def build_quality_report(
    profiles: list[CharacterProfile],
    edges: list[RelationshipEdge],
    manifests: list[dict],
    *,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profiles = list(profiles)
    edges = list(edges)
    manifests = list(manifests)
    profile_q = _profile_quality(profiles)
    rel_q = _relationship_quality(profiles, edges)
    scene_q = _scene_quality(profiles, edges, manifests)
    flags = profile_q["flags"] + rel_q["flags"] + scene_q["flags"]
    report = {
        "schema_version": "dmb-ensemble-quality-v1",
        "pass": not flags,
        "flags": flags,
        "profiles": profile_q,
        "relationships": rel_q,
        "scenes": scene_q,
    }
    if baseline:
        report["delta_from_baseline"] = _delta(baseline, report)
    return report


def _unique_map(report: dict[str, Any]) -> dict[str, int]:
    return {row["field"]: row["unique"] for row in report.get("profiles", {}).get("psychological_fields", [])}


def _delta(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    base_unique = _unique_map(baseline)
    now_unique = _unique_map(current)
    return {
        "unique_psych_fields": {
            field: {"before": base_unique.get(field), "after": now_unique.get(field)}
            for field in PSYCH_FIELDS
        },
        "responsibility_targets": {
            "before": baseline.get("relationships", {}).get("distinct_responsibility_targets"),
            "after": current.get("relationships", {}).get("distinct_responsibility_targets"),
        },
        "max_responsibility_indegree": {
            "before": baseline.get("relationships", {}).get("max_responsibility_indegree"),
            "after": current.get("relationships", {}).get("max_responsibility_indegree"),
        },
        "cross_district_failures": {
            "before": len(baseline.get("relationships", {}).get("cross_district_same_district_failures") or []),
            "after": len(current.get("relationships", {}).get("cross_district_same_district_failures") or []),
        },
        "unexplained_off_district_scenes": {
            "before": len(baseline.get("scenes", {}).get("unexplained_off_district_scenes") or []),
            "after": len(current.get("scenes", {}).get("unexplained_off_district_scenes") or []),
        },
        "consequence_valid_bindings": {
            "before": baseline.get("scenes", {}).get("consequence_valid_bindings"),
            "after": current.get("scenes", {}).get("consequence_valid_bindings"),
        },
        "relationships_lacking_specific_history": {
            "before": len(baseline.get("relationships", {}).get("relationships_lacking_specific_history") or []),
            "after": len(current.get("relationships", {}).get("relationships_lacking_specific_history") or []),
        },
        "repeated_alternate_solutions": {
            "before": (baseline.get("scenes", {}).get("repeated_alternate_solutions") or [{}])[0].get("count"),
            "after": (current.get("scenes", {}).get("repeated_alternate_solutions") or [{}])[0].get("count"),
        },
    }


def render_quality_text(report: dict[str, Any]) -> str:
    lines = ["DMB ensemble quality report", "============================", ""]
    lines.append(f"PASS: {report.get('pass')}")
    if report.get("flags"):
        lines.append("Flags:")
        for flag in report["flags"]:
            lines.append(f"  - {flag}")
        lines.append("")
    lines.append("Psychological unique values:")
    for row in report["profiles"]["psychological_fields"]:
        top = ", ".join(f"{item['count']}×" for item in row["most_repeated"][:3]) or "no repeats"
        lines.append(f"  {row['field']}: {row['unique']}/{row['populated']} unique; repeats={row['repeat_count']}; top={top}")
    rel = report["relationships"]
    lines += [
        "",
        f"Relationships: {rel['edge_count']}",
        f"  types: {rel['counts_by_type']}",
        f"  responsibility targets: {rel['distinct_responsibility_targets']} (max indegree {rel['max_responsibility_indegree']})",
        f"  cross-district integrity failures: {len(rel['cross_district_same_district_failures'])}",
        f"  lacking specific history: {len(rel['relationships_lacking_specific_history'])}",
        "",
    ]
    scene = report["scenes"]
    lines += [
        f"Scenes: {scene['scene_count']} {scene['scenes_by_type']}",
        f"  unexplained off-district: {len(scene['unexplained_off_district_scenes'])}",
        f"  consequence valid bindings: {scene['consequence_valid_bindings']}",
        f"  consequence invalid: {len(scene['consequence_missing_or_invalid'])}",
        f"  generic policy-requirement scenes: {scene['generic_policy_requirement_scenes']}",
    ]
    if report.get("delta_from_baseline"):
        lines.append("")
        lines.append("Delta from baseline:")
        lines.append(json.dumps(report["delta_from_baseline"], indent=2))
    return "\n".join(lines) + "\n"


def write_quality_report(report: dict[str, Any], output_dir: Path | str) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "quality_report.json"
    txt_path = output_dir / "quality_report.txt"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    txt_path.write_text(render_quality_text(report), encoding="utf-8")
    return {"json": json_path, "txt": txt_path}
