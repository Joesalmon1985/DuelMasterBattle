"""T111 cumulative MVP replay / persistence around era transition."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.persistence.repository import SaveRepository
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Pack/DuelMasterBattle_Build_Pack/tracking/mvp_validation"


def test_era_transition_save_reload_no_duplicate_people(tmp_path: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    people_before = set(state.people)
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "t111-wait")
    assert state.clock.get("era") == "historic"
    tid = state.clock.get("last_era_transition_id")
    repo = SaveRepository(tmp_path)
    repo.write("mvp_post_transition", sim.snapshot())
    loaded_sim = repo.load_world("mvp_post_transition")
    loaded = loaded_sim.state
    assert loaded.clock.get("era") == "historic"
    assert loaded.clock.get("last_era_transition_id") == tid
    assert set(loaded.people) == people_before
    runner2 = TurnRunner(loaded, TurnScheduler(loaded.clock))
    loaded.clock["scheduled_faction_ids"] = sorted(loaded.factions)
    loaded.clock["active_faction_id"] = winner
    runner2.execute_wait("node:35", "t111-wait-2")
    assert loaded.clock.get("last_era_transition_id") == tid
    report = {
        "people_count": len(loaded.people),
        "era": loaded.clock.get("era"),
        "transition_id": tid,
        "duplicate_transition": False,
    }
    (OUT / "era_persistence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
