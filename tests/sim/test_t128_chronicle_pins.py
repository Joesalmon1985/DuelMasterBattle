"""T128 — chronicle pins and compaction."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.history.chronicle import HistoryService
from sim.dmb.history.compaction import ChronicleCompaction


def test_pinned_event_survives_compaction() -> None:
    state = WorldState(world_id=WorldId("world:t128"))
    state.people["person:1"] = {"id": "person:1", "alive": True, "history_refs": []}
    state.quests["quest:1"] = {"id": "quest:1", "source_event_id": None}
    hist = HistoryService(state)
    pinned = hist.record(kind="promise", summary="helped", subject_ids=["person:1", "quest:1"])
    hist.pin_live_reference("person:1", pinned["id"])
    state.quests["quest:1"]["source_event_id"] = pinned["id"]
    for i in range(30):
        evt = hist.record(kind="noise", summary=f"noise-{i}", subject_ids=[f"x:{i}"])
        evt["retired"] = True
        # mark retired in place
        state.board["history"]["events"][-1]["retired"] = True
    result = ChronicleCompaction(state).compact_retired(keep_recent=5)
    ids = {e["id"] for e in state.board["history"]["events"]}
    assert pinned["id"] in ids
    assert result["pins"]
