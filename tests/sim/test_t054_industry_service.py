from fractions import Fraction

from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.industry import fraction
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.testing.fixtures import load_fixture


def _meters(sim):
    return {
        factory_id: fraction(record["meter"])
        for factory_id, record in sim.state.industry["factories"].items()
    }


def _advance_chunks(sim, chunks):
    sequence = int(sim.state.clock.get("clock_sequence", 0))
    for chunk in chunks:
        sequence += 1
        result = sim.advance(chunk, sequence)
        assert result.status == "ACCEPTED"


def test_fx_industry_global_oracle_and_save_resume() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    assert fx["seed"] == 303
    _advance_chunks(sim, [60_000])
    assert set(_meters(sim).values()) == {Fraction(3, 5)}
    assert sim.state.units == {}
    _advance_chunks(sim, [40_000])
    assert set(_meters(sim).values()) == {Fraction()}
    assert len(sim.state.units) == 3
    assert ResourceLayerService(sim.state.industry).balance(fx["finite_layer_id"]) == 590

    partial = load_fixture("FX-INDUSTRY")
    _advance_chunks(partial, [59_900])
    resumed = WorldSim(WorldState.from_dict(partial.state.to_dict()))
    _advance_chunks(resumed, [40_100])
    assert resumed.state.units == sim.state.units
    assert _meters(resumed) == _meters(sim)
    assert ResourceLayerService(resumed.state.industry).balance(fx["finite_layer_id"]) == 590


def test_visibility_render_chunks_and_pause_do_not_change_output() -> None:
    visible = load_fixture("FX-INDUSTRY")
    offscreen = load_fixture("FX-INDUSTRY")
    visible.state.player["node_id"] = "node:industry"
    _advance_chunks(visible, [17, 83] * 100)
    _advance_chunks(offscreen, [10_000])
    assert _meters(visible) == _meters(offscreen)
    layer_id = visible.state.board["fx_industry"]["finite_layer_id"]
    assert ResourceLayerService(visible.state.industry).balance(layer_id) == ResourceLayerService(offscreen.state.industry).balance(layer_id)

    paused = load_fixture("FX-INDUSTRY")
    token = paused.clock.acquire_pause("duel", "test")
    _advance_chunks(paused, [10_000])
    assert set(_meters(paused).values()) == {Fraction()}
    paused.clock.release_pause(token)
    _advance_chunks(paused, [10_000])
    assert set(_meters(paused).values()) == {Fraction(1, 10)}


def test_destroyed_factory_cannot_finish_on_later_boundary() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    target = fx["factory_ids"][0]
    _advance_chunks(sim, [99_900])
    assert _meters(sim)[target] == Fraction(999, 1000)
    sim.state.buildings[target]["status"] = "destroyed"
    sim.state.buildings[target]["active"] = False
    _advance_chunks(sim, [100, 10_000])
    assert _meters(sim)[target] == Fraction(999, 1000)
    assert all(unit["factory_id"] != target for unit in sim.state.units.values())
    assert {unit["factory_id"] for unit in sim.state.units.values()} == set(fx["factory_ids"][1:])
