"""T086 FX-VILLAGE shortage quest fixture and branch outcomes."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.industry import fraction
from sim.dmb.quests.runtime import QuestService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.fx_village_solutions import apply_demon_solution

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "godot_project"
    / "content"
    / "fixtures"
    / "village"
    / "fx_village_v1.json"
)
QUEST = (
    Path(__file__).resolve().parents[2]
    / "godot_project"
    / "content"
    / "source"
    / "quests"
    / "shortage"
    / "factory_shortage.json"
)


def _factory_rate(state, factory_id: str) -> float:
    rates: dict = {}
    for event in reversed((state.industry or {}).get("events") or []):
        if event.get("kind") == "industry_rates":
            rates = event.get("rates") or {}
            break
    return float(fraction(rates.get(factory_id) or 0))


def test_fixture_content_present() -> None:
    meta = json.loads(FIXTURE.read_text(encoding="utf-8"))
    quest = json.loads(QUEST.read_text(encoding="utf-8"))
    assert meta["id"] == "FX-VILLAGE"
    assert len(meta["routes"]) == 2
    assert quest["id"] == "quest.factory_shortage"
    assert len(quest["stages"]) == 4


def test_quest_binds_real_person_and_factory_shortage() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    mara_id = fx["mara_id"]
    factory_id = fx["factory_id"]
    quest_id = fx["quest_id"]
    mara = state.people[mara_id]
    factory = state.buildings[factory_id]
    quest = state.quests[quest_id]
    assert mara["name"] == "Mara"
    assert mara["workplace_id"] == factory_id
    assert mara["alive"] is True
    assert factory["shortage"] is True
    assert _factory_rate(state, factory_id) == 0.0
    assert float(factory.get("output_rate") or 0) == 0.0
    assert state.definitions["installed_routes"]["route:A"]["available"] is False
    assert state.definitions["installed_routes"]["route:B"]["available"] is False
    assert "channel:source:ore:finite" in (state.industry or {}).get("channels", {})
    assert quest["stakeholder_id"] == mara_id
    assert quest["affected_entity_id"] == factory_id
    assert quest["status"] == "offered"


def test_demon_victory_restores_route_a() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    quest_id = fx["quest_id"]
    factory_id = fx["factory_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    CatastropheService(state).remove_cube("cube:demon", authority="test")
    applied = apply_demon_solution(state)
    assert applied["computed_rate"] > 0.0
    assert _factory_rate(state, factory_id) > 0.0
    out = svc.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": "demon_duel"},
    )
    assert out["status"] == "completed"
    assert state.quests[quest_id]["resolution"] == "demon_duel"
    assert state.definitions["installed_routes"]["route:A"]["available"] is True


def test_world_repair_acknowledges_correct_actor() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    quest_id = state.board["fx_village"]["quest_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    # Military clears cube before player returns.
    state.hazards["catastrophe"]["cubes"]["cube:demon"]["active"] = False
    state.definitions["installed_routes"]["route:A"]["available"] = True
    out = svc.evaluate(quest_id, world_signals={"world_repaired": True, "actor": "patrol"})
    assert out["status"] == "resolved_by_world"
    assert state.quests[quest_id]["resolution"] == "world_fix_first"


def test_destroyed_target_never_respawns() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    factory_id = fx["factory_id"]
    quest_id = fx["quest_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    BuildingService(state).destroy(factory_id, cause_id="cause:raid")
    out = svc.evaluate(quest_id, world_signals={"target_destroyed": True})
    assert out["status"] == "failed_with_consequence"
    assert state.buildings[factory_id]["status"] == "destroyed"
    assert state.buildings[factory_id]["active"] is False
    # Re-entering / reloading must not resurrect the factory.
    restored = type(state).from_dict(state.to_dict())
    assert restored.buildings[factory_id]["status"] == "destroyed"
    assert restored.buildings[factory_id].get("active") is False
    assert factory_id in restored.tombstones
