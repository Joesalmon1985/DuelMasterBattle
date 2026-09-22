"""G05 simple persistent blocked-exit rockfall quest (any village worker)."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.narrative.knowledge import KnowledgeFact, reveal
from sim.dmb.narrative.semantic import SemanticResolver
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import (
    ACTIVITY_CLEARING,
    MOVE_DURATION_MS,
    QUEST_INSTANCE_ID,
    ROCKFALL_ID,
    TEMPLATE_ID,
    accept_move,
    blocked_tiles,
    complete_move,
    eligible_boulder_helpers,
    get_rockfall,
    install_boulder_quest,
    revalidate,
    rockfall_blocks_travel,
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


def _reveal_rockfall(sim: WorldSim) -> None:
    reveal(sim.state, ROCKFALL_ID, KnowledgeFact(ROCKFALL_ID, "observed", role="rockfall"), role="rockfall")


def _ask_helper(sim: WorldSim, worker_id: str, *, cid: str) -> dict:
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": worker_id}, cid=f"{cid}-talk")
    session = (talk.get("payload") or {}).get("session") or {}
    choices = (talk.get("payload") or {}).get("choices") or []
    assert any(c.get("id") == "ask_clear_rockfall" for c in choices), choices
    return _cmd(
        sim,
        "Interact",
        {
            "action": "choose_dialogue",
            "session_id": session["id"],
            "choice_id": "ask_clear_rockfall",
        },
        cid=f"{cid}-ask",
    )


def test_rockfall_covers_exit_corridor() -> None:
    sim = _sim()
    meta = _meta(sim)
    assert meta["from_node"] == "node:35"
    assert meta["to_node"] == "node:29"
    assert meta["exit_id"] == "node:35.south"
    assert meta.get("rockfall_id") == ROCKFALL_ID or meta.get("boulder_id") == ROCKFALL_ID
    assert meta.get("helper_person_id") in {None, ""}
    rockfall = get_rockfall(sim.state)
    assert rockfall is not None
    assert rockfall["status"] == "blocking"
    pieces = rockfall.get("pieces") or []
    assert 3 <= len(pieces) <= 5
    tiles = blocked_tiles(rockfall, game_ms=0)
    assert len(tiles) >= 3
    xs = {t[0] for t in tiles}
    assert min(xs) < 24 < max(xs) or len(xs) >= 2
    area = export_overworld_area(sim.state, "node:35")
    ents = [e for e in area["entities"] if e.get("id") == ROCKFALL_ID]
    assert len(ents) == 1
    assert ents[0]["kind"] == "rockfall"
    assert ents[0]["label"] == "Rockfall"
    assert len(ents[0].get("pieces") or []) >= 3
    assert ents[0].get("blocked_tiles")
    exits = (sim.state.board["nodes"]["node:35"].get("exits") or {})
    assert "node:29" in exits


def test_multiple_eligible_workers() -> None:
    sim = _sim()
    helpers = eligible_boulder_helpers(sim.state, "node:35")
    assert len(helpers) >= 3
    occupations = {sim.state.people[pid]["occupation"] for pid in helpers}
    assert "Factory worker" in occupations
    assert any(o != "Factory worker" for o in occupations)
    quest = sim.state.quests[QUEST_INSTANCE_ID]
    assert quest["status"] == "offered"
    assert quest.get("helper_person_id") in {None, ""}
    assert quest.get("stakeholder_id") in {None, ""}


def test_each_eligible_worker_offers_after_inspect() -> None:
    sim = _sim()
    helpers = eligible_boulder_helpers(sim.state, "node:35")
    _reveal_rockfall(sim)
    for i, wid in enumerate(helpers):
        talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": wid}, cid=f"talk-{i}")
        choices = (talk.get("payload") or {}).get("choices") or []
        assert any(c.get("id") == "ask_clear_rockfall" for c in choices), (wid, choices)
        assert any(c.get("id") == "ask_occupation" for c in choices)


def test_occupation_choice_does_not_start_clearing() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    _reveal_rockfall(sim)
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": helper}, cid="occ-talk")
    session = (talk.get("payload") or {}).get("session") or {}
    _cmd(
        sim,
        "Interact",
        {"action": "choose_dialogue", "session_id": session["id"], "choice_id": "ask_occupation"},
        cid="occ-choose",
    )
    assert get_rockfall(sim.state)["status"] == "blocking"
    assert sim.state.quests[QUEST_INSTANCE_ID]["status"] == "offered"
    assert sim.state.people[helper].get("activity") != ACTIVITY_CLEARING


def test_asking_worker_a_or_b_binds_that_helper() -> None:
    helpers = eligible_boulder_helpers(_sim().state, "node:35")
    a, b = helpers[0], helpers[1]

    sim_a = _sim()
    _reveal_rockfall(sim_a)
    _ask_helper(sim_a, a, cid="a")
    assert sim_a.state.quests[QUEST_INSTANCE_ID]["helper_person_id"] == a
    assert get_rockfall(sim_a.state)["helper_person_id"] == a
    assert sim_a.state.people[a]["activity"] == ACTIVITY_CLEARING

    sim_b = _sim()
    _reveal_rockfall(sim_b)
    _ask_helper(sim_b, b, cid="b")
    assert sim_b.state.quests[QUEST_INSTANCE_ID]["helper_person_id"] == b
    assert get_rockfall(sim_b.state)["helper_person_id"] == b


def test_second_worker_cannot_duplicate_after_bind() -> None:
    sim = _sim()
    helpers = eligible_boulder_helpers(sim.state, "node:35")
    a, b = helpers[0], helpers[1]
    _reveal_rockfall(sim)
    _ask_helper(sim, a, cid="first")
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": b}, cid="second-talk")
    choices = (talk.get("payload") or {}).get("choices") or []
    assert not any(c.get("id") == "ask_clear_rockfall" for c in choices)
    text = str((talk.get("payload") or {}).get("text") or "")
    assert "rocks" in text.lower() or "dealing" in text.lower() or choices == []


def test_completion_text_not_before_clear() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    _reveal_rockfall(sim)
    _ask_helper(sim, helper, cid="mid")
    # Still clearing — helper must not get completion line.
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": helper}, cid="mid-retalk")
    assert talk["status"] == "ACCEPTED"
    text = str((talk.get("payload") or {}).get("text") or talk.get("public_feedback") or "")
    assert "cleared" not in text.lower()
    assert "get through" not in text.lower()
    assert "moment" in text.lower() or "shifted" in text.lower()


def test_blocked_travel_and_open_after_clear() -> None:
    sim = _sim()
    meta = _meta(sim)
    turn_before = int(sim.state.clock.get("turn") or 0)
    reply = _cmd(
        sim,
        "Travel",
        {"from_node": meta["from_node"], "to_node": meta["to_node"]},
        cid="travel-blocked",
    )
    assert reply["status"] == "REJECTED"
    assert "rockfall" in str(reply.get("public_feedback") or "").lower()
    assert int(sim.state.clock.get("turn") or 0) == turn_before

    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    accept_move(sim.state, helper_person_id=helper)
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 200, "clock_sequence": seq + 1},
        cid="adv1",
    )
    rockfall = get_rockfall(sim.state)
    assert rockfall["status"] == "cleared"
    assert not blocked_tiles(rockfall, game_ms=int(sim.state.clock["game_ms"]))
    for piece in rockfall["pieces"]:
        assert list(piece["position"]) == list(piece["cleared_position"])
    assert sim.state.quests[QUEST_INSTANCE_ID]["status"] == "completed"
    assert sim.state.people[helper].get("activity") != ACTIVITY_CLEARING
    travel = _cmd(
        sim,
        "Travel",
        {"from_node": meta["from_node"], "to_node": meta["to_node"]},
        cid="travel-open",
    )
    assert travel["status"] == "ACCEPTED"
    assert int(sim.state.clock.get("turn") or 0) == turn_before + 1


def test_nearby_inspect_includes_worker_hint() -> None:
    sim = _sim()
    reply = _cmd(sim, "Observe", {"entity_id": ROCKFALL_ID}, cid="obs")
    assert reply["status"] == "ACCEPTED"
    known = sim.state.knowledge.get(ROCKFALL_ID) or {}
    assert known.get("fact") == "observed"
    resolver = SemanticResolver(sim.state)
    rockfall = get_rockfall(sim.state)
    pos = list(rockfall["pieces"][1]["blocking_position"])
    near = resolver.inspect(
        ROCKFALL_ID,
        local_poses={"wizard": pos, ROCKFALL_ID: pos},
    )
    desc = str(near.get("description") or "")
    assert "workers" in desc.lower()
    assert "help" in desc.lower()


def test_done_dialogue_only_after_clear_and_ack_on_close() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    accept_move(sim.state, helper_person_id=helper)
    complete_move(sim.state)
    assert get_rockfall(sim.state)["status"] == "cleared"
    assert not rockfall_blocks_travel(sim.state, "node:35", "node:29")
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": helper}, cid="done-talk")
    text = str((talk.get("payload") or {}).get("text") or "")
    assert "cleared" in text.lower()
    session = (talk.get("payload") or {}).get("session") or {}
    assert not sim.state.quests[QUEST_INSTANCE_ID].get("completion_ack")
    _cmd(sim, "Interact", {"action": "close_dialogue", "session_id": session["id"]}, cid="done-close")
    assert sim.state.quests[QUEST_INSTANCE_ID].get("completion_ack")
    later = _cmd(sim, "Interact", {"action": "talk", "entity_id": helper}, cid="later")
    later_choices = (later.get("payload") or {}).get("choices") or []
    assert not any(c.get("id") == "ask_clear_rockfall" for c in later_choices)


def test_save_load_helper_and_pieces() -> None:
    sim = _sim()
    helpers = eligible_boulder_helpers(sim.state, "node:35")
    helper = helpers[2]
    before = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_rockfall(before)["status"] == "blocking"
    assert before.quests[QUEST_INSTANCE_ID].get("helper_person_id") in {None, ""}

    accept_move(sim.state, helper_person_id=helper)
    mid = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_rockfall(mid)["status"] == "clearing"
    assert mid.quests[QUEST_INSTANCE_ID]["helper_person_id"] == helper
    assert mid.people[helper]["activity"] == ACTIVITY_CLEARING

    complete_move(sim.state)
    after = WorldState.from_dict(deepcopy(sim.state.to_dict()))
    assert get_rockfall(after)["status"] == "cleared"
    assert after.quests[QUEST_INSTANCE_ID]["helper_person_id"] == helper
    for piece in get_rockfall(after)["pieces"]:
        assert list(piece["position"]) == list(piece["cleared_position"])


def test_reinstall_dedupes() -> None:
    sim = _sim()
    again = install_boulder_quest(sim.state, start_node_id="node:35")
    assert again["quest_id"] == QUEST_INSTANCE_ID
    assert again.get("status") == "deduped"
    assert sum(1 for q in sim.state.quests.values() if q.get("template_id") == TEMPLATE_ID) == 1


def test_other_exits_still_travel() -> None:
    sim = _sim()
    turn_before = int(sim.state.clock.get("turn") or 0)
    reply = _cmd(sim, "Travel", {"from_node": "node:35", "to_node": "node:30"}, cid="west")
    assert reply["status"] == "ACCEPTED"
    assert int(sim.state.clock.get("turn") or 0) == turn_before + 1


def test_pause_freezes_progress() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    accept_move(sim.state, helper_person_id=helper)
    start_ms = int(get_rockfall(sim.state)["move_started_game_ms"])
    pause = _cmd(sim, "Pause", {"reason": "test"}, cid="pause1")
    token = (pause.get("payload") or {}).get("token")
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 500, "clock_sequence": seq + 1},
        cid="adv-paused",
    )
    assert get_rockfall(sim.state)["status"] == "clearing"
    assert int(sim.state.clock.get("game_ms") or 0) == start_ms
    _cmd(sim, "Resume", {"token": token}, cid="resume1")
    seq = int(sim.state.clock.get("clock_sequence") or 0)
    _cmd(
        sim,
        "AdvanceGame",
        {"delta_ms": MOVE_DURATION_MS + 500, "clock_sequence": seq + 1},
        cid="adv-resume",
    )
    assert get_rockfall(sim.state)["status"] == "cleared"
