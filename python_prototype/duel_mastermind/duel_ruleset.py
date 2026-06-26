from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

DEFAULT_LOCUS_NAMES = [
    "Roach", "Uzag", "Lieana", "Gyse", "Vorr", "Mael", "Oshen", "Keth",
]


class RulesetValidationError(ValueError):
    pass


@dataclass
class DuelRuleset:
    id: str
    display_name: str
    description: str
    slot_count: int
    point_names: List[str]
    secret_magic_pool: List[int]
    attack_magic_pool: List[int]
    max_attacks_per_player: int
    enemy_name: str
    enemy_archetype: str
    enemy_visual_hint: str
    enemy_difficulty: str
    player_modifiers: Dict = field(default_factory=dict)
    enemy_modifiers: Dict = field(default_factory=dict)
    allow_repeats: bool = True
    allow_hidden_secret_types: bool = False
    base_min_cast_time_seconds: float = 5.0
    base_max_cast_time_seconds: float = 16.0
    enemy_traits: Dict = field(default_factory=dict)
    player_traits: Dict = field(default_factory=dict)
    last_stand_min_attacks: int = 0
    last_stand_seconds: float = 0.0
    tutorial_flags: Dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.slot_count < 1 or self.slot_count > 8:
            raise RulesetValidationError(f"slot_count must be 1-8, got {self.slot_count}")
        if not self.point_names:
            self.point_names = DEFAULT_LOCUS_NAMES[: self.slot_count]
        if len(self.point_names) != self.slot_count:
            raise RulesetValidationError(
                f"point_names length {len(self.point_names)} != slot_count {self.slot_count}"
            )
        self.validate_pools()

    def validate_pools(self) -> None:
        if self.allow_hidden_secret_types:
            return
        secret_set = set(self.secret_magic_pool)
        attack_set = set(self.attack_magic_pool)
        if not secret_set.issubset(attack_set):
            missing = secret_set - attack_set
            raise RulesetValidationError(
                f"secret_magic_pool must be subset of attack_magic_pool; missing in attack pool: {sorted(missing)}"
            )

    def effective_max_attacks(self) -> int:
        return self.max_attacks_per_player + int(self.player_modifiers.get("extra_attacks", 0))

    def bot_delay_multiplier(self) -> float:
        return float(self.enemy_modifiers.get("bot_attack_delay_multiplier", 1.0))

    def is_solved(self, exact_hits: int) -> bool:
        return exact_hits == self.slot_count
