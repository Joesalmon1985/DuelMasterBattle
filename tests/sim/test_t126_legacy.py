"""T126 — relic/scar/contamination dispositions."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.history.legacy import LegacyDispositionService

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_rules_content() -> None:
    data = json.loads((ROOT / "godot_project/content/source/legacy_rules/baseline.json").read_text())
    kinds = {r["kind"] for r in data["rules"]}
    assert {"inert_ruin", "bunker", "future_soldier"} <= kinds


def test_inert_ruin_and_bunker_and_unsupported_soldier() -> None:
    state = WorldState(world_id=WorldId("world:t126"))
    state.settlements["s1"] = {"id": "s1", "operational": True}
    legacy = LegacyDispositionService(state)
    ruin = legacy.record_inert_ruin("s1")
    assert ruin["loot"] is False and ruin["vp"] == 0
    assert state.settlements["s1"]["ruin_only"] is True
    bunker = legacy.preserve_bunker("bunker:1", puzzle_state={"solved": False, "room": "a"})
    assert bunker["payload"]["retains_puzzle"] is True
    soldier = legacy.register_relic("relic:future_soldier", kind="future_soldier")
    assert soldier["joins_army"] is False
    assert soldier["status"] == "unsupported_army_relic"
