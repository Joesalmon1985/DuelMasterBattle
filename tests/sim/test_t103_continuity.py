"""T103 — Rockfall / Person / item continuity through era transition."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.eras.continuity import ContinuityService, person_continuity_row, truthful_occupation_line
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import (
    QUEST_INSTANCE_ID,
    ROCKFALL_ID,
    accept_move,
    complete_move,
    eligible_boulder_helpers,
    get_rockfall,
    rockfall_blocks_travel,
)


def _sim():
    return load_fixture("FX-VILLAGE", seed=507)


def test_person_ids_stable_through_continuity() -> None:
    sim = _sim()
    before_ids = set(sim.state.people)
    sample = sorted(before_ids)[:5]
    before_rows = {pid: person_continuity_row(sim.state, pid) for pid in sample}
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:people")
    assert set(sim.state.people) == before_ids
    for pid in sample:
        after = person_continuity_row(sim.state, pid)
        assert after["person_id"] == before_rows[pid]["person_id"]
        assert after["alive"] == before_rows[pid]["alive"]


def test_rockfall_unseen_blocking_preserved() -> None:
    sim = _sim()
    assert get_rockfall(sim.state) is not None
    assert rockfall_blocks_travel(sim.state, "node:35", "node:29")
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:unseen")
    assert get_rockfall(sim.state)["id"] == ROCKFALL_ID
    assert get_rockfall(sim.state)["status"] in {"blocking", "clearing"}
    assert rockfall_blocks_travel(sim.state, "node:35", "node:29")
    assert QUEST_INSTANCE_ID in sim.state.quests


def test_helper_binding_survives_clearing_state() -> None:
    sim = _sim()
    helpers = eligible_boulder_helpers(sim.state, "node:35")
    assert helpers
    helper = helpers[0]
    accept_move(sim.state, helper_person_id=helper)
    assert sim.state.quests[QUEST_INSTANCE_ID]["helper_person_id"] == helper
    assert get_rockfall(sim.state)["status"] in {"clearing", "moving"}
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:clearing")
    assert sim.state.quests[QUEST_INSTANCE_ID]["helper_person_id"] == helper
    assert get_rockfall(sim.state)["helper_person_id"] == helper
    assert set(sim.state.people) >= {helper}
    # No clone
    assert sum(1 for p in sim.state.people if p == helper) == 1


def test_cleared_rockfall_stays_cleared() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    accept_move(sim.state, helper_person_id=helper)
    complete_move(sim.state)
    assert sim.state.quests[QUEST_INSTANCE_ID]["status"] == "completed"
    assert get_rockfall(sim.state)["status"] in {"cleared", "moved"}
    assert not rockfall_blocks_travel(sim.state, "node:35", "node:29")
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:cleared")
    assert sim.state.quests[QUEST_INSTANCE_ID]["status"] == "completed"
    assert get_rockfall(sim.state)["status"] == "cleared"
    assert not rockfall_blocks_travel(sim.state, "node:35", "node:29")
    # No NPC truthful claim of blocked via quest status
    assert sim.state.quests[QUEST_INSTANCE_ID]["status"] != "active" or get_rockfall(sim.state)["status"] == "cleared"


def test_dead_helper_not_resurrected() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    accept_move(sim.state, helper_person_id=helper)
    sim.state.people[helper]["alive"] = False
    sim.state.people[helper]["status"] = "dead"
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:dead_helper")
    assert sim.state.people[helper]["status"] == "dead"
    assert sim.state.people[helper]["alive"] is False
    assert sim.state.quests[QUEST_INSTANCE_ID].get("helper_person_id") in {None, ""}


def test_displaced_dialogue_truthful() -> None:
    sim = _sim()
    worker = next(
        pid
        for pid, p in sim.state.people.items()
        if p.get("workplace_id") and p.get("node_id") == "node:35" and p.get("alive", True)
    )
    workplace = sim.state.people[worker]["workplace_id"]
    # Collapse workplace into inert ruin.
    building = sim.state.buildings[workplace]
    building["status"] = "inert_ruin"
    building["ruin_only"] = True
    building["active"] = False
    sid = building.get("settlement_id")
    if sid and sid in sim.state.settlements:
        sim.state.settlements[sid]["ruin_only"] = True
        sim.state.settlements[sid]["operational"] = False
        sim.state.settlements[sid]["status"] = "inert"
    ContinuityService(sim.state).adapt_for_transition(
        transition_id="tr:displace",
        collapsed_faction_ids=[sim.state.settlements.get(sid, {}).get("faction_id")] if sid else [],
    )
    line = truthful_occupation_line(sim.state, worker)
    assert "used to work" in line.lower() or "don't have a workplace" in line.lower()
    assert "I work at" not in line or "used to" in line.lower()
    assert sim.state.people[worker]["id"] == worker
    assert sim.state.people[worker]["status"] == "displaced"


def test_protected_item_relocated_keeps_id() -> None:
    sim = _sim()
    item_id = sim.state.ids.new("item")
    # Place required item at a settlement that will collapse.
    settlements = [
        sid
        for sid, s in sim.state.settlements.items()
        if s.get("operational") and not s.get("staging") and s.get("node_id")
    ]
    assert settlements
    home = settlements[0]
    node = sim.state.settlements[home]["node_id"]
    sim.state.items[item_id] = {
        "id": item_id,
        "definition_id": "item.quest_key",
        "alive": True,
        "required": True,
        "quest_linked": True,
        "node_id": node,
        "settlement_id": home,
        "location": "ground",
    }
    sim.state.settlements[home]["ruin_only"] = True
    sim.state.settlements[home]["status"] = "inert"
    sim.state.settlements[home]["operational"] = False
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:item")
    assert item_id in sim.state.items
    assert sim.state.items[item_id]["id"] == item_id
    assert sim.state.items[item_id].get("alive", True)


def test_continuity_idempotent_no_quest_duplicate() -> None:
    sim = _sim()
    ContinuityService(sim.state).adapt_for_transition(transition_id="tr:once")
    again = ContinuityService(sim.state).adapt_for_transition(transition_id="tr:once")
    assert again["idempotent"] is True
    assert sum(1 for qid in sim.state.quests if qid == QUEST_INSTANCE_ID) == 1
