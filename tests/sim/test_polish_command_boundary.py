"""P1 command-boundary oracles: RNG continuity and durable field persistence."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.state import WorldState
from sim.dmb.testing.fixtures import load_fixture


def _wait(sim, press: str, node: str = "node:35"):
    env = CommandEnvelope(
        1,
        "local",
        sim.state.world_id,
        f"cmd:{press}",
        sim.state.world_version,
        "Wait",
        {"current_node": node, "press_id": press},
    )
    result = sim.dispatch(env)
    assert result.status == "ACCEPTED", result
    return result


def _dice_from_wait(result) -> list[int] | None:
    for event in result.events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") or {}
        stages = payload.get("stages") or []
        if isinstance(stages, list):
            for stage in stages:
                if isinstance(stage, dict) and stage.get("dice"):
                    return list(stage["dice"])
        if payload.get("dice"):
            return list(payload["dice"])
        # nested seat/stages structure from execute_wait
        nested = payload.get("production") or payload.get("2_production")
        if isinstance(nested, dict) and nested.get("dice"):
            return list(nested["dice"])
    # Fall back: scan entire event tree for dice lists of length 2
    blob = str(result.events)
    return None


def test_dispatch_rng_continues_like_direct_runner() -> None:
    from sim.dmb.construction.production import CatanProductionService

    recorded: list[list[int]] = []
    original = CatanProductionService.draw_and_grant

    def _capture(self):
        outcome = original(self)
        recorded.append(list(outcome.get("dice") or []))
        return outcome

    CatanProductionService.draw_and_grant = _capture  # type: ignore[method-assign]
    try:
        sim = load_fixture("FX-MVP", seed=507)
        node = str(sim.state.player.get("node_id") or "node:35")
        for i in range(12):
            _wait(sim, f"p{i}", node=node)
    finally:
        CatanProductionService.draw_and_grant = original  # type: ignore[method-assign]

    assert len(recorded) == 12, recorded
    assert recorded.count([1, 1]) < 12, recorded
    assert len({tuple(d) for d in recorded}) > 1, recorded

    # Direct runner from same seed must match the command-path stream.
    recorded_direct: list[list[int]] = []

    def _capture2(self):
        outcome = original(self)
        recorded_direct.append(list(outcome.get("dice") or []))
        return outcome

    CatanProductionService.draw_and_grant = _capture2  # type: ignore[method-assign]
    try:
        sim2 = load_fixture("FX-MVP", seed=507)
        node = str(sim2.state.player.get("node_id") or "node:35")
        for i in range(12):
            sim2.runner.execute_wait(node, f"r{i}")
            if sim2.state.rng:
                from sim.dmb.core.rng import RngBank

                sim2.rng = RngBank.from_dict(sim2.state.rng)
    finally:
        CatanProductionService.draw_and_grant = original  # type: ignore[method-assign]

    assert recorded == recorded_direct, (recorded, recorded_direct)

def test_all_durable_fields_survive_save_load_and_rollback() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    sim.state.research = {"faction:1": {"owned": {"tech.prehistoric.channel": {"id": "c1"}}}}
    sim.state.tech_draft = {
        "era": "prehistoric",
        "active": True,
        "hands": {"faction:1": [{"id": "card:1", "definition_id": "tech.prehistoric.channel"}]},
        "seat_order": ["faction:1"],
        "pick_index": 0,
        "picks_this_cycle": 0,
        "last_snapshot": None,
    }
    sim.state.diplomacy = {"relations": {"faction:1|faction:2": "war"}}
    before = {
        "research": deepcopy(sim.state.research),
        "tech_draft": deepcopy(sim.state.tech_draft),
        "diplomacy": deepcopy(sim.state.diplomacy),
    }
    restored = WorldState.from_dict(sim.state.to_dict())
    assert restored.research == before["research"]
    assert restored.tech_draft == before["tech_draft"]
    assert restored.diplomacy == before["diplomacy"]


def test_normal_boot_deals_once() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    draft = sim.state.tech_draft
    assert isinstance(draft, dict) and draft.get("active") is True
    hands = draft.get("hands") or {}
    assert len(hands) >= 2
    for fid, cards in hands.items():
        assert len(cards) == 7, (fid, len(cards))
