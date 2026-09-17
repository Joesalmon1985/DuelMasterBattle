#!/usr/bin/env python3
"""Normalize BuildPack resource and recipe references into runtime catalogues."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "reference"
CONTENT = ROOT / "godot_project" / "content" / "source"


def _read(name: str) -> dict:
    return json.loads((REFERENCE / name).read_text(encoding="utf-8"))


def compile_catalogues() -> dict[str, dict]:
    source_resources = _read("resources.json")
    resources = []
    aliases: dict[str, str] = {}
    for record in source_resources["industrial_resources"]:
        normalized = dict(record)
        source_name = str(normalized.pop("source_display_name", normalized["name"]))
        normalized["schema_version"] = 1
        normalized["kind"] = "industrial_resource"
        if source_name != normalized["name"]:
            normalized["aliases"] = [source_name]
            aliases[source_name] = normalized["id"]
        else:
            normalized["aliases"] = []
        resources.append(normalized)

    catan = [
        {"id": good_id, "schema_version": 1, "kind": "catan_good", "namespace": "catan_good"}
        for good_id in source_resources["catan_goods"]
    ]
    recipes = [dict(record, schema_version=1, kind="industrial_recipe") for record in _read("recipes.json")["recipes"]]
    mvp = [record for record in recipes if record["era"] in {"prehistoric", "historic"} and record["mvp_subset"]]
    culture = {
        era: [record["id"] for record in recipes if record["era"] == era]
        for era in ("prehistoric", "historic", "modern", "future")
    }
    return {
        "resources": {"schema_version": 1, "resources": resources, "aliases": aliases},
        "catan": {"schema_version": 1, "goods": catan},
        "full": {"schema_version": 1, "recipes": recipes},
        "mvp": {"schema_version": 1, "implemented_eras": ["prehistoric", "historic"], "recipes": mvp},
        "culture": {"schema_version": 1, "access": culture},
    }


def validate(catalogues: dict[str, dict]) -> None:
    resources = catalogues["resources"]["resources"]
    recipes = catalogues["full"]["recipes"]
    assert len(resources) == 48
    resource_by_id = {record["id"]: record for record in resources}
    assert len(resource_by_id) == 48
    assert all(record["id"].startswith("ind.") for record in resources)
    assert all(good["id"].startswith("catan.") for good in catalogues["catan"]["goods"])
    for era in ("prehistoric", "historic", "modern", "future"):
        era_recipes = [record for record in recipes if record["era"] == era]
        assert len(era_recipes) == 60
        assert len({record["processor_id"] for record in era_recipes}) == 60
        assert len({record["output_id"] for record in era_recipes}) == 60
        assert len({(record["input_a_id"], record["input_b_id"]) for record in era_recipes}) == 60
        frequency = Counter(
            resource_id
            for record in era_recipes
            for resource_id in (record["input_a_id"], record["input_b_id"])
        )
        assert set(frequency.values()) == {10}
        for record in era_recipes:
            assert resource_by_id[record["input_a_id"]]["terrain"] != resource_by_id[record["input_b_id"]]["terrain"]
            assert "source_gameplay_role_metadata_only" in record
    assert Counter(record["era"] for record in catalogues["mvp"]["recipes"]) == {
        "prehistoric": 16,
        "historic": 16,
    }
    assert catalogues["resources"]["aliases"] == {
        "Berries and nuts": "ind.prehistoric.woodland.renewable",
        "Phosphate": "ind.modern.fields.finite",
    }


def write_catalogues(catalogues: dict[str, dict]) -> None:
    destinations = {
        "resources": CONTENT / "resources" / "catalog.json",
        "catan": CONTENT / "resources" / "catan_goods.json",
        "full": CONTENT / "recipes" / "full.json",
        "mvp": CONTENT / "recipes" / "mvp.json",
        "culture": CONTENT / "recipes" / "culture_access.json",
    }
    for key, path in destinations.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalogues[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate generated files without writing")
    args = parser.parse_args()
    catalogues = compile_catalogues()
    validate(catalogues)
    if args.check:
        expected = {
            "resources": CONTENT / "resources" / "catalog.json",
            "catan": CONTENT / "resources" / "catan_goods.json",
            "full": CONTENT / "recipes" / "full.json",
            "mvp": CONTENT / "recipes" / "mvp.json",
            "culture": CONTENT / "recipes" / "culture_access.json",
        }
        for key, path in expected.items():
            assert json.loads(path.read_text(encoding="utf-8")) == catalogues[key]
    else:
        write_catalogues(catalogues)
    print("T049_CATALOGUES_OK resources=48 recipes=240 mvp=32")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
