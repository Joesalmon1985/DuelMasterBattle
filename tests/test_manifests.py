from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "godot_project" / "content" / "manifests"
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_source_manifest_hashes_match_files() -> None:
    manifest = _json(MANIFESTS / "sources.json")
    assert manifest["hash_algorithm"] == "sha256"
    assert manifest["sources"]
    for source in manifest["sources"]:
        path = ROOT / source["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == source["sha256"], source["path"]


def test_build_profiles_do_not_claim_completion() -> None:
    development = _json(MANIFESTS / "development.json")
    mvp = _json(MANIFESTS / "mvp.json")
    full = _json(MANIFESTS / "full_baseline.json")
    assert "NOT_COMPLETION_CLAIM" in development["status"]
    assert mvp["status"] == "TARGET_NOT_YET_IMPLEMENTED"
    assert full["status"] == "TARGET_NOT_YET_IMPLEMENTED"
    assert mvp["completion_claim"] is False
    assert full["completion_claim"] is False


def test_profiles_preserve_locked_scope_boundaries() -> None:
    development = _json(MANIFESTS / "development.json")
    mvp = _json(MANIFESTS / "mvp.json")
    full = _json(MANIFESTS / "full_baseline.json")
    assert development["runtime_dependencies"]["internet"] is False
    assert development["runtime_dependencies"]["llm"] is False
    assert development["rules"]["wizard_has_hp_mana_xp"] is False
    assert development["rules"]["permanent_ten_recipe_culture_limit"] is False
    assert mvp["catalogue"]["full_240_recipe_catalogue_preserved"] is True
    assert full["required"]["processor_definitions"] == 240


def test_all_34_invariants_have_planned_owners_and_proof() -> None:
    rule_map = _json(TRACKING / "rule_map.json")
    invariants = rule_map["invariants"]
    assert [entry["id"] for entry in invariants] == list(range(1, 35))
    for entry in invariants:
        assert entry["contracts"]
        assert entry["owners"]
        assert entry["proof"]
