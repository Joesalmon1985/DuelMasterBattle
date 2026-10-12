# Widelands system map

Source pin: master `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4`. Licence GPL-2.0-or-later (`COPYING`).

The original executable has not been launched. CMake and a C++ compiler were not on this machine when the lab was cloned. The map below is from reading the stock path that the hybrid ports, not from a played Widelands session. See `docs/BLOCKERS.md` for the build attempt. Do not treat the hybrid's provisional carrier as this engine.

## Warehouse stock (traced, ported)

| | |
| --- | --- |
| Entry | `WarehouseSupply::add_wares` / `remove_wares` |
| Files | `src/logic/map_objects/tribes/warehouse.cc` (add around 210–219, remove around 222–230); `src/logic/map_objects/tribes/warelist.cc` (`WareList::add` around 43–52, `WareList::remove` around 70–77) |
| Types | `WareList`, `WarehouseSupply`, economy stock totals |
| Upstream | A warehouse is an immovable on the map economy. Add updates the economy total, then the warehouse list. Remove updates the list, then the economy. A zero count is a no-op. Remove of a short count is refused in the port instead of aborting the process. |
| Sim tick | Widelands' game clock drives productionsite programs. That clock was not executed here. |
| State write | Economy total and the warehouse ware list. |
| Visible result | Not observed in a Widelands window. The port's result is covered by `tests/test_widelands_stock.py`. |
| Existing test | Widelands' own production and logistics tests were not run, because the binary was not built. |
| Reuse | Source-derived adapted port in `wizard_rts/widelands_stock.py`. |
| Coupling | The C++ types sit on the Widelands map, tribe, and economy objects. The port keeps only the count update order. |

## Pathways not executed

These names are the systems the lab is here to trace later. They are not implemented in the hybrid.

- Map and immovable lifecycle (`src/logic/map.h` and map object ownership). Not stepped.
- Productionsite input and output programs. The hybrid producer adds one log on a provisional cadence. That cadence is not a Widelands program.
- Road and carrier (`src/logic/map_objects/tribes/carrier.cc` and road objects). Not stepped. The hybrid carrier walks a Manhattan polyline and is marked provisional scaffolding.
- Tribe AI. Not stepped. The hybrid records an `ai_economy` event on a fixed quantum. That is not the Widelands tribe AI.

A clean boundary, from the functions that were read: `WareList` count updates do not need the renderer. They do need the economy object in the original game. The port replaces that object with `EconomyTotals`.
