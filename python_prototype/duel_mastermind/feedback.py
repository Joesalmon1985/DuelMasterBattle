from __future__ import annotations

from collections import Counter
from typing import List, Tuple

from .code import CodeValidationError, validate_colour


def score_guess(secret: List[int], guess: List[int]) -> Tuple[int, int]:
    """Return (exact, colour_only) using multiset Mastermind scoring."""
    if len(secret) != len(guess):
        raise CodeValidationError(
            f"secret and guess must have equal length, got {len(secret)} vs {len(guess)}"
        )
    for s, g in zip(secret, guess):
        validate_colour(int(s))
        validate_colour(int(g))

    exact = 0
    secret_remaining: List[int] = []
    guess_remaining: List[int] = []

    for s, g in zip(secret, guess):
        if s == g:
            exact += 1
        else:
            secret_remaining.append(s)
            guess_remaining.append(g)

    secret_counts = Counter(secret_remaining)
    colour_only = 0
    for g in guess_remaining:
        if secret_counts.get(g, 0) > 0:
            colour_only += 1
            secret_counts[g] -= 1

    return exact, colour_only
