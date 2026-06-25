from __future__ import annotations

from typing import Dict, List

from .constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS
from .duel_ruleset import DuelRuleset

DEFAULT_ENCOUNTER_ID = "archmage_duel"

_ALL_MAGICS = list(range(NUM_COLOURS))
_ARCHMAGE_POINTS = ["Shield", "Body", "Staff", "Mind"]

_ENCOUNTERS: Dict[str, DuelRuleset] = {}


def _register(rs: DuelRuleset) -> DuelRuleset:
    _ENCOUNTERS[rs.id] = rs
    return rs


def _build_catalog() -> None:
    if _ENCOUNTERS:
        return
    _register(
        DuelRuleset(
            id="blue_apprentice",
            display_name="Blue Apprentice",
            description="A novice duelist — one point, limited magics.",
            slot_count=1,
            point_names=["Shield"],
            secret_magic_pool=[1, 2, 9],
            attack_magic_pool=[0, 1, 2, 9],
            max_attacks_per_player=4,
            enemy_name="Blue Apprentice",
            enemy_archetype="blue_wizard",
            enemy_visual_hint="Blue robes and a hesitant wand grip.",
            enemy_difficulty="easy",
        )
    )
    _register(
        DuelRuleset(
            id="thorn_adept",
            display_name="Thorn Adept",
            description="Nature magic — two points, thorny defences.",
            slot_count=2,
            point_names=["Shield", "Body"],
            secret_magic_pool=[6, 3, 0, 7],
            attack_magic_pool=[6, 3, 0, 7, 1],
            max_attacks_per_player=6,
            enemy_name="Thorn Adept",
            enemy_archetype="thorn_druid",
            enemy_visual_hint="Thorns and bark woven into their robes.",
            enemy_difficulty="normal",
            allow_repeats=False,
        )
    )
    _register(
        DuelRuleset(
            id="mirror_mage",
            display_name="Mirror Mage",
            description="Reflected power — three points, repeats allowed.",
            slot_count=3,
            point_names=["Shield", "Body", "Staff"],
            secret_magic_pool=[4, 5, 8, 9],
            attack_magic_pool=[4, 5, 8, 9],
            max_attacks_per_player=8,
            enemy_name="Mirror Mage",
            enemy_archetype="mirror_mage",
            enemy_visual_hint="Mirrored robes that shimmer with duplicate spells.",
            enemy_difficulty="hard",
        )
    )
    _register(
        DuelRuleset(
            id="archmage_duel",
            display_name="Archmage Duel",
            description="The full wizard duel — classic Mastermind rules.",
            slot_count=CODE_LENGTH,
            point_names=list(_ARCHMAGE_POINTS),
            secret_magic_pool=list(_ALL_MAGICS),
            attack_magic_pool=list(_ALL_MAGICS),
            max_attacks_per_player=MAX_GUESSES,
            enemy_name="Archmage",
            enemy_archetype="archmage",
            enemy_visual_hint="Full duel rules — every magic, every point.",
            enemy_difficulty="expert",
        )
    )


def get_encounter(encounter_id: str) -> DuelRuleset:
    _build_catalog()
    if encounter_id not in _ENCOUNTERS:
        raise KeyError(f"unknown encounter: {encounter_id}")
    return _ENCOUNTERS[encounter_id]


def all_encounters() -> List[DuelRuleset]:
    _build_catalog()
    return [
        _ENCOUNTERS["blue_apprentice"],
        _ENCOUNTERS["thorn_adept"],
        _ENCOUNTERS["mirror_mage"],
        _ENCOUNTERS["archmage_duel"],
    ]


def default_encounter() -> DuelRuleset:
    return get_encounter(DEFAULT_ENCOUNTER_ID)
