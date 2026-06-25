from __future__ import annotations

import itertools
from typing import List

from .duel_ruleset import DuelRuleset


def opening_guess_for_ruleset(ruleset: DuelRuleset) -> List[int]:
    pool = ruleset.attack_magic_pool
    if not pool:
        return []
    a = pool[0]
    b = pool[1] if len(pool) > 1 else pool[0]
    pattern = [a, a, b, b]
    return pattern[: ruleset.slot_count]


def generate_candidate_codes(ruleset: DuelRuleset) -> List[List[int]]:
    pool = ruleset.attack_magic_pool
    n = ruleset.slot_count
    if ruleset.allow_repeats:
        codes: List[List[int]] = [[]]
        for _ in range(n):
            codes = [c + [colour] for c in codes for colour in pool]
        return codes
    return [list(p) for p in itertools.permutations(pool, n)]


def candidate_count_for_ruleset(ruleset: DuelRuleset) -> int:
    return len(generate_candidate_codes(ruleset))
