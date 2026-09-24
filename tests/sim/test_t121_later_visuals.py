"""T121 — later-era semantic visuals (no art polish)."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.presentation.semantic_visuals import resolve_visual

ROOT = Path(__file__).resolve().parents[2]


def test_modern_future_asset_manifests() -> None:
    for era in ("modern", "future"):
        data = json.loads((ROOT / f"godot_project/client/assets/{era}/manifest.json").read_text())
        assert data["presentation"] == "semantic_placeholder"
        assert data["era"] == era
        assert len(data["assets"]) >= 5
        assert "idle" in data["animation_families"]


def test_labels_distinguish_legacy_and_new() -> None:
    labels = json.loads((ROOT / "godot_project/content/source/labels/later_eras.json").read_text())
    assert labels["labels"]["building.historic.smelter"]["legacy"] is True
    assert labels["labels"]["building.modern.works"]["legacy"] is False
    assert resolve_visual("building.modern.works")["abbrev"]
    assert resolve_visual("hazard.nuclear")["registered"] is True


def test_era_badge_recognisable_without_debug() -> None:
    labels = json.loads((ROOT / "godot_project/content/source/labels/later_eras.json").read_text())
    assert labels["labels"]["era.modern"]["badge"] == "M"
    assert labels["labels"]["era.future"]["badge"] == "F"
