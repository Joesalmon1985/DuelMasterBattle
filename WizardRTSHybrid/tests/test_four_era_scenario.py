"""Scripted four-era scenario on the developer profile (gated, God allowed). No wares are granted: cards are the developer fixture and the
era change goes through the real transition (`vp.advance_era`); the plus AI plays in between and the ledger must balance throughout."""
from __future__ import annotations

from wizard_rts import ledger, tech, vp
from wizard_rts.content import graph
from wizard_rts.world import HybridWorld


def _run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def _era_cards(era):
    return sorted(cid for cid, c in graph.generated_cards().items() if c["era"] == era)


def _units_of(cards):
    ents = graph.entities()
    gen = graph.generated_cards()
    return {e[5:] for cid in cards for e in gen[cid]["entities"] if e.startswith("unit:") and ents[e]["game"] in ("openra", "mindustry")}


def test_the_civilisation_passes_through_all_four_eras_with_cards_gating_content():
    w = HybridWorld(507, profile="developer")
    w._seq = 0
    snap = ledger.snapshot_totals(w)
    seen = []
    locked_before = {}
    for era in range(4):
        assert vp.era_state(w)["index"] == era
        cards = _era_cards(era)
        units = _units_of(cards)
        # content of this era is closed until its cards are held
        locked_before[era] = {u for u in units if not tech.unit_allowed(w, "Red", u)}
        assert locked_before[era] == units, (era, units - locked_before[era])
        for cid in cards:
            assert tech.grant(w, "Red", cid)["status"] == "ok"
        assert all(tech.unit_allowed(w, "Red", u) for u in units), era
        # a later era's units stay closed
        later = _units_of([c for e in range(era + 1, 4) for c in _era_cards(e)])
        assert not any(tech.unit_allowed(w, "Red", u) for u in later - units), era
        _run(w, 180)
        seen.append(tech.ERAS[vp.era_state(w)["index"]])
        if era < 3:
            assert vp.advance_era(w, f"scenario: era {era} played")
    assert seen == list(tech.ERAS)
    assert not vp.advance_era(w, "past the last era")
    assert not ledger.check(w, snap)
