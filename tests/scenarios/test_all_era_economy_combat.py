"""T122 — economy/combat matrix across all four eras."""

from __future__ import annotations

from sim.dmb.content.catalogue import ERAS, load_full_catalogue
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.units import MilitaryService, era_factor


def test_recipe_counts_and_services_nonstorable() -> None:
    cat = load_full_catalogue()
    for era in ERAS:
        assert len(cat.recipes_for_era(era)) == 60
    services = [r for r in cat.snapshot.resources if r.get("namespace") == "industrial_service"]
    assert services and all(r.get("storable") is False for r in services)


def test_combat_factor_applied_once_per_era() -> None:
    state = WorldState(world_id=WorldId("world:t122"))
    mil = MilitaryService(state)
    for era, expected in (("prehistoric", 1), ("historic", 10), ("modern", 100), ("future", 1000)):
        unit = mil.spawn(
            f"unit.{'ancient' if era=='prehistoric' else era}.line",
            home_node_id="n1",
            faction_id="faction:a",
            era=era,
            factory_id=f"f:{era}",
        )
        assert unit["era_factor"] == expected == era_factor(era)
        assert unit["max_health"] == 100 * expected
        assert unit["derived_attack"] == 15 * expected


def test_service_resource_not_cart_eligible() -> None:
    cat = load_full_catalogue()
    for resource in cat.snapshot.resources:
        if resource.get("namespace") == "industrial_service":
            assert resource.get("baseline_cart_eligible") is False
            assert resource.get("storable") is False
