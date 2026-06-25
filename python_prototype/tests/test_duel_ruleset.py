import pytest

from duel_mastermind.duel_ruleset import DuelRuleset, RulesetValidationError
from duel_mastermind.encounters import all_encounters, get_encounter
from duel_mastermind.constants import CODE_LENGTH, MAX_GUESSES, NUM_COLOURS


class TestDuelRuleset:
    def test_builtin_encounters_load(self):
        encounters = all_encounters()
        assert len(encounters) == 4
        ids = {e.id for e in encounters}
        assert ids == {"blue_apprentice", "thorn_adept", "mirror_mage", "archmage_duel"}

    def test_archmage_matches_legacy_constants(self):
        rs = get_encounter("archmage_duel")
        assert rs.slot_count == CODE_LENGTH
        assert rs.secret_magic_pool == list(range(NUM_COLOURS))
        assert rs.attack_magic_pool == list(range(NUM_COLOURS))
        assert rs.effective_max_attacks() == MAX_GUESSES
        assert rs.enemy_difficulty == "expert"

    def test_effective_max_attacks_with_modifier(self):
        rs = get_encounter("blue_apprentice")
        rs.player_modifiers = {"extra_attacks": 2}
        assert rs.effective_max_attacks() == 6

    def test_pool_subset_validation_passes_for_builtin(self):
        for enc in all_encounters():
            enc.validate_pools()

    def test_invalid_pool_fails_validation(self):
        with pytest.raises(RulesetValidationError):
            DuelRuleset(
                id="bad",
                display_name="Bad",
                description="",
                slot_count=1,
                point_names=["Shield"],
                secret_magic_pool=[9],
                attack_magic_pool=[0, 1],
                max_attacks_per_player=4,
                enemy_name="X",
                enemy_archetype="x",
                enemy_visual_hint="",
                enemy_difficulty="easy",
            )

    def test_hidden_secret_types_allows_superset(self):
        rs = DuelRuleset(
            id="hidden",
            display_name="Hidden",
            description="",
            slot_count=1,
            point_names=["Shield"],
            secret_magic_pool=[9],
            attack_magic_pool=[0, 1],
            max_attacks_per_player=4,
            enemy_name="X",
            enemy_archetype="x",
            enemy_visual_hint="",
            enemy_difficulty="easy",
            allow_hidden_secret_types=True,
        )
        rs.validate_pools()
