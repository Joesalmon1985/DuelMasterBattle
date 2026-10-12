"""Python port of the retained Ward Duel's pure rules (godot_project/sim: feedback.gd, game_logic.gd, candidate_gen.gd, auto_cast.gd,
weave_bot.gd, difficulty_profiles.gd), parity-tested against the GDScript (tests/test_ward_parity.py).

Ported: fracture/echo/fade scoring (`score_attack`, `score_guess`), the match result rules (`compute_result`), candidate generation, the
weave-bot deduction policies `random` and `candidate_filter` (bit-for-bit with Godot's RNG), `capped_minimax` (deterministic sample;
Godot shuffles with the global RNG, so only the policy, not the sample, matches) and the three difficulty profiles.
NOT ported: the real-time cast windows, think timers and event queue of `battle_sim.gd` / `realtime_duel_sim.gd`; `WardDuel` below
is the turn-based logical core (each side casts in turn against the other's hidden ward) that the headless environments use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any

from wizard_rts.puzzle.rng import GodotRng


# ---------------------------------------------------------------- feedback.gd

def score_guess(secret: list[int], guess: list[int]) -> tuple[int, int]:
    if len(secret) != len(guess):
        raise ValueError("secret and guess must have equal length")
    exact = 0
    sr: list[int] = []
    gr: list[int] = []
    for s, g in zip(secret, guess):
        if int(s) == int(g):
            exact += 1
        else:
            sr.append(int(s))
            gr.append(int(g))
    counts: dict[int, int] = {}
    for s in sr:
        counts[s] = counts.get(s, 0) + 1
    colour = 0
    for g in gr:
        if counts.get(g, 0) > 0:
            colour += 1
            counts[g] -= 1
    return exact, colour


def target_slot(attack_index: int, ward_size: int) -> int:
    return attack_index % max(ward_size, 1)


def targets_by_ward_slot(attack_size: int, ward_size: int) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in range(ward_size)]
    for j in range(attack_size):
        out[target_slot(j, ward_size)].append(j)
    return out


def score_attack(ward: list[int], attack: list[int]) -> dict[str, Any]:
    ws = len(ward)
    fractured = [False] * ws
    fracture = 0
    non_fracture: list[int] = []
    for j, a in enumerate(attack):
        t = target_slot(j, ws)
        if ws > 0 and int(a) == int(ward[t]):
            fracture += 1
            fractured[t] = True
        else:
            non_fracture.append(int(a))
    counts: dict[int, int] = {}
    for i in range(ws):
        if not fractured[i]:
            counts[int(ward[i])] = counts.get(int(ward[i]), 0) + 1
    echo = 0
    for g in non_fracture:
        if counts.get(g, 0) > 0:
            echo += 1
            counts[g] -= 1
    broken = ws > 0 and all(fractured)
    return {"fracture": fracture, "echo": echo, "fade": len(attack) - fracture - echo, "broken": broken, "targets": targets_by_ward_slot(len(attack), ws)}


# ---------------------------------------------------------------- game_logic.gd

def _best_progress(guesses: list[tuple[int, int]]) -> tuple[int, int]:
    best = (0, 0)
    for exact, colour in guesses:
        if exact > best[0] or (exact == best[0] and colour > best[1]):
            best = (exact, colour)
    return best


def compute_result(human_solved: bool, bot_solved: bool, human_count: int, bot_count: int,
                   human_guesses: list[tuple[int, int]], bot_guesses: list[tuple[int, int]], max_attacks: int = 12) -> dict[str, Any]:
    def res(outcome: str) -> dict[str, Any]:
        return {"outcome": outcome, "human_solved": human_solved, "bot_solved": bot_solved, "human_guesses": human_count, "bot_guesses": bot_count}

    if human_solved and not bot_solved:
        return res("human_win")
    if bot_solved and not human_solved:
        return res("bot_win")
    if human_solved and bot_solved:
        if human_count < bot_count:
            return res("human_win")
        if bot_count < human_count:
            return res("bot_win")
        return res("draw")
    if not human_solved and not bot_solved and human_count >= max_attacks and bot_count >= max_attacks:
        return res("draw")
    hb, bb = _best_progress(human_guesses), _best_progress(bot_guesses)
    if hb > bb:
        return res("human_win")
    if bb > hb:
        return res("bot_win")
    return res("draw")


# ---------------------------------------------------------------- candidate_gen.gd

def generate_codes(pool: list[int], slots: int, allow_repeats: bool) -> list[list[int]]:
    if allow_repeats:
        return [list(c) for c in product(pool, repeat=slots)]
    out: list[list[int]] = []

    def helper(rem_pool: list[int], remaining: int, cur: list[int]) -> None:
        if remaining == 0:
            out.append(list(cur))
            return
        for i, colour in enumerate(rem_pool):
            if colour in cur:
                continue
            helper(rem_pool[:i] + rem_pool[i + 1:], remaining - 1, cur + [colour])

    helper(list(pool), slots, [])
    return out


# ---------------------------------------------------------------- auto_cast.gd

def random_pattern(count: int, pool: list[int], allow_repeats: bool, rng: GodotRng) -> list[int]:
    result: list[int] = []
    for _ in range(count):
        if not pool:
            result.append(0)
        elif allow_repeats:
            result.append(int(pool[rng.randi_range(0, len(pool) - 1)]))
        else:
            avail = [int(e) for e in pool if int(e) not in result]
            result.append(int(avail[rng.randi_range(0, len(avail) - 1)]) if avail else int(pool[rng.randi_range(0, len(pool) - 1)]))
    return result


# ---------------------------------------------------------------- combatant.gd / difficulty_profiles.gd

@dataclass
class Combatant:
    id: str = ""
    kind: str = "wizard"
    weave_size: int = 4
    attack_pool: list[int] = field(default_factory=list)
    ward_size: int = 4
    ward_pool: list[int] = field(default_factory=list)
    allow_repeats: bool = True
    fixed_ward: list[int] = field(default_factory=list)
    max_casts: int = 10
    bot_logic: str = "candidate_filter"
    bot_solver_cap: int = 60
    bot_mistake_rate: float = 0.0
    bot_opening_attack: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.ward_pool:
            self.ward_pool = list(self.attack_pool)


PROFILES = {  # id -> (bot_logic, mistake_rate, solver_cap, think_min, think_max)
    "easy": ("candidate_filter", 0.4, 0, 26.0, 48.0),
    "medium": ("candidate_filter", 0.0, 0, 16.0, 30.0),
    "hard": ("capped_minimax", 0.0, 60, 10.0, 20.0),
}


# ---------------------------------------------------------------- weave_bot.gd

class WeaveBot:
    def __init__(self, me: Combatant, target: Combatant, seed: int = 0, shuffle_seed: int | None = None) -> None:
        self.c = me
        self.target_ward_size = target.ward_size
        self.target_pool = list(target.ward_pool)
        self.target_repeats = target.allow_repeats
        self.rng = GodotRng(seed)
        self.seed = seed
        self.shuffle_rng = GodotRng(seed if shuffle_seed is None else shuffle_seed)
        self.all = generate_codes(self.target_pool, self.target_ward_size, self.target_repeats)
        self.candidates = [list(c) for c in self.all]
        self.guess_count = 0

    def register_feedback(self, attack: list[int], fracture: int, echo: int) -> None:
        kept = [c for c in self.candidates if (lambda r: r["fracture"] == fracture and r["echo"] == echo)(score_attack(c, attack))]
        self.candidates = kept if kept else [list(c) for c in self.all]

    def generate_ward(self) -> list[int]:
        if self.c.fixed_ward:
            return list(self.c.fixed_ward)
        rng = GodotRng(self.seed + 999)
        return random_pattern(self.c.ward_size, self.c.ward_pool, self.c.allow_repeats, rng)

    def is_legal_attack(self, attack: list[int]) -> bool:
        return len(attack) == self.c.weave_size and all(int(a) in self.c.attack_pool for a in attack)

    def _tile(self, ward: list[int]) -> list[int]:
        out = []
        for j in range(self.c.weave_size):
            s = int(ward[j % len(ward)])
            if s not in self.c.attack_pool:
                s = int(self.c.attack_pool[self.rng.randi_range(0, len(self.c.attack_pool) - 1)])
            out.append(s)
        return out

    def _opening(self) -> list[int]:
        pool = self.c.attack_pool
        if len(pool) == 1 or self.c.weave_size == 1:
            return self._tile([int(pool[self.rng.randi_range(0, len(pool) - 1)])])
        a = self.rng.randi_range(0, len(pool) - 1)
        b = (a + 1 + self.rng.randi_range(0, len(pool) - 2)) % len(pool)
        half = (self.c.weave_size + 1) // 2
        return [int(pool[a]) if j < half else int(pool[b]) for j in range(self.c.weave_size)]

    def _random_attack(self) -> list[int]:
        return random_pattern(self.c.weave_size, self.c.attack_pool, True, self.rng)

    def make_guess(self) -> list[int]:
        c = self.c
        if c.bot_logic == "random" or (c.bot_mistake_rate > 0.0 and self._randf() < c.bot_mistake_rate):
            out = self._random_attack()
        elif self.guess_count == 0:
            out = list(c.bot_opening_attack) if c.bot_opening_attack and self.is_legal_attack(c.bot_opening_attack) else self._opening()
        elif len(self.candidates) <= 2 or c.bot_logic != "capped_minimax":
            out = self._tile(self.candidates[self.rng.randi_range(0, len(self.candidates) - 1)])
        else:
            sample = [list(x) for x in self.candidates]
            for i in range(len(sample) - 1, 0, -1):  # a deterministic Fisher-Yates (Godot shuffles with its global RNG)
                j = self.shuffle_rng.randi_range(0, i)
                sample[i], sample[j] = sample[j], sample[i]
            cap = max(2, c.bot_solver_cap)
            sample = sample[:cap]
            best, best_worst = None, 1 << 30
            for cand in sample:
                attack = self._tile(cand)
                parts: dict[int, int] = {}
                for w in self.candidates:
                    r = score_attack(w, attack)
                    k = r["fracture"] * 32 + r["echo"]
                    parts[k] = parts.get(k, 0) + 1
                worst = max(parts.values())
                if best is None or worst < best_worst:
                    best, best_worst = attack, worst
            out = best if best is not None else self._tile(self.candidates[0])
        self.guess_count += 1
        return out

    def _randf(self) -> float:
        return (self.rng.randi() & 0xFFFFFF) / float(1 << 24)  # not bit-identical to Godot's randf(); mistake_rate > 0 is outside the parity set


# ---------------------------------------------------------------- the turn-based core

class WardDuel:
    """Both sides hide a ward and cast weaves at the other's. A turn is one cast by each side. Ends when a ward is broken or casts run out;
    `compute_result` (ported) decides the winner exactly as the Godot rules do."""

    def __init__(self, player: Combatant, enemy: Combatant, seed: int = 42) -> None:
        self.player, self.enemy = player, enemy
        self.rng = GodotRng(seed)
        self.bot = WeaveBot(enemy, player, seed)
        self.enemy_ward = self.bot.generate_ward()
        self.player_ward = random_pattern(player.ward_size, player.ward_pool, player.allow_repeats, GodotRng(seed + 1))
        self.player_history: list[dict[str, Any]] = []
        self.enemy_history: list[dict[str, Any]] = []
        self.player_broke = self.enemy_broke = False
        self.done = False
        self.result: dict[str, Any] | None = None

    def legal_attack(self, attack: list[int]) -> bool:
        return len(attack) == self.player.weave_size and all(int(a) in self.player.attack_pool for a in attack)

    def cast(self, attack: list[int]) -> dict[str, Any]:
        if self.done:
            return {"status": "finished"}
        if not self.legal_attack(attack):
            return {"status": "rejected", "reason": "illegal_attack"}
        r = score_attack(self.enemy_ward, attack)
        self.player_history.append({"attack": list(attack), "fracture": r["fracture"], "echo": r["echo"], "broken": r["broken"]})
        self.player_broke = self.player_broke or r["broken"]
        # the bot's reply (it reads only the feedback it earns, never the player's ward)
        guess = self.bot.make_guess()
        e = score_attack(self.player_ward, guess)
        self.bot.register_feedback(guess, e["fracture"], e["echo"])
        self.enemy_history.append({"attack": guess, "fracture": e["fracture"], "echo": e["echo"], "broken": e["broken"]})
        self.enemy_broke = self.enemy_broke or e["broken"]
        if self.player_broke or self.enemy_broke or len(self.player_history) >= self.player.max_casts:
            self.done = True
            ph = [(h["fracture"], h["echo"]) for h in self.player_history]
            bh = [(h["fracture"], h["echo"]) for h in self.enemy_history]
            self.result = compute_result(self.player_broke, self.enemy_broke, len(ph), len(bh), ph, bh, self.player.max_casts)
        return {"status": "ok", "fracture": r["fracture"], "echo": r["echo"], "fade": r["fade"], "broken": r["broken"], "done": self.done, "result": self.result}

    def public_view(self) -> dict[str, Any]:
        """What the player knows: his own ward and history and the feedback his casts earned. Never the enemy's ward."""
        return {"player_ward": list(self.player_ward), "casts": len(self.player_history), "max_casts": self.player.max_casts,
                "history": [dict(h) for h in self.player_history], "enemy_casts": len(self.enemy_history), "done": self.done, "result": self.result}
