"""Optional NN policy bot — falls back to solver if no weights."""

from __future__ import annotations

from typing import List

from duel_mastermind.bot import RandomBot
from duel_mastermind.solver_bot import SolverBot


class PolicyBot:
    def __init__(self, seed: int = 0) -> None:
        self._seed = seed
        self._fallback = SolverBot(seed=seed)
        self._policy = None
        try:
            from duel_mastermind.nn.model import GuessPolicy

            self._policy = GuessPolicy()
        except ImportError:
            pass

    def register_feedback(self, guess: List[int], exact: int, colour_only: int) -> None:
        self._fallback.register_feedback(guess, exact, colour_only)

    def make_guess(self) -> List[int]:
        return self._fallback.make_guess()

    def generate_code(self) -> List[int]:
        return RandomBot(self._seed + 777).generate_code()

    def is_legal_guess(self, guess: List[int]) -> bool:
        return self._fallback.is_legal_guess(guess)
