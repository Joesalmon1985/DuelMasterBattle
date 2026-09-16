"""Mutation barrier with provisional write set."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError


@dataclass
class TransactionCoordinator:
    state: WorldState
    _active: bool = False
    _cause: str | None = None
    _snapshot: dict[str, Any] | None = None
    _changes: list[Callable[[WorldState], None]] = field(default_factory=list)

    def begin(self, cause: str) -> None:
        if self._active:
            raise TypeValidationError("transaction already active")
        self._active = True
        self._cause = cause
        self._snapshot = self.state.to_dict()
        self._changes.clear()

    def apply(self, change: Callable[[WorldState], None]) -> None:
        if not self._active:
            raise TypeValidationError("no active transaction")
        self._changes.append(change)

    def commit(self) -> None:
        if not self._active or self._snapshot is None:
            raise TypeValidationError("no active transaction")
        try:
            for change in self._changes:
                change(self.state)
        except Exception:
            self.abort()
            raise
        self._active = False
        self._cause = None
        self._snapshot = None
        self._changes.clear()

    def abort(self) -> None:
        if self._snapshot is not None:
            restored = WorldState.from_dict(deepcopy(self._snapshot))
            self.state.__dict__.update(restored.__dict__)
        self._active = False
        self._cause = None
        self._snapshot = None
        self._changes.clear()
