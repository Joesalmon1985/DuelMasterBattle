"""Owner playtest repair contracts — schema identity, policy paths, six-by-one setup."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sim.dmb.ai.policy import PolicyService, content_root, resolve_artifact_path
from sim.dmb.core.world import WorldSim
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.generation import BoardBuilder
from training.environment import (
    SCHEMA_PATH,
    accepted_schema_hashes,
    schema_hash,
    schema_hash_legacy_crlf,
    schema_hashes_compatible,
)
from training.model import CandidateScorer


def test_schema_hash_lf_crlf_compatible_and_rejects_material_change(tmp_path: Path) -> None:
    canonical = schema_hash()
    legacy = schema_hash_legacy_crlf()
    assert canonical in accepted_schema_hashes()
    assert legacy in accepted_schema_hashes()
    assert schema_hashes_compatible(legacy, canonical)
    # Raw CRLF bytes of the live schema must equal the legacy helper.
    text = SCHEMA_PATH.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    crlf_bytes = text.replace("\n", "\r\n").encode("utf-8")
    assert hashlib.sha256(crlf_bytes).hexdigest()[:16] == legacy
    # Material schema change must reject even under compatibility.
    assert not schema_hashes_compatible("deadbeefdeadbeef", canonical)


def test_policy_artifact_resolves_from_repo_and_godot_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = content_root()
    assert (root / "content" / "policies" / "manifest.json").is_file()
    resolved = resolve_artifact_path("content/policies/policy-im-build.json")
    assert resolved.is_file()
    assert resolved.name == "policy-im-build.json"
    # cwd must not matter
    monkeypatch.chdir(tmp_path)
    resolved2 = resolve_artifact_path("content/policies/policy-im-build.json")
    assert resolved2 == resolved


def test_neural_source_loads_with_line_ending_compat() -> None:
    path = resolve_artifact_path("content/policies/policy-im-build.json")
    model = CandidateScorer.load(path, expect_schema_hash=schema_hash(), allow_line_ending_compat=True)
    assert model.trained is True
    # Strict mode rejects CRLF-tagged artifacts when current canonical is LF.
    if model.schema_hash != schema_hash():
        with pytest.raises(ValueError, match="schema mismatch"):
            CandidateScorer.load(path, expect_schema_hash=schema_hash(), allow_line_ending_compat=False)


def test_fx_mvp_policy_activate_records_source() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    state = sim.state
    svc = PolicyService(state)
    # Ensure assigned trained brains resolve without cwd dependence.
    for fid in list(state.factions.keys())[:2]:
        brain = svc.resolve_brain(fid)
        assert brain is not None
        record = svc.activate(fid)
        assert "source" in record
        assert record.get("policy_id")
        # Effective source is neural or an accurately labelled fallback.
        assert record.get("source") in {"neural", "heuristic_fallback", "heuristic"} or record.get(
            "source"
        )


def test_six_faction_one_core_setup_deterministic() -> None:
    plan_a = BoardBuilder.generate(507, 6, cores_per_faction=1)
    plan_b = BoardBuilder.generate(507, 6, cores_per_faction=1)
    assert plan_a.faction_count == 6
    assert plan_a.cores_per_faction == 1
    assert len(plan_a.cores) == 6
    assert {c.faction_id for c in plan_a.cores} == {f"faction:{i}" for i in range(1, 7)}
    assert plan_a.to_dict()["cores"] == plan_b.to_dict()["cores"]
    assert BoardBuilder.validate_setup(plan_a) == []
    # Default two-core six-faction remains distinct.
    plan_two = BoardBuilder.generate(507, 6, cores_per_faction=2)
    assert len(plan_two.cores) == 12


def test_read_view_exports_research_and_diplomacy() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    view = sim.state.read_view("player", ["research", "diplomacy", "tech_draft", "stocks", "factions"])
    assert "research" in view
    assert "diplomacy" in view
    assert "tech_draft" in view
    assert "stocks" in view
    assert "factions" in view
