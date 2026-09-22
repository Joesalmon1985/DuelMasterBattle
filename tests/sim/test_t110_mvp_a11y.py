"""T110 MVP accessibility / placeholder art manifest."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.presentation.semantic_visuals import index_by_id

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "godot_project/client/assets/mvp/manifest.json"


def test_mvp_manifest_complete_and_semantic() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data.get("min_touch_px") == 48
    assert data.get("missing_assets") == []
    idx = index_by_id()
    for row in data.get("assets") or []:
        sid = str(row.get("semantic_id") or "")
        if sid:
            assert sid in idx or sid.startswith("unit.") or sid.startswith("building.") or sid.startswith("hazard.")
        if row.get("kind") == "silhouette":
            assert sid
        if "text_equivalent" in row:
            assert row["text_equivalent"]
