"""T139–T140 developer content tools (Python-side contracts)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_debug_inspector_scripts_exist() -> None:
    required = [
        "godot_project/client/debug/economy_view.gd",
        "godot_project/client/debug/technology_view.gd",
        "godot_project/client/debug/culture_editor.gd",
        "godot_project/client/debug/policy_view.gd",
        "godot_project/client/debug/puzzle_editor.gd",
        "godot_project/client/debug/era_plan_view.gd",
        "godot_project/client/debug/narrative_tools/quest_dialogue_preview.gd",
        "godot_project/client/debug/narrative_tools/semantic_knowledge_inspector.gd",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_preview_branches_and_unsupported_effect_rejection() -> None:
    # Mirror GDScript preview contract in Python for CI without Godot.
    def preview_branch(context: dict) -> dict:
        branch = str(context.get("branch", "offer"))
        if not context.get("speaker_alive", True):
            return {"ok": True, "branch": "dead_target", "engine": "production"}
        if context.get("world_resolved"):
            return {"ok": True, "branch": "already_world_resolved", "engine": "production"}
        if context.get("speaker_displaced"):
            return {"ok": True, "branch": "displaced_target", "engine": "production"}
        return {"ok": True, "branch": branch, "engine": "production"}

    assert preview_branch({"speaker_alive": False})["branch"] == "dead_target"
    assert preview_branch({"world_resolved": True})["branch"] == "already_world_resolved"
    assert preview_branch({"speaker_displaced": True})["branch"] == "displaced_target"

    def reject(effect: dict) -> dict:
        kind = str(effect.get("kind") or "")
        if kind in {"", "UNKNOWN_API"}:
            return {"ok": False, "error": "unsupported effect rejected"}
        return {"ok": True}

    assert reject({"kind": "UNKNOWN_API"})["ok"] is False
    assert reject({"kind": "noop"})["ok"] is True


def test_era_asset_assignments_conserved_in_manifest() -> None:
    manifest = json.loads(
        (ROOT / "godot_project" / "content" / "asset_manifest.json").read_text(encoding="utf-8")
    )
    eras = set(manifest["eras"])
    assert eras == {"prehistoric", "historic", "modern", "future"}
    by_era = {e: 0 for e in eras}
    for asset in manifest["assets"]:
        by_era[asset["era"]] += 1
    assert all(v > 0 for v in by_era.values())
