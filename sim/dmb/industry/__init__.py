"""Authoritative industrial capacity simulation."""

from fractions import Fraction
from typing import Any


def fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, dict):
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    return Fraction(str(value))


def fraction_wire(value: Any) -> dict[str, str]:
    exact = fraction(value)
    return {"numerator": str(exact.numerator), "denominator": str(exact.denominator)}
