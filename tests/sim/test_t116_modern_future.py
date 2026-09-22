"""T116 — Modern/Future facilities, units and technology."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.units import ERA_FACTORS, MilitaryService, era_factor
from sim.dmb.technology.definitions import TechnologyCatalog, tech_id

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "godot_project" / "content" / "source"


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t116"))



def _load_core(era: str) -> dict:
    path = CONTENT / "eras" / era / "core_upgrade.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_modern_future_core_upgrade_maps() -> None:
    modern = _load_core("modern")
    future = _load_core("future")
    assert modern["combat_factor"] == 100
    assert future["combat_factor"] == 1000
    assert modern["previous_era"] == "historic"
    assert future["previous_era"] == "modern"
    assert future.get("next_cycle_path") == "dystopia"
    assert future.get("next_cycle_path") != "utopia"
    for era, cfg in (("modern", modern), ("future", future)):
        core = cfg["core_upgrade"]
        assert len(core["unit_defs"]) == 3
        assert {u.split(".")[-1] for u in core["unit_defs"]} == {"skirmisher", "line", "heavy"}
        assert len(cfg["terrain_industrial"]) == 6
        for terrain, kinds in cfg["terrain_industrial"].items():
            for kind in ("renewable", "finite"):
                rid = kinds[kind][0]
                assert rid.startswith(f"ind.{era}.")
                assert terrain in rid


def test_thin_unit_defs_and_single_era_factor() -> None:
    units = json.loads((CONTENT / "units" / "later.json").read_text(encoding="utf-8"))
    assert len(units) >= 6
    by_era = {}
    for unit in units:
        by_era.setdefault(unit["era_id"], []).append(unit)
        if unit["id"] == "unit.modern.cleanup":
            assert unit["fields"].get("cleanup_capable") is True
            continue
        assert unit["fields"]["combat_factor"] == ERA_FACTORS[unit["era_id"]]
        assert unit["fields"].get("semantic_placeholder") is True
    assert {"modern", "future"} <= set(by_era)
    assert len([u for u in by_era["modern"] if u["id"] != "unit.modern.cleanup"]) == 3
    assert len(by_era["future"]) == 3

    world = _world()
    mil = MilitaryService(world)
    modern = mil.spawn(
        "unit.modern.line",
        home_node_id="node:1",
        faction_id="faction:a",
        era="modern",
        factory_id="factory:1",
    )
    future = mil.spawn(
        "unit.future.line",
        home_node_id="node:1",
        faction_id="faction:a",
        era="future",
        factory_id="factory:2",
    )
    assert modern["era_factor"] == 100
    assert future["era_factor"] == 1000
    # Factor applied exactly once: base_hp * factor, not squared.
    assert modern["max_health"] == 100 * 100
    assert future["max_health"] == 100 * 1000
    assert modern["max_health"] != 100 * 100 * 100


def test_twenty_four_tech_reachable_and_capped() -> None:
    catalog = TechnologyCatalog()
    catalog.load()
    assert len(catalog.all()) == 24
    modern_primary = catalog.get(tech_id("modern", "primary_flow"))
    assert set(modern_primary.allowed_predecessor_ids) == {
        tech_id("historic", "primary_flow"),
        tech_id("historic", "processor_cap"),
    }
    future_attack = catalog.get(tech_id("future", "unit_attack"))
    assert set(future_attack.allowed_predecessor_ids) == {
        tech_id("modern", "unit_attack"),
        tech_id("modern", "unit_health"),
    }
    for defn in catalog.all():
        assert defn.max_stacks == 3
        assert defn.compatibility_scope in {"logistics", "unit_era"}


def test_missing_technology_reference_fails() -> None:
    catalog = TechnologyCatalog()
    catalog.load()
    payloads = [d.to_payload() for d in catalog.all()]
    for raw in payloads:
        if raw["id"] == tech_id("modern", "primary_flow"):
            raw["fields"]["allowed_predecessor_ids"] = ["tech.historic.missing"]
            break
    broken = TechnologyCatalog()
    with pytest.raises(Exception, match="missing predecessor"):
        broken.load(payloads)


def test_era_factors_are_exact() -> None:
    assert era_factor("modern") == 100
    assert era_factor("future") == 1000
    assert ERA_FACTORS["historic"] == 10
