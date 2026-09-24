"""Semantic visual registry integrity."""

from __future__ import annotations

from sim.dmb.presentation.semantic_visuals import (
    load_registry,
    resolve_visual,
    validate_registry,
)


def test_registry_valid_and_nonempty() -> None:
    reg = load_registry()
    assert len(reg.get("entries") or []) >= 10
    assert validate_registry(reg) == []


def test_resolve_known_and_unknown() -> None:
    known = resolve_visual("hazard.alien")
    assert known["registered"] is True
    assert known["shape"] == "oval"
    assert known["abbrev"]
    unknown = resolve_visual("building.future.unknown_widget")
    assert unknown["registered"] is False
    assert unknown["placeholder"] is True
    assert unknown["abbrev"]
    assert unknown["semantic_id"] == "building.future.unknown_widget"


def test_no_anonymous_entries() -> None:
    for row in load_registry().get("entries") or []:
        assert not row.get("anonymous")
        assert row.get("label") or row.get("abbrev")
