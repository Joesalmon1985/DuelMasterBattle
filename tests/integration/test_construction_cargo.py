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
    timber = sim.state.stocks[store]["catan"]["timber"]
    # 5 credited, 1 reserved for the playtest delivery allocation.
    assert timber["available"] == 4
    assert timber["reserved"] == 1
    assert fx["delivery_reservation_id"] in sim.state.stocks["_reservations"]
    assert set(sim.state.board["nodes"]) == {"node:1", "node:2", "node:3"}
    assert "person:warehouse" in sim.state.people
    assert "person:cart" in sim.state.people
    assert sim.state.tech_draft.get("active") is True
    assert list(sim.state.tech_draft.get("seat_order") or []) == ["faction:1", "faction:player"]


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

    # Second Start must not double-charge or spawn a second delivery.
    stock_before = {
        g: dict(sim.state.stocks[fx["store"]]["catan"][g])
        for g in ("timber", "brick", "wool", "grain")
    }
    again = dispatch("Interact", {"action": "start_delivery"}, "start-2")
    assert again.status == "REJECTED"
    assert again.code == "BUSY"
    for g, before in stock_before.items():
        assert sim.state.stocks[fx["store"]]["catan"][g] == before
    assert (
        sum(int(l["quantity"]) for l in sim.state.carts[cart_id]["cargo_lots"] if l.get("status") == "aboard")
        == aboard
    )

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


def test_fx_cargo_explore_wait_then_start_uses_reserved_allocation() -> None:
    """Joe's sequence: travel all rooms, Wait, then Start — reserved haul remains."""
    from sim.dmb.core.world import CommandEnvelope

    sim = load_fixture("FX-CARGO", seed=202)
    fx = sim.state.board["fx_cargo"]
    store = fx["store"]
    cart_id = fx["cart_id"]
    res_id = fx["delivery_reservation_id"]

    def dispatch(kind: str, payload: dict, cid: str):
        return sim.dispatch(
            CommandEnvelope(
                protocol_version=1,
                session_id="explore",
                world_id=sim.state.world_id,
                command_id=cid,
                expected_world_version=sim.state.world_version,
                kind=kind,
                payload=payload,
            )
        )

    for i, (frm, to) in enumerate(
        [("node:1", "node:2"), ("node:2", "node:3"), ("node:3", "node:2"), ("node:2", "node:1")]
    ):
        assert dispatch("Travel", {"from_node": frm, "to_node": to}, f"t{i}").status == "ACCEPTED"
    for i in range(4):
        assert dispatch(
            "Wait",
            {"current_node": sim.state.player["node_id"], "press_id": f"ew{i}"},
            f"ew{i}",
        ).status == "ACCEPTED"

    assert sim.state.stocks["_reservations"][res_id]["status"] == "reserved"
    reserved_brick = sim.state.stocks[store]["catan"]["brick"]["reserved"]
    assert reserved_brick >= 1

    start = dispatch("Interact", {"action": "start_delivery"}, "start-after-explore")
    assert start.status == "ACCEPTED", start.public_feedback
    assert sim.state.carts[cart_id]["status"] == "en_route"
    assert sum(
        int(lot["quantity"])
        for lot in sim.state.carts[cart_id]["cargo_lots"]
        if lot.get("status") == "aboard"
    ) == 4
    # Fixture reservation consumed into cargo — not double-reserved.
    assert sim.state.stocks["_reservations"][res_id]["status"] != "reserved"


def test_fx_cargo_inspect_warehouse_and_cart() -> None:
    from sim.dmb.core.world import CommandEnvelope

    sim = load_fixture("FX-CARGO", seed=202)
    fx = sim.state.board["fx_cargo"]

    def dispatch(kind: str, payload: dict, cid: str):
        return sim.dispatch(
            CommandEnvelope(
                protocol_version=1,
                session_id="insp",
                world_id=sim.state.world_id,
                command_id=cid,
                expected_world_version=sim.state.world_version,
                kind=kind,
                payload=payload,
            )
        )

    wh = dispatch("Interact", {"entity_id": "person:warehouse"}, "wh")
    assert wh.status == "ACCEPTED"
    assert wh.payload["kind"] == "warehouse"
    assert wh.payload["stock"]["timber"]["reserved"] >= 1
    cart = dispatch("Interact", {"entity_id": "person:cart"}, "cart")
    assert cart.status == "ACCEPTED"
    assert cart.payload["kind"] == "cart"
    assert cart.payload["cart_id"] == fx["cart_id"]
    assert cart.payload["phase"] == "idle"


def test_fx_cargo_tech_picks_after_full_round_not_local_pose() -> None:
    from sim.dmb.core.world import CommandEnvelope

    sim = load_fixture("FX-CARGO", seed=202)
    assert sim.state.tech_draft.get("active") is True

    def dispatch(kind: str, payload: dict, cid: str):
        return sim.dispatch(
            CommandEnvelope(
                protocol_version=1,
                session_id="tech",
                world_id=sim.state.world_id,
                command_id=cid,
                expected_world_version=sim.state.world_version,
                kind=kind,
                payload=payload,
            )
        )

    # Local pose sync must not resolve tech picks.
    pose = dispatch(
        "SyncPose",
        {
            "position": [5, 5],
            "facing": "down",
            "node_id": "node:1",
            "pose_generation": 0,
        },
        "pose1",
    )
    assert pose.status == "ACCEPTED"
    assert not (sim.state.tech_draft.get("last_picks") or {})

    # Two Wait presses complete both seats → one pick each.
    w0 = dispatch("Wait", {"current_node": "node:1", "press_id": "tw0"}, "tw0")
    assert w0.status == "ACCEPTED"
    assert not w0.payload["seat"].get("round_complete")
    w1 = dispatch("Wait", {"current_node": "node:1", "press_id": "tw1"}, "tw1")
    assert w1.status == "ACCEPTED"
    assert w1.payload["seat"].get("round_complete") is True
    picks = sim.state.tech_draft.get("last_picks") or {}
    assert set(picks) == {"faction:1", "faction:player"}
    assert sim.state.tech_draft.get("pick_index") == 1
