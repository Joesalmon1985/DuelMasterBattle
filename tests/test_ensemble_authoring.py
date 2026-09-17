from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dialogue_generation.ensemble.profiles import load_profiles
from dialogue_generation.ensemble.quality import build_quality_report
from dialogue_generation.ensemble.relationship_graph import (
    MAX_RESPONSIBILITY_INDEGREE,
    MIN_RESPONSIBILITY_TARGETS,
    build_relationship_graph,
)
from dialogue_generation.ensemble.scene_manifest_generator import generate_scene_manifests
from dialogue_generation.ensemble.validation import validate_ensemble


PROFILE_CSV = ROOT / "docs" / "characters" / "DMB_Character_Profiles_88_Disco_Elysium_Depth.csv"


def _build():
    profiles = load_profiles(PROFILE_CSV)
    edges = build_relationship_graph(profiles)
    manifests = generate_scene_manifests(profiles, edges, target_scenes=300, seed=1337)
    return profiles, edges, manifests


def test_profile_and_relationship_counts():
    profiles, edges, _ = _build()
    assert len(profiles) == 88
    assert len(edges) == 352
    assert all(edge.source_id != edge.target_id for edge in edges)
    rel_ids = [edge.relationship_id for edge in edges]
    assert len(rel_ids) == len(set(rel_ids))


def test_scene_generation_is_deterministic_and_valid():
    profiles, edges, a = _build()
    b = generate_scene_manifests(profiles, edges, target_scenes=300, seed=1337)
    assert a == b
    assert len(a) == 300
    report = validate_ensemble(profiles, edges, a)
    assert report["valid"], report["errors"]
    assert report["stats"]["characters"] == 88
    assert report["stats"]["scenes"] == 300


def test_psychological_diversity_and_depth_fields():
    profiles = load_profiles(PROFILE_CSV)
    majors = [p for p in profiles if p.tier == "Major"]
    for field in ("Central_Contradiction", "Core_Fear", "False_Belief"):
        assert len({p[field] for p in majors}) == len(majors)
        counts = Counter(p[field] for p in profiles)
        assert max(counts.values()) <= (3 if field == "Central_Contradiction" else 4)
    for profile in profiles:
        assert profile["Formative_Event"]
        assert profile["Cross_District_Reason"]
        blob = " ".join(
            profile[field]
            for field in (
                "Core_Fear",
                "Immediate_Want",
                "Central_Contradiction",
                "Secret",
                "Formative_Event",
                "Quest_Hook",
                "Village_Role",
            )
        )
        token = profile["Village_Role"].split("/")[0].strip().lower()
        assert (
            profile["Home_or_Base"].lower() in blob.lower()
            or token in blob.lower()
            or profile.district.split("&")[0].strip().lower() in blob.lower()
        )


def test_cross_district_and_responsibility_caps():
    profiles, edges, _ = _build()
    ids = {p.id for p in profiles}
    resp = [e for e in edges if e.relation_type == "responsibility"]
    assert all(e.source_id in ids and e.target_id in ids for e in edges)
    assert all(e.source_district != e.target_district and not e.same_district for e in edges if e.relation_type == "cross_district")
    assert len({e.target_id for e in resp}) >= MIN_RESPONSIBILITY_TARGETS
    indeg = Counter(e.target_id for e in resp)
    assert max(indeg.values()) <= MAX_RESPONSIBILITY_INDEGREE
    assert all(e.shared_history and e.origin_event and e.reason_for_presence for e in edges)


def test_scene_presence_policies_and_consequences():
    profiles, edges, manifests = _build()
    by_id = {p.id: p for p in profiles}
    scene_ids = {m["scene_id"] for m in manifests}
    intros = [m for m in manifests if m["scene_type"] == "introduction"]
    assert len(intros) == 88
    for manifest in manifests:
        assert manifest.get("policy_refs")
        for pid in manifest["participant_ids"]:
            if by_id[pid].district != manifest["district"]:
                assert (manifest.get("presence_reasons") or {}).get(pid)
        if manifest["scene_type"] == "consequence":
            trigger = manifest["trigger"]
            assert trigger["kind"] == "prior_scene_receipt"
            assert trigger["required_scene_id"] in scene_ids
            assert trigger["required_scene_id"] != manifest["scene_id"]
            assert trigger["required_outcome_id"]
            assert trigger["required_effects"]
            for effect in trigger["required_effects"]:
                assert effect["target"] in by_id
    quality = build_quality_report(profiles, edges, manifests)
    assert quality["pass"], quality["flags"]
    report_path = ROOT / "tools" / "dialogue_generation" / "ensemble" / "quality_baseline.json"
    baseline = json.loads(report_path.read_text(encoding="utf-8"))
    assert quality["relationships"]["distinct_responsibility_targets"] > baseline["relationships"]["distinct_responsibility_targets"]
    assert quality["profiles"]["psychological_fields"][2]["unique"] > baseline["profiles"]["psychological_fields"][2]["unique"]
