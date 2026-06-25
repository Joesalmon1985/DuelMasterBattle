import pytest

from duel_mastermind import CodeValidationError, score_guess


class TestFeedback:
    def test_all_exact(self):
        assert score_guess([0, 1, 2, 3], [0, 1, 2, 3]) == (4, 0)

    def test_no_match(self):
        assert score_guess([0, 0, 1, 2], [3, 4, 5, 6]) == (0, 0)

    def test_exact_and_colour_only(self):
        assert score_guess([0, 0, 1, 2], [0, 1, 0, 3]) == (1, 2)

    def test_duplicate_secret_guess(self):
        # secret [0,0,1,2], guess [0,0,0,0] -> exact=2, colour_only=0
        assert score_guess([0, 0, 1, 2], [0, 0, 0, 0]) == (2, 0)

    def test_all_same_colour_secret(self):
        assert score_guess([1, 1, 1, 1], [1, 2, 3, 4]) == (1, 0)

    def test_permutation(self):
        assert score_guess([0, 1, 2, 3], [3, 2, 1, 0]) == (0, 4)

    def test_invalid_guess_raises(self):
        with pytest.raises(CodeValidationError):
            score_guess([0, 1, 2, 3], [0, 1, 2])

    def test_one_slot(self):
        assert score_guess([2], [2]) == (1, 0)

    def test_two_slot(self):
        assert score_guess([1, 2], [2, 1]) == (0, 2)
