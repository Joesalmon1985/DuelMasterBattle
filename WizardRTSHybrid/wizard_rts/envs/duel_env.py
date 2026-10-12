"""Mastermind duel environments on the canonical rules (legacy `sim.dmb.adventure.mastermind` scoring) and the ported Ward Duel.

`MastermindEnv` is the code-breaking duel the story's warden uses (and the hazard-baseline duel). It accepts other slot/colour/cast
configurations than the game's 4/6/10 by reusing the canonical `score_guess`; with the canonical configuration it reproduces
`MastermindDuel.submit_guess` exactly (tests/test_duel_env.py parity test). The secret is never in an observation.

Secret policies (the opponent): `random` (uniform), `rule_based` (the patterned codes a rival favours: repeats, runs, palindromes) and
`adversarial` (the code is only fixed by consistency: after every guess it answers with the feedback that keeps the most candidates
alive, so it is the hardest legal opponent; its answers are always consistent with some secret, so no impossible state arises).

`WardDuelEnv` plays the two-sided Ward Duel core (ported fracture/echo scoring, weave bot) from the player's side.
"""

from __future__ import annotations

import random
from collections import Counter
from itertools import product
from typing import Any

import numpy as np

from sim.dmb.adventure.mastermind import score_guess

from wizard_rts.duel import ward as W
from wizard_rts.envs import Env


class MastermindEnv(Env):
    name = "mastermind"

    def __init__(self, slots: int = 4, colours: int = 6, max_casts: int = 10, opponent: str = "random", step_cost: float = 0.02) -> None:
        super().__init__()
        self.slots, self.colours, self.max_casts, self.opponent, self.step_cost = slots, colours, max_casts, opponent, step_cost
        self.max_steps = max_casts + 2
        self.secret: list[int] = []
        self.history: list[dict[str, Any]] = []
        self._cands: list[tuple[int, ...]] = []

    # ---- opponent
    def _pick_secret(self, rng: random.Random) -> list[int]:
        if self.opponent == "random":
            return [rng.randrange(self.colours) for _ in range(self.slots)]
        if self.opponent == "rule_based":
            kind = rng.choice(["repeat", "run", "palindrome", "pair"])
            a, b = rng.randrange(self.colours), rng.randrange(self.colours)
            if kind == "repeat":
                return [a] * self.slots
            if kind == "run":
                return [(a + i) % self.colours for i in range(self.slots)]
            if kind == "palindrome":
                half = [rng.randrange(self.colours) for _ in range((self.slots + 1) // 2)]
                return (half + half[::-1][self.slots % 2:])[: self.slots]
            return [a if i % 2 == 0 else b for i in range(self.slots)]
        if self.opponent == "adversarial":
            return []  # decided by consistency as the game goes on
        raise ValueError(self.opponent)

    def _reset(self, **scenario: Any) -> None:
        rng = random.Random(self.seed)
        self.secret = self._pick_secret(rng)
        self.history = []
        self._cands = list(product(range(self.colours), repeat=self.slots)) if self.opponent == "adversarial" else []

    # ---- rules
    def is_legal(self, action: Any) -> bool:
        try:
            return len(action) == self.slots and all(0 <= int(c) < self.colours for c in action) and len(self.history) < self.max_casts
        except (TypeError, ValueError):
            return False

    def _feedback(self, guess: list[int]) -> tuple[int, int]:
        if self.opponent != "adversarial":
            return score_guess(self.secret, guess)
        buckets: dict[tuple[int, int], list[tuple[int, ...]]] = {}
        for c in self._cands:
            buckets.setdefault(score_guess(list(c), guess), []).append(c)
        # the largest surviving set; the full-match answer is only given when it is the only candidate left (a forced solve)
        win = (self.slots, 0)
        key = max((k for k in buckets if k != win or len(self._cands) == 1), key=lambda k: (len(buckets[k]), k))
        self._cands = buckets[key]
        if len(self._cands) == 1 or key == win:
            self.secret = list(self._cands[0])
        return key

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        guess = [int(c) for c in action]
        exact, colour = self._feedback(guess)
        n = len(self.history) + 1
        self.history.append({"guess": guess, "exact": exact, "colour_only": colour, "cast": n})
        if exact == self.slots:
            self.done, self.reason = True, "solved"
            return 1.0 - self.step_cost * n, {"outcome": "success", "casts": n}
        if n >= self.max_casts:
            self.done, self.reason = True, "exhausted"
            return -0.2, {"outcome": "draw", "casts": n}
        return -self.step_cost, {}

    def observe(self) -> dict[str, Any]:
        return {"slots": self.slots, "colours": self.colours, "max_casts": self.max_casts, "casts_used": len(self.history),
                "history": [dict(h) for h in self.history]}  # never the secret

    def legal_actions(self) -> list[Any]:
        return [list(c) for c in product(range(self.colours), repeat=self.slots)] if not self.done else []

    def state(self) -> Any:
        return {"seed": self.seed, "history": self.history, "done": self.done, "reason": self.reason, "opponent": self.opponent}

    # ---- diagnostics
    def check_invariants(self) -> list[str]:
        """Impossible states: feedback inconsistent with some secret, out-of-range counts, an overrun of the cast limit."""
        problems = []
        if len(self.history) > self.max_casts:
            problems.append("cast_limit_exceeded")
        for h in self.history:
            if h["exact"] < 0 or h["colour_only"] < 0 or h["exact"] + h["colour_only"] > self.slots:
                problems.append("feedback_out_of_range:%d" % h["cast"])
        if self.opponent != "adversarial" and self.secret:
            for h in self.history:
                if score_guess(self.secret, h["guess"]) != (h["exact"], h["colour_only"]):
                    problems.append("feedback_wrong:%d" % h["cast"])
        else:
            from wizard_rts.mastermind_solvers import all_codes, consistent

            hist = [(h["guess"], h["exact"], h["colour_only"]) for h in self.history]
            if hist and not consistent(all_codes(self.slots, self.colours), hist):
                problems.append("no_secret_is_consistent_with_the_feedback")
        return problems

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        """Fixed-size vector for a network: for each of the cast slots, a one-hot guess and its two feedback counts."""
        obs = obs or self.observe()
        per = self.slots * self.colours + 2
        v = np.zeros(self.max_casts * per + 1)
        for i, h in enumerate(obs["history"][: self.max_casts]):
            base = i * per
            for s, c in enumerate(h["guess"]):
                v[base + s * self.colours + c] = 1.0
            v[base + self.slots * self.colours] = h["exact"] / self.slots
            v[base + self.slots * self.colours + 1] = h["colour_only"] / self.slots
        v[-1] = len(obs["history"]) / self.max_casts
        return v


class WardDuelEnv(Env):
    name = "ward_duel"

    def __init__(self, pool: list[int] | None = None, slots: int = 4, weave: int = 4, max_casts: int = 10, enemy_logic: str = "candidate_filter") -> None:
        super().__init__()
        self.pool = list(pool or [0, 1, 3, 4, 6, 9])
        self.slots, self.weave, self.max_casts, self.enemy_logic = slots, weave, max_casts, enemy_logic
        self.max_steps = max_casts + 1
        self.duel: W.WardDuel | None = None

    def _reset(self, **scenario: Any) -> None:
        p = W.Combatant(id="p", kind="player", weave_size=self.weave, attack_pool=self.pool, ward_size=self.slots, ward_pool=self.pool, max_casts=self.max_casts)
        e = W.Combatant(id="e", weave_size=self.weave, attack_pool=self.pool, ward_size=self.slots, ward_pool=self.pool, max_casts=self.max_casts, bot_logic=self.enemy_logic)
        self.duel = W.WardDuel(p, e, seed=self.seed)

    def is_legal(self, action: Any) -> bool:
        return self.duel is not None and self.duel.legal_attack([int(a) for a in action]) and not self.duel.done

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        r = self.duel.cast([int(a) for a in action])
        if r["done"]:
            self.done, self.reason = True, "finished"
            o = r["result"]["outcome"]
            return {"human_win": 1.0, "bot_win": -1.0, "draw": 0.0}[o], {"outcome": o}
        return -0.01, {"fracture": r["fracture"], "echo": r["echo"]}

    def observe(self) -> dict[str, Any]:
        return self.duel.public_view()

    def legal_actions(self) -> list[Any]:
        return [list(a) for a in product(self.pool, repeat=self.weave)] if not self.done else []

    def state(self) -> Any:
        d = self.duel
        return {"seed": self.seed, "ph": d.player_history, "eh": d.enemy_history, "done": d.done}
