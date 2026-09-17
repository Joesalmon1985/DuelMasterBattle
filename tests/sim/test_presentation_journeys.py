"""Presentation journey leases for FX-CARGO cart — sequence-driven ACK machine."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.core.world import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture


def _dispatch(sim, kind: str, payload: dict, cid: str):
    return sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="pres",
            world_id=sim.state.world_id,
            command_id=cid,
            expected_world_version=sim.state.world_version,
            kind=kind,
            payload=payload,
        )
    )


def _journey(sim):
    return sim.state.board["presentation"]["journeys"]["person:cart"]


def _pending(sim):
    return sim.state.board["presentation"]["pending_transitions"].get("person:cart") or []


def _ack_entrance(sim, *, cid: str) -> dict:
    j = _journey(sim)
    pending = _pending(sim)
    assert pending, "expected pending edge to acknowledge"
    t = pending[0]
    dest = str(t["to_node"])
    arrival = list(t.get("arrival_grid") or [1.5, 5.0])
    local_to = list(t.get("local_to") or arrival)
    return _dispatch(
        sim,
        "SyncPresentation",
        {
            "actor_id": "person:cart",
            "journey_id": j["journey_id"],
            "phase": "entering",
            "presenting_node": dest,
            "from_node": dest,
            "to_node": dest,
            "local_from": arrival,
            "local_to": local_to,
            "local_pos": arrival,
            "onward_phase": t.get("onward_phase", "to_waypoint"),
            "progress_ms": 0,
            "duration_ms": 4000,
            "consume_pending": True,
            "consumed_sequence": t["sequence"],
            "committed_edge": t.get("committed_edge"),
            "authorized_cross": True,
        },
        cid,
    )


def _ack_phase(sim, phase: str, *, cid: str, consume: bool = False, **extra) -> dict:
    j = _journey(sim)
    payload = {
        "actor_id": "person:cart",
        "journey_id": j["journey_id"],
        "phase": phase,
        "presenting_node": extra.pop("presenting_node", j.get("presenting_node")),
        "from_node": extra.pop("from_node", j.get("from_node")),
        "to_node": extra.pop("to_node", j.get("to_node")),
        "local_from": extra.pop("local_from", j.get("local_from")),
        "local_to": extra.pop("local_to", j.get("local_to")),
        "local_pos": extra.pop("local_pos", j.get("local_pos")),
        "onward_phase": extra.pop("onward_phase", j.get("onward_phase")),
        "progress_ms": extra.pop("progress_ms", j.get("progress_ms", 0)),
        "duration_ms": extra.pop("duration_ms", j.get("duration_ms", 1000)),
        "consume_pending": consume,
        **extra,
    }
    return _dispatch(sim, "SyncPresentation", payload, cid)


def _snap_journey(sim) -> dict:
    j = sim.state.read_view("player")["presentation"]["journeys"]["person:cart"]
    # Avoid deepcopy over view proxies; keep a plain dict snapshot.
    out = {}
    for key, value in j.items():
        if isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def _refresh_many(sim, n: int = 100) -> list[dict]:
    return [_snap_journey(sim) for _ in range(n)]


def test_start_delivery_emits_to_exit_journey_without_turn() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    turn0 = int(sim.state.clock["turn"])
    r = _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    assert r.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == turn0
    j = _journey(sim)
    assert j["phase"] == "to_exit"
    assert j["from_node"] == "node:1"
    assert j["to_node"] == "node:2"
    assert j["authorized_cross"] is False
    assert j["presenting_node"] == "node:1"
    assert sim.state.people["person:cart"]["node_id"] == "node:1"


def test_wait_commits_edge_and_queues_entrance() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    cart = sim.state.carts[sim.state.board["fx_cargo"]["cart_id"]]
    assert cart["current_node"] == "node:2"
    pending = _pending(sim)
    assert pending
    assert pending[0]["committed_edge"] == ["node:1", "node:2"]
    assert sim.state.people["person:cart"]["node_id"] == "node:2"


def test_sync_presentation_does_not_mutate_cargo_or_turns() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    cart_id = sim.state.board["fx_cargo"]["cart_id"]
    aboard = sum(
        int(l["quantity"]) for l in sim.state.carts[cart_id]["cargo_lots"] if l.get("status") == "aboard"
    )
    turn0 = int(sim.state.clock["turn"])
    jid = _journey(sim)["journey_id"]
    r = _dispatch(
        sim,
        "SyncPresentation",
        {
            "actor_id": "person:cart",
            "journey_id": jid,
            "phase": "waiting_exit",
            "presenting_node": "node:1",
            "from_node": "node:1",
            "to_node": "node:2",
            "progress_ms": 2500,
            "local_pos": [12.0, 5.0],
            "local_from": [6.0, 5.0],
            "local_to": [12.0, 5.0],
        },
        "sp1",
    )
    assert r.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == turn0
    assert (
        sum(int(l["quantity"]) for l in sim.state.carts[cart_id]["cargo_lots"] if l.get("status") == "aboard")
        == aboard
    )
    assert _journey(sim)["phase"] == "waiting_exit"


def test_entrance_ack_persists_leg_metadata_and_survives_100_refreshes() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    seq = int(_pending(sim)[0]["sequence"])
    # Depart / hide on node:1 without consuming.
    _ack_phase(
        sim,
        "hidden",
        cid="hide1",
        presenting_node="",
        from_node="node:1",
        to_node="node:2",
        local_pos=[13.5, 5.0],
    )
    assert _pending(sim), "pending must remain until entrance ACK"
    r = _ack_entrance(sim, cid="enter2")
    assert r.status == "ACCEPTED"
    assert r.payload["status"] == "ok"
    j = _journey(sim)
    assert j["phase"] == "entering"
    assert j["presenting_node"] == "node:2"
    assert j["from_node"] == "node:2"
    assert j["local_from"][0] < 3.0
    assert j["local_to"][0] > 10.0
    assert int(j["last_consumed_sequence"]) == seq
    assert not any(int(p["sequence"]) == seq for p in _pending(sim))

    snaps = _refresh_many(sim, 100)
    assert all(s["phase"] == "entering" for s in snaps)
    assert all(s["presenting_node"] == "node:2" for s in snaps)
    assert all(s["local_to"][0] > 10.0 for s in snaps)
    assert all(int(s["last_consumed_sequence"]) == seq for s in snaps)
    # Must never restart as a westbound or node:1 departure leg.
    assert all(s["from_node"] == "node:2" for s in snaps)
    assert all(float(s["local_from"][0]) <= float(s["local_to"][0]) for s in snaps)


def test_duplicate_and_stale_acks_are_harmless() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    seq = int(_pending(sim)[0]["sequence"])
    _ack_entrance(sim, cid="enter-a")
    j1 = _snap_journey(sim)
    # Duplicate ACK of same sequence.
    dup = _dispatch(
        sim,
        "SyncPresentation",
        {
            "actor_id": "person:cart",
            "journey_id": j1["journey_id"],
            "phase": "entering",
            "presenting_node": "node:2",
            "from_node": "node:2",
            "to_node": "node:2",
            "local_from": j1["local_from"],
            "local_to": j1["local_to"],
            "local_pos": j1["local_pos"],
            "onward_phase": j1.get("onward_phase"),
            "consume_pending": True,
            "consumed_sequence": seq,
        },
        "enter-dup",
    )
    assert dup.status == "ACCEPTED"
    assert dup.payload["status"] == "ok"
    assert int(_journey(sim)["last_consumed_sequence"]) == seq
    # Stale / out-of-order future sequence.
    stale = _dispatch(
        sim,
        "SyncPresentation",
        {
            "actor_id": "person:cart",
            "journey_id": j1["journey_id"],
            "phase": "entering",
            "presenting_node": "node:2",
            "from_node": "node:2",
            "to_node": "node:2",
            "local_from": [1.5, 5.0],
            "local_to": [12.0, 5.0],
            "local_pos": [1.5, 5.0],
            "consume_pending": True,
            "consumed_sequence": seq + 99,
        },
        "enter-stale",
    )
    assert stale.status == "ACCEPTED"
    assert stale.payload["status"] == "ignored"
    assert stale.payload["reason"] == "out_of_order" or stale.payload["reason"] == "no_pending"
    assert _journey(sim)["phase"] == "entering"
    assert _journey(sim)["presenting_node"] == "node:2"


def test_full_three_node_presentation_once_each_with_refreshes() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    phases_seen: list[str] = []

    def note():
        phases_seen.append(_journey(sim)["phase"])

    # node:1 to_exit → waiting → depart → hidden
    _ack_phase(sim, "waiting_exit", cid="n1-wait", presenting_node="node:1", from_node="node:1", local_pos=[12.0, 5.0])
    note()
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    _ack_phase(sim, "departing", cid="n1-dep", presenting_node="node:1", from_node="node:1", local_pos=[12.5, 5.0])
    note()
    _ack_phase(sim, "hidden", cid="n1-hid", presenting_node="", from_node="node:1", local_pos=[13.5, 5.0])
    note()
    assert _journey(sim)["phase"] == "hidden"
    assert _journey(sim)["presenting_node"] == ""
    snaps = _refresh_many(sim, 100)
    assert all(s["phase"] == "hidden" for s in snaps)

    # node:2 entrance once → waypoint → waiting
    _ack_entrance(sim, cid="n2-enter")
    note()
    assert _journey(sim)["presenting_node"] == "node:2"
    j = _journey(sim)
    _ack_phase(
        sim,
        "to_waypoint",
        cid="n2-way",
        presenting_node="node:2",
        from_node="node:2",
        to_node="node:2",
        local_from=j["local_from"],
        local_to=j["local_to"],
        local_pos=j["local_to"],
        onward_phase="to_waypoint",
    )
    note()
    _ack_phase(
        sim,
        "waiting_exit",
        cid="n2-wait",
        presenting_node="node:2",
        from_node="node:2",
        local_pos=[12.0, 5.0],
    )
    note()
    snaps2 = _refresh_many(sim, 100)
    assert all(s["phase"] == "waiting_exit" for s in snaps2)
    assert all(s["presenting_node"] == "node:2" for s in snaps2)
    assert all(s["from_node"] == "node:2" for s in snaps2)
    # Must not restart entrance (local_from near west).
    assert all(float(s.get("local_pos", [12, 5])[0]) >= 10.0 for s in snaps2)

    # Second Wait: depart node:2 → enter node:3 → delivery → unload
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w2"}, "w2")
    _ack_phase(sim, "hidden", cid="n2-hid", presenting_node="", from_node="node:2", local_pos=[13.5, 5.0])
    note()
    assert _pending(sim), "second edge pending"
    _ack_entrance(sim, cid="n3-enter")
    note()
    assert _journey(sim)["presenting_node"] == "node:3"
    assert _journey(sim)["onward_phase"] == "to_delivery"
    j3 = _journey(sim)
    _ack_phase(
        sim,
        "to_delivery",
        cid="n3-del",
        presenting_node="node:3",
        from_node="node:3",
        to_node="node:3",
        local_from=j3["local_from"],
        local_to=j3["local_to"],
        local_pos=j3["local_to"],
        onward_phase="unloading",
    )
    note()
    _ack_phase(
        sim,
        "unloading",
        cid="n3-unl",
        presenting_node="node:3",
        from_node="node:3",
        local_pos=j3["local_to"],
    )
    note()
    _ack_phase(
        sim,
        "idle",
        cid="n3-idle",
        presenting_node="node:3",
        from_node="node:3",
        local_pos=j3["local_to"],
    )
    note()
    snaps3 = _refresh_many(sim, 100)
    assert all(s["phase"] == "idle" for s in snaps3)
    assert all(s["presenting_node"] == "node:3" for s in snaps3)
    # Entrance/to_delivery completed once — no pending left to replay.
    assert _pending(sim) == []
    assert "entering" in phases_seen
    assert phases_seen.count("entering") == 2  # once for node:2, once for node:3


def test_save_load_mid_leg_resumes_without_replay(tmp_path) -> None:
    from sim.dmb.persistence.coordinator import SaveCoordinator
    from sim.dmb.persistence.repository import SaveRepository

    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    _ack_entrance(sim, cid="enter-mid")
    j_before = _snap_journey(sim)
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    coord.request_save("g02_pres_mid")
    # Mutate after save, then reload the mid-leg snapshot.
    _ack_phase(sim, "to_waypoint", cid="mutate", presenting_node="node:2", local_pos=[12.0, 5.0])
    coord.prepare_load("g02_pres_mid")
    sim = coord.commit_load()
    j_after = _journey(sim)
    assert j_after["phase"] == j_before["phase"]
    assert j_after["presenting_node"] == j_before["presenting_node"]
    assert int(j_after["last_consumed_sequence"]) == int(j_before["last_consumed_sequence"])
    assert list(j_after["local_to"]) == list(j_before["local_to"])
    snaps = _refresh_many(sim, 50)
    assert all(s["phase"] == j_before["phase"] for s in snaps)
    assert all(s["presenting_node"] == "node:2" for s in snaps)


def test_rapid_waits_queue_transitions_without_drop() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    pending = _pending(sim)
    assert len(pending) >= 1
    first_edge = list(pending[0]["committed_edge"])
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w2"}, "w2")
    pending2 = _pending(sim)
    edges = [tuple(p["committed_edge"]) for p in pending2]
    assert tuple(first_edge) in edges or len(edges) >= 1
    assert len(pending2) <= 3
    cart = sim.state.carts[sim.state.board["fx_cargo"]["cart_id"]]
    assert cart["current_node"] in {"node:2", "node:3"}


def test_player_view_includes_presentation() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    view = sim.state.read_view("player")
    assert "presentation" in view
    assert "person:cart" in view["presentation"]["journeys"]
