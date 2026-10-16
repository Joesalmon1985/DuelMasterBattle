"""The Trial's monsters and rivals as Ward Duel opponents: the legacy bestiary (`data/trial/legacy_bestiary.json`) translated to Wizard World's
retained three-by-three duel. The legacy colours map one to one (0 Flame/Fire, 1 Frost/Water, 3 Stone, 6 Vine, 4 Light, 5 Shadow). A creature's Ward
is drawn from the colours the apprentice can cast among the creature's own (a Ward nobody can break is not a duel), its bot logic, solver cap and
mistake rate are the legacy's, and the cast allowances make the fight brief: an enemy of 6 casts against an apprentice's 8 (10 for the bosses).
Which encounters are lethal is the Trial's rule (`LETHAL`), not the bestiary's: the Giant Fly lets you escape (the book does), a Trialmastiff or a
Cave Troll does not."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data" / "trial" / "legacy_bestiary.json"
LETHAL = {"guard_dog", "cave_troll", "flying_guardian", "boa_constrictor", "throm_duel", "mirror_demon", "bloodbeast", "rock_grub", "trog_champion", "manticore", "poison_ivy"}
ESCAPE = {"giant_fly"}  # a lost fight: wounded, and the creature stays
BOSS = {"bloodbeast", "manticore", "throm_duel"}


@lru_cache(maxsize=1)
def bestiary() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))["opponents"]


def spec(enemy_id: str, player_pool: list[int]) -> dict[str, Any]:
    """An opponent spec in the shape `duel_lease.begin(spec=...)` takes."""
    b = bestiary()[enemy_id]
    pool = [int(c) for c in b.get("ward_pool", []) if int(c) in player_pool] or list(player_pool)
    out = {"display_name": str(b.get("display_name", enemy_id)), "tier": "duel.wizard_3x3", "bot_logic": str(b.get("bot_logic", "candidate_filter")),
           "bot_solver_cap": int(b.get("bot_solver_cap", 60)), "bot_mistake_rate": 0.0,
           "think_min_seconds": float(b.get("think_min_seconds", 10.0)), "think_max_seconds": float(b.get("think_max_seconds", 18.0)),
           "max_casts": 8 if enemy_id in BOSS else 6, "player_max_casts": 10 if enemy_id in BOSS else 8, "ward_pool": pool, "enemy_id": enemy_id,
           "lethal": enemy_id in LETHAL, "escape": enemy_id in ESCAPE}
    fixed = b.get("fixed_ward")
    if fixed:
        fw = [int(c) for c in fixed if int(c) in player_pool]
        if fw:
            out["fixed_ward"] = (fw * 3)[:3]  # a one-slot legacy Ward becomes the same colour in every place: easy, as the book's mastiff is
    return out
