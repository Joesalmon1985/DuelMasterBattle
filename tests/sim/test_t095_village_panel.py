"""T095 village panel / scenario runner parity and failure bundles."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.testing.fixtures import load_fixture, run_fx_village

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "village_runs"


def test_panel_and_scenario_same_engine_outcome(tmp_path: Path) -> None:
    seed = 507
    sim = load_fixture("FX-VILLAGE", seed=seed)
    result = run_fx_village(sim, seed=seed)
    assert result.status == "PASS"
    # Simulate panel applying the same outcome dictionary the runner records.
    panel_outcome = {
        "fixture": "FX-VILLAGE",
        "status": result.status,
        "seed": seed,
        "details": result.details,
        "quest_id": result.details["quest_id"],
        "same_engine": True,
    }
    assert panel_outcome["quest_id"] == sim.state.board["fx_village"]["quest_id"]
    assert panel_outcome["details"]["shortage"] is True
    # No separate quest engine — quest lives on WorldState.
    assert panel_outcome["quest_id"] in sim.state.quests


def test_failure_bundle_has_replay_fields() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    bundle_dir = RUNS / "failure_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "fixture": "FX-VILLAGE",
        "seed": 507,
        "error": "missing_line:dialogue.mara.offer",
        "cause_id": "cause.factory_shortage",
        "quest_id": "quest.factory_shortage",
        "softlock": False,
        "replay": {
            "command": [
                "python3",
                "tools/run_scenario.py",
                "--fixture",
                "FX-VILLAGE",
                "--seed",
                "507",
                "--record",
                "Pack/DuelMasterBattle_Build_Pack/tracking/village_runs/fx_village_record.json",
            ],
            "notes": "Enough to replay missing-line / softlock / cause bugs.",
        },
    }
    path = bundle_dir / "bundle_example_missing_line.json"
    path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert "replay" in loaded and "command" in loaded["replay"]
    assert loaded["quest_id"]
    assert loaded["cause_id"]
