from __future__ import annotations

from typing import Dict, List

from .constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS
from .duel_ruleset import DEFAULT_LOCUS_NAMES, DuelRuleset

DEFAULT_ENCOUNTER_ID = "archmage_duel"

_ALL_MAGICS = list(range(NUM_COLOURS))

_ENCOUNTERS: Dict[str, DuelRuleset] = {}


def _register(rs: DuelRuleset) -> DuelRuleset:
    _ENCOUNTERS[rs.id] = rs
    return rs


def _loci(count: int) -> List[str]:
    return list(DEFAULT_LOCUS_NAMES[:count])


def _build_catalog() -> None:
    if _ENCOUNTERS:
        return
    _register(
        DuelRuleset(
            id="blue_apprentice",
            display_name="Blue Apprentice",
            description="First tutorial — one locus, three essences.",
            slot_count=1,
            point_names=_loci(1),
            secret_magic_pool=[0, 1, 2],
            attack_magic_pool=[0, 1, 2],
            max_attacks_per_player=4,
            enemy_name="Blue Apprentice",
            enemy_archetype="blue_wizard",
            enemy_visual_hint="Blue robes and a hesitant wand grip.",
            enemy_difficulty="easy",
            allow_repeats=False,
            base_min_cast_time_seconds=8.0,
            base_max_cast_time_seconds=24.0,
            tutorial_flags={"suppress_auto_cast_warnings": True},
        )
    )
    _register(
        DuelRuleset(
            id="thorn_adept",
            display_name="Thorn Adept",
            description="Nature magic — two loci, thorny wards.",
            slot_count=2,
            point_names=_loci(2),
            secret_magic_pool=[0, 1, 6, 3],
            attack_magic_pool=[0, 1, 6, 3],
            max_attacks_per_player=6,
            enemy_name="Thorn Adept",
            enemy_archetype="thorn_druid",
            enemy_visual_hint="Thorns and bark woven into their robes.",
            enemy_difficulty="normal",
            allow_repeats=False,
            base_min_cast_time_seconds=5.0,
            base_max_cast_time_seconds=16.0,
        )
    )
    _register(
        DuelRuleset(
            id="mirror_mage",
            display_name="Mirror Mage",
            description="Reflected power — three loci, repeats allowed.",
            slot_count=3,
            point_names=_loci(3),
            secret_magic_pool=[4, 5, 1, 2, 9],
            attack_magic_pool=[4, 5, 1, 2, 9],
            max_attacks_per_player=8,
            enemy_name="Mirror Mage",
            enemy_archetype="mirror_mage",
            enemy_visual_hint="Mirrored robes that shimmer with duplicate spells.",
            enemy_difficulty="hard",
            base_min_cast_time_seconds=5.0,
            base_max_cast_time_seconds=16.0,
        )
    )
    _register(
        DuelRuleset(
            id="archmage_duel",
            display_name="Archmage Duel",
            description="The full wizard duel — four loci, ten essences.",
            slot_count=CODE_LENGTH,
            point_names=_loci(4),
            secret_magic_pool=list(_ALL_MAGICS),
            attack_magic_pool=list(_ALL_MAGICS),
            max_attacks_per_player=MAX_GUESSES,
            enemy_name="Archmage",
            enemy_archetype="archmage",
            enemy_visual_hint="Full duel rules — every essence, every locus.",
            enemy_difficulty="expert",
            base_min_cast_time_seconds=3.0,
            base_max_cast_time_seconds=10.0,
        )
    )
    _register(
        DuelRuleset(
            id="eightfold_warden",
            display_name="The Eightfold Warden",
            description="Boss duel — all eight loci.",
            slot_count=8,
            point_names=_loci(8),
            secret_magic_pool=list(_ALL_MAGICS),
            attack_magic_pool=list(_ALL_MAGICS),
            max_attacks_per_player=18,
            enemy_name="Eightfold Warden",
            enemy_archetype="eightfold_warden",
            enemy_visual_hint="Eight runes orbit an unstable barrier.",
            enemy_difficulty="expert",
            base_min_cast_time_seconds=2.0,
            base_max_cast_time_seconds=8.0,
            last_stand_min_attacks=1,
            last_stand_seconds=20.0,
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
