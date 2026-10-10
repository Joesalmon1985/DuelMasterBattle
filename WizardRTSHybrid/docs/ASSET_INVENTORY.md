# Asset inventory

The hybrid does not copy Widelands or OpenRA art, audio, or maps.

| Asset | Origin | Shipped |
| --- | --- | --- |
| Wizard sprite and Overworld HUD, including the touch pad | Existing DuelMasterBattle client, GPL-3 | Yes, by launching the Godot project |
| Hex tiles, roads, buildings, carriers, soldiers, hazard marker | Drawn rectangles in `hybrid_world.gd`. Not upstream art. | Yes, as code |
| Widelands data under `external/widelands/data` | Widelands GPL-2.0-or-later | No |
| OpenRA mod sequences and maps under `external/openra` | OpenRA GPL-3, plus game data the engine downloads separately | No |
| Mod SDK example mod | GPL-3 code; the SDK README says art can use other terms | No |

If a later change copies a file out of `external/`, add a row here and in `docs/LICENSES.md` before the package script runs.
