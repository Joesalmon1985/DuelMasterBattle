"""T115 — full four-era industrial catalogue oracles."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from sim.dmb.content.catalogue import (
    ERAS,
    RAW_COUNT,
    RAW_FREQUENCY,
    RECIPE_COUNT,
    RECIPES_PER_ERA,
    FullCatalogue,
    load_full_catalogue,
    recipes_for_era,
    validate_full_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "godot_project" / "content" / "manifests" / "full.json"


def test_full_catalogue_floors_and_era_filters() -> None:
    catalogue = load_full_catalogue()
    assert len(catalogue.snapshot.resources) == RAW_COUNT
    assert len(catalogue.snapshot.recipes) == RECIPE_COUNT
    for era in ERAS:
        era_recipes = catalogue.recipes_for_era(era)
        assert len(era_recipes) == RECIPES_PER_ERA
        frequency = Counter(
            rid for recipe in era_recipes for rid in (recipe["input_a_id"], recipe["input_b_id"])
        )
        assert set(frequency.values()) == {RAW_FREQUENCY}
        pairs = {(r["input_a_id"], r["input_b_id"]) for r in era_recipes}
        assert len(pairs) == RECIPES_PER_ERA
        for recipe in era_recipes:
            a = catalogue.get_resource(recipe["input_a_id"])
            b = catalogue.get_resource(recipe["input_b_id"])
            assert a["terrain"] != b["terrain"]
            assert recipe["input_quantities"] == [1, 1]
            assert recipe["baseline_military_supply"] is True


def test_all_cultures_access_all_sixty() -> None:
    catalogue = load_full_catalogue()
    for era in ERAS:
        access = set(catalogue.snapshot.culture_access[era])
        assert len(access) == RECIPES_PER_ERA
        assert access == {r["id"] for r in catalogue.recipes_for_era(era)}


def test_services_remain_nonstorable() -> None:
    catalogue = load_full_catalogue()
    services = [
        r for r in catalogue.snapshot.resources if r.get("namespace") == "industrial_service"
    ]
    assert services
    assert all(r.get("storable") is False for r in services)


def test_workbook_roles_do_not_change_mechanics() -> None:
    for recipe in load_full_catalogue().snapshot.recipes:
        assert "source_gameplay_role_metadata_only" in recipe
        assert "sink" not in recipe
        assert "population_cost" not in recipe


def test_era_filtered_helper_and_mvp_subset() -> None:
    full_hist = recipes_for_era("historic")
    mvp_hist = recipes_for_era("historic", mvp_only=True)
    assert len(full_hist) == 60
    assert len(mvp_hist) == 16
    assert {r["id"] for r in mvp_hist}.issubset({r["id"] for r in full_hist})


def test_full_manifest_matches_catalogue() -> None:
    assert MANIFEST.exists()
    result = validate_full_manifest(MANIFEST)
    assert result["summary"]["resources"] == 48
    assert result["summary"]["recipes"] == 240
    assert result["manifest"]["acceptance_gate"] == "G07"


def test_pick_cross_terrain_from_full_set() -> None:
    catalogue = FullCatalogue.load()
    modern = catalogue.resources_for_era("modern")
    available = [r["id"] for r in modern]
    recipe = catalogue.pick_cross_terrain_recipe("modern", available)
    assert recipe is not None
    assert recipe["era"] == "modern"
    assert recipe["input_a_id"] in available
    assert recipe["input_b_id"] in available
