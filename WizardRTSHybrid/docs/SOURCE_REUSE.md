# Source reuse

| Upstream | SHA | File and symbol | Mechanic | Status | Comparison | Remaining |
| --- | --- | --- | --- | --- | --- | --- |
| Widelands | `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4` | `warelist.cc` `WareList::add`, `WareList::remove`; `warehouse.cc` `WarehouseSupply::add_wares`, `remove_wares` | Warehouse and economy counts | source-derived adapted | Scenario 3. `tests/test_widelands_stock.py` | Productionsite program and real carrier still unused |
| Widelands | same | carrier, road, productionsite, tribe AI | Haul, production program, AI | not implemented | Scenarios 1, 4, 5, 6 are provisional stand-ins | Compile Widelands (`B1`), then trace those paths |
| OpenRA | `e7e9e4ad270221d7fb9725b348c75504d48c1ebd` | `Util.ApplyPercentageModifiers`, `DamageWarhead.InflictDamage`, `Health.InflictDamage` | Damage and HP clamp | source-derived adapted | Scenarios 4 and 5. `tests/test_openra_damage.py` | Actor search and hit shapes |
| OpenRA | same | `PathFinder.FindPathToTargetCell` | Movement | not implemented | Scenario 1 is a Manhattan step | Needs the OpenRA world and locomotor |
| OpenRA | same | order generator, attack traits, death types, bot modules | Orders, targeting, death, AI | not implemented | `OpenRA.Test` passed 508 tests, including orders and coordinates | A skirmish was not played |
| OpenRA Mod SDK | `df103939c7e472e715b9fce7cbaf7e35b54dc037` | `make.ps1`, example mod | Mod without an engine fork | not implemented in the hybrid | Build note in `docs/original_runs/` | Example mod must build before it can teach the extension path |
| DuelMasterBattle | this repo | `HazardDuelService`, `ClockService`, Overworld | Duel lease, pause, avatar | existing DuelMasterBattle | `tests/test_world.py` duel cases | Graphical board path is `run_hybrid_duel.gd` |

Carrier schedule and soldier stepping in `wizard_rts/economy.py` and `wizard_rts/military.py` are `provisional-scaffolding`. They are not listed as Widelands or OpenRA reuse.
