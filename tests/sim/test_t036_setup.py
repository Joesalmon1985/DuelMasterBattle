"""T036 world setup bootstrap and replacement carts."""

from __future__ import annotations

import pytest

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.generation import BoardBuilder
from sim.dmb.world.setup import WorldSetupService


def test_setup_once_starter_goods_carts_road_staging_no_vp() -> None:
    state = WorldState(world_id=WorldId("world:t036"), ids=IdAllocator(WorldId("world:t036")))
    plan = BoardBuilder.generate(11, 2)
    setup = WorldSetupService(state)
    # Pick a staging node not used as a core
    core_nodes = {c.node_id for c in plan.cores}
    staging = next(n for n in plan.board.nodes if n not in core_nodes)
    first = setup.apply(plan, staging_nodes=[staging])
    assert first["status"] == "applied"
    second = setup.apply(plan, staging_nodes=[staging])
    assert second["status"] == "already_applied"

    assert len(state.settlements) == 4 + 1  # 2 factions * 2 cores + staging
    carts = [c for c in state.carts.values() if c.get("status") != "destroyed"]
    assert len(carts) == 8  # 2 per core * 4 cores
    roads = [r for r in state.roads.values() if r.get("setup")]
    assert len(roads) == 4

    # Starter goods present
    credited = 0
    for store_id, store in state.stocks.items():
        if store_id.startswith("_"):
            continue
        credited += int(store.get("catan", {}).get("timber", {}).get("available", 0))
    assert credited == 8  # 2 timber * 4 cores

    staging_recs = [s for s in state.settlements.values() if s.get("staging")]
    assert len(staging_recs) == 1
    assert ScoreService(state).settlement_vp(staging_recs[0]) == 0


def test_replacement_cart_new_id_after_cost() -> None:
    state = WorldState(world_id=WorldId("world:t036b"), ids=IdAllocator(WorldId("world:t036b")))
    plan = BoardBuilder.generate(11, 2)
    setup = WorldSetupService(state)
    setup.apply(plan)
    store = next(k for k in state.stocks if k.startswith("store:"))
    ledger = StockLedger(state)
    ledger.credit(store, "ore", 2)  # starter has timber/brick but not ore
    old_ids = set(state.carts)
    cart = setup.replace_cart(faction_id="faction:1", home_store=store, current_node="node:1")
    assert cart["id"] not in old_ids
    assert cart["id"] in state.carts
    with pytest.raises(TypeValidationError):
        # Drain goods then fail
        ledger.consume(store, {"timber": ledger.available(store, "timber")})
        setup.replace_cart(faction_id="faction:1", home_store=store, current_node="node:1")
