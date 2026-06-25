import pytest

from duel_mastermind import MAX_GUESSES, SolverBot, score_guess
from duel_mastermind.bot_factory import make_bot
from duel_mastermind.candidate_gen import opening_guess_for_ruleset
from duel_mastermind.encounters import get_encounter
from duel_mastermind.solver_bot import generate_all_codes


REPRESENTATIVE_SECRETS = [
    [0, 1, 2, 3],
    [9, 9, 9, 9],
    [0, 0, 1, 1],
    [3, 7, 3, 7],
    [5, 2, 8, 1],
]


class TestSolverBot:
    def test_archmage_generates_10000_codes(self):
        rs = get_encounter("archmage_duel")
        assert len(generate_all_codes(rs)) == 10_000
        bot = SolverBot(rs)
        assert bot.all_code_count() == 10_000

    def test_candidate_counts_per_encounter(self):
        blue = get_encounter("blue_apprentice")
        assert SolverBot(blue).all_code_count() == 4
        thorn = get_encounter("thorn_adept")
        assert SolverBot(thorn).all_code_count() == 20
        mirror = get_encounter("mirror_mage")
        assert SolverBot(mirror).all_code_count() == 64

    def test_opening_guess_from_pool(self):
        blue = get_encounter("blue_apprentice")
        bot = SolverBot(blue)
        assert bot.make_guess() == opening_guess_for_ruleset(blue)

    def test_filtering_preserves_true_secret(self):
        rs = get_encounter("archmage_duel")
        secret = [2, 5, 8, 1]
        bot = SolverBot(rs)
        opener = bot.make_guess()
        bot.register_feedback(opener, *score_guess(secret, opener))
        assert secret in bot._candidates

    def test_filtering_removes_inconsistent(self):
        rs = get_encounter("archmage_duel")
        secret = [0, 1, 2, 3]
        bot = SolverBot(rs)
        guess = bot.make_guess()
        bot.register_feedback(guess, *score_guess(secret, guess))
        assert [9, 9, 9, 9] not in bot._candidates

    def test_only_legal_guesses(self):
        rs = get_encounter("thorn_adept")
        bot = SolverBot(rs)
        assert bot.is_legal_guess(bot.make_guess())

    def test_stops_on_solve_or_max(self):
        rs = get_encounter("archmage_duel")
        for secret in REPRESENTATIVE_SECRETS:
            bot = SolverBot(rs)
            solved, count, _ = bot.solve_secret(secret)
            assert solved
            assert count <= MAX_GUESSES

    def test_deterministic(self):
        rs = get_encounter("archmage_duel")
        secret = [4, 4, 4, 4]
        b1 = SolverBot(rs)
        b2 = SolverBot(rs)
        s1, c1, g1 = b1.solve_secret(secret)
        s2, c2, g2 = b2.solve_secret(secret)
        assert s1 == s2 and c1 == c2 and g1 == g2


class TestDifficultyBots:
    @pytest.mark.parametrize("encounter_id", ["blue_apprentice", "archmage_duel"])
    def test_makes_legal_guesses(self, encounter_id):
        rs = get_encounter(encounter_id)
        bot = make_bot(rs, seed=42)
        assert bot.is_legal_guess(bot.make_guess())
