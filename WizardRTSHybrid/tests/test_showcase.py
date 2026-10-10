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
)


def test_structure_damage_uses_one_pipeline() -> None:
    world = HybridWorld()
    warehouse = next(
        building_id
        for building_id, building in world.buildings.items()
        if building["kind"] == "warehouse" and building["faction_name"] == "Red"
    )
    tree = next(iter(world.rocks))
    missed = world.damage_building(warehouse, 200, ["infantry"], {"wood": 100})
    assert missed == 0
    assert world.buildings[warehouse]["hp"] == 1000
    dealt = world.damage_building(warehouse, 200, ["structure"], {"wood": 100})
    assert dealt == 200
    assert world.buildings[warehouse]["hp"] == 800
    assert world.buildings[warehouse]["operational"] is True
    assert world.damage_building(tree, 500, ["structure"], {"wood": 100}) == 0
    world.buildings[warehouse]["hp"] = 50
    world.damage_building(warehouse, 200, ["structure"], {"wood": 100})
    assert world.buildings[warehouse]["hp"] == 0
    assert world.buildings[warehouse]["operational"] is False
    again = world.damage_building(warehouse, 200, ["structure"], {"wood": 100})
    assert again == 0


def test_showcase_entities_and_art() -> None:
    world = HybridWorld()
    definitions = {building.get("definition") for building in world.buildings.values()}
    definitions.update(unit.get("definition") for unit in world.units.values())
    definitions.update(carrier.get("definition") for carrier in world.carriers.values())
    definitions.update(tree.get("definition") for tree in world.trees.values())
    for name in REQUIRED:
        assert name in definitions, name
    start = (world.player["tx"], world.player["ty"])
    assert (start[0] + 1, start[1]) not in world.blocked
    assert world.roads
    assert world.trees
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
