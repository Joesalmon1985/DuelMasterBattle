from collections import Counter

from tools.content.import_recipes import compile_catalogues, validate


def test_reference_catalogues_normalize_to_contract() -> None:
    catalogues = compile_catalogues()
    validate(catalogues)
    assert len(catalogues["resources"]["resources"]) == 48
    assert Counter(r["era"] for r in catalogues["mvp"]["recipes"]) == {
        "prehistoric": 16,
        "historic": 16,
    }


def test_aliases_and_namespaces_are_explicit() -> None:
    catalogues = compile_catalogues()
    assert catalogues["resources"]["aliases"]["Berries and nuts"].endswith(".woodland.renewable")
    assert catalogues["resources"]["aliases"]["Phosphate"].endswith(".fields.finite")
    industrial_ids = {r["id"] for r in catalogues["resources"]["resources"]}
    catan_ids = {r["id"] for r in catalogues["catan"]["goods"]}
    assert industrial_ids.isdisjoint(catan_ids)
    assert all(r["namespace"] != "catan_good" for r in catalogues["resources"]["resources"])


def test_workbook_roles_remain_metadata_only() -> None:
    recipes = compile_catalogues()["full"]["recipes"]
    assert all("source_gameplay_role_metadata_only" in recipe for recipe in recipes)
    assert all("sink" not in recipe and "population_cost" not in recipe for recipe in recipes)
