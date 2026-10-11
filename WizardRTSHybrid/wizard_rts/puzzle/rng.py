"""Godot 4's RandomNumberGenerator (PCG32), so a seed generates the same dungeon in Python and in the Godot game.

Verified bit-for-bit against `godot --headless` output in tests/test_puzzle_parity.py (seeds, `randi`, `randi_range`).
Godot: `seed(s)` = pcg32_srandom_r(state, s, 1442695040888963407); `randi_range(a, b)` = bounded unbiased draw of b - a + 1 plus a.
"""

from __future__ import annotations

MASK64 = (1 << 64) - 1
MASK32 = (1 << 32) - 1
MULT = 6364136223846793005
DEFAULT_INC = 1442695040888963407


class GodotRng:
    def __init__(self, seed: int = 0) -> None:
        self.seed(seed)

    def seed(self, seed: int) -> None:
        self.state = 0
        self.inc = ((DEFAULT_INC << 1) | 1) & MASK64
        self._next()
        self.state = (self.state + (int(seed) & MASK64)) & MASK64
        self._next()

    def _next(self) -> int:
        old = self.state
        self.state = (old * MULT + self.inc) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & MASK32
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & MASK32

    def randi(self) -> int:
        return self._next()

    def bounded(self, bounds: int) -> int:
        threshold = ((-bounds) & MASK32) % bounds
        while True:
            r = self._next()
            if r >= threshold:
                return r % bounds

    def randi_range(self, a: int, b: int) -> int:
        if a == b:
            return a
        lo, hi = min(a, b), max(a, b)
        return self.bounded(hi - lo + 1) + lo
