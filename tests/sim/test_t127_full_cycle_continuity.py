"""T127 — living continuity across full cycles."""

from __future__ import annotations

from sim.dmb.eras.service import EraService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import QUEST_INSTANCE_ID


def test_people_quest_persist_across_reseed() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    people0 = set(state.people)
    known = list(state.board["fx_era"]["known_person_ids"])
    assert known
    pid = known[0]
    state.player["wizard"] = {"colours": ["blue"], "aspects": ["ward"], "memory": ["rockfall"]}
    state.clock["era"] = "future"
    EraService(state).reseed_cycle(plan_id="t127", faction_count=6)
    assert set(state.people) == people0
    assert pid in state.people
    assert QUEST_INSTANCE_ID in state.quests
    wizard = state.player.get("wizard") or {}
    assert wizard.get("colours") == ["blue"]
    assert wizard.get("aspects") == ["ward"]
