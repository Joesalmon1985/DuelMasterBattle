"""The Dystopian military revolution, stated as tests (owner programme 13 Oct 2026): a Mindustry unit of tier N beats its Red Alert counterpart with most of its
health left, and costs far more sophisticated inputs (more distinct materials, power-hungry reconstructors, liquids at the top)."""
from __future__ import annotations

import pytest

from wizard_rts import duel_matrix as D
from wizard_rts.industry import blocks as B
from wizard_rts.industry import registry as R
from wizard_rts.industry import units as U

# (Mindustry unit, Red Alert counterpart, minimum fraction of its health the Mindustry unit keeps)
MATCHUPS = [
    ("mindustry.dagger", "openra.e1", 0.5), ("mindustry.nova", "openra.e3", 0.5), ("mindustry.pulsar", "openra.e1", 0.8),
    ("mindustry.mace", "openra.2tnk", 0.4), ("mindustry.atrax", "openra.2tnk", 0.5),
    ("mindustry.fortress", "openra.4tnk", 0.3), ("mindustry.fortress", "openra.3tnk", 0.5), ("mindustry.quasar", "openra.3tnk", 0.15),
    ("mindustry.scepter", "openra.4tnk", 0.8), ("mindustry.reign", "openra.4tnk", 0.9),
]


@pytest.mark.parametrize("mdy,ra,keep", MATCHUPS)
def test_a_mindustry_unit_beats_its_red_alert_counterpart_with_health_to_spare(mdy, ra, keep):
    r = D.fight(mdy, ra, seconds=150)
    assert r["winner"] == "A" and r["hp_a"] >= keep, r


def test_two_low_tier_mindustry_units_beat_one_red_alert_heavy_tank():
    r = D.fight("mindustry.mace", "openra.4tnk", na=2, nb=1, seconds=150)
    assert r["winner"] == "A", r


def chain(unit):
    items: dict[str, int] = {}
    blocks = []
    u = unit
    while True:
        prev = next(((pair[0], blk) for blk in B.full()["blocks"].values() for pair in (blk.get("upgrades") or []) if len(pair) > 1 and pair[1] == u), None)
        if prev is None:
            break
        for i, n in prev[1]["consume"]["items"].items():
            items[i] = items.get(i, 0) + n
        blocks.append(prev[1]["id"])
        u = prev[0]
    for blk in B.full()["blocks"].values():
        for pl in blk.get("plans") or []:
            if pl["unit"] == u:
                for i, n in pl["requirements"].items():
                    items[i] = items.get(i, 0) + n
                blocks.append(blk["id"])
    return items, blocks


def test_higher_tiers_cost_more_materials_and_more_machines_each_step():
    last = 0
    for name in ("dagger", "mace", "fortress", "scepter", "reign"):
        items, blocks = chain(name)
        value = sum(R.item_info(i)["cost"] * n for i, n in items.items())
        assert value > last and len(blocks) == U.chains()[name], (name, value, blocks)
        last = value
    items, _ = chain("reign")
    assert {"plastanium", "surge-alloy", "phase-fabric"} <= set(items)  # the top tier needs the rarest industrial materials
    assert sum(1 for blk in ("tetrative-reconstructor",) if B.full()["blocks"][blk]["consume"]["liquids"]) == 1  # and a liquid coolant


def test_every_mindustry_unit_needs_power_to_be_made():
    for name in U.unit_list():
        if not U.is_producible(name):
            continue
        items, blocks = chain(name) if name in U.chains() else ({}, [])
        if not blocks:
            continue
        assert any(B.full()["blocks"][b]["consume"]["power_per_tick"] > 0 for b in blocks), name
