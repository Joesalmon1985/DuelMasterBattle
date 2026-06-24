import pytest

from duel_mastermind import (
    CODE_LENGTH,
    MAX_GUESSES,
    GameActionError,
    GamePhase,
    GuessRecord,
    RandomBot,
    SequentialDuelGame,
    compute_result,
)


def _setup_human(game: SequentialDuelGame, code: list) -> None:
    for i, c in enumerate(code):
        game.set_human_secret_peg(i, c)
    game.lock_human_secret()


class TestSequentialGame:
    def test_human_setup_and_lock(self):
        g = SequentialDuelGame()
        assert g.phase == GamePhase.HUMAN_SETUP
        assert not g.can_lock_human_secret()
        for i in range(CODE_LENGTH):
            g.set_human_secret_peg(i, i)
        assert g.can_lock_human_secret()
        g.lock_human_secret()
        assert g.phase == GamePhase.BOT_GUESSING

    def test_lock_requires_all_pegs(self):
        g = SequentialDuelGame()
        g.set_human_secret_peg(0, 0)
        with pytest.raises(GameActionError):
            g.lock_human_secret()

    def test_bot_guesses_up_to_12(self):
        g = SequentialDuelGame(bot_seed=1)
        _setup_human(g, [0, 1, 2, 3])
        g.run_all_bot_guesses()
        assert g.phase == GamePhase.HUMAN_GUESSING
        assert len(g.bot_guesses) <= MAX_GUESSES
        assert g._bot_secret is not None

    def test_human_win_on_solve(self):
        g = SequentialDuelGame(bot_seed=99)
        _setup_human(g, [5, 5, 5, 5])
        g.run_all_bot_guesses()
        # Force known bot secret via re-init trick: set bot secret directly for test
        bot = RandomBot(99)
        bot.generate_code()  # consume bot guesses RNG state
        # Instead: patch bot secret
        g._bot_secret = [0, 1, 2, 3]
        g.submit_human_guess([0, 1, 2, 3])
        assert g.phase == GamePhase.FINISHED
        assert g.result.outcome == "human_win"
        assert g.result.human_solved

    def test_12_guess_limit_human(self):
        g = SequentialDuelGame(bot_seed=2)
        _setup_human(g, [0, 0, 0, 0])
        g.run_all_bot_guesses()
        g._bot_secret = [9, 9, 9, 9]
        for _ in range(MAX_GUESSES):
            g.submit_human_guess([1, 1, 1, 1])
        assert g.phase == GamePhase.FINISHED
        assert not g.result.human_solved
        assert len(g.human_guesses) == MAX_GUESSES

    def test_illegal_guess_rejected(self):
        g = SequentialDuelGame()
        _setup_human(g, [0, 1, 2, 3])
        g.run_all_bot_guesses()
        with pytest.raises(GameActionError):
            g.submit_human_guess([0, 1, 2])

    def test_bot_only_legal_guesses(self):
        bot = RandomBot(seed=42)
        for _ in range(100):
            assert bot.is_legal_guess(bot.make_guess())


class TestComputeResult:
    def test_human_only_solves(self):
        r = compute_result(True, False, 3, 5, [], [])
        assert r.outcome == "human_win"

    def test_bot_only_solves(self):
        r = compute_result(False, True, 5, 2, [], [])
        assert r.outcome == "bot_win"

    def test_both_solve_fewer_wins(self):
        r = compute_result(True, True, 2, 5, [], [])
        assert r.outcome == "human_win"
        r2 = compute_result(True, True, 5, 2, [], [])
        assert r2.outcome == "bot_win"

    def test_both_solve_equal_draw(self):
        r = compute_result(True, True, 3, 3, [], [])
        assert r.outcome == "draw"

    def test_neither_solved_tiebreak(self):
        hg = [GuessRecord([0, 1, 2, 3], 2, 1)]
        bg = [GuessRecord([0, 0, 0, 0], 1, 0)]
        r = compute_result(False, False, 1, 1, hg, bg)
        assert r.outcome == "human_win"
