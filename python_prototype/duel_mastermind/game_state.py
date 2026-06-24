from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from .bot import RandomBot
from .code import CodeValidationError, SecretCode, validate_code, validate_colour
from .constants import CODE_LENGTH, MAX_GUESSES
from .feedback import score_guess


class GamePhase(Enum):
    HUMAN_SETUP = auto()
    BOT_GUESSING = auto()
    HUMAN_GUESSING = auto()
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
    """Sequential Human vs Bot: bot attacks human code, then human attacks bot code."""

    def __init__(self, bot_seed: int = 42) -> None:
        self._bot_seed = bot_seed
        self.reset()

    def reset(self, bot_seed: Optional[int] = None) -> None:
        if bot_seed is not None:
            self._bot_seed = bot_seed
        self._bot = RandomBot(self._bot_seed)
        self.phase = GamePhase.HUMAN_SETUP
        self._human_setup: List[Optional[int]] = [None] * CODE_LENGTH
        self._human_secret: Optional[List[int]] = None
        self._bot_secret: Optional[List[int]] = None
        self._bot_guesses: List[GuessRecord] = []
        self._human_guesses: List[GuessRecord] = []
        self._current_human_guess: List[Optional[int]] = [None] * CODE_LENGTH
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
        return MAX_GUESSES - len(self._bot_guesses)

    @property
    def human_guesses_remaining(self) -> int:
        return MAX_GUESSES - len(self._human_guesses)

    def can_lock_human_secret(self) -> bool:
        return self.phase == GamePhase.HUMAN_SETUP and all(p is not None for p in self._human_setup)

    def set_human_secret_peg(self, slot: int, colour: int) -> None:
        if self.phase != GamePhase.HUMAN_SETUP:
            raise GameActionError("not in human setup phase")
        if slot < 0 or slot >= CODE_LENGTH:
            raise GameActionError(f"slot must be 0-{CODE_LENGTH - 1}")
        validate_colour(colour)
        self._human_setup[slot] = colour

    def lock_human_secret(self) -> None:
        if not self.can_lock_human_secret():
            raise GameActionError("all 4 pegs must be set before lock")
        pegs = [p for p in self._human_setup if p is not None]
        self._human_secret = pegs
        self.phase = GamePhase.BOT_GUESSING

    def bot_make_guess(self) -> Optional[GuessRecord]:
        if self.phase != GamePhase.BOT_GUESSING:
            raise GameActionError("not in bot guessing phase")
        if self._bot_solved or len(self._bot_guesses) >= MAX_GUESSES:
            return None
        guess = self._bot.make_guess()
        assert self._human_secret is not None
        exact, colour_only = score_guess(self._human_secret, guess)
        record = GuessRecord(guess=guess, exact=exact, colour_only=colour_only)
        self._bot_guesses.append(record)
        if exact == CODE_LENGTH:
            self._bot_solved = True
            self._finish_bot_guessing()
        elif len(self._bot_guesses) >= MAX_GUESSES:
            self._finish_bot_guessing()
        return record

    def _finish_bot_guessing(self) -> None:
        self._bot_secret = self._bot.generate_code()
        self.phase = GamePhase.HUMAN_GUESSING

    def set_human_guess_peg(self, slot: int, colour: int) -> None:
        if self.phase != GamePhase.HUMAN_GUESSING:
            raise GameActionError("not in human guessing phase")
        if slot < 0 or slot >= CODE_LENGTH:
            raise GameActionError(f"slot must be 0-{CODE_LENGTH - 1}")
        validate_colour(colour)
        self._current_human_guess[slot] = colour

    def can_submit_human_guess(self) -> bool:
        return self.phase == GamePhase.HUMAN_GUESSING and all(p is not None for p in self._current_human_guess)

    def submit_human_guess(self, guess: Optional[List[int]] = None) -> GuessRecord:
        if self.phase != GamePhase.HUMAN_GUESSING:
            raise GameActionError("not in human guessing phase")
        if len(self._human_guesses) >= MAX_GUESSES:
            raise GameActionError("no guesses remaining")
        if guess is None:
            if not self.can_submit_human_guess():
                raise GameActionError("all 4 pegs must be set")
            guess = [p for p in self._current_human_guess if p is not None]
        try:
            validate_code(guess)
        except CodeValidationError as e:
            raise GameActionError(str(e)) from e
        assert self._bot_secret is not None
        exact, colour_only = score_guess(self._bot_secret, guess)
        record = GuessRecord(guess=guess, exact=exact, colour_only=colour_only)
        self._human_guesses.append(record)
        self._current_human_guess = [None] * CODE_LENGTH
        if exact == CODE_LENGTH:
            self._human_solved = True
            self._finish_game()
        elif len(self._human_guesses) >= MAX_GUESSES:
            self._finish_game()
        return record

    def _finish_game(self) -> None:
        self.phase = GamePhase.FINISHED
        self._result = compute_result(
            self._human_solved,
            self._bot_solved,
            len(self._human_guesses),
            len(self._bot_guesses),
            self._human_guesses,
            self._bot_guesses,
        )

    def run_all_bot_guesses(self) -> List[GuessRecord]:
        """Convenience for tests/UI: bot guesses until solved or limit."""
        records = []
        while self.phase == GamePhase.BOT_GUESSING:
            r = self.bot_make_guess()
            if r is None:
                break
            records.append(r)
        return records


def compute_result(
    human_solved: bool,
    bot_solved: bool,
    human_guess_count: int,
    bot_guess_count: int,
    human_guesses: List[GuessRecord],
    bot_guesses: List[GuessRecord],
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
    # Neither solved — tie-break
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
