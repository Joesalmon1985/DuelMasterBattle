"""The mixed settlement is real entities with imported art ids."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "godot_project" / "client" / "hybrid" / "art" / "catalogue.json"

REQUIRED = (
    "widelands.lumberjack",
    "widelands.warehouse",
    "widelands.coalmine",
    "widelands.tavern",
    "widelands.farm",
    "widelands.sawmill",
    "widelands.carrier",
    "widelands.beech",
    "widelands.soldier",
    "openra.barracks",
    "openra.e1",
    "openra.3tnk",
    "openra.weap",
    "openra.proc",
)


def test_showcase_entities_and_art() -> None:
    world = HybridWorld()
    definitions = {building.get("definition") for building in world.buildings.values()}
    definitions.update(unit.get("definition") for unit in world.units.values())
    definitions.update(carrier.get("definition") for carrier in world.carriers.values())
    for name in REQUIRED:
        assert name in definitions, name
    start = (world.player["tx"], world.player["ty"])
    assert (start[0] + 1, start[1]) not in world.blocked
    assert world.roads
    assert any(building.get("kind") == "tree" for building in world.buildings.values())
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    assert catalogue["missing_required"] == []
    present = {item["id"] for item in catalogue["items"]}
    assert "widelands.road" in present
    for name in REQUIRED:
        assert name in present
        match = next(item for item in catalogue["items"] if item["id"] == name)
        if match["mode"] == "sheet":
            path = ROOT / "godot_project" / match["godot"].replace("res://", "")
            blob = path.read_bytes()[:8]
            assert blob == b"\x89PNG\r\n\x1a\n"
        else:
            assert match["frames_godot"]
