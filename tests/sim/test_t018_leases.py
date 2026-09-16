"""T018 encounter lease exclusivity."""

from __future__ import annotations

import pytest

from sim.dmb.core.types import TypeValidationError
from sim.dmb.encounters.registry import EncounterRegistry


def test_two_active_leases_cannot_own_one_entity() -> None:
    reg = EncounterRegistry()
    reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:a")
    with pytest.raises(TypeValidationError, match="already leased"):
        reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:b")


def test_stale_duplicate_delta_cannot_overwrite() -> None:
    reg = EncounterRegistry()
    lease = reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:a")
    with pytest.raises(TypeValidationError, match="stale"):
        reg.checkpoint("lease:a", {"hp": 1}, version=lease.version, base_hash="deadbeef")


def test_close_returns_authority_once() -> None:
    reg = EncounterRegistry()
    reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:a")
    closed = reg.close("lease:a", {"winner": "player"})
    assert closed["authority"] == "server"
    assert "unit:1" not in reg.entity_index
    with pytest.raises(KeyError):
        reg.close("lease:a", {"winner": "player"})


def test_failed_preparation_leaves_owner_intact() -> None:
    reg = EncounterRegistry()
    reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:a")
    with pytest.raises(TypeValidationError):
        reg.grant("duel", ["unit:1", "unit:2"], {"hp": 10}, "lease:b")
    assert reg.entity_index["unit:1"] == "lease:a"
    assert "lease:b" not in reg.leases
