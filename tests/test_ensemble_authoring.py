from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dialogue_generation.ensemble.profiles import load_profiles
from dialogue_generation.ensemble.relationship_graph import build_relationship_graph
from dialogue_generation.ensemble.scene_manifest_generator import generate_scene_manifests
from dialogue_generation.ensemble.validation import validate_ensemble


PROFILE_CSV = ROOT / "docs" / "characters" / "DMB_Character_Profiles_88_Disco_Elysium_Depth.csv"


def test_profile_and_relationship_counts():
    profiles = load_profiles(PROFILE_CSV)
    edges = build_relationship_graph(profiles)
    assert len(profiles) == 88
    assert len(edges) >= 300
    assert all(edge.source_id != edge.target_id for edge in edges)


def test_scene_generation_is_deterministic_and_valid():
    profiles = load_profiles(PROFILE_CSV)
    edges = build_relationship_graph(profiles)
    a = generate_scene_manifests(profiles, edges, target_scenes=300, seed=1337)
    b = generate_scene_manifests(profiles, edges, target_scenes=300, seed=1337)
    assert a == b
    assert len(a) == 300
    report = validate_ensemble(profiles, edges, a)
    assert report["valid"], report["errors"]
    assert report["stats"]["characters"] == 88
    assert report["stats"]["scenes"] == 300
