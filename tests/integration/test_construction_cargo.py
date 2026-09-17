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
