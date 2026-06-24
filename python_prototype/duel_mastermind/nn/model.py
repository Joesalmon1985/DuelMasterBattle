"""Small MLP policy predicting next guess peg ids."""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn
except ImportError:  # pragma: no cover
    torch = None
    nn = None

from duel_mastermind.constants import CODE_LENGTH, NUM_COLOURS
from duel_mastermind.nn.dataset import MAX_STEPS, STEP_DIM


def build_model(hidden: int = 64):
    if torch is None:
        raise ImportError("torch not available")
    input_dim = MAX_STEPS * STEP_DIM
    return nn.Sequential(
        nn.Linear(input_dim, hidden),
        nn.ReLU(),
        nn.Linear(hidden, hidden),
        nn.ReLU(),
        nn.Linear(hidden, CODE_LENGTH * NUM_COLOURS),
    )


class GuessPolicy:
    def __init__(self, hidden: int = 64):
        if torch is None:
            raise ImportError("torch not available")
        self.model = build_model(hidden)
        self._device = torch.device("cpu")

    def predict_guess(self, history_flat) -> list:
        self.model.eval()
        with torch.no_grad():
            x = torch.tensor(history_flat, dtype=torch.float32).unsqueeze(0)
            logits = self.model(x).view(CODE_LENGTH, NUM_COLOURS)
            return [int(logits[i].argmax().item()) for i in range(CODE_LENGTH)]
