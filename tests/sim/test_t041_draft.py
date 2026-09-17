"""T041 seven-round simultaneous technology draft."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.rng import RngBank
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.technology.draft import DraftService
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler


def _draft(factions: list[str], *, seed: int = 41) -> DraftService:
    state = WorldState(world_id=WorldId("world:t041"), ids=IdAllocator(WorldId("world:t041")))
    state.rng = RngBank(streams={"tech_draft": {"seed": seed, "version": 1, "draws": 0}}).to_dict()
    for fid in factions:
        state.factions[fid] = {"id": fid}
    svc = DraftService(state)
    svc.deal("prehistoric", factions)
    return svc


def test_after_round_one_hands_six_and_one_owned() -> None:
    factions = ["faction:1", "faction:2", "faction:3"]
    svc = _draft(factions)
    snap = svc.collect_choices({"round": 1})
    choices = {fid: snap["hands"][fid][0]["id"] for fid in factions}
    outcome = svc.resolve_round(choices)
    assert all(size == 6 for size in outcome["hand_sizes"].values())
    assert all(count == 1 for count in outcome["owned_counts"].values())
    assert outcome["pick_index"] == 1
    assert not outcome["redealt"]


def test_after_round_seven_fresh_hands() -> None:
    factions = ["faction:1", "faction:2"]
    svc = _draft(factions)
    for _ in range(7):
        svc.collect_choices({"n": _})
        outcome = svc.resolve_round(svc.auto_pick_first())
    assert outcome["redealt"]
    assert all(size == 7 for size in outcome["hand_sizes"].values())
    assert all(count == 7 for count in outcome["owned_counts"].values())
    assert outcome["pick_index"] == 0


def test_singleton_self_pass() -> None:
    svc = _draft(["faction:solo"])
    before = [c["id"] for c in svc.draft_state()["hands"]["faction:solo"]]
    svc.collect_choices({})
    picked = before[0]
    outcome = svc.resolve_round({"faction:solo": picked})
    after = [c["id"] for c in svc.draft_state()["hands"]["faction:solo"]]
    assert picked not in after
    assert set(after) == set(before) - {picked}
    assert outcome["hand_sizes"]["faction:solo"] == 6


def test_interrupt_discards_without_old_picks() -> None:
    factions = ["faction:1", "faction:2"]
    svc = _draft(factions)
    # Complete one pick first.
    svc.collect_choices({})
    svc.resolve_round(svc.auto_pick_first())
    owned_before = {fid: set(svc.research.research_of(fid)["owned"]) for fid in factions}
    # Mid-cycle interrupt.
    discarded = svc.discard_for_era("era_interrupt")
    assert discarded["discarded"]
    assert not svc.draft_state()["active"]
    assert all(len(svc.draft_state()["hands"].get(fid, [])) == 0 for fid in factions)
    # No additional cards acquired from discarded hands.
    for fid in factions:
        assert set(svc.research.research_of(fid)["owned"]) == owned_before[fid]


def test_runner_seat_end_resolves_and_interrupt_clears() -> None:
    state = WorldState(world_id=WorldId("world:t041r"), ids=IdAllocator(WorldId("world:t041r")))
    state.rng = RngBank(streams={"tech_draft": {"seed": 7, "version": 1, "draws": 0}}).to_dict()
    state.factions = {"faction:a": {"id": "faction:a"}, "faction:b": {"id": "faction:b"}}
    state.clock["scheduled_faction_ids"] = ["faction:a", "faction:b"]
    DraftService(state).deal("prehistoric", ["faction:a", "faction:b"])
    runner = TurnRunner(state, TurnScheduler(state.clock))
    runner.scheduler.begin_turn("Wait")
    assert state.clock["scheduled_faction_ids"] == ["faction:a", "faction:b"]
    seat_a = runner.scheduler.finish_seat()
    assert not seat_a["round_complete"]
    seat_b = runner.scheduler.finish_seat()
    seat_b = runner._maybe_resolve_tech_draft(seat_b)
    assert seat_b["round_complete"]
    assert seat_b["tech_draft"]["owned_counts"]["faction:a"] == 1
    runner.interrupt("vp_threshold")
    runner._discard_tech_draft_on_interrupt()
    assert not state.tech_draft.get("active")
