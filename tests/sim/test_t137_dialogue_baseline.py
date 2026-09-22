"""T137 dialogue coverage and integrity."""

from __future__ import annotations

from tools.content.compile import compile_baseline_dialogue
from tools.content.validate import load_bank, validate_dialogue_integrity


def test_baseline_dialogue_meets_1200_and_integrity() -> None:
    lines = load_bank(include_baseline=True)
    report = validate_dialogue_integrity(lines)
    assert report["line_count"] >= 1200
    assert report["ok"], report["errors"]
    eras = {str(l.get("era_id")) for l in lines}
    assert "prehistoric" in eras and "historic" in eras
    families = {str(l.get("family")) for l in lines if l.get("family")}
    assert len(families) >= 8
    branches = {str(l.get("branch")) for l in lines if l.get("branch")}
    for needed in (
        "dead_target",
        "displaced_target",
        "world_resolved",
        "already_world_resolved",
        "full_cycle",
    ):
        assert needed in branches
    rivals = [l for l in lines if str(l.get("id", "")).startswith("dialogue.rival.")]
    assert len(rivals) >= 4


def test_compile_baseline_pack() -> None:
    result = compile_baseline_dialogue()
    assert result["ok"], result.get("validate")
    assert result["manifest"]["baseline_line_count"] >= 1200
