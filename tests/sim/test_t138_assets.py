"""T138 era art/audio semantic placeholders and asset provenance."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_four_era_asset_families_and_manifest() -> None:
    eras = ("prehistoric", "historic", "modern", "future")
    for era in eras:
        path = ROOT / "godot_project" / "client" / "assets" / era / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["presentation"] == "semantic_placeholder"
        assert data["missing_assets"] == []
        assert data["readable_without_colour_alone"] is True
        assert "walk" in data["animation_families"]
        for asset in data["assets"]:
            assert asset["provenance"]["licence"]
            assert asset.get("non_colour_cue") or asset["kind"] == "effect"
    audio = json.loads(
        (ROOT / "godot_project" / "client" / "audio" / "palettes.json").read_text(encoding="utf-8")
    )
    assert set(audio["eras"]) == set(eras)
    for era, pal in audio["eras"].items():
        for cue in pal["cues"]:
            assert cue["text_equivalent"]
            assert cue["rate_limit_ms"] >= 200
    manifest = json.loads(
        (ROOT / "godot_project" / "content" / "asset_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["missing_assets"] == []
    assert manifest["accessibility"]["reduced_motion"] is True
    assert manifest["accessibility"]["label_scale"] is True
    assert len(manifest["assets"]) >= 40
