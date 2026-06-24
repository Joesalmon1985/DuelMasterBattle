"""Generate training traces from SolverBot teacher over random secrets."""

from __future__ import annotations

import random
from typing import List, Tuple

import numpy as np

from duel_mastermind.constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS
from duel_mastermind.feedback import score_guess
from duel_mastermind.solver_bot import SolverBot

# Each history step: 4 guess one-hot (10 each) + 2 feedback scalars = 42 floats
STEP_DIM = CODE_LENGTH * NUM_COLOURS + 2
MAX_STEPS = MAX_GUESSES


def encode_guess_feedback(guess: List[int], exact: int, colour_only: int) -> np.ndarray:
    vec = np.zeros(STEP_DIM, dtype=np.float32)
    for i, g in enumerate(guess):
        vec[i * NUM_COLOURS + g] = 1.0
    vec[CODE_LENGTH * NUM_COLOURS] = exact / CODE_LENGTH
    vec[CODE_LENGTH * NUM_COLOURS + 1] = colour_only / CODE_LENGTH
    return vec


def generate_traces(num_secrets: int = 32, seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Return (X, y) where X is padded history and y is next-guess peg ids."""
    rng = random.Random(seed)
    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    for _ in range(num_secrets):
        secret = [rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH)]
        bot = SolverBot()
        history: List[np.ndarray] = []
        for _step in range(MAX_STEPS):
            guess = bot.make_guess()
            exact, colour_only = score_guess(secret, guess)
            if exact == CODE_LENGTH:
                break
            bot.register_feedback(guess, exact, colour_only)
            history.append(encode_guess_feedback(guess, exact, colour_only))
            padded = np.zeros((MAX_STEPS, STEP_DIM), dtype=np.float32)
            for i, h in enumerate(history[-MAX_STEPS:]):
                padded[i] = h
            xs.append(padded.flatten())
            ys.append(np.array(bot.make_guess(), dtype=np.int64))
            # undo extra make_guess — regenerate properly
            break
    # Simpler: one sample per teacher guess step
    xs.clear()
    ys.clear()
    for _ in range(num_secrets):
        secret = [rng.randrange(NUM_COLOURS) for _ in range(CODE_LENGTH)]
        bot = SolverBot()
        history = []
        for _step in range(MAX_STEPS):
            next_guess = bot.make_guess()
            exact, colour_only = score_guess(secret, next_guess)
            if exact == CODE_LENGTH:
                break
            padded = np.zeros((MAX_STEPS, STEP_DIM), dtype=np.float32)
            for i, h in enumerate(history[-MAX_STEPS:]):
                padded[i] = h
            xs.append(padded.flatten())
            ys.append(np.array(next_guess, dtype=np.int64))
            history.append(encode_guess_feedback(next_guess, exact, colour_only))
            bot.register_feedback(next_guess, exact, colour_only)
    return np.stack(xs), np.stack(ys)
