"""Generate shared golden fixtures for Python + Godot parity tests."""

from __future__ import annotations

import json
from pathlib import Path

from duel_mastermind import (
    CODE_LENGTH,
    MAX_GUESSES,
    OPENING_GUESS,
    RandomBot,
    SequentialDuelGame,
    SolverBot,
    compute_result,
    generate_all_codes,
    score_guess,
)
from duel_mastermind.code import is_valid_code

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "shared_fixtures"


def generate_all() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    feedback_cases = [
        {"secret": [0, 1, 2, 3], "guess": [0, 1, 2, 3], "exact": 4, "colour_only": 0},
        {"secret": [0, 0, 1, 2], "guess": [0, 1, 0, 3], "exact": 1, "colour_only": 2},
        {"secret": [0, 0, 1, 2], "guess": [0, 0, 0, 0], "exact": 2, "colour_only": 0},
        {"secret": [1, 1, 1, 1], "guess": [1, 2, 3, 4], "exact": 1, "colour_only": 0},
        {"secret": [0, 1, 2, 3], "guess": [3, 2, 1, 0], "exact": 0, "colour_only": 4},
        {"secret": [0, 0, 1, 2], "guess": [3, 4, 5, 6], "exact": 0, "colour_only": 0},
    ]
    for case in feedback_cases:
        e, c = score_guess(case["secret"], case["guess"])
        assert e == case["exact"] and c == case["colour_only"]
    _write("feedback_cases.json", {"version": 1, "cases": feedback_cases})

    duplicate_cases = [
        {"secret": [0, 0, 0, 1], "guess": [0, 0, 1, 0], "exact": 2, "colour_only": 2},
        {"secret": [2, 2, 2, 2], "guess": [2, 2, 3, 3], "exact": 2, "colour_only": 0},
    ]
    for case in duplicate_cases:
        e, c = score_guess(case["secret"], case["guess"])
        assert e == case["exact"] and c == case["colour_only"]
    _write("duplicate_edge_cases.json", {"version": 1, "cases": duplicate_cases})

    illegal_guesses = [
        {"guess": [0, 1, 2], "valid": False},
        {"guess": [0, 1, 2, 3, 4], "valid": False},
        {"guess": [-1, 0, 1, 2], "valid": False},
        {"guess": [0, 1, 2, 10], "valid": False},
        {"guess": [0, 1, 2, 3], "valid": True},
        {"guess": [9, 9, 9, 9], "valid": True},
    ]
    for case in illegal_guesses:
        assert is_valid_code(case["guess"]) == case["valid"]
    _write("illegal_guesses.json", {"version": 1, "cases": illegal_guesses})

    _write("guess_limit.json", {
        "version": 1,
        "max_guesses": MAX_GUESSES,
        "code_length": CODE_LENGTH,
    })

    bot = RandomBot(seed=42)
    bot_guesses = [bot.make_guess() for _ in range(20)]
    bot_code = bot.generate_code()
    for g in bot_guesses + [bot_code]:
        assert is_valid_code(g)
    _write("bot_legal_guesses.json", {
        "version": 1,
        "seed": 42,
        "guesses": bot_guesses,
        "code": bot_code,
    })

    win_draw_cases = [
        {
            "human_solved": True, "bot_solved": False,
            "human_guess_count": 3, "bot_guess_count": 5,
            "human_guesses": [], "bot_guesses": [],
            "expected_outcome": "human_win",
        },
        {
            "human_solved": False, "bot_solved": True,
            "human_guess_count": 5, "bot_guess_count": 2,
            "human_guesses": [], "bot_guesses": [],
            "expected_outcome": "bot_win",
        },
        {
            "human_solved": True, "bot_solved": True,
            "human_guess_count": 3, "bot_guess_count": 3,
            "human_guesses": [], "bot_guesses": [],
            "expected_outcome": "draw",
        },
        {
            "human_solved": False, "bot_solved": False,
            "human_guess_count": 12, "bot_guess_count": 12,
            "human_guesses": [{"guess": [0, 1, 2, 3], "exact": 2, "colour_only": 1}],
            "bot_guesses": [{"guess": [0, 0, 0, 0], "exact": 1, "colour_only": 0}],
            "expected_outcome": "draw",
        },
        {
            "human_solved": False, "bot_solved": False,
            "human_guess_count": 1, "bot_guess_count": 1,
            "human_guesses": [{"guess": [0, 1, 2, 3], "exact": 2, "colour_only": 1}],
            "bot_guesses": [{"guess": [0, 0, 0, 0], "exact": 1, "colour_only": 0}],
            "expected_outcome": "human_win",
        },
    ]
    for case in win_draw_cases:
        from duel_mastermind.game_state import GuessRecord
        hg = [GuessRecord(**g) for g in case["human_guesses"]]
        bg = [GuessRecord(**g) for g in case["bot_guesses"]]
        r = compute_result(
            case["human_solved"], case["bot_solved"],
            case["human_guess_count"], case["bot_guess_count"],
            hg, bg,
        )
        assert r.outcome == case["expected_outcome"]
    _write("win_draw_states.json", {"version": 1, "cases": win_draw_cases})

    representative_secrets = [
        [0, 1, 2, 3],
        [9, 9, 9, 9],
        [0, 0, 1, 1],
        [3, 7, 3, 7],
        [5, 2, 8, 1],
        [1, 4, 1, 4],
    ]
    solver_cases = {
        "version": 1,
        "candidate_count": len(generate_all_codes()),
        "opening_guess": OPENING_GUESS,
        "representative_secrets": representative_secrets,
    }
    assert solver_cases["candidate_count"] == 10_000
    bot = SolverBot()
    assert bot.make_guess() == OPENING_GUESS
    for secret in representative_secrets:
        solved, count, _ = bot.solve_secret(secret)
        assert solved and count <= MAX_GUESSES, f"solver failed on {secret}"
    _write("solver_cases.json", solver_cases)

    print(f"Generated fixtures in {FIXTURES_DIR}")


def _write(name: str, data: dict) -> None:
    path = FIXTURES_DIR / name
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate_all()
