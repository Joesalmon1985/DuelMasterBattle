from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from .bot_factory import make_bot
from .code import CodeValidationError, validate_code_for_ruleset, validate_colour_in_pool
from .constants import CODE_LENGTH, MAX_GUESSES
from .duel_ruleset import DuelRuleset
from .encounters import default_encounter
from .feedback import score_guess


class GamePhase(Enum):
    HUMAN_SETUP = auto()
    HUMAN_TURN = auto()
    BOT_TURN = auto()
    FINISHED = auto()


class GameActionError(ValueError):
    pass


@dataclass
class GuessRecord:
    guess: List[int]
    exact: int
    colour_only: int

    def to_dict(self) -> Dict:
        return {"guess": self.guess, "exact": self.exact, "colour_only": self.colour_only}


@dataclass
class GameResult:
    outcome: str  # "human_win" | "bot_win" | "draw"
    human_solved: bool
    bot_solved: bool
    human_guess_count: int
    bot_guess_count: int
    message: str


class SequentialDuelGame:
    """Alternating Human vs Bot: one attack per turn, human goes first."""

    def __init__(self, ruleset: Optional[DuelRuleset] = None, bot_seed: int = 42) -> None:
        self._ruleset = ruleset or default_encounter()
        self._bot_seed = bot_seed
        self.reset()

    def get_ruleset(self) -> DuelRuleset:
        return self._ruleset

    def reset(self, bot_seed: Optional[int] = None, ruleset: Optional[DuelRuleset] = None) -> None:
        if bot_seed is not None:
            self._bot_seed = bot_seed
        if ruleset is not None:
            self._ruleset = ruleset
        self._bot = make_bot(self._ruleset, self._bot_seed)
        n = self._ruleset.slot_count
        self.phase = GamePhase.HUMAN_SETUP
        self._human_setup: List[Optional[int]] = [None] * n
        self._human_secret: Optional[List[int]] = None
        self._bot_secret: Optional[List[int]] = None
        self._bot_guesses: List[GuessRecord] = []
        self._human_guesses: List[GuessRecord] = []
        self._current_human_guess: List[Optional[int]] = [None] * n
        self._bot_solved = False
        self._human_solved = False
        self._result: Optional[GameResult] = None

    @property
    def human_setup_pegs(self) -> List[Optional[int]]:
        return list(self._human_setup)

    @property
    def current_human_guess(self) -> List[Optional[int]]:
        return list(self._current_human_guess)

    @property
    def bot_guesses(self) -> List[GuessRecord]:
        return list(self._bot_guesses)

    @property
    def human_guesses(self) -> List[GuessRecord]:
        return list(self._human_guesses)

    @property
    def result(self) -> Optional[GameResult]:
        return self._result

    @property
    def bot_guesses_remaining(self) -> int:
        return self._ruleset.effective_max_attacks() - len(self._bot_guesses)

    @property
    def human_guesses_remaining(self) -> int:
        return self._ruleset.effective_max_attacks() - len(self._human_guesses)

    def can_lock_human_secret(self) -> bool:
        return self.phase == GamePhase.HUMAN_SETUP and all(p is not None for p in self._human_setup)

    def set_human_secret_peg(self, slot: int, colour: int) -> None:
        if self.phase != GamePhase.HUMAN_SETUP:
            raise GameActionError("not in human setup phase")
        n = self._ruleset.slot_count
        if slot < 0 or slot >= n:
            raise GameActionError(f"slot must be 0-{n - 1}")
        try:
            validate_colour_in_pool(colour, self._ruleset.secret_magic_pool)
        except CodeValidationError as e:
            raise GameActionError(str(e)) from e
        self._human_setup[slot] = colour

    def lock_human_secret(self) -> None:
        if not self.can_lock_human_secret():
            raise GameActionError("all pegs must be set before lock")
        pegs = [p for p in self._human_setup if p is not None]
        try:
            validate_code_for_ruleset(pegs, self._ruleset, self._ruleset.secret_magic_pool)
        except CodeValidationError as e:
            raise GameActionError(str(e)) from e
        self._human_secret = pegs
        self._bot_secret = self._bot.generate_code()
        self.phase = GamePhase.HUMAN_TURN

    def bot_make_guess(self) -> Optional[GuessRecord]:
        if self.phase != GamePhase.BOT_TURN:
            raise GameActionError("not in bot turn")
        max_attacks = self._ruleset.effective_max_attacks()
        if self._bot_solved or len(self._bot_guesses) >= max_attacks:
            return None
        guess = self._bot.make_guess()
        assert self._human_secret is not None
        exact, colour_only = score_guess(self._human_secret, guess)
        record = GuessRecord(guess=guess, exact=exact, colour_only=colour_only)
        self._bot_guesses.append(record)
        if hasattr(self._bot, "register_feedback"):
            self._bot.register_feedback(guess, exact, colour_only)
        if self._ruleset.is_solved(exact):
            self._bot_solved = True
            self._finish_game()
        elif self._both_exhausted():
            self._finish_game()
        else:
            self.phase = GamePhase.HUMAN_TURN
        return record

    def set_human_guess_peg(self, slot: int, colour: int) -> None:
        if self.phase != GamePhase.HUMAN_TURN:
            raise GameActionError("not in human turn")
        n = self._ruleset.slot_count
        if slot < 0 or slot >= n:
            raise GameActionError(f"slot must be 0-{n - 1}")
        try:
            validate_colour_in_pool(colour, self._ruleset.attack_magic_pool)
        except CodeValidationError as e:
            raise GameActionError(str(e)) from e
        self._current_human_guess[slot] = colour

    def can_submit_human_guess(self) -> bool:
        return self.phase == GamePhase.HUMAN_TURN and all(p is not None for p in self._current_human_guess)

    def submit_human_guess(self, guess: Optional[List[int]] = None) -> GuessRecord:
        if self.phase != GamePhase.HUMAN_TURN:
            raise GameActionError("not in human turn")
        max_attacks = self._ruleset.effective_max_attacks()
        if len(self._human_guesses) >= max_attacks:
            raise GameActionError("no guesses remaining")
        if guess is None:
            if not self.can_submit_human_guess():
                raise GameActionError("all pegs must be set")
            guess = [p for p in self._current_human_guess if p is not None]
        try:
            validate_code_for_ruleset(guess, self._ruleset, self._ruleset.attack_magic_pool)
        except CodeValidationError as e:
            raise GameActionError(str(e)) from e
        assert self._bot_secret is not None
        exact, colour_only = score_guess(self._bot_secret, guess)
        record = GuessRecord(guess=guess, exact=exact, colour_only=colour_only)
        self._human_guesses.append(record)
        n = self._ruleset.slot_count
        self._current_human_guess = [None] * n
        if self._ruleset.is_solved(exact):
            self._human_solved = True
            self._finish_game()
        elif self._both_exhausted():
            self._finish_game()
        else:
            self.phase = GamePhase.BOT_TURN
        return record

    def _both_exhausted(self) -> bool:
        max_attacks = self._ruleset.effective_max_attacks()
        return (
            not self._human_solved
            and not self._bot_solved
            and len(self._human_guesses) >= max_attacks
            and len(self._bot_guesses) >= max_attacks
        )

    def _finish_game(self) -> None:
        self.phase = GamePhase.FINISHED
        self._result = compute_result(
            self._human_solved,
            self._bot_solved,
            len(self._human_guesses),
            len(self._bot_guesses),
            self._human_guesses,
            self._bot_guesses,
            self._ruleset.effective_max_attacks(),
        )


def compute_result(
    human_solved: bool,
    bot_solved: bool,
    human_guess_count: int,
    bot_guess_count: int,
    human_guesses: List[GuessRecord],
    bot_guesses: List[GuessRecord],
    max_attacks: int = MAX_GUESSES,
) -> GameResult:
    if human_solved and not bot_solved:
        return GameResult("human_win", True, False, human_guess_count, bot_guess_count,
                          f"You solved the bot's code in {human_guess_count} guesses!")
    if bot_solved and not human_solved:
        return GameResult("bot_win", False, True, human_guess_count, bot_guess_count,
                          f"Bot solved your code in {bot_guess_count} guesses!")
    if human_solved and bot_solved:
        if human_guess_count < bot_guess_count:
            return GameResult("human_win", True, True, human_guess_count, bot_guess_count,
                              f"Both solved! You used fewer guesses ({human_guess_count} vs {bot_guess_count}).")
        if bot_guess_count < human_guess_count:
            return GameResult("bot_win", True, True, human_guess_count, bot_guess_count,
                              f"Both solved! Bot used fewer guesses ({bot_guess_count} vs {human_guess_count}).")
        return GameResult("draw", True, True, human_guess_count, bot_guess_count,
                          f"Both solved in {human_guess_count} guesses — draw!")
    if (
        not human_solved
        and not bot_solved
        and human_guess_count >= max_attacks
        and bot_guess_count >= max_attacks
    ):
        return GameResult(
            "draw",
            False,
            False,
            human_guess_count,
            bot_guess_count,
            f"Neither solved after {max_attacks} attacks each — draw!",
        )
    h_best = _best_progress(human_guesses)
    b_best = _best_progress(bot_guesses)
    if h_best > b_best:
        return GameResult("human_win", False, False, human_guess_count, bot_guess_count,
                          "Neither solved. You had better progress — you win!")
    if b_best > h_best:
        return GameResult("bot_win", False, False, human_guess_count, bot_guess_count,
                          "Neither solved. Bot had better progress — bot wins!")
    return GameResult("draw", False, False, human_guess_count, bot_guess_count,
                      "Neither solved. Draw!")


def _best_progress(guesses: List[GuessRecord]) -> Tuple[int, int]:
    if not guesses:
        return (0, 0)
    return max((g.exact, g.colour_only) for g in guesses)
