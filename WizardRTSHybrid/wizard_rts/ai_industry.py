"""The faction AI uses the Mindustry layer (roadmap M6: AI-usable coverage).

Once a faction has drafted the automation, industry and unit-fabrication cards, is in the Modern era or later, and its home warehouse
holds the construction goods of a small drill -> belt -> smelter -> factory line, the AI places that line with the same search the
developer fixture uses (`industry.fixture.modern_fixture(..., grant=False)`): real sites on existing deposits, roads, belts, paid in
delivered goods. Nothing is granted. If no layout is found the AI waits ten game minutes and tries again; one line per faction.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import construction as con
from wizard_rts import tech

NEEDED = {"plank": 70, "granite": 40, "iron": 30}  # the goods the fixture's line costs (about), with a margin
RETRY_MS = 10 * 60_000
CARDS = ("dmb.card.automation", "dmb.card.industry", "dmb.card.unit_fabrication")


def industry_step(world: Any, name: str, wh: dict) -> bool:
    """Called from the faction's economy decision. True when it placed a line this call."""
    if world.terrain is None or int(getattr(world, "era_index", 0)) < 2:
        return False
    st = world.tech.get(name)
    if not st or not all(c in st["cards"] for c in CARDS):
        return False
    state = world.__dict__.setdefault("_ai_industry", {}).setdefault(name, {"built": False, "retry_ms": 0, "fails": 0})
    now = int(world.dmb.clock.get("game_ms", 0))
    if state["built"] or now < state["retry_ms"] or state["fails"] >= 3:
        return False
    stock = world.stocks.get(wh["id"], {})
    if any(int(stock.get(g, 0)) < n for g, n in NEEDED.items()):
        return False
    from wizard_rts.industry import fixture

    try:
        ids = fixture.modern_fixture(world, name, grant=False)
    except RuntimeError as exc:  # no workable layout now: try again later, at most three times
        state["retry_ms"] = now + RETRY_MS
        state["fails"] += 1
        world.events.append({"kind": "ai_industry_failed", "faction": name, "why": str(exc)})
        return False
    state["built"] = True
    world.events.append({"kind": "ai_industry_placed", "faction": name, "belts": len(ids["belts"])})
    return True
