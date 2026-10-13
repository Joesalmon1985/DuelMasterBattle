# Source reuse

| Upstream | SHA | File and symbol | Mechanic | Status | Comparison | Remaining |
| --- | --- | --- | --- | --- | --- | --- |
| Widelands | `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4` | `warelist.cc` `WareList::add`, `WareList::remove`; `warehouse.cc` `WarehouseSupply::add_wares`, `remove_wares` | Warehouse and economy counts | source-derived adapted | Scenario 3. `tests/test_widelands_stock.py` | Productionsite program and real carrier still unused |
| Widelands | same | carrier, road, productionsite, tribe AI | Haul, production program, AI | not implemented | Scenarios 1, 4, 5, 6 are provisional stand-ins | Compile Widelands (`B1`), then trace those paths |
| OpenRA | `e7e9e4ad270221d7fb9725b348c75504d48c1ebd` | `Util.ApplyPercentageModifiers`, `DamageWarhead.InflictDamage`, `Health.InflictDamage` | Damage and HP clamp | source-derived adapted | Scenarios 4 and 5. `tests/test_openra_damage.py` | Actor search and hit shapes |
| OpenRA | same | `PathFinder.FindPathToTargetCell` | Movement | not implemented | Scenario 1 is a Manhattan step | Needs the OpenRA world and locomotor |
| OpenRA | same | order generator, attack traits, death types, bot modules | Orders, targeting, death, AI | not implemented | `OpenRA.Test` passed 508 tests, including orders and coordinates | A skirmish was not played |
| OpenRA Mod SDK | `df103939c7e472e715b9fce7cbaf7e35b54dc037` | `make.ps1`, example mod | Mod without an engine fork | not implemented in the hybrid | Build note in `docs/original_runs/` | Example mod must build before it can teach the extension path |
| OpenRA | same | `OpenRA.Utility --extract`, `--png`, RA sequences | Sprite frames | extracted into the Godot project | `art/catalogue.json` | Not the OpenRA renderer. Facings are an approximation. |
| DuelMasterBattle | this repo | `HazardDuelService`, `ClockService`, Overworld | Duel lease, pause, avatar | existing DuelMasterBattle | `tests/test_world.py` duel cases | Graphical board path is `run_hybrid_duel.gd` |
| Mindustry v146 | `26b66f9b…` | `Items.java`, `Liquids.java`, `Blocks.java`, `UnitTypes.java`; formulas of `Drill`, `Conveyor`, `UnitFactory`, `PowerNode` | Item hardness/cost, block requirements, craft/drill/belt/power numbers, dagger stats | imported to JSON and used by `wizard_rts/industry/` with labelled hybrid overrides | `tests/test_mindustry_pipeline.py`, `test_industry_mechanics.py`, `test_industry_slice.py`; headed `run_hybrid_industry.gd` | Ground units only; no liquids, routers, art or sound (placeholders). Costs are hybrid adaptation. |

Carrier schedule and soldier stepping in `wizard_rts/economy.py` and `wizard_rts/military.py` are `provisional-scaffolding`. They are not listed as Widelands or OpenRA reuse.

## Autonomous v2 run additions (13 Oct 2026, Ubuntu laptop)

| Item | Source | Licence / note |
| --- | --- | --- |
| `scripts/mix_crypto.py`: Westwood MIX header decryption (RSA-wrapped Blowfish key). Blowfish tables computed from the digits of pi and checked against the published first words and a published test vector; the 42-byte public key string is the well-known Westwood key published in the C&C community tools (XCC, OpenRA `MixFile`). Byte orders (modulus big-endian, key-block integers little-endian, standard big-endian Blowfish) were found by trial against `hires.mix` until the header was consistent with the file size. | Algorithm and public key are public knowledge; this implementation was written from the format description, not copied from OpenRA source (the OpenRA C# `MixFile.cs` is not in `external/`). | `tests/test_mix_crypto.py`. |
| Art `art/openra/{e2,e3,shok}-*.png` (stand 0-7, run 16-63) and `{ttnk,ctnk}-0000..0031.png` replace the alias placeholders | `hires.mix`, `expand/hires1.mix`, `expand/expand2.mix` of the player's own Red Alert content, decoded by `mix_crypto.py` and `shp_td.py` via `scripts/import_openra_units.py` | As the other Red Alert sprites: use permitted for this project, not relicensed. The Tesla tank `spinner` frames (32-63) are not imported yet. |
| Sprite facing: Red Alert frames run counter-clockwise from north; `hybrid_art.gd` now maps compass facing to that order | OpenRA facing convention (0 = north, increasing towards west), verified on 3TNK and E1 frames | `godot_project/client/tests/run_hybrid_facing.gd` |
