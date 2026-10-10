# Task ledger

| ID | Outcome | Priority | Depends | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| T-DOCS | Living agent record under `WizardRTSHybrid/` | 1 | none | VERIFIED | This file, `AGENTS.md`, `PROJECT_STATUS.md`, `WORK_LOG.md`, `CLAUDE_HANDOFF.md` |
| T-CLONES | Full clones and a pinned manifest | 1 | none | VERIFIED | `sources/manifest.json`, `scripts/setup_external.ps1`. Clones are gitignored. |
| T-BASELINE | Overworld movement still drives the avatar. Retained ward duel still passes. | 1 | none | VERIFIED | `run_hybrid_walk.gd` uses `ui_hold_key_direction`. `tests/sim/test_u05_retained_ward_duel.py` 2 passed. |
| T-OPENRA-BUILD | Compile OpenRA and run an engine test | 2 | T-CLONES | VERIFIED | `docs/original_runs/OPENRA.md`. Build succeeded. 508 tests passed. |
| T-SDK-BUILD | Build the example mod | 2 | T-CLONES | VERIFIED | `docs/original_runs/OPENRA_MOD_SDK.md`. `OpenRA.Mods.Example.dll` built. The SDK `launch-game.cmd` expects `OpenRA.exe`, which this build does not emit. |
| T-WIDELANDS-BUILD | Compile Widelands | 2 | T-CLONES | BLOCKED | `B1`. Configure fails with `CMAKE_CXX_COMPILER not set`. |
| T-MAPS | System maps and reference scenarios from the trees that were read and the runs that happened | 3 | T-OPENRA-BUILD | VERIFIED | `docs/WIDELANDS_SYSTEM_MAP.md`, `docs/OPENRA_SYSTEM_MAP.md`, `docs/REFERENCE_SCENARIOS.md`. Widelands was not executed. |
| T-COORDS | Gap-free hex partition | 4 | none | VERIFIED | `tests/test_coords.py`. Godot `HYBRID_COORDS_OK 2424`. |
| T-WORLD | One scene, hex crossing does not advance time | 5 | T-COORDS | VERIFIED | `tests/test_world.py`. Headed walk `HYBRID_WALK_OK`, 20 crossings, camera on John. |
| T-CLOCK | Advance while walking or idle. Duel pause yields zero quanta. | 6 | T-WORLD | VERIFIED | `advance()` tests. `FIVE_MINUTES_OK` produce=598 deliver=30 over 300.2s. Duel test `paused=true` and `held_open=true`. |
| T-ECON | Warehouse stock, one conversion, one delivery | 7 | T-CLOCK | VERIFIED | Source-derived stock port. Provisional schedule. Not an original Widelands process. |
| T-MIL | One attack that changes HP | 7 | T-CLOCK | VERIFIED | Source-derived damage. Provisional movement. Not OpenRA `PathFinder`. |
| T-DUEL | In-world retained board, one outcome, pose restored | 8 | T-WORLD | VERIFIED | `HYBRID_DUEL_OK`. Shot `docs/evidence/duel/duel_open.png`. |
| T-CLEAN | Package runs with `external/` hidden | 8 | T-ECON, T-MIL, T-DUEL | VERIFIED | `tests/test_clean_environment.py` passed. `scripts/package_hybrid.ps1`. |
| T-HANDOFF | Docs match the repo and the next task is named | 9 | the rows above | VERIFIED | `docs/CLAUDE_HANDOFF.md` |
| T-ART | Imported sprites on the live settlement, inspected in a headed shot | 4 | T-WORLD | PARTIAL | `scripts/import_assets.py`. `HYBRID_VISUAL_OK` and `HYBRID_WALK_OK` from start (100, 50). Roads and terrain tiling are still weak. Not a finished presentation gate. |
| T-FOREST | Physical lumberjack + ranger, tree lifecycle, separate carrier (Phase A) | 1 | T-WORLD | VERIFIED | `tests/test_forestry.py` (5 tests); headed `run_hybrid_forestry.gd` HYBRID_FORESTRY_OK, 9 shots in `docs/evidence/forestry/`. Data in `wizard_rts/forest_data.py` transcribed from Widelands Lua. |
| T-CATALOGUE | Machine-readable feature catalogue | 1 | T-MAPS | PARTIAL | `scripts/build_catalogue.py` -> `docs/feature_catalogue.json`, statuses from `docs/feature_status.json`. Discovery counts only; Lua is not yet parsed for programmes. |
| T-PROGRAMS | Generic worker/production programme interpreter for farms, mines, hunters (Phase B) | 1 | T-FOREST | PARTIAL | `wizard_rts/workers.py`, `programs_data.py`. Done: forestry, quarry, coal/iron mines, smelting, ax workshop, sawmill. TODO: farm/wheat fields, hunter/animals, sheep farm, well/water, tavern/rations, gold, marble, a Lua importer for programme data. |
| T-LOGISTICS | Road graph, requests, multi-hop carriers (Phase C) | 1 | T-FOREST | PARTIAL | `wizard_rts/logistics.py`, `tests/test_logistics.py` (conservation, no teleport, request by road). Missing: flags/junction objects, donkeys, priorities, rerouting around blocked roads. |
| T-SIX | Six factions with own economies (Phase E part) | 1 | T-LOGISTICS | PARTIAL | Six capitals with economies (`tests/test_commands.py`). Missing: AI commanders, six-faction autonomous war. |
| T-RECRUIT | Goods-fed recruitment (Phase D) | 1 | T-LOGISTICS | PARTIAL | Barracks/war factory queues consume delivered planks (placeholder recipe). Missing: sword/brick chains. |
| T-GOD | Wizard/God Mode switch and RTS HUD (Phase F) | 1 | T-FOREST | PARTIAL | Button + G key, six-faction picker, build menu, road tool, selection/box/groups, move/attack/stop/demolish, queues, minimap. GUI-input test `run_hybrid_god.gd` HYBRID_GOD_OK, shots in `docs/evidence/god_mode/`. Missing: attack-move, patrol, rally UI, repairs, worker/garrison panels, most original menus. |
| T-RULES | OpenRA actor/weapon rules imported as data | 1 | T-MAPS | VERIFIED | `scripts/import_openra_rules.py` (MiniYaml with Inherits) -> `wizard_rts/data/openra_rules.json`: 92 actors, 45 weapons. Runtime reads only the JSON. |
| T-COMBAT | Units and buildings fight with OpenRA ranges, reload, burst, projectile flight, Versus armor | 1 | T-RULES | PARTIAL | `wizard_rts/military.py`, `tests/test_combat.py`. Missing: spread damage, formations, hierarchical pathfinder, aircraft/ships, veterancy, garrisons. |
| T-AI | Six faction commanders on the shared command API | 1 | T-COMBAT, T-RECRUIT | PARTIAL | `wizard_rts/ai.py` (economy plan, road repair, recruitment, defend, attack-move squads, personalities). Missing: AI cannot rebuild mines (no prospecting), no repair, no expansion. |
| T-IMPORT | Widelands Lua importer and generic buildings (Phase G) | 1 | T-PROGRAMS | PARTIAL | `scripts/import_widelands_programs.py`, `wizard_rts/wl_defs.py`, `tests/test_generic_buildings.py`, bench 120/120, God Mode GUI test places an Empire building. Missing: military/training sites, fishing, swimming, terraforming, breeding, scouting; AI use of imported kinds; per-building headed verification. |

Compiling OpenRA is not by itself the hybrid military milestone. T-MIL stays source-derived adapted.
