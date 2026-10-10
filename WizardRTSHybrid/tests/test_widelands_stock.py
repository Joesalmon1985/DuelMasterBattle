"""Warehouse stock rules adapted from Widelands WareList and WarehouseSupply."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wizard_rts.widelands_stock import EconomyTotals, WarehouseSupply  # noqa: E402


def test_add_ignores_zero_and_updates_economy_before_stock() -> None:
    store: dict[str, int] = {}
    economy = EconomyTotals()
    supply = WarehouseSupply(store, economy)
    supply.add_wares("log", 0)
    assert store == {}
    supply.add_wares("log", 3)
    assert store["log"] == 3
    assert economy.totals["log"] == 3


def test_remove_updates_stock_before_economy_and_refuses_a_short_stock() -> None:
    store = {"log": 2}
    economy = EconomyTotals()
    economy.totals["log"] = 2
    supply = WarehouseSupply(store, economy)
    supply.remove_wares("log", 0)
    assert store["log"] == 2
    try:
        supply.remove_wares("log", 3)
    except ValueError:
        pass
    else:
        raise AssertionError("short remove should fail")
    assert store["log"] == 2
    assert economy.totals["log"] == 2
    supply.remove_wares("log", 2)
    assert store["log"] == 0
    assert economy.totals["log"] == 0
