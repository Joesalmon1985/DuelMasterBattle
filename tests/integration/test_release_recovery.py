"""T152 — save corruption, content mismatch, backup restore, crash recovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import bootstrap_world
from sim.dmb.persistence.coordinator import RECOVERY_SLOT, SaveCoordinator
from sim.dmb.persistence.repository import SaveRepository


def test_backup_restore_after_corrupt_primary(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=42)
    repo = SaveRepository(tmp_path)
    coord = SaveCoordinator(sim, repo)
    coord.request_save("slot0")
    good_node = sim.state.player["node_id"]
    # Second save creates .previous.json backup of first good write.
    sim.state.player["node_id"] = "node:2"
    coord.request_save("slot0")
    primary = repo.slot_path("slot0")
    primary.write_text("{not-json", encoding="utf-8")
    restored = repo.read("slot0")
    assert restored.get("_recovery", {}).get("restored_from_backup") is True
    assert "backup" in restored["_recovery"]["message"].lower()
    assert restored["world"]["player"]["node_id"] in {good_node, "node:2"}


def test_content_hash_mismatch_refuses_silent_load(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=9)
    repo = SaveRepository(tmp_path)
    repo.write("slot0", sim.snapshot())
    path = repo.slot_path("slot0")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["world"]["player"]["node_id"] = "node:hacked"
    # Keep stale hash so body no longer matches.
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(TypeValidationError, match="content hash mismatch"):
        repo.read("slot0")


def test_content_hash_mismatch_falls_back_to_backup(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=11)
    repo = SaveRepository(tmp_path)
    coord = SaveCoordinator(sim, repo)
    coord.request_save("slot0")
    original_node = sim.state.player["node_id"]
    sim.state.player["node_id"] = "node:2"
    coord.request_save("slot0")
    path = repo.slot_path("slot0")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["content_hash"] = "0" * 64
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    restored = repo.read("slot0")
    assert restored.get("_recovery", {}).get("restored_from_backup") is True
    assert restored["world"]["player"]["node_id"] == original_node


def test_no_half_save_pair_after_failed_write(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=3)
    repo = SaveRepository(tmp_path)
    repo.write("slot0", sim.snapshot())
    good = repo.slot_path("slot0").read_text(encoding="utf-8")
    with pytest.raises(TypeValidationError):
        repo.write("slot0", {"schema_version": 1, "world": {"world_id": "broken"}})
    assert repo.slot_path("slot0").read_text(encoding="utf-8") == good
    # Backup of last good write may exist from prior replaces; primary remains good.
    assert json.loads(good)["world"]["world_id"] == sim.state.world_id


def test_recovery_checkpoint_survives_crash_restart(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=77)
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    sim.state.clock["game_ms"] = 2500
    sim.state.player["position"] = [4.0, 7.0]
    coord.write_recovery_checkpoint("crash_probe")
    # New coordinator mimics process restart.
    restarted = SaveCoordinator(bootstrap_world(seed=1), SaveRepository(tmp_path))
    assert restarted.has_recovery_checkpoint()
    out = restarted.restore_recovery_checkpoint()
    assert out["sim"].state.clock["game_ms"] == 2500
    assert out["sim"].state.player["position"] == [4.0, 7.0]
    assert out["meta"]["slot"] == RECOVERY_SLOT


def test_prototype_saves_not_deleted_on_recovery(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=5)
    repo = SaveRepository(tmp_path)
    coord = SaveCoordinator(sim, repo)
    coord.request_save("prototype_user")
    coord.write_recovery_checkpoint("periodic")
    assert repo.slot_path("prototype_user").is_file()
    coord.restore_recovery_checkpoint()
    assert repo.slot_path("prototype_user").is_file()
