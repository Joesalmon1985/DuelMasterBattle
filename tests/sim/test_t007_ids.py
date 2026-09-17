"""T007 identity and wire-integer behavioural checks."""

from __future__ import annotations

import json

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.types import JSON_INT_MAX, TypeValidationError, parse_wire_int, wire_int


def test_id_resume() -> None:
    alloc = IdAllocator("world:a")
    first = alloc.new("person")
    payload = alloc.to_dict()
    restored = IdAllocator.from_dict(json.loads(json.dumps(payload)), expected_world_id="world:a")
    second = restored.new("person")
    assert first == "person:1"
    assert second == "person:2"
    assert first != second


def test_foreign_world_id_rejected() -> None:
    alloc = IdAllocator("world:a")
    alloc.new("cart")
    with pytest.raises(TypeValidationError, match="foreign world_id"):
        IdAllocator.from_dict(alloc.to_dict(), expected_world_id="world:other")


def test_large_counter_roundtrip() -> None:
    huge = JSON_INT_MAX + 99
    encoded = wire_int(huge)
    assert isinstance(encoded, str)
    assert parse_wire_int(encoded) == huge
    alloc = IdAllocator("world:a", counters={"person": huge})
    roundtrip = IdAllocator.from_dict(json.loads(json.dumps(alloc.to_dict())))
    assert roundtrip.peek("person") == huge
    assert roundtrip.new("person") == f"person:{huge + 1}"
