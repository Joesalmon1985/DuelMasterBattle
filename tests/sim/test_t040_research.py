"""T040 research archive and scoped modifiers."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.technology.definitions import TechnologyCatalog, tech_id
from sim.dmb.technology.research import TechnologyService


def _svc() -> TechnologyService:
    state = WorldState(world_id=WorldId("world:t040"), ids=IdAllocator(WorldId("world:t040")))
    catalog = TechnologyCatalog()
    catalog.load()
    return TechnologyService(state, catalog=catalog)


def test_unplayable_pick_remains_owned_inactive() -> None:
    svc = _svc()
    fid = "faction:1"
    card = svc.make_card_instance(tech_id("prehistoric", "primary_flow"), playable=False)
    svc.acquire(fid, card)
    receipts = svc.activate_eligible(fid)
    assert receipts == []
    research = svc.research_of(fid)
    assert card["id"] in research["owned"]
    assert card["id"] in research["inactive_archive"]
    assert research["owned"][card["id"]]["status"] == "owned_inactive"
    assert svc.effective_modifiers(fid)["primary_flow"] == 0.0


def test_either_predecessor_activates_once() -> None:
    svc = _svc()
    fid = "faction:1"
    # Own historic primary without predecessors → inactive.
    hist = svc.make_card_instance(tech_id("historic", "primary_flow"))
    svc.acquire(fid, hist)
    assert svc.activate_eligible(fid) == []
    assert hist["id"] in svc.research_of(fid)["inactive_archive"]

    # Activate prehistoric processor (either allowed predecessor).
    pred = svc.make_card_instance(tech_id("prehistoric", "processor_cap"))
    svc.acquire(fid, pred)
    receipts = svc.activate_eligible(fid)
    kinds = [r["kind"] for r in receipts]
    assert kinds.count("activate") == 2  # pred + historic once
    research = svc.research_of(fid)
    assert hist["id"] not in research["inactive_archive"]
    assert research["owned"][hist["id"]]["status"] == "active"
    # Gaining the other predecessor later does not re-activate historic.
    other = svc.make_card_instance(tech_id("prehistoric", "primary_flow"))
    svc.acquire(fid, other)
    more = svc.activate_eligible(fid)
    assert sum(1 for r in more if r["kind"] == "activate" and r["definition_id"] == hist["definition_id"]) == 0
    assert len(research["active_stacks"][hist["definition_id"]]) == 1


def test_fourth_capped_copy_inert() -> None:
    svc = _svc()
    fid = "faction:1"
    def_id = tech_id("prehistoric", "cart_capacity")
    for _ in range(4):
        card = svc.make_card_instance(def_id)
        svc.acquire(fid, card)
    receipts = svc.activate_eligible(fid)
    activates = [r for r in receipts if r["kind"] == "activate"]
    caps = [r for r in receipts if r["kind"] == "cap_inert"]
    assert len(activates) == 3
    assert len(caps) == 1
    mods = svc.effective_modifiers(fid)
    assert mods["cart_capacity"] == 3.0  # +1 × 3 stacks


def test_duplicate_projection_refresh_no_bonus() -> None:
    svc = _svc()
    fid = "faction:1"
    def_id = tech_id("prehistoric", "primary_flow")
    for _ in range(2):
        svc.acquire(fid, svc.make_card_instance(def_id))
    svc.activate_eligible(fid)
    first = svc.effective_modifiers(fid)
    second = svc.effective_modifiers(fid)
    assert first == second
    assert first["primary_flow"] == 0.2
    # Calling activate again does not inflate stacks.
    svc.activate_eligible(fid)
    assert svc.effective_modifiers(fid)["primary_flow"] == 0.2


def test_unit_era_scope_filters_old_tech() -> None:
    svc = _svc()
    fid = "faction:1"
    svc.acquire(fid, svc.make_card_instance(tech_id("prehistoric", "unit_health")))
    svc.activate_eligible(fid)
    assert svc.effective_modifiers(fid, asset_era="prehistoric", scope="unit_era")["unit_health"] == 0.1
    assert svc.effective_modifiers(fid, asset_era="historic", scope="unit_era")["unit_health"] == 0.0
