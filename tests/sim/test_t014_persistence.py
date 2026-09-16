"""T014 persistence repository checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import bootstrap_world
from sim.dmb.persistence.repository import SaveRepository


def test_save_load_continuation_identical(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=21)
    sim.state.ids.new("person")
    sim.rng.draw_int("gameplay", 0, 10)
    sim.state.rng = sim.rng.to_dict()
    repo = SaveRepository(tmp_path)
    snap = sim.snapshot()
    repo.write("slot0", snap)
    loaded = repo.load_world("slot0")
    assert loaded.state.to_dict() == sim.state.to_dict()
    assert loaded.state.ids.new("person") == sim.state.ids.new("person")


def test_corrupt_candidate_never_replaces_good(tmp_path: Path) -> None:
    sim = bootstrap_world()
    repo = SaveRepository(tmp_path)
    repo.write("slot0", sim.snapshot())
    good = repo.slot_path("slot0").read_text(encoding="utf-8")
    with pytest.raises(TypeValidationError):
        repo.write("slot0", {"schema_version": 1, "world": {"world_id": "x"}})
    assert repo.slot_path("slot0").read_text(encoding="utf-8") == good


def test_unsupported_source_save_remains_untouched(tmp_path: Path) -> None:
    sim = bootstrap_world()
    repo = SaveRepository(tmp_path)
    repo.write("slot0", sim.snapshot())
    good = repo.slot_path("slot0").read_text(encoding="utf-8")
    with pytest.raises(TypeValidationError, match="unsupported"):
        repo.write("slot0", {"schema_version": 99, "world": sim.state.to_dict()})
    assert repo.slot_path("slot0").read_text(encoding="utf-8") == good


def test_ids_and_rng_resume_exactly(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=5)
    for _ in range(3):
        sim.rng.draw_int("gameplay", 0, 50)
    sim.state.rng = sim.rng.to_dict()
    expected = [sim.rng.draw_int("gameplay", 0, 50) for _ in range(3)]
    # Rewind draws for save point
    sim.state.rng["streams"]["gameplay"]["draws"] = 3
    repo = SaveRepository(tmp_path)
    repo.write("slot0", sim.snapshot())
    loaded = repo.load_world("slot0")
    got = [loaded.rng.draw_int("gameplay", 0, 50) for _ in range(3)]
    assert got == expected
