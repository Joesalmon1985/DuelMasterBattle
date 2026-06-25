import pytest

from duel_mastermind import (
    CODE_LENGTH,
    MAX_GUESSES,
    GameActionError,
    GamePhase,
    GuessRecord,
    RandomBot,
    SequentialDuelGame,
    SolverBot,
    compute_result,
    score_guess,
)
from duel_mastermind.encounters import get_encounter


def _setup_human(game: SequentialDuelGame, code: list) -> None:
    for i, c in enumerate(code):
        game.set_human_secret_peg(i, c)
    game.lock_human_secret()


class TestAlternatingGame:
    def test_human_setup_and_lock(self):
        g = SequentialDuelGame()
        assert g.phase == GamePhase.HUMAN_SETUP
        assert not g.can_lock_human_secret()
        for i in range(CODE_LENGTH):
            g.set_human_secret_peg(i, i)
        assert g.can_lock_human_secret()
        g.lock_human_secret()
        assert g.phase == GamePhase.HUMAN_TURN
        assert g._human_secret is not None
        assert g._bot_secret is not None

    def test_lock_requires_all_pegs(self):
        g = SequentialDuelGame()
        g.set_human_secret_peg(0, 0)
        with pytest.raises(GameActionError):
            g.lock_human_secret()

    def test_human_attack_records_feedback(self):
        g = SequentialDuelGame(bot_seed=1)
        _setup_human(g, [0, 1, 2, 3])
        g.submit_human_guess([1, 1, 1, 1])
        assert len(g.human_guesses) == 1
        assert g.human_guesses[0].exact >= 0

    def test_human_then_bot_turn(self):
        g = SequentialDuelGame(bot_seed=1)
        _setup_human(g, [0, 1, 2, 3])
        g.submit_human_guess([1, 1, 1, 1])
        assert g.phase == GamePhase.BOT_TURN
        g.bot_make_guess()
        assert g.phase == GamePhase.HUMAN_TURN
        assert len(g.bot_guesses) == 1

    def test_one_bot_guess_per_turn(self):
        g = SequentialDuelGame(bot_seed=5)
        _setup_human(g, [0, 1, 2, 3])
        g.submit_human_guess([1, 1, 1, 1])
        g.bot_make_guess()
        assert len(g.bot_guesses) == 1
        g.submit_human_guess([2, 2, 2, 2])
        g.bot_make_guess()
        assert len(g.bot_guesses) == 2

    def test_human_win_immediate(self):
        g = SequentialDuelGame(bot_seed=99)
        _setup_human(g, [5, 5, 5, 5])
        g._bot_secret = [0, 1, 2, 3]
        g.submit_human_guess([0, 1, 2, 3])
        assert g.phase == GamePhase.FINISHED
        assert g.result.outcome == "human_win"
        assert g.result.human_solved

    def test_bot_win_immediate(self):
        rs = get_encounter("archmage_duel")
        g = SequentialDuelGame(rs, bot_seed=42)
        _setup_human(g, [0, 0, 1, 1])
        g.submit_human_guess([9, 9, 9, 9])
        assert g.phase == GamePhase.BOT_TURN
        g.bot_make_guess()
        assert g.phase == GamePhase.FINISHED
        assert g.result.bot_solved

    def test_draw_at_12_each(self):
        rs = get_encounter("archmage_duel")
        g = SequentialDuelGame(rs, bot_seed=2)
        g._bot = RandomBot(rs, 2)
        _setup_human(g, [0, 0, 0, 0])
        g._bot_secret = [9, 9, 9, 9]
        miss = [1, 1, 1, 1]
        safety = 0
        while g.phase != GamePhase.FINISHED and safety < 30:
            if g.phase == GamePhase.HUMAN_TURN:
                g.submit_human_guess(miss)
            elif g.phase == GamePhase.BOT_TURN:
                g.bot_make_guess()
            safety += 1
        assert g.phase == GamePhase.FINISHED
        assert not g.result.human_solved
        assert not g.result.bot_solved
        assert g.result.outcome == "draw"
        assert len(g.human_guesses) == MAX_GUESSES
        assert len(g.bot_guesses) == MAX_GUESSES

    def test_blue_apprentice_one_slot_flow(self):
        rs = get_encounter("blue_apprentice")
        g = SequentialDuelGame(rs, bot_seed=3)
        g._bot = SolverBot(rs)  # deterministic opening [0]
        _setup_human(g, [1])
        g.submit_human_guess([0])
        assert g.phase == GamePhase.BOT_TURN
        g.bot_make_guess()
        assert g.phase == GamePhase.HUMAN_TURN

    def test_bot_memory_persists(self):
        rs = get_encounter("archmage_duel")
        g = SequentialDuelGame(rs, bot_seed=7)
        _setup_human(g, [2, 5, 8, 1])
        g.submit_human_guess([0, 0, 0, 0])
        assert g.phase == GamePhase.BOT_TURN
        bot = g._bot
        assert isinstance(bot, SolverBot)
        count_before = bot.candidate_count
        g.bot_make_guess()
        count_after = bot.candidate_count
        assert count_after < count_before

    def test_illegal_guess_rejected(self):
        g = SequentialDuelGame()
        _setup_human(g, [0, 1, 2, 3])
        with pytest.raises(GameActionError):
            g.submit_human_guess([0, 1, 2])
        assert len(g.human_guesses) == 0
        assert g.phase == GamePhase.HUMAN_TURN

    def test_bot_only_legal_guesses(self):
        rs = get_encounter("blue_apprentice")
        bot = RandomBot(rs, seed=42)
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

    def test_both_exhausted_is_draw(self):
        r = compute_result(False, False, MAX_GUESSES, MAX_GUESSES, [], [], MAX_GUESSES)
        assert r.outcome == "draw"
        assert str(MAX_GUESSES) in r.message

    def test_neither_solved_tiebreak(self):
        hg = [GuessRecord([0, 1, 2, 3], 2, 1)]
        bg = [GuessRecord([0, 0, 0, 0], 1, 0)]
        r = compute_result(False, False, 1, 1, hg, bg)
        assert r.outcome == "human_win"
