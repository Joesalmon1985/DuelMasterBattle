#!/usr/bin/env python3
"""Evaluate bot difficulty metrics over a fixed validation secret set."""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from duel_mastermind.bot_factory import make_bot
from duel_mastermind.constants import CODE_LENGTH, MAX_GUESSES
from duel_mastermind.feedback import score_guess
from duel_mastermind.solver_bot import SolverBot

VALIDATION_SECRETS = [
    [0, 1, 2, 3],
    [9, 9, 9, 9],
    [0, 0, 1, 1],
    [3, 7, 3, 7],
    [5, 2, 8, 1],
    [1, 4, 1, 4],
    [6, 6, 6, 6],
    [2, 8, 2, 8],
]


def run_bot_on_secret(bot, secret: list) -> tuple[bool, int]:
    if isinstance(bot, SolverBot):
        return bot.solve_secret(list(secret))[:2]
    solved = False
    count = MAX_GUESSES
    for i in range(MAX_GUESSES):
        guess = bot.make_guess()
        exact, colour_only = score_guess(secret, guess)
        if exact == CODE_LENGTH:
            return True, i + 1
        bot.register_feedback(guess, exact, colour_only)
    return solved, count


def evaluate_level(level: str) -> dict:
    counts: list[int] = []
    failures = 0
    for secret in VALIDATION_SECRETS:
        bot = make_bot(level, 42)
        solved, count = run_bot_on_secret(bot, secret)
        if not solved:
            failures += 1
        counts.append(count)
    solved_within = sum(1 for c in counts if c < MAX_GUESSES or c == MAX_GUESSES)
    return {
        "bot": level,
        "average_guesses": statistics.mean(counts),
        "median_guesses": statistics.median(counts),
        "solved_within_12_pct": 100.0 * (len(counts) - failures) / len(counts),
        "worst_case": max(counts),
        "failure_count": failures,
    }


def main() -> None:
    for level in ["easy", "normal", "hard", "expert"]:
        m = evaluate_level(level)
        print(
            f"{m['bot']}: avg={m['average_guesses']:.2f} "
            f"median={m['median_guesses']:.1f} "
            f"solved_within_12={m['solved_within_12_pct']:.0f}% "
            f"failures={m['failure_count']} worst={m['worst_case']}"
        )


if __name__ == "__main__":
    main()
