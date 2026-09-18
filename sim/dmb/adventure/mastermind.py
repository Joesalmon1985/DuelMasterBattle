"""C10 Mastermind baseline used by hazard Challenge (single Python owner of duel state).

Audit (R06):
- python_prototype/duel_mastermind: correct exact/colour scoring; pools/cast counts differ from C10.
- godot_project/sim/realtime_duel_sim.gd: live cast windows, not Mastermind code-breaking.
- Decision: port scoring into this module; store secrets/guesses only in Python lease state.
  Godot presents guesses/feedback and never owns the secret or outcome.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

SLOT_COUNT = 4
COLOUR_COUNT = 6  # colours 0..5
MAX_CASTS = 10
COLOUR_NAMES = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]


def score_guess(secret: list[int], guess: list[int]) -> tuple[int, int]:
    """Return (exact, colour_only) after removing exact matches (C10 example)."""
    if len(secret) != len(guess):
        raise ValueError("secret and guess length mismatch")
    exact = 0
    secret_remaining: list[int] = []
    guess_remaining: list[int] = []
    for s, g in zip(secret, guess):
        if int(s) == int(g):
            exact += 1
        else:
            secret_remaining.append(int(s))
            guess_remaining.append(int(g))
    counts = Counter(secret_remaining)
    colour_only = 0
    for g in guess_remaining:
        if counts.get(g, 0) > 0:
            colour_only += 1
            counts[g] -= 1
    return exact, colour_only


def validate_guess(guess: list[Any]) -> list[int] | None:
    if not isinstance(guess, list) or len(guess) != SLOT_COUNT:
        return None
    out: list[int] = []
    for item in guess:
        try:
            colour = int(item)
        except (TypeError, ValueError):
            return None
        if colour < 0 or colour >= COLOUR_COUNT:
            return None
        out.append(colour)
    return out


class MastermindDuel:
    """Authoritative Mastermind session stored on a hazard_duel lease."""

    @staticmethod
    def attach(duel: dict[str, Any], *, rng: random.Random | None = None) -> dict[str, Any]:
        rng = rng or random.Random()
        secret = [rng.randrange(COLOUR_COUNT) for _ in range(SLOT_COUNT)]
        duel["mastermind"] = {
            "slot_count": SLOT_COUNT,
            "colour_count": COLOUR_COUNT,
            "max_casts": MAX_CASTS,
            "secret": secret,
            "guesses": [],
            "casts_used": 0,
            "colour_names": list(COLOUR_NAMES),
        }
        duel["ruleset"] = "c10_mastermind_baseline"
        duel["playable"] = True
        return duel

    @staticmethod
    def public_view(duel: dict[str, Any]) -> dict[str, Any]:
        mm = duel.get("mastermind") or {}
        return {
            "duel_id": duel.get("id"),
            "cube_id": duel.get("cube_id"),
            "hex_id": duel.get("hex_id"),
            "slot_count": int(mm.get("slot_count", SLOT_COUNT)),
            "colour_count": int(mm.get("colour_count", COLOUR_COUNT)),
            "max_casts": int(mm.get("max_casts", MAX_CASTS)),
            "casts_used": int(mm.get("casts_used", 0)),
            "guesses": list(mm.get("guesses") or []),
            "colour_names": list(mm.get("colour_names") or COLOUR_NAMES),
            "ruleset": duel.get("ruleset"),
        }

    @staticmethod
    def submit_guess(duel: dict[str, Any], guess_raw: list[Any]) -> dict[str, Any]:
        if duel.get("resolved"):
            return {"status": "already_resolved"}
        mm = duel.get("mastermind")
        if not isinstance(mm, dict):
            return {"status": "rejected", "reason": "no_mastermind"}
        guess = validate_guess(guess_raw)
        if guess is None:
            return {"status": "rejected", "reason": "invalid_guess"}
        casts = int(mm.get("casts_used", 0))
        if casts >= int(mm.get("max_casts", MAX_CASTS)):
            return {"status": "exhausted", "outcome": "draw"}
        secret = [int(x) for x in mm.get("secret") or []]
        exact, colour_only = score_guess(secret, guess)
        casts += 1
        mm["casts_used"] = casts
        entry = {
            "guess": guess,
            "exact": exact,
            "colour_only": colour_only,
            "cast": casts,
        }
        mm.setdefault("guesses", []).append(entry)
        if exact == int(mm.get("slot_count", SLOT_COUNT)):
            return {
                "status": "solved",
                "outcome": "success",
                "feedback": entry,
                "public": MastermindDuel.public_view(duel),
            }
        if casts >= int(mm.get("max_casts", MAX_CASTS)):
            return {
                "status": "exhausted",
                "outcome": "draw",
                "feedback": entry,
                "public": MastermindDuel.public_view(duel),
            }
        return {
            "status": "continue",
            "feedback": entry,
            "public": MastermindDuel.public_view(duel),
        }
