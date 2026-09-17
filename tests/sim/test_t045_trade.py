"""T045 bilateral trade escrow and causal settlement."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.logistics.trade import TradeService


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t045"), ids=IdAllocator(WorldId("world:t045")))
    state.factions = {
        "faction:a": {"id": "faction:a"},
        "faction:b": {"id": "faction:b"},
    }
    return state


def test_one_leg_escrow_not_spendable_both_settle_once() -> None:
    state = _world()
    ledger = StockLedger(state)
    store_a = "store:a"
    store_b = "store:b"
    ledger.credit(store_a, "timber", 2)
    ledger.credit(store_b, "ore", 2)
    trade = TradeService(state, ledger=ledger)

    contract = trade.propose(
        "faction:a",
        "faction:b",
        give={"timber": 2},
        receive={"ore": 2},
        proposer_store=store_a,
        counterparty_store=store_b,
    )
    trade.accept(contract["id"])
    trade.dispatch_legs(contract["id"])

    # Deliver A→B first into escrow.
    trade.deliver_leg_to_escrow(contract["id"], "a")
    assert ledger.escrow(store_b, "timber") == 2
    assert ledger.available(store_b, "timber") == 0
    assert ledger.available(store_a, "ore") == 0

    # Second leg completes settle once.
    first = trade.deliver_leg_to_escrow(contract["id"], "b")
    assert first["status"] == "settled"
    assert ledger.available(store_b, "timber") == 2
    assert ledger.available(store_a, "ore") == 2
    assert ledger.escrow(store_b, "timber") == 0
    assert ledger.escrow(store_a, "ore") == 0

    again = trade.settle(contract["id"])
    assert again["status"] == "settled"
    assert ledger.available(store_b, "timber") == 2
    assert ledger.totals("timber")["accounted"] == 2
    assert ledger.totals("ore")["accounted"] == 2


def test_destroyed_leg_no_invented_repayment() -> None:
    state = _world()
    ledger = StockLedger(state)
    store_a = "store:a"
    store_b = "store:b"
    ledger.credit(store_a, "timber", 2)
    ledger.credit(store_b, "ore", 2)
    trade = TradeService(state, ledger=ledger)
    contract = trade.propose(
        "faction:a",
        "faction:b",
        give={"timber": 2},
        receive={"ore": 2},
        proposer_store=store_a,
        counterparty_store=store_b,
    )
    trade.accept(contract["id"])
    trade.dispatch_legs(contract["id"])
    # Escrow B→A ore first, then destroy A→B timber leg.
    trade.deliver_leg_to_escrow(contract["id"], "b")
    assert ledger.escrow(store_a, "ore") == 2
    defaulted = trade.destroy_leg(contract["id"], "a")
    assert defaulted["reason"] == "destroyed_leg"
    # Surviving escrow stays; no free timber appears for B.
    assert ledger.available(store_b, "timber") == 0
    assert ledger.escrow(store_a, "ore") == 2
    assert ledger.totals("timber")["lost"] >= 2 or any(
        True for act in defaulted["actions"] if act.get("action") == "loss_recorded_no_repayment"
        or act.get("action") == "cargo_retained"
        or "destroyed" in str(act)
    )


def test_interrupt_leaves_goods_at_real_locations() -> None:
    state = _world()
    ledger = StockLedger(state)
    store_a = "store:a"
    store_b = "store:b"
    ledger.credit(store_a, "timber", 2)
    ledger.credit(store_b, "ore", 2)
    trade = TradeService(state, ledger=ledger)
    contract = trade.propose(
        "faction:a",
        "faction:b",
        give={"timber": 2},
        receive={"ore": 2},
        proposer_store=store_a,
        counterparty_store=store_b,
    )
    trade.accept(contract["id"])
    trade.dispatch_legs(contract["id"])
    cart_a = trade._trades()[contract["id"]]["legs"]["a"]["cart_id"]
    assert state.carts[cart_a]["cargo_lots"]
    node = state.carts[cart_a]["current_node"]
    cancelled = trade.cancel_or_default(contract["id"], reason="interrupt")
    assert cancelled["reason"] == "interrupt"
    # Cargo still aboard at the same node — not teleported home.
    assert state.carts[cart_a]["current_node"] == node
    aboard = [lot for lot in state.carts[cart_a]["cargo_lots"] if lot.get("status") == "aboard"]
    assert sum(int(l["quantity"]) for l in aboard) == 2
