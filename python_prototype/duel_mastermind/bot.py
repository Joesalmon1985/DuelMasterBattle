from __future__ import annotations

import random
from typing import List, Union

from .candidate_gen import generate_candidate_codes, opening_guess_for_ruleset
from .code import validate_code_for_ruleset
from .constants import CODE_LENGTH
from .duel_ruleset import DuelRuleset
from .encounters import default_encounter
from .feedback import score_guess


class RandomBot:
    def __init__(self, ruleset: DuelRuleset | None = None, seed: int = 0) -> None:
        self._ruleset = ruleset or default_encounter()
        self._rng = random.Random(seed)

    def generate_code(self) -> List[int]:
        pool = self._ruleset.secret_magic_pool
        n = self._ruleset.slot_count
        if self._ruleset.allow_repeats:
            return [self._rng.choice(pool) for _ in range(n)]
        return self._rng.sample(pool, n)

    def make_guess(self) -> List[int]:
        pool = self._ruleset.attack_magic_pool
        n = self._ruleset.slot_count
        if self._ruleset.allow_repeats:
            return [self._rng.choice(pool) for _ in range(n)]
        return self._rng.sample(pool, n)

    def register_feedback(self, _guess: List[int], _exact: int, _colour_only: int) -> None:
        pass

    def is_legal_guess(self, guess: List[int]) -> bool:
        try:
            validate_code_for_ruleset(guess, self._ruleset, self._ruleset.attack_magic_pool)
            return True
        except Exception:
            return False
