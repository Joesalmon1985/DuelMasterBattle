"""Who people are beyond their job: worldviews, temperament and what they think of the mentor, magic and the apprentice.

A persona is generated once per Person, deterministically (`random.Random(crc32(seed|body key|persona))`, so it does not depend on who was met first)
and stored on the Person record (`persona`). Occupations only *tilt* the draw: a forester leans Druidic, a soldier Monarchist, but every persona gets
noise and one strong personal conviction, so two foresters are rarely the same and none is forced. Scores use the seven worldview codes of the
Dialogue Factory (`wizard.worldview_table`), the same keys as the 88 profiles' `Score_*` columns, so authored profiles can replace generated ones later.
The mentor and the attacker have authored personas (`data/narrative/characters.json`).
"""

from __future__ import annotations

import json
import random
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts.narrative import wizard

DATA = Path(__file__).resolve().parents[1] / "data" / "narrative" / "characters.json"
CODES = ("M", "A", "R", "G", "S", "D", "C")


@lru_cache(maxsize=1)
def authored() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def _draw(world: Any, key: str, role: str) -> dict[str, Any]:
    cfg = authored()
    rng = random.Random(zlib.crc32(f"{world.seed}|{key}|persona".encode()))
    scores = {c: rng.randint(0, 2) for c in CODES}
    for code, w in cfg["tendencies"].get(role, cfg["tendencies"]["worker"]).items():
        scores[code] += int(w)
    scores[rng.choice(CODES)] += 2  # one personal conviction, whatever the trade
    order = sorted(CODES, key=lambda c: (-scores[c], CODES.index(c)))
    traits = rng.sample(cfg["traits"], 2)
    mentor = authored()["characters"]["mentor"]["persona"]
    table = wizard.worldview_table()
    sym = table[mentor["primary"]]["delta"][order[0]] * 2 + table[mentor["secondary"]]["delta"][order[0]] + rng.choice((-1, 0, 0, 1))
    attitude = "fond" if sym >= 3 else ("wary" if sym <= -1 else "respectful")
    magic = {"S": "devoted", "C": "devoted", "R": "reverent", "D": "cautious", "A": "wary", "G": "practical", "M": "practical"}[order[0]]
    return {"scores": scores, "primary": order[0], "secondary": order[1], "traits": traits, "mentor": attitude, "magic": magic}


def persona(world: Any, pid: str) -> dict[str, Any]:
    """The Person's persona (made on first use for a simulation body, authored for the named characters)."""
    rec = world.dmb.people[pid]
    p = rec.get("persona")
    if p is None:
        link = rec.get("link") or {}
        key = f"{link.get('kind', 'person')}:{link.get('id', pid)}"
        p = _draw(world, key, str(link.get("role", "worker")))
        rec["persona"] = p
    return p


def set_authored(world: Any, pid: str, name: str) -> dict[str, Any]:
    spec = authored()["characters"][name]["persona"]
    scores = {c: 0 for c in CODES}
    scores[spec["primary"]], scores[spec["secondary"]] = 6, 3
    rec = world.dmb.people[pid]
    rec["persona"] = {"scores": scores, "primary": spec["primary"], "secondary": spec["secondary"], "traits": list(spec["traits"]),
                      "mentor": spec.get("mentor", "respectful"), "magic": spec["magic"]}
    return rec["persona"]


def affinity(persona: dict[str, Any], code: str) -> int:
    """How a person with this persona takes a reply of worldview `code`: the established delta of their own primary worldview towards it
    (3 for the same view, 1 or less for kindred ones, negative for opposed ones), plus a point for their secondary view if it agrees."""
    table = wizard.worldview_table()
    return int(table[persona["primary"]]["delta"][code]) + (1 if persona["secondary"] == code else 0)


def reaction(persona: dict[str, Any], code: str) -> str:
    a = affinity(persona, code)
    return "agree" if a >= 2 else ("disagree" if a <= -1 else "neutral")
