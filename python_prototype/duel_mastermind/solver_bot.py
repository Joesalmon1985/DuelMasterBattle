from __future__ import annotations

from typing import Dict, List, Tuple

from .code import validate_code
from .constants import CODE_LENGTH, MAX_COLOUR, MIN_COLOUR, NUM_COLOURS
from .feedback import score_guess

OPENING_GUESS: List[int] = [0, 0, 1, 1]


def generate_all_codes() -> List[List[int]]:
    """All 10^4 codes for length 4, 10 colours, repeats allowed."""
    codes: List[List[int]] = []
    for a in range(NUM_COLOURS):
        for b in range(NUM_COLOURS):
            for c in range(NUM_COLOURS):
                for d in range(NUM_COLOURS):
                    codes.append([a, b, c, d])
    return codes


ALL_CODES: List[List[int]] = generate_all_codes()


class SolverBot:
    """Candidate-elimination bot with configurable strategy (not claimed optimal)."""

    STRATEGY_RANDOM = "random"
    STRATEGY_MINIMAX = "minimax"
    MAX_MINIMAX_POOL_HARD = 100
    MAX_MINIMAX_POOL_EXPERT = 500

    def __init__(
        self,
        strategy: str = STRATEGY_MINIMAX,
        seed: int = 0,
        max_minimax_pool: int = MAX_MINIMAX_POOL_HARD,
    ) -> None:
        self._strategy = strategy
        self._seed = seed
        self._max_minimax_pool = max_minimax_pool
        self._candidates: List[List[int]] = [list(c) for c in ALL_CODES]
        self._guess_count = 0
        self._last_guess: List[int] = []

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @staticmethod
    def all_code_count() -> int:
        return len(ALL_CODES)

    def register_feedback(self, guess: List[int], exact: int, colour_only: int) -> None:
        target = (exact, colour_only)
        self._candidates = [
            c for c in self._candidates if score_guess(c, guess) == target
        ]

    def make_guess(self) -> List[int]:
        if self._guess_count == 0:
            guess = list(OPENING_GUESS)
        elif self._strategy == self.STRATEGY_RANDOM:
            idx = (self._seed + self._guess_count) % len(self._candidates)
            guess = list(self._candidates[idx])
        else:
            guess = self._pick_minimax_guess()
        self._guess_count += 1
        self._last_guess = guess
        return guess

    def _pick_minimax_guess(self) -> List[int]:
        if len(self._candidates) == 1:
            return list(self._candidates[0])
        best_guess: List[int] | None = None
        best_worst = 10_000
        best_is_candidate = False
        pool = self._candidates
        pool = pool[: self._max_minimax_pool]
        for guess in pool:
            partitions: Dict[Tuple[int, int], int] = {}
            for secret in self._candidates:
                fb = score_guess(secret, guess)
                partitions[fb] = partitions.get(fb, 0) + 1
            worst = max(partitions.values()) if partitions else 0
            is_cand = guess in self._candidates
            if (
                best_guess is None
                or worst < best_worst
                or (worst == best_worst and is_cand and not best_is_candidate)
                or (worst == best_worst and is_cand == best_is_candidate and guess < best_guess)
            ):
                best_guess = list(guess)
                best_worst = worst
                best_is_candidate = is_cand
        return best_guess or list(self._candidates[0])

    def generate_code(self) -> List[int]:
        import random

        rng = random.Random(self._seed + 999)
        return [rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH)]

    def is_legal_guess(self, guess: List[int]) -> bool:
        try:
            validate_code(guess)
            return True
        except Exception:
            return False

    def solve_secret(self, secret: List[int], max_guesses: int = 12) -> Tuple[bool, int, List[List[int]]]:
        """Deterministic solve loop for tests."""
        self._candidates = [list(c) for c in ALL_CODES]
        self._guess_count = 0
        guesses: List[List[int]] = []
        for _ in range(max_guesses):
            g = self.make_guess()
            guesses.append(g)
            exact, colour_only = score_guess(secret, g)
            if exact == CODE_LENGTH:
                return True, len(guesses), guesses
            self.register_feedback(g, exact, colour_only)
        return False, len(guesses), guesses
