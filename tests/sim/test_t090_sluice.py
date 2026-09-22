"""T090 sluice dungeon layout and bounded solution validator."""

from __future__ import annotations

import json
from pathlib import Path

from tools.content.validate_puzzles import validate_sluice

SLUICE = (
    Path(__file__).resolve().parents[2]
    / "godot_project"
    / "content"
    / "source"
    / "dungeons"
    / "sluice"
)


def test_sluice_content_present() -> None:
    layout = json.loads((SLUICE / "layout.json").read_text(encoding="utf-8"))
    puzzle = json.loads((SLUICE / "puzzle.json").read_text(encoding="utf-8"))
    assert layout["id"] == "dungeon.sluice"
    assert {r["id"] for r in layout["rooms"]} >= {
        "room.entrance",
        "room.workshop",
        "room.corridor",
        "room.chamber",
        "room.exit",
    }
    assert puzzle["id"] == "puzzle.sluice"
    assert any(c.get("id") == "clue.inscription" for r in layout["rooms"] for c in r.get("clues") or [])
    assert not any(r.get("permanent_lock") for r in layout["rooms"])


def test_machine_trace_solves_all_reset_states() -> None:
    report = validate_sluice()
    assert report["ok"], report["errors"]
    assert len(report["traces"]) >= 2
    for trace in report["traces"]:
        assert trace["solved"] is True
        assert trace["route_b_eligible"] is True
        assert trace["units"] == 0
