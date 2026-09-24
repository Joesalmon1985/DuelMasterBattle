#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.eras.service import EraService

sim = load_fixture("FX-ERA", seed=1212)
state = sim.state
print("FX-CYCLE boot era=", state.clock.get("era"), "people=", len(state.people))
state.clock["era"] = "future"
out = EraService(state).reseed_cycle(plan_id="play-fx-cycle", faction_count=6)
print("reseed", out["receipt"]["cycle"], "factions", len(out["receipt"]["new_faction_ids"]))
print("FX_CYCLE_OK")
PY
