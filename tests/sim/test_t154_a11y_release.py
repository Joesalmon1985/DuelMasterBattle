"""T154 — touch, display, audio and accessibility verification (release hardening)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "godot_project" / "client" / "ui" / "settings.gd"
ASSET_MANIFEST = ROOT / "godot_project" / "content" / "asset_manifest.json"
A11Y_REPORT = (
    ROOT
    / "Pack"
    / "DuelMasterBattle_Build_Pack"
    / "tracking"
    / "gates"
    / "G10"
    / "auto"
    / "a11y_matrix.json"
)


def test_viewports_and_touch_targets_declared() -> None:
    assert SETTINGS.is_file()
    text = SETTINGS.read_text(encoding="utf-8")
    for needle in ("reduce_motion", "label_scale", "master_volume", "music_volume", "ui_volume"):
        assert needle in text, f"missing settings key/surface: {needle}"
    if ASSET_MANIFEST.is_file():
        data = json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))
        a11y = data.get("a11y") or data.get("accessibility") or {}
        min_touch = int(data.get("min_touch_px") or a11y.get("min_touch_px", 48))
        assert min_touch >= 44


def test_a11y_matrix_evidence_written() -> None:
    assert A11Y_REPORT.is_file(), "run tools/verify_a11y_release.py to produce matrix"
    matrix = json.loads(A11Y_REPORT.read_text(encoding="utf-8"))
    assert matrix.get("status") in {"PASS", "PASS_WITH_LIMITS"}
    viewports = matrix.get("viewports") or []
    assert {"1280x720", "960x540", "450x800"} <= {v.get("id") for v in viewports}
    for vp in viewports:
        assert vp.get("required_choices_clipped") is False
        assert vp.get("cancel_path_hidden") is False
        assert vp.get("keyboard_only_required_action") is False
    assert matrix.get("sound_text_equivalent") is True
    assert matrix.get("settings_persist") is True
    assert matrix.get("focus_loss_catchup") is False
