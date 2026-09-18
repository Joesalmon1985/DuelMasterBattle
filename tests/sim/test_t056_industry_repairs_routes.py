from fractions import Fraction

import pytest

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.construction.orders import ConstructionService
from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry import fraction
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import (
    FactoryRoute,
    ProcessorBinding,
    RouteSelector,
    validate_processor,
)
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.testing.fixtures import load_fixture


def _advance(sim, milliseconds=1000):
    sequence = int(sim.state.clock["clock_sequence"]) + 1
    assert sim.advance(milliseconds, sequence).status == "ACCEPTED"


def test_paid_repair_restores_full_processor_rate_once() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    processor = sim.state.buildings[fx["processor_id"]]
    processor["health"] = 50
    processor["faction_id"] = "faction:industry"
    store = "store:industry"
    ledger = StockLedger(sim.state)
    ledger.credit(store, "brick", 2)
    ledger.credit(store, "ore", 2)

    _advance(sim)
    low_delta = fraction(sim.state.industry["factories"][fx["factory_ids"][0]]["meter"])
    service = ConstructionService(sim.state, ledger=ledger)
    order = service.reserve_order(
        "repair",
        faction_id="faction:industry",
        store_id=store,
        target_building=fx["processor_id"],
    )
    assert order["status"] == "ready"
    committed = service.commit_delivered(order["id"])
    assert committed["completion_receipt"]["result"]["health"] == 100
    assert sim.state.stocks["_consumed"][-1]["goods"] == {"brick": 1, "ore": 1}
    service.commit_delivered(order["id"])
    assert len(sim.state.stocks["_consumed"]) == 1

    before = fraction(sim.state.industry["factories"][fx["factory_ids"][0]]["meter"])
    _advance(sim)
    full_delta = fraction(sim.state.industry["factories"][fx["factory_ids"][0]]["meter"]) - before
    assert full_delta > low_delta


def test_paid_processor_expansion_and_useful_alternate_selection() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    store = "store:industry"
    ledger = StockLedger(sim.state)
    for good in ("timber", "brick", "ore"):
        ledger.credit(store, good, 1)
    service = ConstructionService(sim.state, ledger=ledger)
    order = service.reserve_order(
        "processor",
        faction_id="faction:industry",
        store_id=store,
        target_node=fx["node_id"],
    )
    result = service.commit_delivered(order["id"])
    assert result["status"] == "committed"
    assert result["completion_receipt"]["result"]["building_id"] in sim.state.buildings
    assert sim.state.stocks["_consumed"][-1]["goods"] == {"timber": 1, "brick": 1, "ore": 1}

    disabled = ProcessorBinding(
        "processor:disabled", "r", "prehistoric", "a", "b", active=False
    )
    useful = ProcessorBinding("processor:useful", "r", "prehistoric", "a", "b")
    routes = [
        FactoryRoute("factory:x", disabled.building_id, "unit:x", 1),
        FactoryRoute("factory:x", useful.building_id, "unit:x", 1),
    ]
    selected = RouteSelector().select_installed_route(
        "factory:x", routes, {disabled.building_id: disabled, useful.building_id: useful}
    )
    assert selected and selected.processor_id == useful.building_id

    brain = HeuristicBrain()
    choice = brain.choose(
        {"own": {"vp": 0}},
        [
            {"id": "route:idle", "action_kind": "construct", "params": {"action": "route"}, "benefit": {"additional_milliunits_per_second": 0}},
            {"id": "route:useful", "action_kind": "construct", "params": {"action": "route"}, "benefit": {"additional_milliunits_per_second": 10}},
        ],
    )
    assert choice == "route:useful"


def test_unsupported_imported_industrial_input_remains_unavailable() -> None:
    binding = ProcessorBinding("p", "r", "prehistoric", "known", "imported")
    channels = {
        "known": PrimaryChannel(
            "known", "source", "node", "woodland", "prehistoric", 0,
            "wood", "layer", False, Fraction(1), True,
        )
    }
    with pytest.raises(TypeValidationError, match="missing exact source channel imported"):
        validate_processor(binding, channels, {"input_a_id": "wood", "input_b_id": "silk"})
