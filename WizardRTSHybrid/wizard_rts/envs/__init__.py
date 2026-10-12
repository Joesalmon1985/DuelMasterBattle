"""Headless scenario environments over the real game (owner run of 11 Oct 2026, section D).

Every environment wraps the actual simulation code (the Python world, the legacy quest/people/duel services, the ported puzzle and
Ward Duel rules), exposes `reset(seed)`, `step(action)`, a legal-action mask, an observation containing only what the wizard could
know, a bounded episode with a termination reason, `save()/load()`, `state_hash()` and a diagnostic trace. No environment keeps a
second copy of any rule.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from typing import Any

import numpy as np


class Env:
    """Common contract. Subclasses implement `_reset`, `_step`, `observe`, `legal_actions` and `state`."""

    name = "env"
    max_steps = 1000

    def __init__(self) -> None:
        self.seed = 0
        self.t = 0
        self.done = False
        self.reason = ""
        self.trace: list[dict[str, Any]] = []
        self.return_ = 0.0

    # ---- lifecycle
    def reset(self, seed: int | None = None, **scenario: Any) -> dict[str, Any]:
        if seed is not None:
            self.seed = int(seed)
        self.t, self.done, self.reason, self.trace, self.return_ = 0, False, "", [], 0.0
        self._reset(**scenario)
        return self.observe()

    def step(self, action: Any) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """(obs, reward, terminated, truncated, info). A step after the end is rejected, never silently applied."""
        if self.done:
            return self.observe(), 0.0, True, False, {"reason": "already_done"}
        legal = self.is_legal(action)
        if not legal:
            r, info = self._illegal(action)
        else:
            r, info = self._step(action)
        self.t += 1
        terminated = self.done and self.reason not in ("truncated",)
        truncated = False
        if not self.done and self.t >= self.max_steps:
            self.done, self.reason, truncated = True, "truncated", True
        self.return_ += r
        self.trace.append({"t": self.t, "action": _jsonable(action), "reward": round(float(r), 6), "legal": legal, "reason": self.reason})
        info = dict(info, reason=self.reason, legal=legal)
        return self.observe(), float(r), terminated, truncated, info

    # ---- to implement
    def _reset(self, **scenario: Any) -> None:
        raise NotImplementedError

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        raise NotImplementedError

    def _illegal(self, action: Any) -> tuple[float, dict[str, Any]]:
        return -0.05, {"illegal": True}

    def is_legal(self, action: Any) -> bool:
        return True

    def observe(self) -> dict[str, Any]:
        raise NotImplementedError

    def legal_actions(self) -> list[Any]:
        raise NotImplementedError

    def state(self) -> Any:
        """A JSON-able canonical state used for hashing, saving and replay."""
        raise NotImplementedError

    # ---- common
    def state_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.state(), sort_keys=True, default=str).encode()).hexdigest()[:16]

    def save(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def load(blob: bytes) -> "Env":
        return pickle.loads(blob)

    def replay(self, actions: list[Any], seed: int | None = None, **scenario: Any) -> str:
        """Re-run an action list from a fresh reset and return the final state hash (deterministic replay)."""
        self.reset(seed if seed is not None else self.seed, **scenario)
        for a in actions:
            self.step(a)
        return self.state_hash()


def _jsonable(x: Any) -> Any:
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (list, tuple)):
        return [_jsonable(i) for i in x]
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    return x
