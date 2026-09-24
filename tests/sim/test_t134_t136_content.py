"""T134–T136 quest templates, dungeons and rivals."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "godot_project" / "content" / "source"

FAMILIES = (
    "shortage",
    "transport",
    "catastrophe",
    "diplomacy",
    "military",
    "personal",
    "discovery",
    "conflict",
)
DUNGEONS = ("cave", "mine", "sluice", "temple", "bunker", "industrial", "alien", "machine")


def _family_templates(family: str) -> list[dict]:
    out = []
    for path in sorted((SOURCE / "quests" / family).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("family") == family:
            out.append(data)
    return out


def test_eight_families_have_two_templates_each() -> None:
    for family in FAMILIES:
        templates = _family_templates(family)
        assert len(templates) >= 2, family
        ids = {t["id"] for t in templates}
        assert len(ids) == len(templates)
        # Not rename-only: distinct cause kinds
        causes = {tuple(t["required_cause"]["kinds"]) for t in templates}
        assert len(causes) >= 2, family


def test_templates_have_branches_and_competing_costs() -> None:
    for family in FAMILIES:
        for t in _family_templates(family):
            assert len(t.get("solutions") or []) >= 2
            assert "world_resolved_route" in t
            assert "invalid_target_route" in t
            assert "dead_target_route" in t
            assert "displaced_target_route" in t
            assert "full_cycle_route" in t
            assert t["binding"].get("compulsory_main_quest") is False
            assert t["binding"].get("competing_cost")
            assert t.get("required_item_recovery", {}).get("recoverable") is True


def test_eight_dungeons_and_four_rivals() -> None:
    for name in DUNGEONS:
        layout = json.loads((SOURCE / "dungeons" / name / "layout.json").read_text(encoding="utf-8"))
        puzzle = json.loads((SOURCE / "dungeons" / name / "puzzle.json").read_text(encoding="utf-8"))
        assert layout["id"] == f"dungeon.{name}" or name == "sluice"
        assert puzzle.get("solution_trace")
        assert puzzle.get("recovery_trace")
        assert puzzle.get("hidden_secret_readable_by_rivals") is False
    rivals = list((SOURCE / "rivals").glob("*.json"))
    assert len(rivals) == 4
    profiles = []
    for path in rivals:
        r = json.loads(path.read_text(encoding="utf-8"))
        assert r["reads_hidden_secrets"] is False
        profiles.append(r["deduction_strategy"])
    assert len(set(profiles)) == 4
