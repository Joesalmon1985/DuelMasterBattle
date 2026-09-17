"""T008 definition catalogue checks."""

from __future__ import annotations

import pytest

from sim.dmb.content.catalog import DefinitionCatalog
from sim.dmb.core.types import TypeValidationError


def _defs(rate: int = 1) -> list[dict]:
    return [
        {
            "id": "node.home",
            "schema_version": 1,
            "kind": "node",
            "era_id": "all",
            "name_key": "Home",
            "fields": {"rate": rate},
        },
        {
            "id": "node.road",
            "schema_version": 1,
            "kind": "node",
            "era_id": "all",
            "name_key": "Road",
            "fields": {"rate": rate, "home_ref": "node.home", "build_cost": 3},
        },
    ]


def test_unknown_reference_fails() -> None:
    catalog = DefinitionCatalog()
    bad = _defs()
    bad[1]["fields"]["home_ref"] = "node.missing"
    with pytest.raises(TypeValidationError, match="bad ref"):
        catalog.load(bad)


def test_duplicate_definition_id_fails() -> None:
    catalog = DefinitionCatalog()
    with pytest.raises(TypeValidationError, match="duplicate"):
        catalog.load(_defs() + _defs()[:1])


def test_negative_cost_fails() -> None:
    catalog = DefinitionCatalog()
    bad = _defs()
    bad[1]["fields"]["build_cost"] = -1
    with pytest.raises(TypeValidationError, match="negative cost"):
        catalog.load(bad)


def test_hash_stable_under_key_reordering() -> None:
    a = DefinitionCatalog()
    b = DefinitionCatalog()
    a.load(_defs())
    reordered = [
        {
            "name_key": "Road",
            "fields": {"home_ref": "node.home", "build_cost": 3, "rate": 1},
            "kind": "node",
            "id": "node.road",
            "schema_version": 1,
            "era_id": "all",
        },
        {
            "fields": {"rate": 1},
            "id": "node.home",
            "schema_version": 1,
            "kind": "node",
            "era_id": "all",
            "name_key": "Home",
        },
    ]
    b.load(reordered)
    assert a.catalog_hash == b.catalog_hash


def test_rate_change_changes_hash() -> None:
    a = DefinitionCatalog()
    b = DefinitionCatalog()
    a.load(_defs(1))
    b.load(_defs(2))
    assert a.catalog_hash != b.catalog_hash
