from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dialogue_generation.ensemble_writer.auditors import mechanics_audit_local, parse_audit_result, soften_llm_canon_blocks
from dialogue_generation.ensemble_writer.packet_compiler import compile_scene_packet, packet_contains_catalogue
from dialogue_generation.ensemble_writer.pilot import process_scene, resolve_selection, run_pilot
from dialogue_generation.ensemble_writer.selector import MAX_COUNT, select_pilot_scenes, validate_count
from dialogue_generation.ollama_client import OllamaResponse


def _scene(scene_id: str, scene_type: str, primary: str, others: list[str], district: str, tier: str, secret: str = "a private kiln crack from a shortened cooling cycle") -> dict:
    ids = [primary, *others]
    profiles = []
    for index, pid in enumerate(ids):
        profiles.append({
            "character_id": pid,
            "display_name": pid.replace("NPC_", "Name "),
            "role": "Reeve" if index == 0 else "Clerk",
            "narrative_tier": tier if index == 0 else "Supporting",
            "district": district if index == 0 else district,
            "home_or_base": f"{district} Hall",
            "presence_reason": "Works here" if index == 0 else "Same district colleague",
            "voice": {"register": "dry", "sentence_shape": "short", "vocabulary_domain": "records", "verbal_tic": "as far as I saw", "humour_style": "rare", "silence_behaviour": "waits"},
            "psychology": {
                "core_desire": f"keep {district} standing",
                "immediate_want": "a quiet confirmation",
                "core_fear": "the kiln crack becoming public",
                "central_contradiction": "demands honesty while hiding the cooling cycle",
                "moral_boundary": "will not falsify weights",
                "false_belief": "silence keeps the village fed",
                "pressure_behaviour": "talks procedure",
                "repair_behaviour": "does a practical favour",
                "social_mask": "unbothered competence",
                "self_image": "the person who cannot be spared",
                "specific_regret": "shortened the cooling cycle",
                "specific_hope": "the apprentice is not blamed",
                "misjudges_others_by": "treats questions as inspections",
            },
            "knowledge": {"boundary": f"Does not know sealed records outside {district}", "what_they_notice": "rehearsed accounts", "what_they_miss": "how sharp they sound"},
            "private": {"secret": secret, "protective_lie": "this is only a work problem"},
        })
        if index == 1:
            profiles[-1]["district"] = district
    trigger = {"kind": "first_meaningful_contact"}
    if scene_type == "consequence":
        trigger = {
            "kind": "prior_scene_receipt",
            "required_scene_id": "SCN_001_INTRO",
            "required_outcome_id": "OUTCOME_RELATIONSHIP_OR_QUEST_CHANGE",
            "required_effects": [{"type": "relationship", "target": others[0] if others else primary, "minimum_state": 1}],
        }
    return {
        "scene_id": scene_id,
        "scene_type": scene_type,
        "district": district,
        "location": f"{district} Hall",
        "primary_character_id": primary,
        "participant_ids": ids,
        "participant_profiles": profiles,
        "presence_reasons": {pid: "Works in the district" for pid in ids},
        "character_objectives": {pid: "wants the work to continue" for pid in ids},
        "knowledge_boundaries": {pid: f"boundary-{pid}" for pid in ids},
        "private_facts_for_writer_only": {pid: [secret if pid == primary else "a lesser private errand"] for pid in ids},
        "forbidden_revelations": [f"Do not explicitly reveal {secret}"],
        "reveal_policy": {"primary_secret_may_be_revealed": False},
        "relationship_context": [{
            "relationship_id": "REL_TEST",
            "source_id": primary,
            "target_id": others[0] if others else primary,
            "type": "ally",
            "origin_event": "They covered a missed cooling cycle together.",
            "shared_history": "Five winters ago they chose not to log the kiln fault.",
            "public_story": "Colleagues",
            "private_truth": "They still owe each other silence.",
            "current_tension": "Inspection is due.",
            "reason_for_presence": "Ordinary work overlap",
            "reciprocity": "explicit",
        }],
        "dramatic_problem": f"{primary} is already mid-task when the other person arrives.",
        "quest_material": {"hook": "Prove the cooling cycle was shortened", "complication": "Naming it starves a household", "alternate_solution": "Record it as emergency relief"},
        "puzzle_material": {"type": "physical", "logic": "the crack is visible at dusk", "clue_source": "kiln wall"},
        "player_affordances": ["ask_for_evidence_or_clarification"],
        "possible_outcomes": ["player_gains_or_corrects_knowledge"],
        "policy_refs": ["POLICY_KNOWLEDGE_BOUNDARY", "POLICY_PRIVATE_FACT_REVEAL"],
        "scene_requirements": ["Keep the secret in subtext"],
        "trigger": trigger,
    }


def _catalogue() -> list[dict]:
    specs = [
        ("SCN_001_INTRO", "introduction", "NPC_001", ["NPC_008"], "Council & Civic", "Major"),
        ("SCN_002_INTROB", "introduction", "NPC_010", ["NPC_012"], "Market & Inn", "Supporting"),
        ("SCN_080_REL", "relationship", "NPC_020", ["NPC_021", "NPC_022"], "Timber Quarter", "Supporting"),
        ("SCN_100_QUEST", "quest", "NPC_035", ["NPC_033", "NPC_036"], "Fields & Mill", "Major"),
        ("SCN_140_SECRET", "secret_pressure", "NPC_049", ["NPC_050", "NPC_056"], "Mine & Forge", "Major"),
        ("SCN_200_CON", "consequence", "NPC_080", ["NPC_073"], "Households", "Minor"),
        ("SCN_210_CONB", "consequence", "NPC_006", ["NPC_001"], "Council & Civic", "Minor"),
        ("SCN_150_DIST", "district_group", "NPC_041", ["NPC_042", "NPC_043", "NPC_044"], "Wool & Weavery", "Major"),
    ]
    return [_scene(*row) for row in specs]


def test_validate_count_caps():
    assert validate_count(5) == 5
    with pytest.raises(ValueError):
        validate_count(11)
    assert validate_count(11, allow_more=True) == 11
    with pytest.raises(ValueError):
        validate_count(21, allow_more=True)


def test_scene_selection_is_deterministic_and_diverse():
    catalogue = _catalogue()
    a = select_pilot_scenes(catalogue, count=5)
    b = select_pilot_scenes(catalogue, count=5)
    assert [s["scene_id"] for s in a] == [s["scene_id"] for s in b]
    types = [s["scene_type"] for s in a]
    assert types == ["introduction", "relationship", "quest", "secret_pressure", "consequence"]
    primaries = [s["primary_character_id"] for s in a]
    assert len(set(primaries)) == 5
    districts = {s["district"] for s in a}
    assert len(districts) >= 4
    tiers = {p["narrative_tier"] for s in a for p in s["participant_profiles"] if p["character_id"] == s["primary_character_id"]}
    assert {"Major", "Supporting", "Minor"} <= tiers
    assert any(len(s["participant_ids"]) >= 3 for s in a)


def test_packet_keeps_private_facts_and_predecessor_separate():
    catalogue = _catalogue()
    consequence = next(s for s in catalogue if s["scene_type"] == "consequence")
    packet = compile_scene_packet(consequence, catalogue=catalogue)
    assert packet["SCENE_FUNCTION"]["scene_type"] == "consequence"
    assert "WRITER_ONLY_PRIVATE_FACTS" in packet
    assert "CANONICAL_FACTS" in packet
    secret = packet["WRITER_ONLY_PRIVATE_FACTS"][consequence["primary_character_id"]][0]
    assert secret
    canonical_blob = json.dumps(packet["CANONICAL_FACTS"])
    assert "WRITER_ONLY_PRIVATE_FACTS" not in packet["CANONICAL_FACTS"]
    assert packet["FORBIDDEN_REVELATIONS"]
    assert packet["CANONICAL_FACTS"]["predecessor"]["scene_id"] == "SCN_001_INTRO"
    assert packet["CANONICAL_FACTS"]["trigger"]["required_scene_id"] == "SCN_001_INTRO"
    assert "Score_Throne" not in json.dumps(packet)
    assert packet_contains_catalogue(packet, 300) is False
    assert len(json.dumps(packet)) < 20000


def test_mechanics_audit_canon_block_and_parse():
    catalogue = _catalogue()
    intro = catalogue[0]
    packet = compile_scene_packet(intro, catalogue=catalogue)
    secret = packet["WRITER_ONLY_PRIVATE_FACTS"][intro["primary_character_id"]][0]
    leak = {
        "scene_id": intro["scene_id"],
        "lines": [
            {"speaker_id": intro["primary_character_id"], "text": secret, "action": "", "beat": 1},
            {"speaker_id": "NPC_999", "text": "Hello", "action": "", "beat": 1},
        ],
    }
    report = mechanics_audit_local(packet, leak)
    assert report["canon_block"] is True
    assert report["verdict"] == "CANON_BLOCK"
    categories = {item["category"] for item in report["findings"]}
    assert "secret_leakage" in categories
    assert "identity" in categories
    named = {
        "scene_id": intro["scene_id"],
        "lines": [{"speaker_id": "Name 001", "text": "The ledger is still open.", "beat": 1}],
    }
    from dialogue_generation.ensemble_writer.auditors import normalize_speakers
    cleaned = normalize_speakers(named, packet)
    assert cleaned["lines"][0]["speaker_id"] == intro["primary_character_id"]
    clean_report = mechanics_audit_local(packet, cleaned)
    assert "identity" not in {item["category"] for item in clean_report["findings"]}
    parsed = parse_audit_result({"verdict": "PASS", "findings": [{"severity": "canon_block", "category": "x", "detail": "y"}]})
    assert parsed["canon_block"] is True
    preserved = parse_audit_result({
        "verdict": "CANON_BLOCK",
        "canon_block": True,
        "summary": "The dialogue adheres to the provided authoring limits.",
        "findings": [
            {"severity": "canon_block", "category": "identity", "detail": "No changes were made to the character identities."},
            {"severity": "canon_block", "category": "history", "detail": "The relationship state between characters remains unchanged."},
        ],
    })
    assert preserved["canon_block"] is False
    assert preserved["verdict"] != "CANON_BLOCK"
    numbered = {
        "scene_id": intro["scene_id"],
        "lines": [{"speaker_id": "1", "text": "The ledger is still open.", "beat": 1}],
    }
    remapped = normalize_speakers(numbered, packet)
    assert remapped["lines"][0]["speaker_id"] == intro["primary_character_id"]
    assert mechanics_audit_local(packet, remapped)["canon_block"] is False
    llm_false = soften_llm_canon_blocks({
        "verdict": "CANON_BLOCK",
        "canon_block": True,
        "summary": "ok",
        "findings": [
            {"severity": "canon_block", "category": "identity", "detail": "Both characters maintain their identities as intended."},
            {"severity": "canon_block", "category": "quest progression", "detail": "The dialogue does not affect the quest progression."},
        ],
    })
    assert llm_false["canon_block"] is False


def test_resume_skips_completed_final(tmp_path: Path):
    catalogue = _catalogue()
    scene = catalogue[0]
    output = tmp_path / "pilot"
    output.mkdir()
    (output / f"{scene['scene_id']}_final.json").write_text(json.dumps({
        "scene_id": scene["scene_id"],
        "approved": True,
        "lines": [],
        "canon_block_before_revision": False,
        "canon_block_after_revision": False,
    }), encoding="utf-8")
    (output / f"{scene['scene_id']}_packet.json").write_text(json.dumps({"scene_id": scene["scene_id"]}), encoding="utf-8")

    class Boom:
        def generate_with_retry(self, *args, **kwargs):
            raise AssertionError("Ollama should not be called for a completed scene")

    result = process_scene(scene, catalogue, output, Boom(), model="mistral", force=False)
    assert result["status"] == "skipped_complete"
    assert "final" in result["skipped_passes"]


def test_selection_file_is_not_silently_replaced(tmp_path: Path):
    catalogue = _catalogue()
    output = tmp_path / "pilot"
    output.mkdir()
    first, record = resolve_selection(catalogue, output, count=5, force=False)
    second, again = resolve_selection(catalogue, output, count=5, force=False)
    assert [s["scene_id"] for s in first] == [s["scene_id"] for s in second]
    assert record["scene_ids"] == again["scene_ids"]
    with pytest.raises(ValueError, match="silently substituting"):
        resolve_selection(catalogue, output, count=6, force=False)


def test_offline_pilot_writes_packets_without_ollama(tmp_path: Path):
    catalogue = _catalogue()
    manifest = tmp_path / "scenes.json"
    manifest.write_text(json.dumps({"scenes": catalogue}), encoding="utf-8")
    output = tmp_path / "out"
    summary = run_pilot(manifest_path=manifest, output_dir=output, model="mistral", count=5, offline=True)
    assert summary["selection"]["count"] == 5
    assert (output / "pilot_summary.json").exists()
    assert (output / "pilot_review.md").exists()
    for scene_id in summary["selection"]["scene_ids"]:
        assert (output / f"{scene_id}_packet.json").exists()
    assert summary["scenes"][0]["status"] == "packet_only"


def test_mock_llm_pipeline_approves_clean_scene(tmp_path: Path):
    catalogue = _catalogue()
    scene = catalogue[0]
    packet = compile_scene_packet(scene, catalogue=catalogue)
    lines = [
        {"speaker_id": scene["primary_character_id"], "text": "The ledger is still open.", "action": "does not look up", "beat": 1},
        {"speaker_id": "NPC_008", "text": "Then stop pretending this is a quiet morning.", "action": "", "beat": 2},
        {"speaker_id": "PLAYER", "text": "What broke?", "intent": "ask_for_evidence_or_clarification", "beat": 3},
    ]
    responses = [
        {"scene_id": scene["scene_id"], "rejected_as_exposition": False, "beats": [
            {"beat": i, "speaker_or_focus": scene["primary_character_id"], "surface_action": "works", "hidden_intention": "hide the crack", "new_pressure_or_change": "inspection", "information_change": "none yet"}
            for i in range(1, 6)
        ]},
        {"scene_id": scene["scene_id"], "lines": lines},
        {"verdict": "PASS", "canon_block": False, "summary": "ok", "findings": []},
        {"verdict": "PASS", "canon_block": False, "summary": "ok", "findings": []},
        {"verdict": "PASS", "canon_block": False, "summary": "ok", "findings": []},
        {"scene_id": scene["scene_id"], "revision_notes": ["tightened pauses"], "canonical_changes_attempted": False, "lines": lines},
        {"verdict": "PASS", "canon_block": False, "summary": "still ok", "findings": []},
    ]

    class Fake:
        def __init__(self):
            self.calls = 0
        def generate_with_retry(self, prompt, **kwargs):
            data = responses[self.calls]
            self.calls += 1
            return OllamaResponse(True, data=data)
        def model_ready(self, model_name=None):
            return OllamaResponse(True, data={"model": {"name": model_name}})

    output = tmp_path / "mock"
    result = process_scene(scene, catalogue, output, Fake(), model="mistral", force=True)
    assert result["approved"] is True
    assert result["canon_block_after_revision"] is False
    assert (output / f"{scene['scene_id']}_final.json").exists()
