"""Neural family-specialist primary-seat behaviour (C14 diversity)."""

from __future__ import annotations

from sim.dmb.ai.neural import NeuralBrain


def test_trade_specialist_can_use_trade_as_primary() -> None:
    ranked = [
        {"id": "c1", "action_kind": "construct"},
        {"id": "t1", "action_kind": "trade_propose"},
        {"id": "m1", "action_kind": "military_move"},
    ]
    choice = NeuralBrain._select_slots(ranked, prefer_family="trade")
    assert choice["primary_id"] == "t1"


def test_war_specialist_prefers_military_primary() -> None:
    ranked = [
        {"id": "c1", "action_kind": "construct"},
        {"id": "m1", "action_kind": "military_move"},
    ]
    choice = NeuralBrain._select_slots(ranked, prefer_family="war")
    assert choice["primary_id"] == "m1"


def test_build_specialist_prefers_construct_primary() -> None:
    ranked = [
        {"id": "m1", "action_kind": "military_move"},
        {"id": "c1", "action_kind": "construct"},
    ]
    choice = NeuralBrain._select_slots(ranked, prefer_family="build")
    assert choice["primary_id"] == "c1"


def test_generalist_keeps_legacy_primary_kinds() -> None:
    ranked = [
        {"id": "t1", "action_kind": "trade_propose"},
        {"id": "c1", "action_kind": "construct"},
    ]
    choice = NeuralBrain._select_slots(ranked, prefer_family=None)
    assert choice["primary_id"] == "c1"
    assert choice["proposal_id"] == "t1"
