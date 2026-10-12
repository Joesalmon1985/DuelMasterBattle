"""The faction AI places the Mindustry line itself (roadmap M6: AI-usable coverage) once the three cards are drafted and the goods are in
the warehouse. Nothing is granted by the fixture: the placement pays in delivered goods, like a player's."""
from wizard_rts import ai_industry
from wizard_rts import construction as con
from wizard_rts.world import HybridWorld


def _ready_world():
    w = HybridWorld(507, profile="developer")
    w.era_index = 2
    for c in ai_industry.CARDS:
        w.grant_card("Red", c)
    wh = con.faction_warehouse(w, "Red")
    for g, n in ai_industry.NEEDED.items():
        w.stocks.setdefault(wh["id"], {})[g] = n + 40
    return w, wh


def test_ai_places_the_line_once_and_only_when_ready():
    w, wh = _ready_world()
    assert ai_industry.industry_step(w, "Red", wh) is True
    assert any(e["kind"] == "ai_industry_placed" and e["faction"] == "Red" for e in w.events)
    assert any(b["kind"] == "mdy:conveyor" for b in w.buildings.values())
    assert ai_industry.industry_step(w, "Red", wh) is False  # one line per faction


def test_ai_waits_without_cards_era_or_goods():
    w, wh = _ready_world()
    w.era_index = 1
    assert ai_industry.industry_step(w, "Red", wh) is False
    w.era_index = 2
    w.stocks[wh["id"]]["iron"] = 0
    assert ai_industry.industry_step(w, "Red", wh) is False
    w2 = HybridWorld(507, profile="developer")
    w2.era_index = 2
    assert ai_industry.industry_step(w2, "Red", con.faction_warehouse(w2, "Red")) is False
