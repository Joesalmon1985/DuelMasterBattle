from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DifficultyProfile:
    id: str
    display_name: str
    description: str
    bot_logic: str = "candidate_filter"
    bot_min_cast_time_multiplier: float = 1.0
    bot_max_cast_time_multiplier: float = 1.0
    bot_mistake_rate: float = 0.0
    bot_solver_cap: int = 100


_PROFILES = {
    "easy": DifficultyProfile("easy", "Easy", "Slower rival", "easy_random", 1.4, 1.4, 0.35, 0),
    "medium": DifficultyProfile("medium", "Medium", "Balanced", "candidate_filter", 1.0, 1.0, 0.05, 100),
    "hard": DifficultyProfile("hard", "Hard", "Dangerous", "capped_minimax", 0.75, 0.75, 0.0, 100),
}


def get_profile(difficulty_id: str) -> DifficultyProfile:
    if difficulty_id not in _PROFILES:
        raise KeyError(difficulty_id)
    return _PROFILES[difficulty_id]
