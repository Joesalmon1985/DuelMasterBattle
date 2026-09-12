from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from dialogue_generation.fixture_builder import build_fixture
from dialogue_generation.workbook_reader import EXPECTED_HEADERS, extract_beats, read_cast_rows, workbook_sha256


def _make_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dialogue Matrix"
    ws.append(EXPECTED_HEADERS)
    ws.append([
        "E17A", "soap", "A family argument over the mill", "Alice", "Reeve", "instigator",
        "stubborn", "opening", "start", "I need your help.", "No", "", "", "", "", "", "", "", "",
        "We found a way through.", "It ended badly.",
    ])
    ws.append([
        "E17A", "soap", "A family argument over the mill", "Bram", "Miller", "witness",
        "guarded", "decision", "after Alice", "", "Yes", 1, "Who do you believe?",
        "I believe Alice.", "Then stand by her.", "I believe Bram.", "Then hear me out.",
        "Alice trusted", "Bram trusted", "The mill survives.", "The mill is lost.",
    ])
    wb.save(path)


def _export_for(workbook: Path, path: Path) -> None:
    rows = read_cast_rows(workbook, "E17A")
    beats = extract_beats(rows)
    banks = []
    for i, beat in enumerate(beats):
        responses = []
        if beat.consequential:
            responses = [
                {"worldview": "guildist", "context_fit": 5, "conviction_tier": 1, "branch": "A", "john": "Alice has the stronger claim.", "npc_reaction": "Then you understand.", "scores": {}},
                {"worldview": "guildist", "context_fit": 5, "conviction_tier": 1, "branch": "B", "john": "Bram deserves to be heard.", "npc_reaction": "Good. Listen closely.", "scores": {}},
            ]
        else:
            responses = [
                {"worldview": "guildist", "context_fit": 5, "conviction_tier": 1, "branch": None, "john": f"John reply {i}", "npc_reaction": f"NPC reaction {i}", "scores": {}}
            ]
        banks.append({
            "bank_id": f"BANK_{i}",
            "representative_beat_id": beat.beat_id,
            "source_text": beat.source_text,
            "beat_type": beat.beat_type,
            "consequential": beat.consequential,
            "branch_a": beat.branch_a,
            "branch_b": beat.branch_b,
            "source_refs": [{
                "instance_id": beat.instance_id,
                "beat_id": beat.beat_id,
                "sheet": beat.source_sheet,
                "row": beat.source_row,
                "field": beat.source_field,
                "character": beat.character,
                "village_role": beat.village_role,
                "story_role": beat.story_role,
            }],
            "responses": responses,
            "review": {"approved": True, "issues": [], "summary": "ok"},
        })
    payload = {
        "schema_version": "1.0",
        "cast_id": "E17A",
        "source_workbook": {"path": str(workbook), "sha256": workbook_sha256(workbook)},
        "bank_count": len(banks),
        "banks": banks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_fixture_maps_all_beats_and_choices(tmp_path: Path) -> None:
    workbook = tmp_path / "matrix.xlsx"
    export_json = tmp_path / "generated" / "E17A.json"
    fixture_root = tmp_path / "fixtures"
    _make_workbook(workbook)
    _export_for(workbook, export_json)

    result = build_fixture(
        "E17A",
        workbook=workbook,
        export_json=export_json,
        fixture_root=fixture_root,
        preferred_worldview="guildist",
    )

    assert result["validation"] == "PASS"
    assert result["mapped_beats"] == result["beat_instances"]
    assert result["source_rows"] == 2
    target = fixture_root / "E17A"
    assert {p.name for p in target.iterdir()} == {"village.json", "cast.json", "quest.json", "dialogue.json"}

    village = json.loads((target / "village.json").read_text(encoding="utf-8"))
    cast = json.loads((target / "cast.json").read_text(encoding="utf-8"))
    quest = json.loads((target / "quest.json").read_text(encoding="utf-8"))
    dialogue = json.loads((target / "dialogue.json").read_text(encoding="utf-8"))

    assert village["economic_profile"] == "E17"
    assert village["resources"] == ["Wood", "Grain", "Ore"]
    assert len(cast["cast"]) == 2
    assert quest["start_node"].startswith("scene_01_")
    choice_nodes = [n for n in quest["nodes"].values() if n.get("type") == "choice"]
    assert len(choice_nodes) == 1
    assert len(choice_nodes[0]["options"]) == 2
    branch_entries = [d for d in dialogue["dialogue"] if d.get("variant") in {"branch_a", "branch_b"}]
    assert len(branch_entries) == 2
    assert any(d.get("node_id") == "__epilogue__" and d.get("variant") == "normal" for d in dialogue["dialogue"])
    assert any(d.get("node_id") == "__epilogue__" and d.get("variant") == "tragic" for d in dialogue["dialogue"])


def test_validate_only_does_not_write(tmp_path: Path) -> None:
    workbook = tmp_path / "matrix.xlsx"
    export_json = tmp_path / "E17A.json"
    fixture_root = tmp_path / "fixtures"
    _make_workbook(workbook)
    _export_for(workbook, export_json)
    result = build_fixture(
        "E17A",
        workbook=workbook,
        export_json=export_json,
        fixture_root=fixture_root,
        validate_only=True,
    )
    assert result["written"] is False
    assert not (fixture_root / "E17A").exists()
