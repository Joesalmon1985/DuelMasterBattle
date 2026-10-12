"""Spellbook visual playtest review launcher contract (P2/P9)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import windows_playtest as wp  # noqa: E402


def test_playtest_review_env_isolation() -> None:
    env = wp.playtest_review_env()
    assert env["DMB_PLAYTEST_REVIEW"] == "1"
    assert env["DMB_SAVE_SLOT"] == wp.G05_REVIEW_SAVE_SLOT
    assert env["DMB_SAVE_SLOT"] != "g05_village"
    assert env["DMB_FIXTURE"] == wp.G05_MVP_FIXTURE
    assert env["DMB_SEED"] == wp.G05_MVP_SEED


def test_chapters_json_has_eight_placeholders() -> None:
    path = ROOT / "godot_project" / "content" / "polish" / "visual_review_chapters.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []
    assert len(chapters) == 8
    for ch in chapters:
        assert ch.get("checkpoint_id", "").startswith("CP-")
        assert "checkpoint_slot" in ch
