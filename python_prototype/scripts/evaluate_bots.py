#!/usr/bin/env python3
"""Evaluate bot difficulty metrics over a deterministic validation secret set."""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataclasses import replace

from duel_mastermind.bot_factory import make_bot
from duel_mastermind.constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS
from duel_mastermind.encounters import get_encounter
from duel_mastermind.feedback import score_guess
from duel_mastermind.solver_bot import SolverBot

QUICK_VALIDATION_SECRETS = [
    [0, 1, 2, 3],
    [9, 9, 9, 9],
    [0, 0, 1, 1],
    [3, 7, 3, 7],
    [5, 2, 8, 1],
    [1, 4, 1, 4],
    [6, 6, 6, 6],
    [2, 8, 2, 8],
]

MASTER_SEED = 42


def generate_validation_secrets(count: int, master_seed: int = MASTER_SEED) -> list[list[int]]:
    rng = random.Random(master_seed)
    secrets: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    while len(secrets) < count:
        code = tuple(rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH))
        if code not in seen:
            seen.add(code)
            secrets.append(list(code))
    return secrets


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


def evaluate_level(level: str, secrets: list[list[int]]) -> dict:
    counts: list[int] = []
    failures = 0
    for secret in secrets:
        rs = replace(get_encounter("archmage_duel"), enemy_difficulty=level)
        bot = make_bot(rs, MASTER_SEED)
        solved, count = run_bot_on_secret(bot, secret)
        if not solved:
            failures += 1
        counts.append(count)
    return {
        "bot": level,
        "average_guesses": statistics.mean(counts),
        "median_guesses": statistics.median(counts),
        "solved_within_12_pct": 100.0 * (len(counts) - failures) / len(counts),
        "worst_case": max(counts),
        "failure_count": failures,
        "secret_count": len(secrets),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate bot difficulty levels")
    parser.add_argument("--count", type=int, default=100, help="Number of validation secrets")
    parser.add_argument("--quick", action="store_true", help="Use 8 fixed secrets only")
    args = parser.parse_args()

    if args.quick:
        secrets = QUICK_VALIDATION_SECRETS
    else:
        secrets = generate_validation_secrets(args.count)

    print(f"Validation secrets: {len(secrets)} (master_seed={MASTER_SEED})")
    results: list[dict] = []
    for level in ["easy", "normal", "hard", "expert"]:
        m = evaluate_level(level, secrets)
        results.append(m)
        print(
            f"{m['bot']}: avg={m['average_guesses']:.2f} "
            f"median={m['median_guesses']:.1f} "
            f"solved_within_12={m['solved_within_12_pct']:.0f}% "
            f"failures={m['failure_count']} worst={m['worst_case']}"
        )

    # Note: on small samples Normal can match or beat Hard due to minimax pool-cap variance.
    if len(secrets) <= 20:
        normal_avg = next(r["average_guesses"] for r in results if r["bot"] == "normal")
        hard_avg = next(r["average_guesses"] for r in results if r["bot"] == "hard")
        if normal_avg <= hard_avg:
            print(
                "Note: Normal avg <= Hard on this sample — minimax pool caps add variance; "
                "use --count 100 for stable ordering."
            )


if __name__ == "__main__":
    main()
