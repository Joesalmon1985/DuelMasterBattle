import pytest

from duel_mastermind import score_guess
from duel_mastermind.code import CodeValidationError, validate_code_for_ruleset
from duel_mastermind.encounters import get_encounter


class TestVariableSlotFeedback:
    @pytest.mark.parametrize(
        "secret,guess,expected",
        [
            ([1], [1], (1, 0)),
            ([1], [2], (0, 0)),
            ([1, 2], [2, 1], (0, 2)),
            ([0, 1, 2, 3], [0, 1, 2, 3], (4, 0)),
        ],
    )
    def test_score_guess_variable_lengths(self, secret, guess, expected):
        assert score_guess(secret, guess) == expected

    def test_mismatched_lengths_rejected(self):
        with pytest.raises(CodeValidationError):
            score_guess([1, 2], [1])


class TestRulesetCodeValidation:
    def test_secret_pool_validation(self):
        rs = get_encounter("blue_apprentice")
        validate_code_for_ruleset([1], rs, rs.secret_magic_pool)
        with pytest.raises(CodeValidationError):
            validate_code_for_ruleset([0], rs, rs.secret_magic_pool)

    def test_attack_pool_validation(self):
        rs = get_encounter("blue_apprentice")
        validate_code_for_ruleset([0], rs, rs.attack_magic_pool)
        with pytest.raises(CodeValidationError):
            validate_code_for_ruleset([5], rs, rs.attack_magic_pool)

    def test_wrong_slot_count(self):
        rs = get_encounter("thorn_adept")
        with pytest.raises(CodeValidationError):
            validate_code_for_ruleset([0], rs, rs.attack_magic_pool)
