from __future__ import annotations

from typing import List, Optional, Tuple

from .constants import CODE_LENGTH, MAX_COLOUR, MIN_COLOUR, NUM_COLOURS


class CodeValidationError(ValueError):
    pass


def validate_colour(colour: int) -> None:
    if not isinstance(colour, int) or colour < MIN_COLOUR or colour > MAX_COLOUR:
        raise CodeValidationError(f"colour must be {MIN_COLOUR}-{MAX_COLOUR}, got {colour!r}")


def validate_code(code: List[int]) -> None:
    if len(code) != CODE_LENGTH:
        raise CodeValidationError(f"code must have length {CODE_LENGTH}, got {len(code)}")
    for i, c in enumerate(code):
        if not isinstance(c, int) or c < MIN_COLOUR or c > MAX_COLOUR:
            raise CodeValidationError(f"colour at index {i} must be {MIN_COLOUR}-{MAX_COLOUR}, got {c!r}")


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
