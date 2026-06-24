import pytest

from duel_mastermind import MAX_GUESSES, OPENING_GUESS, SolverBot, generate_all_codes, score_guess
from duel_mastermind.bot_factory import make_bot


REPRESENTATIVE_SECRETS = [
    [0, 1, 2, 3],
    [9, 9, 9, 9],
    [0, 0, 1, 1],
    [3, 7, 3, 7],
    [5, 2, 8, 1],
]


class TestSolverBot:
    def test_generates_10000_codes(self):
        assert len(generate_all_codes()) == 10_000
        assert SolverBot.all_code_count() == 10_000

    def test_opening_guess(self):
        bot = SolverBot()
        assert bot.make_guess() == OPENING_GUESS

    def test_filtering_preserves_true_secret(self):
        secret = [2, 5, 8, 1]
        bot = SolverBot()
        bot.make_guess()
        bot.register_feedback(OPENING_GUESS, *score_guess(secret, OPENING_GUESS))
        assert secret in bot._candidates

    def test_filtering_removes_inconsistent(self):
        secret = [0, 1, 2, 3]
        bot = SolverBot()
        guess = bot.make_guess()
        bot.register_feedback(guess, *score_guess(secret, guess))
        assert [9, 9, 9, 9] not in bot._candidates

    def test_only_legal_guesses(self):
        bot = SolverBot()
        for _ in range(20):
            assert bot.is_legal_guess(bot.make_guess())

    def test_stops_on_solve_or_12(self):
        for secret in REPRESENTATIVE_SECRETS:
            bot = SolverBot()
            solved, count, _ = bot.solve_secret(secret)
            assert solved
            assert count <= MAX_GUESSES

    def test_deterministic(self):
        secret = [4, 4, 4, 4]
        b1 = SolverBot()
        b2 = SolverBot()
        s1, c1, g1 = b1.solve_secret(secret)
        s2, c2, g2 = b2.solve_secret(secret)
        assert s1 == s2 and c1 == c2 and g1 == g2


class TestDifficultyBots:
    @pytest.mark.parametrize("level", ["easy", "normal", "hard", "expert"])
    def test_makes_legal_guesses(self, level):
        bot = make_bot(level, seed=42)
        for _ in range(10):
            assert bot.is_legal_guess(bot.make_guess())
