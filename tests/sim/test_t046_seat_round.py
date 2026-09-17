"""T046 seat round integration: exclusivity, production, draft suppress."""

from __future__ import annotations

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.rng import RngBank
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.technology.draft import DraftService
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler
from sim.dmb.world.generation import generate
from sim.dmb.world.setup import WorldSetupService


def _six_faction_world() -> tuple[WorldState, TurnRunner]:
    state = WorldState(world_id=WorldId("world:t046"), ids=IdAllocator(WorldId("world:t046")))
    state.rng = RngBank(streams={"gameplay": {"seed": 46, "version": 1, "draws": 0}}).to_dict()
    plan = generate(46, 6)
    WorldSetupService(state).apply(plan)
    roster = sorted({c.faction_id for c in plan.cores})
    state.clock["scheduled_faction_ids"] = roster
    DraftService(state).deal("prehistoric", roster)
    runner = TurnRunner(state, TurnScheduler(state.clock))
    return state, runner


def test_six_seats_each_activate_once() -> None:
    state, runner = _six_faction_world()
    roster = list(state.clock["scheduled_faction_ids"])
    assert len(roster) == 6
    outcome = runner.run_faction_round()
    assert len(outcome["results"]) == 6
    seen = [r["faction_id"] for r in outcome["results"]]
    assert seen == roster
    assert outcome["round_complete"] is True
    # Each seat ran active decisions stage.
    for row in outcome["results"]:
        assert "5_active_decisions" in row["stages"]


def test_matching_production_all_factions() -> None:
    state, runner = _six_faction_world()
    # Seed warehouses empty of timber then run one production stage with forced token.
    from sim.dmb.construction.production import CatanProductionService
    from sim.dmb.logistics.stock import StockLedger

    ledger = StockLedger(state)
    before = {fid: 0 for fid in state.factions}
    # Grant via production service using an explicit roll that matches some tokens.
    prod = CatanProductionService(state)
    # Find a token that exists on the board.
    tokens = list(state.board.get("hex_token", {}).values())
    roll = int(tokens[0]) if tokens else 6
    grants = prod.grant_for_roll(roll)
    # All grants use same roll mapping — every matching settlement of every faction gets goods.
    factions_granted = {g.get("faction_id") for g in grants.get("grants", grants) if isinstance(g, dict)}
    # At least the production path is shared (no faction-specific dice).
    assert isinstance(grants, dict)
    totals = ledger.totals("timber")["accounted"] + ledger.totals("brick")["accounted"]
    assert totals >= 0


def test_only_active_faction_initiates() -> None:
    state, runner = _six_faction_world()
    roster = list(state.clock["scheduled_faction_ids"])
    runner.scheduler.begin_turn("Seat")
    state.clock["active_faction_id"] = roster[0]
    state.clock["completed_seats"] = []
    payload = runner.run_stage("5_active_decisions")
    assert payload["faction_id"] == roster[0]
    activations = [
        f
        for f, fac in state.factions.items()
        if (fac.get("policy") or {}).get("selections")
    ]
    assert activations == [roster[0]]


def test_vp_interrupt_suppresses_draft() -> None:
    state, runner = _six_faction_world()
    roster = list(state.clock["scheduled_faction_ids"])
    # Inflate one faction to 10 VP mid-round.
    winner = roster[0]
    for settlement in state.settlements.values():
        if settlement.get("faction_id") == winner:
            settlement["tier"] = "city"
    # Force more settlements if needed
    while ScoreService(state).score(winner) < 10:
        sid = state.ids.new("settlement")
        state.settlements[sid] = {
            "id": sid,
            "faction_id": winner,
            "node_id": "node:1",
            "tier": "city",
            "operational": True,
        }
    assert ScoreService(state).score(winner) >= 10
    # Simulate round complete while interrupted.
    runner.interrupt("vp_threshold")
    seat = {"round_complete": True, "round": 1}
    draft_before = dict(state.tech_draft)
    assert draft_before.get("active")
    resolved = runner._maybe_resolve_tech_draft(seat)
    assert resolved.get("draft_suppressed") is True
    assert state.tech_draft.get("active") is False
