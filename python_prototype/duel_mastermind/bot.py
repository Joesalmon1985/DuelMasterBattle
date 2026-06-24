from __future__ import annotations

import random
from typing import List, Optional

from .code import SecretCode, validate_code
from .constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS


class RandomBot:
    """Generates legal codes and random legal guesses using a seeded RNG."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def generate_code(self) -> List[int]:
        return [self._rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH)]

    def make_guess(self) -> List[int]:
        return [self._rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH)]

    def register_feedback(self, guess: List[int], exact: int, colour_only: int) -> None:
        pass  # Random bot ignores feedback

    def is_legal_guess(self, guess: List[int]) -> bool:
        try:
            validate_code(guess)
            return True
        except Exception:
            return False
