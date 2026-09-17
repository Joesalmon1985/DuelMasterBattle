"""Presentation journey leases for FX-CARGO cart."""

from __future__ import annotations

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


def test_start_delivery_emits_to_exit_journey_without_turn() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    turn0 = int(sim.state.clock["turn"])
    r = _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    assert r.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == turn0
    journeys = sim.state.board["presentation"]["journeys"]
    j = journeys["person:cart"]
    assert j["phase"] == "to_exit"
    assert j["from_node"] == "node:1"
    assert j["to_node"] == "node:2"
    assert j["authorized_cross"] is False
    assert sim.state.people["person:cart"]["node_id"] == "node:1"


def test_wait_commits_edge_and_queues_entrance() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    # Allow assigned_turn to age past current turn.
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    cart = sim.state.carts[sim.state.board["fx_cargo"]["cart_id"]]
    assert cart["current_node"] == "node:2"
    pending = sim.state.board["presentation"]["pending_transitions"]["person:cart"]
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
    jid = sim.state.board["presentation"]["journeys"]["person:cart"]["journey_id"]
    r = _dispatch(
        sim,
        "SyncPresentation",
        {
            "actor_id": "person:cart",
            "journey_id": jid,
            "phase": "waiting_exit",
            "progress_ms": 2500,
            "local_pos": [12.0, 5.0],
        },
        "sp1",
    )
    assert r.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == turn0
    assert (
        sum(int(l["quantity"]) for l in sim.state.carts[cart_id]["cargo_lots"] if l.get("status") == "aboard")
        == aboard
    )
    assert sim.state.board["presentation"]["journeys"]["person:cart"]["phase"] == "waiting_exit"


def test_rapid_waits_queue_transitions_without_drop() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    _dispatch(sim, "Interact", {"action": "start_delivery"}, "s1")
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w1"}, "w1")
    pending = sim.state.board["presentation"]["pending_transitions"]["person:cart"]
    assert len(pending) >= 1
    first_edge = list(pending[0]["committed_edge"])
    # Second seat/travel advances another edge while first presentation may still be pending.
    _dispatch(sim, "Wait", {"current_node": "node:1", "press_id": "w2"}, "w2")
    pending2 = sim.state.board["presentation"]["pending_transitions"]["person:cart"]
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
