from __future__ import annotations

from typing import List, Optional, Tuple

from typing import TYPE_CHECKING

from .constants import CODE_LENGTH, MAX_COLOUR, MIN_COLOUR, NUM_COLOURS

if TYPE_CHECKING:
    from .duel_ruleset import DuelRuleset


class CodeValidationError(ValueError):
    pass


def validate_colour(colour: int) -> None:
    if not isinstance(colour, int) or colour < MIN_COLOUR or colour > MAX_COLOUR:
        raise CodeValidationError(f"colour must be {MIN_COLOUR}-{MAX_COLOUR}, got {colour!r}")


def validate_code(code: List[int]) -> None:
    validate_code_length(code, CODE_LENGTH)


def validate_code_length(code: List[int], length: int) -> None:
    if len(code) != length:
        raise CodeValidationError(f"code must have length {length}, got {len(code)}")
    for i, c in enumerate(code):
        if not isinstance(c, int) or c < MIN_COLOUR or c > MAX_COLOUR:
            raise CodeValidationError(f"colour at index {i} must be {MIN_COLOUR}-{MAX_COLOUR}, got {c!r}")


def validate_colour_in_pool(colour: int, pool: List[int]) -> None:
    validate_colour(colour)
    if colour not in pool:
        raise CodeValidationError(f"colour {colour} not in allowed pool {pool}")


def validate_code_for_ruleset(code: List[int], ruleset: "DuelRuleset", pool: List[int]) -> None:
    validate_code_length(code, ruleset.slot_count)
    for i, c in enumerate(code):
        try:
            validate_colour_in_pool(int(c), pool)
        except CodeValidationError as e:
            raise CodeValidationError(f"colour at index {i}: {e}") from e


def is_valid_code(code: List[int]) -> bool:
    try:
        validate_code(code)
        return True
    except CodeValidationError:
        return False


class SecretCode:
    """A validated 4-peg secret code. Repeated colours allowed."""

    def __init__(self, pegs: List[int]) -> None:
        validate_code(pegs)
        self._pegs = list(pegs)

    @property
    def pegs(self) -> List[int]:
        return list(self._pegs)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretCode):
            return NotImplemented
        return self._pegs == other._pegs

    def __repr__(self) -> str:
        return f"SecretCode({self._pegs})"
