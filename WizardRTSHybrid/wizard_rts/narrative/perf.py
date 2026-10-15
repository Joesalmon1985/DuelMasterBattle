"""Counters and timers for the performance tests. This is the one narrative module allowed to read the wall clock (it measures cost and never
feeds a decision), and the counters are not part of the pickled world."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

COUNTS: dict[str, int] = {}
SECONDS: dict[str, float] = {}


def count(name: str, n: int = 1) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + n


@contextmanager
def timed(name: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        SECONDS[name] = SECONDS.get(name, 0.0) + (time.perf_counter() - t0)
        COUNTS[name] = COUNTS.get(name, 0) + 1


def reset() -> None:
    COUNTS.clear()
    SECONDS.clear()
