"""Data-driven audit of the content coverage table: every functional entity must be unlockable, buildable and explained."""
from __future__ import annotations

import pytest

from wizard_rts import coverage, tech
from wizard_rts.content import graph

ROWS = coverage.build()


def test_every_row_is_classified_and_pending_rows_name_a_blocker():
    for r in ROWS:
        assert r["status"] in ("functional", "pending", "excluded"), r["key"]
        if r["status"] != "functional":
            assert r["blocker"], r["key"]


def test_every_functional_entity_is_on_exactly_one_card_or_in_the_foundation():
    ents = graph.entities()
    for r in ROWS:
        if r["status"] == "functional" and r["entity"]:
            assert r["entity"] in ents, r["key"]
            assert r["card"], f"{r['key']} is functional but cannot be unlocked"


@pytest.mark.parametrize("game", ["widelands", "openra", "mindustry"])
def test_functional_rows_have_a_cost_or_recipe(game):
    ents = graph.entities()
    for r in ROWS:
        if r["game"] == game and r["status"] == "functional" and r["entity"] in ents and r["type"] != "item":
            e = ents[r["entity"]]
            if e["type"] == "building":
                assert e["cost"], r["key"]
