# Work log

## 2026-10-10

- Harness: Cursor agent, Windows 10.0.26200, `py -3` (3.14). Godot 4.5.1. Branch `feature/wizard-rts-hybrid` from `7f8ebb53`.
- Objective: the approved hybrid plan. Agent docs, full labs, coordinate proof, continuous Overworld, autonomous clock, stock and damage ports, in-world duel, clean run, handover.
- Inspected: `sim/dmb` clock, duels, hazards; `overworld.gd` movement and the black scene fader; Widelands `WareList` and `WarehouseSupply`; OpenRA `Util`, `DamageWarhead`, `Health`, and `PathFinder`.
- Changes: `WizardRTSHybrid/wizard_rts/` world, coords, stock port, damage port, server. Godot `hybrid_world` extends Overworld. The scene fader is hidden because this scene does not run the area fade. Camera smoothing is off so a fast walk does not leave the draw window. Viewport readback uses Forward+ because the Compatibility renderer returned a black image and `texture_2d_get` was empty.
- Experiments: exclusive 48 by 48 squares were not used. Carrier routing and soldier stepping stayed provisional after reading `PathFinder.FindPathToTargetCell`.
- Commands and results:
  - `pytest WizardRTSHybrid/tests` excluding the five-minute script: 16 passed, including the clean-environment guard.
  - `test_u05_retained_ward_duel.py`: 2 passed.
  - Godot coords: `HYBRID_COORDS_OK 2424`.
  - Headed walk: `HYBRID_WALK_OK` start (96, 71) hex [2, 3] end (533, 83) hex [18, 3], crossings=20, same world, camera on John. Terrain pixel check passed on start, middle, and end.
  - Five minutes: `FIVE_MINUTES_OK` elapsed=300.2 produce=598 deliver=30.
  - Headed duel: `HYBRID_DUEL_OK` pose=(85, 47) paused=true ms=33600 cleared=true same_pose=true same_ids=true held_open=true. The shot is the retained "Set your Ward" board.
  - OpenRA: `dotnet build OpenRA.slnx` succeeded. `dotnet test` 508 passed, 2 skipped.
  - Mod SDK: first `make.cmd all` could not see `dotnet`. Retry with `C:\Program Files\dotnet` on `PATH` built `OpenRA.Mods.Example.dll`.
  - Widelands: CMake 4.4.4 configure failed. `nmake` missing. `CMAKE_C_COMPILER` and `CMAKE_CXX_COMPILER` not set.
- Rejected: treating a black PNG as a pass. The first shots were the opaque Overworld fader. Later middle and end shots were gray because camera smoothing lagged the draw window. Both were fixed and rerun.
- A dropped TCP client used to kill the server. `serve()` now continues after `ConnectionResetError`.
- Commit: the handover commit on this branch. `external/` is not included.
- OpenRA launch reached `Loading mod: ra` on OpenGL at 1920x1080 and was then stopped. No skirmish was played.
- With `external` renamed to `external.off`, the same 16 tests passed (`CLEAN_HIDDEN_OK`), then the labs were restored.
- Still open: Widelands compiler (B1). The Mod SDK `launch-game.cmd` expects `OpenRA.exe`.

## 2026-10-10 v0.2 visual import

- Branch `feature/wizard-rts-hybrid-v02` from `5785e03`. Baseline before edits: 16 pytest passed, ward duel 2 passed, `HYBRID_COORDS_OK 2424`, `HYBRID_WALK_OK`.
- `scripts/import_assets.py` copies Widelands sprites and runs `OpenRA.Utility --extract` and `--png` with `ENGINE_DIR` set. Catalogue has no missing required ids.
- The red settlement is real entities: lumberjack, sawmill, warehouse, mine, tavern, farm, barracks, refinery, war factory, turret, trees, rocks, carrier, Barbarian soldier, rifle infantry, heavy tank. The wizard starts at (100, 50), just east of that settlement. Zoom is 0.48.
- Inspected `docs/evidence/gallery/mashup_1280x720.png`, `mashup_wide_1280x720.png`, and `mashup_1920x1080.png` at native size. The hut, green-roof warehouse, farm, barracks, war factory, tank, infantry, soldier, and wizard are visible together. Roads are faint. The grass texture repeats. The refinery sits near the left edge at the play zoom. OpenRA units use the temperate palette's default player colour.
- After the move, pytest 17 passed and `HYBRID_WALK_OK` start=(100, 50) end=(522, 62) crossings=20.
- Not done: building health, cross-game attacks, recipe economy, God Mode, long runs, a package that includes the art.
- Follow-up on the same day: every non-scenery building has `hp`, `max_hp`, `target_type`, and `armor`. `damage_building` uses the existing OpenRA-derived `inflict_damage`. A weapon whose target list omits `structure` deals 0. A dead building is not damaged again. Units do not call this yet. Pytest 18 passed.
- Documented `docs/STATE_OF_PLAY.md` and merged the hybrid branch into `main` at Joe's request. Spellbook polish dirt stayed unstaged.

- 2026-10-10 (Claude): added `order` op and unit attack orders through `damage_building`; destroyed buildings stop producing. 20 hybrid tests + 2 duel tests pass.

- 2026-10-10 (Claude): Phase A forestry. Trees are persistent entities with Widelands lifecycle (sapling 55s, pole 65s, mature 72s, old 25m25s, death/seed chances). Workers (lumberjack, ranger) run data-driven programmes: findobject/findspace, A* walk one tile per 600 ms, animate, callobject fall, createware, plant, return. A log exists only after a felled tree; it is stored in the hut output; a road carrier hauls it to the warehouse; a second carrier feeds the sawmill. A destroyed workplace cancels the job and releases the tree. Timer-based log minting removed. OpenRA refinery removed from the default settlement. Hazard moved to the producer road. `speed` op (time_scale 1..60) for tests. Duel test now captures ids when the board opens. Evidence: `docs/evidence/forestry/`. FIVE_MINUTES_OK produce=14 deliver=7 (real worker pace).

- 2026-10-10 (Claude): Phases C/D/F first slices. Road graph + transfers + per-road carriers (logistics.py); construction sites, generic road builder, recruitment queues (construction.py); six factions (Red, Blue, Green, Yellow, Purple, Orange) with own economies; unit move/attack orders over A* with occupancy; God Mode (god_mode.gd): HUD button + G, faction picker, build menu, road/move/attack/stop/demolish tools, box select, control groups, queues, minimap, ring markers by faction colour. Headed GUI test `run_hybrid_god.gd` drives real mouse events (window coords scaled to the stretched viewport) through button, faction, build, road, warehouse stock, barracks queue, box select, right-click move, attack, back to Wizard Mode with pose and world unchanged. Launcher: `launch_hybrid.ps1 -Mode God`. 33 Python tests pass.

- 2026-10-10 (Claude): Phase B first slice: generic building-programme interpreter (needs / consume / sleep / animate / mine / produce / callworker) in `workers.py`, data in `programs_data.py` transcribed from Widelands Lua (empire sawmill, barbarians coalmine, ironmine, smelting_works iron, ax_workshop produce_ax, quarry + stonemason cut_granite). Finite coal and iron fields (5x5 per mine, mine yield 33.33 %, when_empty 5 %), rocks with amounts. Barracks recruits from axes, war factory from granite + plank. Conservation test over seven wares. Removed mine ration input (hybrid deviation until a food chain exists). First rifleman arrives about 550 game seconds in. Importer gained quarry, ironmine, smelting works, ax workshop and stonemason art.
