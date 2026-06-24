import pytest

from duel_mastermind import (
    CODE_LENGTH,
    MAX_GUESSES,
    NUM_COLOURS,
    CodeValidationError,
    SecretCode,
    is_valid_code,
    score_guess,
    validate_code,
)


class TestCodeValidation:
    def test_valid_code(self):
        validate_code([0, 1, 2, 3])
        assert is_valid_code([9, 9, 9, 9])

    def test_wrong_length_rejected(self):
        with pytest.raises(CodeValidationError):
            validate_code([0, 1, 2])
        with pytest.raises(CodeValidationError):
            validate_code([0, 1, 2, 3, 4])

    def test_out_of_range_rejected(self):
        with pytest.raises(CodeValidationError):
            validate_code([-1, 0, 1, 2])
        with pytest.raises(CodeValidationError):
            validate_code([0, 1, 2, 10])

    def test_duplicate_colours_allowed(self):
        c = SecretCode([0, 0, 1, 1])
        assert c.pegs == [0, 0, 1, 1]

    def test_constants(self):
        assert CODE_LENGTH == 4
        assert NUM_COLOURS == 10
        assert MAX_GUESSES == 12
