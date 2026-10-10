# Asset inventory

Imported sprites live in `godot_project/client/hybrid/art/`. `WizardRTSHybrid/scripts/import_assets.py` copies them from the pinned trees. The game does not read `external/` to draw them. Audio and maps are still not copied.

| Asset | Origin | Shipped |
| --- | --- | --- |
| Wizard sprite and Overworld HUD, including the touch pad | Existing DuelMasterBattle client, GPL-3 | Yes, by launching the Godot project |
| Summer meadow, Barbarian road strip, lumberjack hut, Empire sawmill, Barbarian warehouse, coal mine, tavern, farm, beech, rocks, carrier walk sheets, soldier idle | Widelands `47c5cae8`, GPL-2.0-or-later | Yes, `art/widelands/` |
| RA barracks, war factory, refinery, heavy tank, rifle infantry, gun turret, bullet, piff, small explosion | OpenRA Utility extraction of the local RA packages. Original artwork, permitted for this project. | Yes, `art/openra/` |
| Hazard marker | Drawn circle. Not an imported sprite. | Yes, as code |
| Widelands audio and maps | Widelands GPL-2.0-or-later | No |
| OpenRA maps and audio | OpenRA content packages | No |
| Mod SDK example mod | GPL-3 code; the SDK README says art can use other terms | No |

If a later change copies a file out of `external/`, add a row here and in `docs/LICENSES.md` before the package script runs.
