"""Exact deduction baselines for the Mastermind duel (used by tests, the story agent and the duel environment).

`ConsistentSolver` plays the first code still consistent with every feedback so far (deterministic, no hidden information used).
`MinimaxSolver` is Knuth's worst-case minimiser over the remaining candidates. Both read only (guess, exact, colour_only) history,
so they cannot see the secret.
"""

from __future__ import annotations

from collections import Counter
from itertools import product

from sim.dmb.adventure.mastermind import score_guess


def all_codes(slots: int, colours: int) -> list[tuple[int, ...]]:
    return list(product(range(colours), repeat=slots))


def consistent(codes: list[tuple[int, ...]], history: list[tuple[list[int], int, int]]) -> list[tuple[int, ...]]:
    out = codes
    for guess, exact, colour in history:
        out = [c for c in out if score_guess(list(c), list(guess)) == (exact, colour)]
    return out


class ConsistentSolver:
    def __init__(self, slots: int = 4, colours: int = 6) -> None:
        self.slots, self.colours = slots, colours
        self.candidates = all_codes(slots, colours)

    def next_guess(self, history: list[tuple[list[int], int, int]] | None = None) -> list[int]:
        if history:
            self.candidates = consistent(self.candidates, history[-1:])  # incremental: earlier feedback is already applied
        if not history:
            half = max(1, self.slots // 2)  # the classic opening: AABB for 4 slots
            return [0] * half + [1] * (self.slots - half)
        return list(self.candidates[0])


class MinimaxSolver(ConsistentSolver):
    def next_guess(self, history: list[tuple[list[int], int, int]] | None = None) -> list[int]:
        if history:
            self.candidates = consistent(self.candidates, history[-1:])
        if not history:
            half = max(1, self.slots // 2)
            return [0] * half + [1] * (self.slots - half)
        cands = self.candidates
        if len(cands) <= 2:
            return list(cands[0])
        best, best_key = cands[0], None
        for g in cands:  # restricting guesses to candidates keeps it fast and still near-optimal
            worst = max(Counter(score_guess(list(c), list(g)) for c in cands).values())
            key = (worst, 0)
            if best_key is None or key < best_key:
                best, best_key = g, key
        return list(best)


def solve(secret: list[int], solver: ConsistentSolver, max_casts: int = 10) -> int | None:
    """Casts needed to find `secret`, or None if the solver ran out (used by the property tests)."""
    history: list[tuple[list[int], int, int]] = []
    for cast in range(1, max_casts + 1):
        g = solver.next_guess(history)
        e, c = score_guess(secret, g)
        if e == len(secret):
            return cast
        history.append((g, e, c))
    return None
