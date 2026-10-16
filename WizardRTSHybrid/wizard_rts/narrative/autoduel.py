"""A story Ward Duel played on the Python core for a wizard without a screen (an AI seat): the same rules the board runs, the same report shape the
board sends, verified by `duel_lease.resolve` exactly like a human's. Nothing is rigged: the AI's guesses come from the retained candidate-filter
solver with a seed of its own, the enemy's Ward from the lease's seed, and the result is whatever the rules produce."""

from __future__ import annotations

import zlib
from typing import Any

from wizard_rts.duel import ward


def _combatant(spec: dict[str, Any], cid: str) -> ward.Combatant:
    return ward.Combatant(id=cid, weave_size=int(spec["weave_size"]), attack_pool=list(spec["attack_pool"]), ward_size=int(spec["ward_size"]),
                          ward_pool=list(spec["ward_pool"]), allow_repeats=bool(spec.get("allow_repeats", True)), max_casts=int(spec["max_casts"]),
                          bot_logic=str(spec.get("bot_logic", "random")), bot_mistake_rate=float(spec.get("bot_mistake_rate", 0.0)),
                          fixed_ward=[int(x) for x in spec["fixed_ward"]] if spec.get("fixed_ward") else [])


def play_lease(world: Any, rec: dict[str, Any], seed: str, careful: bool = True) -> dict[str, Any]:
    """Play `rec` (a lease record) and return the report `duel_lease.resolve` verifies."""
    enc = rec["encounter"]
    player = _combatant(enc["player_combatant"], "p")
    enemy = _combatant(enc["enemy_combatant"], "e")
    duel = ward.WardDuel(player, enemy, seed=int(rec["bot_seed"]))
    solver = ward.WeaveBot(player, enemy, seed=zlib.crc32(f"{world.seed}|{seed}".encode()) & 0x7FFFFFFF)
    history = []
    while not duel.done:
        attack = solver.make_guess() if careful else [player.attack_pool[0]] * player.weave_size
        r = duel.cast(attack)
        solver.register_feedback(attack, r["fracture"], r["echo"])
        history.append({"pattern": list(attack), "fracture": r["fracture"], "echo": r["echo"], "broke": r["broken"]})
    outcome = {"human_win": "victory", "bot_win": "defeat", "draw": "stalemate"}[duel.result["outcome"]]
    return {"outcome": outcome, "player_casts": len(history), "enemy_casts": len(duel.enemy_history), "history": history, "enemy_ward": list(duel.enemy_ward),
            "player_ward": list(duel.player_ward)}
