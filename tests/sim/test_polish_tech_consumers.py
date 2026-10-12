"""R04: TechnologyService modifiers wired into authoritative consumers."""

from __future__ import annotations

from fractions import Fraction

from sim.dmb.industry import fraction
from sim.dmb.industry.constraints import build_constraints
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.routes import ProcessorBinding
from sim.dmb.industry.service import (
    _channel_from_dict,
    _processor_from_dict,
    _route_from_dict,
)
from sim.dmb.industry.tech_flow import apply_primary_flow_channels, faction_for_building
from sim.dmb.logistics.carts import CartService, DEFAULT_CAPACITY
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.military.units import MilitaryService
from sim.dmb.technology.definitions import TechnologyCatalog, tech_id
from sim.dmb.technology.research import TechnologyService
from sim.dmb.testing.fixtures import _load_fx_industry


def _activate_one(svc: TechnologyService, faction_id: str, effect_kind: str, *, era: str = "prehistoric") -> None:
    card = svc.make_card_instance(tech_id(era, effect_kind))
    svc.acquire(faction_id, card)
    svc.activate_eligible(faction_id)


def test_primary_flow_scales_channel_capacity() -> None:
    sim = _load_fx_industry()
    state = sim.state
    faction = "faction:industry"
    research = TechnologyService(state, catalog=TechnologyCatalog())
    research.catalog.load()
    channels = {cid: _channel_from_dict(rec) for cid, rec in state.industry["channels"].items()}
    baseline = apply_primary_flow_channels(state, channels, research=research)
    _activate_one(research, faction, "primary_flow")
    boosted = apply_primary_flow_channels(state, channels, research=research)
    base_cap = next(iter(baseline.values())).capacity
    boosted_cap = next(iter(boosted.values())).capacity
    assert boosted_cap > base_cap
    assert boosted_cap == base_cap * Fraction(11, 10)


def test_processor_cap_scales_processor_binding_capacity() -> None:
    sim = _load_fx_industry()
    state = sim.state
    faction = "faction:industry"
    proc_id = "processor:fx-industry"
    proc = _processor_from_dict(state.industry["processors"][proc_id])
    node_id = str(state.buildings[proc_id]["node_id"])
    research = TechnologyService(state, catalog=TechnologyCatalog())
    research.catalog.load()
    baseline = ProcessorBinding(**proc.__dict__).capacity
    _activate_one(research, faction, "processor_cap")
    scale = fraction(research.logistics_multiplier(faction_for_building(state, proc_id, node_id), "processor_cap"))
    boosted = ProcessorBinding(**{**proc.__dict__, "modifier": proc.modifier * scale}).capacity
    assert boosted > baseline
    assert boosted == baseline * Fraction(11, 10)


def test_factory_ceiling_scales_allocation_ceiling() -> None:
    sim = _load_fx_industry()
    state = sim.state
    faction = "faction:industry"
    research = TechnologyService(state, catalog=TechnologyCatalog())
    research.catalog.load()
    _activate_one(research, faction, "factory_ceiling")
    scale = Fraction(str(research.logistics_multiplier(faction, "factory_ceiling")))
    ceiling = {fid: Fraction(1, 60) * scale for fid in state.industry["routes"]}
    channels = {cid: _channel_from_dict(rec) for cid, rec in state.industry["channels"].items()}
    processors = {pid: _processor_from_dict(rec) for pid, rec in state.industry["processors"].items()}
    routes = [_route_from_dict(rec) for rec in state.industry["routes"].values()]
    layers = {lid: LayerState.from_dict(rec) for lid, rec in state.industry.get("layers", {}).items()}
    built = build_constraints(routes, processors, channels, layers, factory_ceiling=ceiling)
    factory_constraint = next(c for c in built.constraints if c.reason == "factory_ceiling")
    assert factory_constraint.capacity == Fraction(1, 60) * Fraction(11, 10)


def test_cart_capacity_bonus_on_create_and_load() -> None:
    sim = _load_fx_industry()
    state = sim.state
    faction = "faction:industry"
    research = TechnologyService(state, catalog=TechnologyCatalog())
    research.catalog.load()
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    base = carts.create(owner_faction=faction, home_store="store:x", current_node="node:industry", capacity=4)
    assert base["capacity"] == 4
    _activate_one(research, faction, "cart_capacity")
    boosted = carts.create(owner_faction=faction, home_store="store:y", current_node="node:industry", capacity=4)
    assert boosted["capacity"] == DEFAULT_CAPACITY + 1
    ledger.credit("store:x", "timber", 5)
    res = ledger.reserve("res:cart", {"timber": 5}, store_id="store:x")
    carts.load_from_reservation(boosted["id"], res["id"])


def test_unit_health_and_attack_on_spawn() -> None:
    sim = _load_fx_industry()
    state = sim.state
    faction = "faction:industry"
    research = TechnologyService(state, catalog=TechnologyCatalog())
    research.catalog.load()
    military = MilitaryService(state)
    baseline = military.spawn(
        "unit.ancient.skirmisher",
        home_node_id="node:industry",
        faction_id=faction,
        era="prehistoric",
        factory_id="factory:fx-skirmisher",
    )
    _activate_one(research, faction, "unit_health")
    _activate_one(research, faction, "unit_attack")
    boosted = military.spawn(
        "unit.ancient.skirmisher",
        home_node_id="node:industry",
        faction_id=faction,
        era="prehistoric",
        factory_id="factory:fx-skirmisher",
    )
    assert boosted["max_health"] > baseline["max_health"]
    assert boosted["derived_attack"] > baseline["derived_attack"]
    assert boosted["current_health"] == boosted["max_health"]
