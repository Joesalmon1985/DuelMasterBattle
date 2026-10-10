# Project status

Branch: `feature/wizard-rts-hybrid-v02`, cut from `feature/wizard-rts-hybrid` at `5785e03`. Unrelated spellbook and content edits stay unstaged. `main` is not updated. Build-pack T143 is not advanced.

## What works

- Python `HybridWorld` on one 20 by 20 hex map. Tile ownership is `cube_round`. Godot agrees on 2424 samples.
- The Overworld wizard walks with the existing key hook. A headed run crossed 20 hexes, stayed on one `world_id`, and kept the camera on John. Shots: `docs/evidence/walk/`.
- Game time advances while the player is idle. Five real minutes: `FIVE_MINUTES_OK` elapsed=300.2 produce=598 deliver=30 game_ms=299400.
- Warehouse counts use the Widelands-derived list. A processor turns a log into a plank. The red carrier stops on the hazard. Blue still delivers.
- Soldier HP uses the OpenRA-derived damage chain. Movement is a provisional step.
- The retained ward board opens from the hazard. While it is open, `paused` is true and `game_ms` does not move. A win clears the hazard. Pose and entity ids match the pre-resolve world. Shot: `docs/evidence/duel/duel_open.png`.
- OpenRA bleed compiled with .NET SDK 10.0.401. `OpenRA.Test`: 508 passed, 2 skipped.
- The Mod SDK example assembly compiled after `dotnet` was put on `PATH`.

## What is partial

- Carrier routes and soldier steps are provisional scaffolding. The snapshot says so.
- The red settlement now has imported sprites for a lumberjack hut, Empire sawmill, Barbarian warehouse, coal mine, tavern, farm, beech trees, rocks, a carrier sheet, a Barbarian soldier, plus OpenRA barracks, refinery, war factory, gun turret, rifle infantry, and a heavy tank. Catalogue: `godot_project/client/hybrid/art/catalogue.json`. Inspected shots: `docs/evidence/gallery/`. Roads are still easy to miss. Terrain tiling is visible. This is not a finished visual gate.
- OpenRA's game window and Widelands' game window have not been played. See `docs/original_runs/`.

## What is broken or blocked

- Widelands configure: `CMAKE_CXX_COMPILER not set` and `nmake` missing. Blocker B1. Environment, not an incompatibility.
- Mod SDK `launch-game.cmd` looks for `OpenRA.exe`. The build produced `OpenRA.dll`.

## Commands

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 WizardRTSHybrid/tests/test_five_minutes.py
py -3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
```

Godot 4.5.1 console, Forward+:

```
$env:HYBRID_SIM_PORT = "8765"
py -3 -m wizard_rts.server
godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_hybrid_walk.gd
godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_hybrid_duel.gd
godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd
```

Set `HYBRID_SHOT_DIR` to save PNGs. The sim must be started first. One server process only. A second bind can leave the old world accepting connections.

## Next task

Add current health, max health, and a target type on every building, then one attack that reduces a Widelands building's health through `inflict_damage`. Do not start a second damage function. Keep the imported sprites. B1 stays blocked until a C++ compiler exists. Do not rerun bare cmake.
