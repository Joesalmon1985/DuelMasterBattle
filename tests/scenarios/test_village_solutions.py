"""T093 both FX-VILLAGE solutions, acknowledgements, and persistent return loop."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.adventure.puzzles import PuzzleService
from sim.dmb.construction.buildings import BuildingService
from sim.dmb.player.inventory import InventoryService
from sim.dmb.quests.runtime import QuestService
from sim.dmb.testing.fixtures import load_fixture

ROOT = Path(__file__).resolve().parents[2]
QUEST = ROOT / "godot_project" / "content" / "source" / "quests" / "shortage" / "factory_shortage.json"
DIALOGUE = ROOT / "godot_project" / "content" / "source" / "dialogue" / "shortage" / "mara_lines.json"
SLUICE_PUZZLE = ROOT / "godot_project" / "content" / "source" / "dungeons" / "sluice" / "puzzle.json"


def _ack_for(resolution: str) -> dict:
    lines = json.loads(DIALOGUE.read_text(encoding="utf-8"))["lines"]
    return next(line for line in lines if line.get("resolution") == resolution)


def _confirm_industry(state, factory_id: str, route_id: str) -> None:
    state.definitions["installed_routes"][route_id]["available"] = True
    state.definitions["installed_routes"][route_id]["selected"] = True
    state.buildings[factory_id]["output_rate"] = 1.0
    state.buildings[factory_id]["shortage"] = False
    state.buildings[factory_id]["allocation"] = {"route": route_id, "units": 1}


def test_quest_and_dialogue_content() -> None:
    quest = json.loads(QUEST.read_text(encoding="utf-8"))
    dialogue = json.loads(DIALOGUE.read_text(encoding="utf-8"))
    assert quest["version"] == 2
    assert {s["id"] for s in quest["solutions"]} == {"demon_duel", "sluice_route"}
    assert not next(s for s in quest["solutions"] if s["id"] == "sluice_route")["claims_demon_cleared"]
    ids = {line["id"] for line in dialogue["lines"]}
    assert "dialogue.mara.route_b_complete" in ids
    assert "dialogue.mara.route_a_complete" in ids


def test_route_b_completion_does_not_claim_demon_cleared() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    quest_id = fx["quest_id"]
    factory_id = fx["factory_id"]
    svc = QuestService(state)
    svc.accept(quest_id)

    # Solve sluice: remove sabotage, open sluice, enable route B (policy selects).
    puzzle_def = json.loads(SLUICE_PUZZLE.read_text(encoding="utf-8"))
    puzzles = PuzzleService(state)
    puzzles.register_definition(puzzle_def)
    lease = puzzles.prepare_lease("puzzle.sluice")["lease"]
    inv = InventoryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice.workshop",
        position=[2.0, 1.0],
        quest_bound=True,
    )
    inv.pickup(handle["id"])
    lid, ver = lease["id"], lease["version"]
    out = puzzles.sync_local_pose(
        lid, expected_version=ver, actor_id="box.sluice", position=[0.0, 0.0], kind="movable_box"
    )
    ver = out["version"]
    out = puzzles.act(
        lid,
        expected_version=ver,
        mechanism_id="receptor.sluice",
        action="place",
        item_id=handle["id"],
    )
    ver = out["version"]
    if not out["lease"]["checkpoint"].get("solved"):
        out = puzzles.act(lid, expected_version=ver, mechanism_id="gate.final", action="open")
        ver = out["version"]
        out = puzzles.act(lid, expected_version=ver, mechanism_id="sluice.actuator", action="on")
    assert "sluice_sabotage" not in state.definitions.get("production_modifiers", {})
    assert (state.definitions.get("history_facts") or {}).get("sluice_open", {}).get("value") is True
    # Demon cube remains — Route B must not claim it cleared.
    assert state.hazards["catastrophe"]["cubes"]["cube:demon"]["active"] is True
    state.definitions["installed_routes"]["route:B"]["available"] = True
    _confirm_industry(state, factory_id, "route:B")
    result = svc.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": "sluice_route"},
    )
    assert result["status"] == "completed"
    assert state.quests[quest_id]["resolution"] == "sluice_route"
    ack = _ack_for("sluice_route")
    assert ack["claims_demon_cleared"] is False
    assert "ridge is still unsafe" in ack["text"]
    assert float(state.buildings[factory_id]["output_rate"]) > 0.0


def test_demon_solution_restores_route_a_industry() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    quest_id = fx["quest_id"]
    factory_id = fx["factory_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    state.hazards["catastrophe"]["cubes"]["cube:demon"]["active"] = False
    state.definitions["installed_routes"]["route:A"]["available"] = True
    _confirm_industry(state, factory_id, "route:A")
    out = svc.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": "demon_duel"},
    )
    assert out["status"] == "completed"
    assert state.quests[quest_id]["resolution"] == "demon_duel"
    ack = _ack_for("demon_duel")
    assert ack["claims_demon_cleared"] is True
    assert float(state.buildings[factory_id]["output_rate"]) > 0.0


def test_world_resolved_and_destroyed_remain_playable() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    quest_id = fx["quest_id"]
    factory_id = fx["factory_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    state.hazards["catastrophe"]["cubes"]["cube:demon"]["active"] = False
    state.definitions["installed_routes"]["route:A"]["available"] = True
    world = svc.evaluate(quest_id, world_signals={"world_repaired": True, "actor": "patrol"})
    assert world["status"] == "resolved_by_world"
    assert _ack_for("world_fix_first")["id"] == "dialogue.mara.world_resolved"

    sim2 = load_fixture("FX-VILLAGE", seed=506)
    state2 = sim2.state
    fx2 = state2.board["fx_village"]
    q2 = fx2["quest_id"]
    f2 = fx2["factory_id"]
    QuestService(state2).accept(q2)
    BuildingService(state2).destroy(f2, cause_id="cause:raid")
    lost = QuestService(state2).evaluate(q2, world_signals={"target_destroyed": True})
    assert lost["status"] == "failed_with_consequence"
    assert _ack_for("target_destroyed")["id"] == "dialogue.mara.displaced_loss"


def test_no_duplicate_quest_or_reward_on_return() -> None:
    sim = load_fixture("FX-VILLAGE", seed=505)
    state = sim.state
    fx = state.board["fx_village"]
    quest_id = fx["quest_id"]
    factory_id = fx["factory_id"]
    mara_id = fx["mara_id"]
    svc = QuestService(state)
    svc.accept(quest_id)
    # Leave / save / return — same quest id, same bindings.
    saved = state.to_dict()
    restored_state = type(state).from_dict(saved)
    assert list(restored_state.quests.keys()) == [quest_id]
    assert restored_state.quests[quest_id]["stakeholder_id"] == mara_id
    assert restored_state.quests[quest_id]["status"] == "active"
    svc2 = QuestService(restored_state)
    restored_state.hazards["catastrophe"]["cubes"]["cube:demon"]["active"] = False
    restored_state.definitions["installed_routes"]["route:A"]["available"] = True
    _confirm_industry(restored_state, factory_id, "route:A")
    first = svc2.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": "demon_duel"},
    )
    assert first["status"] == "completed"
    # Second evaluate / return does not re-complete or mint a second quest.
    again = svc2.evaluate(
        quest_id,
        world_signals={"output_confirmed": True, "intervention": "demon_duel"},
    )
    assert again["status"] == "unchanged"
    assert len(restored_state.quests) == 1
    assert restored_state.quests[quest_id]["status"] == "completed"
