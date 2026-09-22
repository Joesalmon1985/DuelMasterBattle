"""T117 — Historic→Modern→Future ordinary continuity."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.construction.scoring import ScoreService, VP_THRESHOLD
from sim.dmb.eras.planner import next_era_id
from sim.dmb.eras.service import EraService
from sim.dmb.eras.upgrades import load_core_config
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler
from sim.dmb.world.boulder_quest import QUEST_INSTANCE_ID, ROCKFALL_ID, get_rockfall


def test_next_era_chain() -> None:
    assert next_era_id("prehistoric") == "historic"
    assert next_era_id("historic") == "modern"
    assert next_era_id("modern") == "future"
    assert next_era_id("future") == "prehistoric"


def test_modern_future_core_configs_load() -> None:
    modern = load_core_config("modern")
    future = load_core_config("future")
    assert modern["core_upgrade"]["unit_defs"][0].startswith("unit.modern.")
    assert future["core_upgrade"]["unit_defs"][0].startswith("unit.future.")


def _active_winner(state) -> str:
    active = [
        fid
        for fid, fac in state.factions.items()
        if fac.get("status") == "active" and fac.get("operational", True) is not False
    ]
    if not active:
        active = sorted(
            {
                str(s.get("faction_id"))
                for s in state.settlements.values()
                if s.get("faction_id") and not s.get("ruin_only")
            }
        )
    preferred = str((state.board.get("fx_era") or {}).get("winner_faction_id") or "")
    if preferred in active:
        return preferred
    return sorted(active)[0]


def _ensure_threshold(state, faction_id: str) -> None:
    """Give ``faction_id`` enough current-era VP via pad cities (do not clear legacy)."""
    # Boost existing non-legacy cores/settlements to city tier without touching legacy sites.
    for settlement in state.settlements.values():
        if settlement.get("faction_id") != faction_id or settlement.get("ruin_only"):
            continue
        if settlement.get("legacy") and not settlement.get("upgraded"):
            continue
        settlement["operational"] = True
        settlement["status"] = "active"
        settlement["tier"] = "city"
    pad = 0
    while ScoreService(state).score(faction_id) < VP_THRESHOLD:
        sid = f"settlement:t117-pad:{pad}"
        state.settlements[sid] = {
            "id": sid,
            "faction_id": faction_id,
            "node_id": "node:35",
            "tier": "city",
            "operational": True,
            "legacy": False,
            "upgraded": True,
            "status": "active",
            "warehouse_id": f"{sid}:wh",
            "centre_id": f"{sid}:centre",
        }
        pad += 1
        if pad > 20:
            raise AssertionError("unable to pad VP to threshold")


def _transition_to_next(state, *, event_id: str, expected_era: str) -> dict:
    winner = _active_winner(state)
    _ensure_threshold(state, winner)
    assert ScoreService(state).score(winner) >= VP_THRESHOLD
    state.clock.pop("interrupt_reason", None)
    state.clock.pop("era_transition_handled_interrupt", None)
    state.clock["interrupt_reason"] = "vp_threshold"
    state.clock["interrupt_factions"] = [winner]
    out = EraService(state).maybe_trigger_from_interrupt(event_id=event_id)
    assert out is not None
    assert state.clock.get("era") == expected_era
    return out


def test_historic_quest_person_survive_into_modern() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    people_before = set(state.people)
    known = list(state.board["fx_era"]["known_person_ids"])
    assert known
    pid = known[0]
    rock_before = deepcopy(get_rockfall(state))

    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "t117-pre-hist")
    assert state.clock.get("era") == "historic"
    assert set(state.people) == people_before
    assert QUEST_INSTANCE_ID in state.quests
    assert get_rockfall(state)["id"] == ROCKFALL_ID

    legacy_settlement_ids = {
        sid
        for sid, settlement in state.settlements.items()
        if settlement.get("legacy") and not settlement.get("upgraded")
    }
    assert legacy_settlement_ids, "expected at least one Historic legacy site before Modern"

    _transition_to_next(state, event_id="t117-hist-mod", expected_era="modern")
    assert set(state.people) == people_before
    assert pid in state.people
    assert QUEST_INSTANCE_ID in state.quests
    assert get_rockfall(state)["id"] == rock_before["id"]

    # Settlements that remain legacy keep old factory definitions (not modernised).
    remaining_legacy = {
        sid
        for sid, settlement in state.settlements.items()
        if settlement.get("legacy") and not settlement.get("era_core")
    }
    assert remaining_legacy
    for bid, building in state.buildings.items():
        if str(building.get("settlement_id") or "") not in remaining_legacy:
            continue
        if str(building.get("slot_kind") or "") != "factory":
            continue
        def_id = str(building.get("def_id") or building.get("definition_id") or "")
        assert "modern" not in def_id
        assert str(building.get("era") or "") != "modern"

    core = state.settlements["settlement:3"]
    assert core.get("era") == "modern"
    assert core.get("era_core") is True
    grants = state.command_receipts.get("era_core_starter") or {}
    assert any("t117-hist-mod" in k for k in grants)
    assert EraService(state).maybe_trigger_from_interrupt(event_id="t117-hist-mod") is None


def test_modern_to_future_preserves_ids() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    people_before = set(state.people)
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "t117-to-hist")
    assert state.clock.get("era") == "historic"

    _transition_to_next(state, event_id="t117-to-mod", expected_era="modern")
    assert set(state.people) == people_before
    assert QUEST_INSTANCE_ID in state.quests
    _transition_to_next(state, event_id="t117-to-fut", expected_era="future")
    assert set(state.people) == people_before
    assert QUEST_INSTANCE_ID in state.quests
