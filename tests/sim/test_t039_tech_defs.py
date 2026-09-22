"""T039 technology definitions and prerequisite graph."""

from __future__ import annotations

import pytest

from sim.dmb.content.catalog import DefinitionCatalog
from sim.dmb.core.types import TypeValidationError
from sim.dmb.technology.definitions import (
    TechnologyCatalog,
    build_baseline_tech_defs,
    load_technology_definitions,
    tech_id,
)


def test_six_cards_per_mvp_era() -> None:
    catalog = TechnologyCatalog()
    catalog.load()
    assert len(catalog.by_era("prehistoric")) == 6
    assert len(catalog.by_era("historic")) == 6
    assert len(catalog.by_era("modern")) == 6
    assert len(catalog.by_era("future")) == 6
    assert len(catalog.all()) == 24
    assert catalog.pool_for_era("prehistoric")
    assert catalog.pool_for_era("historic")
    assert catalog.pool_for_era("modern")
    assert catalog.pool_for_era("future")


def test_prehistoric_has_no_prerequisites() -> None:
    catalog = TechnologyCatalog()
    catalog.load()
    for defn in catalog.by_era("prehistoric"):
        assert defn.allowed_predecessor_ids == ()


def test_historic_activates_with_either_predecessor() -> None:
    catalog = TechnologyCatalog()
    catalog.load()
    primary = catalog.get(tech_id("historic", "primary_flow"))
    assert set(primary.allowed_predecessor_ids) == {
        tech_id("prehistoric", "primary_flow"),
        tech_id("prehistoric", "processor_cap"),
    }
    # Either predecessor alone is enough under any_previously_activated.
    assert primary.prerequisite_mode == "any_previously_activated"
    health = catalog.get(tech_id("historic", "unit_health"))
    assert set(health.allowed_predecessor_ids) == {
        tech_id("prehistoric", "unit_health"),
        tech_id("prehistoric", "unit_attack"),
    }


def test_cycle_fails_validation() -> None:
    defs = [d.to_payload() for d in build_baseline_tech_defs()]
    # Introduce an artificial cycle between two prehistoric cards.
    for raw in defs:
        if raw["id"] == tech_id("prehistoric", "primary_flow"):
            raw["fields"]["allowed_predecessor_ids"] = [tech_id("prehistoric", "processor_cap")]
        if raw["id"] == tech_id("prehistoric", "processor_cap"):
            raw["fields"]["allowed_predecessor_ids"] = [tech_id("prehistoric", "primary_flow")]
    catalog = TechnologyCatalog()
    with pytest.raises(TypeValidationError, match="cycle"):
        catalog.load(defs)


def test_missing_predecessor_fails() -> None:
    defs = [d.to_payload() for d in build_baseline_tech_defs()]
    for raw in defs:
        if raw["id"] == tech_id("historic", "primary_flow"):
            raw["fields"]["allowed_predecessor_ids"] = ["tech.prehistoric.missing_card"]
            break
    catalog = TechnologyCatalog()
    with pytest.raises(TypeValidationError, match="missing predecessor"):
        catalog.load(defs)


def test_baseline_usable_without_lucky_draft() -> None:
    """Buildings/routes do not require any technology to function."""
    catalog = TechnologyCatalog()
    catalog.load()
    # No tech is flagged as a hard gate for baseline capability.
    for defn in catalog.all():
        assert defn.compatibility_scope in {"logistics", "unit_era"}
        assert defn.max_stacks == 3
    # Content loads into the shared definition catalog.
    payloads = list(load_technology_definitions().values())
    shared = DefinitionCatalog()
    shared.load(payloads)
    assert shared.catalog_hash
    # Baseline capability does not depend on drawing any specific card.
    assert all(d.pool_weight >= 1 for d in catalog.all())
