# Licences

The hybrid package ships this text.

| Work | Licence | What is in the hybrid |
| --- | --- | --- |
| DuelMasterBattle | GPL-3.0-or-later | The host game, the duel lease, `WorldState`, `ClockService`, `HazardDuelService`, and the Overworld presentation. |
| Widelands, commit `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4` | GPL-2.0-or-later, Widelands Development Team | A derivative of `WareList::add`, `WareList::remove`, `WarehouseSupply::add_wares`, and `WarehouseSupply::remove_wares` in `wizard_rts/widelands_stock.py`. Selected sprites under `godot_project/client/hybrid/art/widelands/`, listed in `catalogue.json`. GPL-2.0-or-later can be combined with this GPL-3 program. |
| OpenRA, commit `e7e9e4ad270221d7fb9725b348c75504d48c1ebd` | GPL-3.0-or-later, OpenRA Developers and Contributors | A derivative of `Util.ApplyPercentageModifiers`, `DamageWarhead.InflictDamage`, and `Health.InflictDamage` in `wizard_rts/openra_damage.py`. |
| Red Alert sprites extracted by that OpenRA build | Original game artwork. Use in this project was permitted by the owner. Not relicensed. | PNG frames under `godot_project/client/hybrid/art/openra/`, produced by `OpenRA.Utility --png` from the local RA content packages. See `catalogue.json`. |
| OpenRA Mod SDK, commit `df103939c7e472e715b9fce7cbaf7e35b54dc037` | GPL-3.0-or-later | Not copied into the package. It is a development lab only. |

Attribution to ship with the package:

- Warehouse stock accounting is derived from Widelands (GPL-2.0-or-later), copyright Widelands Development Team.
- Damage arithmetic is derived from OpenRA (GPL-3.0-or-later), copyright OpenRA Developers and Contributors.

`external/` is not part of the package. `scripts/package_hybrid.ps1` copies `wizard_rts/`, `tests/`, and this file only.
