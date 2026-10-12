"""Source-derived Widelands warehouse stock.

Adapted from Widelands master 47c5cae8c6cb080e4bf86163a3873bd0847bc0e4:

- src/logic/map_objects/tribes/warelist.cc WareList::add and WareList::remove
- src/logic/map_objects/tribes/warehouse.cc WarehouseSupply::add_wares and remove_wares

The C++ does not execute. Zero counts are ignored. Removal refuses a short
stock instead of aborting the process. Add updates the economy total before
the warehouse list. Remove updates the warehouse list before the economy
total. That order is the original one. GPL-2.0-or-later, Widelands Development
Team. This derivative is used inside the GPL-3 hybrid.
"""

from __future__ import annotations

SOURCE = {
    "repository": "https://github.com/widelands/widelands",
    "commit": "47c5cae8c6cb080e4bf86163a3873bd0847bc0e4",
    "symbols": [
        "Widelands::WareList::add",
        "Widelands::WareList::remove",
        "Widelands::WarehouseSupply::add_wares",
        "Widelands::WarehouseSupply::remove_wares",
    ],
    "status": "source-derived-adapted",
}


class WareList:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store

    def stock(self, ware: str) -> int:
        return int(self.store.get(ware, 0))

    def add(self, ware: str, count: int) -> None:
        amount = int(count)
        if amount == 0:
            return
        if amount < 0:
            raise ValueError("negative ware count")
        self.store[ware] = self.stock(ware) + amount

    def remove(self, ware: str, count: int) -> None:
        amount = int(count)
        if amount == 0:
            return
        if amount < 0 or self.stock(ware) < amount:
            raise ValueError("ware stock short")
        self.store[ware] = self.stock(ware) - amount


class EconomyTotals:
    """Stand-in for Economy::add_wares_or_workers / remove_wares_or_workers counts."""

    def __init__(self) -> None:
        self.totals: dict[str, int] = {}

    def add(self, ware: str, count: int) -> None:
        self.totals[ware] = int(self.totals.get(ware, 0)) + int(count)

    def remove(self, ware: str, count: int) -> None:
        have = int(self.totals.get(ware, 0))
        if have < int(count):
            raise ValueError("economy total short")
        self.totals[ware] = have - int(count)


class WarehouseSupply:
    def __init__(self, store: dict[str, int], economy: EconomyTotals | None) -> None:
        self.wares = WareList(store)
        self.economy = economy

    def add_wares(self, ware: str, count: int) -> None:
        if int(count) == 0:
            return
        if self.economy is not None:
            self.economy.add(ware, count)
        self.wares.add(ware, count)

    def remove_wares(self, ware: str, count: int) -> None:
        if int(count) == 0:
            return
        self.wares.remove(ware, count)
        if self.economy is not None:
            self.economy.remove(ware, count)
