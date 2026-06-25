from __future__ import annotations

from typing import Union

from .bot import RandomBot
from .solver_bot import SolverBot


def make_bot(difficulty: str = "expert", seed: int = 42) -> Union[RandomBot, SolverBot]:
    level = difficulty.lower()
    if level == "easy":
        return RandomBot(seed)
    if level == "normal":
        return SolverBot(strategy=SolverBot.STRATEGY_RANDOM, seed=seed)
    if level == "hard":
        return SolverBot(strategy=SolverBot.STRATEGY_MINIMAX, seed=seed, max_minimax_pool=SolverBot.MAX_MINIMAX_POOL_HARD)
    # expert
    return SolverBot(strategy=SolverBot.STRATEGY_MINIMAX, seed=seed, max_minimax_pool=SolverBot.MAX_MINIMAX_POOL_EXPERT)
