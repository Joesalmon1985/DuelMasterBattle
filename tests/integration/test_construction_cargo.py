"""T038 FX-CARGO construction/cargo integration."""

from __future__ import annotations

from sim.dmb.testing.fixtures import load_fixture, run_fx_cargo


def test_fx_cargo_delivered_settlement_blockage_and_save() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    assert sim.state.board["fx_cargo"]["seed"] == 202
    result = run_fx_cargo(sim, seed=202)
    assert result.status == "PASS"
    assert result.details["block_cleared"] is True
    assert result.details["in_transit_cargo_preserved"] == 2
    assert result.details["settlement_at_n2"]


def test_load_fixture_fx_cargo_seed() -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    fx = sim.state.board["fx_cargo"]
    assert fx["cart_id"] in sim.state.carts
    assert sim.state.carts[fx["cart_id"]]["capacity"] == 4
    store = fx["store"]
    timber = sim.state.stocks[store]["catan"]["timber"]["available"]
    assert timber == 5
    assert set(sim.state.board["nodes"]) == {"node:1", "node:2", "node:3"}
    assert "person:warehouse" in sim.state.people
    assert "person:cart" in sim.state.people


def test_fx_cargo_playable_interact_delivery() -> None:
    """Fresh launch path: Interact start/block/clear + Wait — not run_fx_cargo() setup."""
    from sim.dmb.core.world import CommandEnvelope

    sim = load_fixture("FX-CARGO", seed=202)
    fx = sim.state.board["fx_cargo"]
    cart_id = fx["cart_id"]
    n0, n2 = fx["N0"], fx["N2"]

    def dispatch(kind: str, payload: dict, cid: str):
        return sim.dispatch(
            CommandEnvelope(
                protocol_version=1,
                session_id="play",
                world_id=sim.state.world_id,
                command_id=cid,
                expected_world_version=sim.state.world_version,
                kind=kind,
                payload=payload,
            )
        )

    start = dispatch("Interact", {"action": "start_delivery"}, "start-1")
    assert start.status == "ACCEPTED", start.public_feedback
    assert sim.state.carts[cart_id]["status"] == "en_route"
    aboard = sum(
        int(lot["quantity"])
        for lot in sim.state.carts[cart_id]["cargo_lots"]
        if lot.get("status") == "aboard"
    )
    assert aboard == 4

    block = dispatch("Interact", {"action": "place_route_block"}, "block-1")
    assert block.status == "ACCEPTED"
    dispatch("Wait", {"current_node": n0, "press_id": "pw1"}, "w1")
    assert sim.state.carts[cart_id]["status"] == "blocked"
    assert sim.state.carts[cart_id]["current_node"] == n0
    assert (
        sum(int(l["quantity"]) for l in sim.state.carts[cart_id]["cargo_lots"] if l.get("status") == "aboard")
        == aboard
    )

    clear = dispatch("Interact", {"action": "clear_hazard"}, "clear-1")
    assert clear.status == "ACCEPTED"
    assert sim.state.carts[cart_id]["status"] == "en_route"
    dispatch("Wait", {"current_node": n0, "press_id": "pw2"}, "w2")
    assert sim.state.carts[cart_id]["current_node"] == fx["N1"]
    dispatch("Wait", {"current_node": n0, "press_id": "pw3"}, "w3")
    assert sim.state.carts[cart_id]["current_node"] == n2
    assert sim.state.carts[cart_id]["status"] == "arrived"
    assert sim.state.board["fx_cargo"].get("delivery_status") == "delivered"
    settlements = [
        s
        for s in sim.state.settlements.values()
        if s.get("node_id") == n2 and not s.get("staging") and s.get("operational")
    ]
    assert settlements, "construction should complete after delivery via Wait stages"
