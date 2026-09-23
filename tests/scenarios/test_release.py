"""T157 — release scenario and multi-cycle regression suite."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.eras.service import EraService
from sim.dmb.persistence.coordinator import SaveCoordinator
from sim.dmb.persistence.repository import SaveRepository
from sim.dmb.testing.fixtures import load_fixture

ROOT = Path(__file__).resolve().parents[2]
TRACK = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "release_tests"
FX_CYCLE = ROOT / "godot_project" / "content" / "fixtures" / "cycles" / "fx_cycle.json"


def test_fx_recovery_roundtrip(tmp_path: Path) -> None:
    """FX-RECOVERY behavioural stand-in: coordinated save/load without half-pairs."""
    TRACK.mkdir(parents=True, exist_ok=True)
    sim = load_fixture("FX-CLOCK", seed=1001)
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    node0 = sim.state.player.get("node_id")
    saved = coord.request_save("release0")
    sim.state.clock["game_ms"] = int(sim.state.clock.get("game_ms", 0)) + 9000
    sim.state.player["node_id"] = "node:999"
    coord.prepare_load("release0")
    restored = coord.commit_load()
    assert restored.state.player.get("node_id") == node0
    payload = {
        "slot": saved["slot"],
        "world_version": restored.state.world_version,
        "fixture": "FX-RECOVERY",
        "seed": 1001,
        "parent_fixture": "FX-CLOCK",
    }
    (TRACK / "fx_recovery.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_three_full_cycle_continuations() -> None:
    TRACK.mkdir(parents=True, exist_ok=True)
    meta = json.loads(FX_CYCLE.read_text(encoding="utf-8"))
    seed = int(meta.get("seed") or 1212)
    sim = load_fixture("FX-ERA", seed=seed)
    state = sim.state
    people0 = set(state.people)
    state.clock["era"] = "future"
    state.clock["cycle"] = 0
    cycles = []
    for i in range(3):
        out = EraService(state).reseed_cycle(plan_id=f"release-cycle-{i}", faction_count=6)
        cycles.append(int(out["receipt"]["cycle"]))
        state.clock["era"] = "future"
    assert len(cycles) == 3
    assert set(state.people) == people0
    report = {
        "fixture": "FX-CYCLE",
        "parent_fixture": "FX-ERA",
        "cycles": cycles,
        "people_preserved": True,
        "seed": seed,
    }
    (TRACK / "multi_cycle.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def test_release_manifest_present() -> None:
    manifest = ROOT / "godot_project" / "content" / "manifests" / "release.json"
    assert manifest.is_file(), "run tools/package_desktop.py first"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data.get("offline") is True
    assert data.get("network_required") is False
    assert data.get("api_keys_required") is False
