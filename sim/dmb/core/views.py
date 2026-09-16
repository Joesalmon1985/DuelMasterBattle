"""Immutable scoped view helpers."""

from __future__ import annotations

from typing import Any, Mapping

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, validate_definition_id, validate_instance_id


def scoped_view(state: WorldState, scope: str = "player") -> Mapping[str, Any]:
    return state.read_view(scope)


def assert_id_kinds_separated(definition_id: str, instance_id: str) -> None:
    validate_definition_id(definition_id)
    validate_instance_id(instance_id)
    if definition_id == instance_id:
        raise TypeValidationError("definition and instance IDs cannot be interchanged")
