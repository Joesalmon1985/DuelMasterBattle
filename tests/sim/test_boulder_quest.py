"""G05 simple persistent blocked-exit boulder quest."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import WorldSim
from sim.dmb.narrative.knowledge import KnowledgeFact, reveal
from sim.dmb.narrative.semantic import SemanticResolver
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import (
    ACTIVITY_MOVING,
    BOULDER_ID,
    MOVE_DURATION_MS,
    QUEST_INSTANCE_ID,
    TEMPLATE_ID,
    accept_move,
    complete_move,
    get_boulder,
    install_boulder_quest,
    revalidate,
)
from sim.dmb.world.overworld_export import export_overworld_area


def _sim() -> WorldSim:
    return load_fixture("FX-VILLAGE", seed=507)


def _meta(sim: WorldSim) -> dict:
    return dict(((sim.state.board.get("g05") or {}).get("boulder_quest") or {}))


def _cmd(sim: WorldSim, kind: str, payload: dict, *, cid: str = "c1") -> dict:
    env = CommandEnvelope(
        protocol_version=1,
        session_id="test",
        world_id=sim.state.world_id,
        command_id=cid,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )
    return sim.dispatch(env).to_dict()


def test_exactly_one_boulder_blocks_selected_exit() -> None:
    sim = _sim()
    meta = _meta(sim)
    assert meta["from_node"] == "node:35"
    assert meta["to_node"] == "node:29"
    assert meta["exit_id"] == "node:35.south"
    assert meta["boulder_id"] == BOULDER_ID
    mechs = (sim.state.board.get("mechanisms") or {})
    boulders = [m for m in mechs.values() if str(m.get("kind")) == "boulder"]
    assert len(boulders) == 1
    boulder = get_boulder(sim.state)
    assert boulder is not None
    assert boulder["status"] == "blocking"
    # Strategic adjacency remains.
    exits = (sim.state.board["nodes"]["node:35"].get("exits") or {})
    assert "node:29" in exits
    area = export_overworld_area(sim.state, "node:35")
    ents = [e for e in area["entities"] if e.get("id") == BOULDER_ID]
    assert len(ents) == 1
    assert ents[0]["kind"] == "boulder"


def test_blocked_travel_rejects_without_world_turn() -> None:
    sim = _sim()
    meta = _meta(sim)
    turn_before = int(sim.state.clock.get("turn") or 0)
    node_before = sim.state.player["node_id"]
    reply = _cmd(
        sim,
        "Travel",
        {"from_node": meta["from_node"], "to_node": meta["to_node"]},
        cid="travel-blocked",
    )
    assert reply["status"] == "REJECTED"
    assert "boulder blocks" in str(reply.get("public_feedback") or "").lower()
    assert int(sim.state.clock.get("turn") or 0) == turn_before
    assert sim.state.player["node_id"] == node_before


def test_other_exits_still_travel() -> None:
    sim = _sim()
    turn_before = int(sim.state.clock.get("turn") or 0)
    reply = _cmd(
        sim,
        "Travel",
        {"from_node": "node:35", "to_node": "node:30"},
        cid="travel-west",
    )
    assert reply["status"] == "ACCEPTED"
    assert sim.state.player["node_id"] == "node:30"
    assert int(sim.state.clock.get("turn") or 0) == turn_before + 1


def test_observe_boulder_exposes_knowledge() -> None:
    sim = _sim()
    reply = _cmd(sim, "Observe", {"entity_id": BOULDER_ID}, cid="obs-b")
    assert reply["status"] == "ACCEPTED"
    known = sim.state.knowledge.get(BOULDER_ID) or {}
    assert known.get("fact") == "observed"
    desc = str((reply.get("payload") or {}).get("description") or "")
    assert "boulder" in desc.lower()
    resolver = SemanticResolver(sim.state)
    near = resolver.inspect(BOULDER_ID, local_poses={"wizard": [24.0, 40.0], BOULDER_ID: [24.0, 40.0]})
    assert "heavy" in str(near.get("description") or "").lower() or "John" in str(near.get("description") or "")


def test_quest_binds_one_factory_worker() -> None:
    sim = _sim()
    meta = _meta(sim)
    worker_id = str(meta["worker_person_id"])
    person = sim.state.people[worker_id]
    assert person["occupation"] == "Factory worker"
    assert person.get("workplace_id")
    quest = sim.state.quests[QUEST_INSTANCE_ID]
    assert quest["status"] == "offered"
    assert quest["stakeholder_id"] == worker_id
    assert quest["template_id"] == TEMPLATE_ID
    # Re-install must not duplicate.
    again = install_boulder_quest(sim.state, start_node_id="node:35")
    assert again["quest_id"] == QUEST_INSTANCE_ID
    assert sum(1 for q in sim.state.quests.values() if q.get("template_id") == TEMPLATE_ID) == 1


def test_ask_worker_transitions_once_and_sets_activity() -> None:
    sim = _sim()
    meta = _meta(sim)
    worker_id = str(meta["worker_person_id"])
    reveal(sim.state, BOULDER_ID, KnowledgeFact(BOULDER_ID, "observed", role="boulder"), role="boulder")
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": worker_id}, cid="talk1")
    assert talk["status"] == "ACCEPTED"
    session = (talk.get("payload") or {}).get("session") or {}
    choices = (talk.get("payload") or {}).get("choices") or []
    assert any(c.get("id") == "ask_move_boulder" for c in choices)
    choose = _cmd(
        sim,
        "Interact",
        {
            "action": "choose_dialogue",
            "session_id": session["id"],
            "choice_id": "ask_move_boulder",
        },
        cid="choose1",
    )
    assert choose["status"] == "ACCEPTED"
    quest = sim.state.quests[QUEST_INSTANCE_ID]
    assert quest["status"] == "active"
    assert int(quest["stage"]) == 2
    boulder = get_boulder(sim.state)
    assert boulder["status"] == "moving"
    assert boulder["moved_by_person_id"] == worker_id
    person = sim.state.people[worker_id]
    assert person["occupation"] == "Factory worker"
    assert person["activity"] == ACTIVITY_MOVING
    # Duplicate accept is idempotent.
    again = accept_move(sim.state, effect_id="effect.boulder_quest.accept")
    assert again["status"] == "idempotent"


def test_completion_moves_boulder_and_opens_travel() -> None:
    sim = _sim()
    meta = _meta(sim)
    worker_id = str(meta["worker_person_id"])
    accept_move(sim.state)
    boulder_id_before = BOULDER_ID
    pos_blocking = list(get_boulder(sim.state)["blocking_position"])
    # Advance Game Time past move duration.
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 200, "clock_sequence": seq + 1},
        cid="adv1",
    )
    boulder = get_boulder(sim.state)
    assert boulder["id"] == boulder_id_before
    assert boulder["status"] == "moved"
    assert list(boulder["position"]) != pos_blocking
    assert BOULDER_ID in (sim.state.board.get("mechanisms") or {})
    quest = sim.state.quests[QUEST_INSTANCE_ID]
    assert quest["status"] == "completed"
    person = sim.state.people[worker_id]
    assert person["occupation"] == "Factory worker"
    assert person.get("activity") != ACTIVITY_MOVING
    turn_before = int(sim.state.clock.get("turn") or 0)
    travel = _cmd(
        sim,
        "Travel",
        {"from_node": meta["from_node"], "to_node": meta["to_node"]},
        cid="travel-open",
    )
    assert travel["status"] == "ACCEPTED"
    assert sim.state.player["node_id"] == meta["to_node"]
    assert int(sim.state.clock.get("turn") or 0) == turn_before + 1


def test_pause_freezes_boulder_progress() -> None:
    sim = _sim()
    accept_move(sim.state)
    start_ms = int(get_boulder(sim.state)["move_started_game_ms"])
    pause = _cmd(sim, "Pause", {"reason": "test"}, cid="pause1")
    token = (pause.get("payload") or {}).get("token")
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 500, "clock_sequence": seq + 1},
        cid="adv-paused",
    )
    assert get_boulder(sim.state)["status"] == "moving"
    assert int(sim.state.clock.get("game_ms") or 0) == start_ms  # no advance while paused
    _cmd(sim, "Resume", {"token": token}, cid="resume1")
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 500, "clock_sequence": seq + 1},
        cid="adv-resume",
    )
    assert get_boulder(sim.state)["status"] == "moved"


def test_save_load_before_during_after() -> None:
    from sim.dmb.core.state import WorldState

    sim = _sim()
    meta = _meta(sim)
    # Before accept
    before = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_boulder(before)["status"] == "blocking"
    assert before.quests[QUEST_INSTANCE_ID]["status"] == "offered"

    # During move
    accept_move(sim.state)
    mid = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_boulder(mid)["status"] == "moving"
    assert mid.people[meta["worker_person_id"]]["activity"] == ACTIVITY_MOVING

    # After completion
    complete_move(sim.state)
    after = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_boulder(after)["status"] == "moved"
    assert after.quests[QUEST_INSTANCE_ID]["status"] == "completed"
    assert BOULDER_ID in (after.board.get("mechanisms") or {})
    assert meta["worker_person_id"] in after.people


def test_leave_return_preserves_ids() -> None:
    sim = _sim()
    meta = _meta(sim)
    worker_id = meta["worker_person_id"]
    _cmd(sim, "Travel", {"from_node": "node:35", "to_node": "node:30"}, cid="leave")
    assert sim.state.player["node_id"] == "node:30"
    # Return via reverse travel
    _cmd(sim, "Travel", {"from_node": "node:30", "to_node": "node:35"}, cid="return")
    assert sim.state.player["node_id"] == "node:35"
    assert worker_id in sim.state.people
    assert BOULDER_ID in (sim.state.board.get("mechanisms") or {})
    assert QUEST_INSTANCE_ID in sim.state.quests
    assert sum(1 for q in sim.state.quests.values() if q.get("template_id") == TEMPLATE_ID) == 1


def test_already_moved_cannot_create_duplicate_active_quest() -> None:
    sim = _sim()
    complete_move(sim.state)  # force moved even from offered
    # Re-offer path: evaluate should resolve rather than spawn a second quest.
    out = revalidate(sim.state)
    assert out["status"] in {"resolved_by_world", "unchanged", "ok"} or sim.state.quests[QUEST_INSTANCE_ID][
        "status"
    ] in {"completed", "resolved_by_world"}
    assert sum(1 for q in sim.state.quests.values() if q.get("template_id") == TEMPLATE_ID) == 1
    # Worker must not offer move when boulder already gone.
    worker_id = _meta(sim)["worker_person_id"]
    reveal(sim.state, BOULDER_ID, KnowledgeFact(BOULDER_ID, "observed", role="boulder"), role="boulder")
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": worker_id}, cid="talk-done")
    choices = (talk.get("payload") or {}).get("choices") or []
    assert not any(c.get("id") == "ask_move_boulder" for c in choices)


def test_dead_worker_before_accept_rebinds() -> None:
    sim = _sim()
    meta = _meta(sim)
    worker_id = str(meta["worker_person_id"])
    person = sim.state.people[worker_id]
    person["alive"] = False
    person["status"] = "dead"
    out = revalidate(sim.state)
    assert out["status"] == "rebound"
    new_id = out["worker_person_id"]
    assert new_id != worker_id
    assert sim.state.people[new_id]["occupation"] == "Factory worker"
    assert sim.state.quests[QUEST_INSTANCE_ID]["stakeholder_id"] == new_id
