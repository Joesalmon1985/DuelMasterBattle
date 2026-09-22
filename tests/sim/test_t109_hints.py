"""T109 optional hints remain optional and non-spoiling by default."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HINTS = ROOT / "godot_project/content/source/dialogue/tutorial/hints.json"


def test_hints_optional_and_spoiler_flagged() -> None:
    data = json.loads(HINTS.read_text(encoding="utf-8"))
    assert data.get("hints_optional") is True
    lines = data.get("lines") or []
    assert lines
    topics = {str(l.get("topic")) for l in lines}
    assert "wait" in topics and "movement" in topics
    spoilers = [l for l in lines if l.get("spoiler")]
    assert spoilers  # at least one spoiler-separated
    # Required action topics exist even if spoilers hidden
    non_spoiler = [l for l in lines if not l.get("spoiler")]
    assert any(l.get("topic") == "wait" for l in non_spoiler)
