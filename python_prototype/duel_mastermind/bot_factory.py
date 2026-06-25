from __future__ import annotations

from typing import Union

from .bot import RandomBot
from .duel_ruleset import DuelRuleset
from .encounters import default_encounter
from .solver_bot import SolverBot


def make_bot(ruleset: DuelRuleset | None = None, seed: int = 42) -> Union[RandomBot, SolverBot]:
    rs = ruleset or default_encounter()
    level = rs.enemy_difficulty.lower()
    if level == "easy":
        return RandomBot(rs, seed)
    if level == "normal":
        return SolverBot(rs, strategy=SolverBot.STRATEGY_RANDOM, seed=seed)
    if level == "hard":
        return SolverBot(
            rs,
            strategy=SolverBot.STRATEGY_MINIMAX,
            seed=seed,
            max_minimax_pool=SolverBot.MAX_MINIMAX_POOL_HARD,
        )
    return SolverBot(
        rs,
        strategy=SolverBot.STRATEGY_MINIMAX,
        seed=seed,
        max_minimax_pool=SolverBot.MAX_MINIMAX_POOL_EXPERT,
    )
