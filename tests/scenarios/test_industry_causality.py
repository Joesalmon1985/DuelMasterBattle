"""Causal FX-INDUSTRY scenarios through authoritative services and clock."""

from copy import deepcopy
from fractions import Fraction

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding, RouteSelector
from sim.dmb.people.jobs import JobService
from sim.dmb.testing.fixtures import load_fixture


def _advance(sim, milliseconds=100):
    sequence = int(sim.state.clock["clock_sequence"]) + 1
    assert sim.advance(milliseconds, sequence).status == "ACCEPTED"


def _bundle(sim):
    """Failure payload includes exact meter/carry values and finite balances."""
    fx = sim.state.board["fx_industry"]
    return {
        "carries": {
            key: str(fraction(value["meter"]))
            for key, value in sim.state.industry["factories"].items()
        },
        "finite_balance": str(
            ResourceLayerService(sim.state.industry).balance(fx["finite_layer_id"])
        ),
        "events": sim.state.industry["events"][-3:],
    }


def test_depletion_shared_last_unit_and_insertion_order_conserve_exactly() -> None:
    outcomes = []
    for reverse in (False, True):
        sim = load_fixture("FX-INDUSTRY")
        fx = sim.state.board["fx_industry"]
        layer = sim.state.industry["layers"][fx["finite_layer_id"]]
        layer["finite_balance"] = fraction_wire(Fraction(1, 100))
        if reverse:
            sim.state.industry["routes"] = dict(
                reversed(list(sim.state.industry["routes"].items()))
            )
        _advance(sim)
        remaining = ResourceLayerService(sim.state.industry).balance(fx["finite_layer_id"])
        assert remaining == 0, _bundle(sim)
        weighted_progress = sum(
            fraction(sim.state.industry["factories"][factory_id]["meter"]) * cost
            for factory_id, cost in zip(fx["factory_ids"], (2, 3, 5), strict=True)
        )
        assert weighted_progress == Fraction(1, 100), _bundle(sim)
        carries = sorted(
            fraction(sim.state.industry["factories"][factory_id]["meter"])
            for factory_id in fx["factory_ids"]
        )
        outcomes.append(carries)
        _advance(sim)
        assert sorted(
            fraction(sim.state.industry["factories"][factory_id]["meter"])
            for factory_id in fx["factory_ids"]
        ) == carries, _bundle(sim)
    assert outcomes[0] == outcomes[1]


def test_catastrophe_strike_visual_only_and_real_destruction_have_causes() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    finite_channel = next(
        value
        for value in sim.state.industry["channels"].values()
        if value["layer_id"] == fx["finite_layer_id"]
    )
    original_capacity = finite_channel["capacity"]
    finite_channel["capacity"] = fraction_wire(0)  # explicit source catastrophe
    before = deepcopy(_bundle(sim))
    _advance(sim, 1000)
    assert _bundle(sim)["carries"] == before["carries"], _bundle(sim)
    assert _bundle(sim)["finite_balance"] == before["finite_balance"], _bundle(sim)
    finite_channel["capacity"] = original_capacity
    _advance(sim, 1000)
    assert _bundle(sim)["carries"] != before["carries"], _bundle(sim)

    jobs = JobService(sim.state)
    jobs.register_job(
        "industry:strike",
        workplace_id=fx["processor_id"],
        job_id="job:processor",
        node_id=fx["node_id"],
    )
    _advance(sim)
    jobs.set_modifier("industry:strike", 0)
    strike_carries = _bundle(sim)["carries"]
    _advance(sim, 1000)
    assert _bundle(sim)["carries"] == strike_carries, _bundle(sim)
    jobs.set_modifier("industry:strike", 1)

    snapshot = deepcopy(sim.state.to_dict())
    IndustryProjection(sim.state).workers(node_id=fx["node_id"])
    assert sim.state.to_dict() == snapshot

    target = fx["factory_ids"][0]
    BuildingService(sim.state).destroy(target, cause_id="cause:test")
    destroyed_meter = fraction(sim.state.industry["factories"][target]["meter"])
    _advance(sim, 1000)
    assert fraction(sim.state.industry["factories"][target]["meter"]) == destroyed_meter
    assert any(
        fraction(sim.state.industry["factories"][other]["meter"]) > destroyed_meter
        for other in fx["factory_ids"][1:]
    ), _bundle(sim)


def test_route_fallback_and_legacy_layer_balance_continue_exactly() -> None:
    disabled = ProcessorBinding("p:a", "r", "prehistoric", "a", "b", active=False)
    alternate = ProcessorBinding("p:b", "r", "prehistoric", "a", "b")
    routes = [
        FactoryRoute("f", disabled.building_id, "u", 2),
        FactoryRoute("f", alternate.building_id, "u", 2),
    ]
    selected = RouteSelector().select_installed_route(
        "f", routes, {disabled.building_id: disabled, alternate.building_id: alternate}
    )
    assert selected and selected.processor_id == "p:b"

    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    layers = ResourceLayerService(sim.state.industry)
    old_before = layers.balance(fx["finite_layer_id"])
    new = layers.create_layer("hex:ore", "future.ore", "historic", 1, finite=True)
    _advance(sim, 1000)
    old_after = layers.balance(fx["finite_layer_id"])
    assert old_before - old_after == Fraction(1, 10), _bundle(sim)
    assert layers.balance(new.layer_id) == 600, _bundle(sim)
