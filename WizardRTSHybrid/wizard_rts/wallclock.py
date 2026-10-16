"""The one place the game reads the wall clock (the real time at which a save was closed, for the offline catch-up). The simulation never reads it: the
narrative package takes it from here, so its isolation test (no wall clock inside the layer) stays true and a test can replace `now`."""
from __future__ import annotations

import time


def now() -> float:
    return time.time()
