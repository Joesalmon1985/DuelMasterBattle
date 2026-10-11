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
| T-TRIBES | Each faction plays a Widelands tribe with its own soldier chain | 1 | T-IMPORT, T-AI | PARTIAL | `wizard_rts/tribes.py`, starter stock, `recipe_for`. Planner landed (`ai.tribe_step`, `tests/test_tribe_ai.py`). Gap: tribe barracks do not yet produce soldiers (see handoff). |
| T-TERRAIN | Square-grid Widelands-derived terrain with gameplay consequences (D5) | 1 | T-WORLD | VERIFIED | `wizard_rts/terrain.py`, `mapgen.py`, `grid.py`; `tests/test_terrain.py` (11); headed `run_hybrid_terrain.gd` on Ubuntu (Forward+, Intel HD 520). Rules from `terrain_defs.json` (Widelands commit 47c5cae8). Not an exact Widelands geometry (DECISIONS D5). |
| T-RESOURCES | Deposits that belong to places: `ActMine`, worker mine/breed, tree growth by terrain affinity | 1 | T-TERRAIN | VERIFIED | `wizard_rts/resources.py`; `tests/test_fishing.py` (4), `tests/test_resources.py` (adapted), bench 153/153. |
| T-FISH | Fisher huts and the fish breeder on finite, breedable fish | 1 | T-RESOURCES | VERIFIED | Fish are bred only up to their initial amount. Frisian ponds (clay pit, aqua farm, charcoal burner) are NOT implemented. |
| T-NAVAL | Naval yard and submarine pen on water, ships from delivered goods, naval locomotor, cloak and detection, AI fleets | 1 | T-TERRAIN, T-COMBAT | VERIFIED (sim) / PARTIAL (graphics) | `tests/test_naval.py` (13). Headed `run_hybrid_naval.gd` drives the God Mode GUI. Ship and yard art are PLACEHOLDER shapes; destroyer, cruiser, transport, missile sub are locked with their reasons. |
| T-ENV | Headless training interface: reset, step, observe, masks, rewards, save, replay | 1 | T-TERRAIN | VERIFIED | `wizard_rts/sim_api.py`, `tests/test_sim_api.py` (10), `scripts/bench_sim.py`. No Gymnasium/PettingZoo adapter yet; no training done. |
| T-ECON-UNLOCK | Compound `or` return conditions: marble mines, Frisian bakeries, sewing room, breweries | 1 | T-IMPORT | VERIFIED | 153 of 178 production sites run (bench 153/153). Remaining: scouts, ferries and shipyards (replaced by OpenRA ships), ponds, gamekeeper, some Amazon rare-tree sites. |
| T-GOD-INSPECT | God Mode explains why a building is not producing, shows deposits, tile info, workers | 2 | T-GOD | PARTIAL | `World.status_text`, deposits toggle, hover tile inspector, worker inspection. Headed GUI test of the inspector is not written. |
| T-TRIBE-ECON | Each non-Barbarian faction recruits OpenRA infantry from its own tribe's civilian chain | 1 | T-IMPORT, T-AI | PARTIAL | Barbarians and Empire recruit from their own chains; Frisians, Atlanteans and Amazons recruit after the 25-minute hybrid ax fallback (`tests/test_tribe_fallback.py`). Their own chains still stall (Amazon rare trees, Atlantean silk and iron, Frisian fur); see `docs/CLAUDE_HANDOFF.md`. |
| T-PT-MOVE | Smooth worker/carrier movement, visible cargo (playtest 1) | 0 | T-ART | VERIFIED | `hybrid_art.gd _motion`, 130 ware sprites, delta snapshots. `run_hybrid_playtest.gd`, `docs/evidence/playtest_v03/carrier_walking.gif`. |
| T-PT-TREES | Trees grow and are felled visibly (playtest 2) | 0 | T-ART | VERIFIED | Stage sprite precedence fixed. `run_hybrid_forestry.gd` asserts the rendered sprite of one tree at every stage. |
| T-PT-WEAP | War factory art, footprint and exit (playtest 3) | 0 | T-ART | VERIFIED | Door overlay from `weap3.shp`, 3x2 footprint. `docs/evidence/playtest_v03/war_factory_before_after.png`, `tests/test_playtest_fixes.py`. |
| T-PT-STUCK | Are workers or carriers stuck? (playtest 4) | 0 | T-PT-MOVE | VERIFIED | `diagnostics.py`; cause was a walking loop on idle figures. Only standing stall: the wizard's hazard on a road. |
| T-PT-MCV | Command centres, MCV, deploy, separation, outposts, AI expansion (playtest 5) | 1 | T-LOGISTICS | VERIFIED | `territory.py`, `tests/test_territory.py`, `run_hybrid_mcv.gd`, AI reports. |
| T-PT-BURN | Destruction in 4 s with fire (playtest 6) | 0 | T-MIL | VERIFIED | `lifecycle.begin_destruction`, `tests/test_playtest_fixes.py`. |
| T-PT-AI | Diagnose and improve the AI; long multi-seed evidence (playtest 7) | 1 | T-PT-MCV | VERIFIED | `docs/evidence/ai_report/`, `tests/test_ai_behaviour.py`. Open: reward and horizon for learning, naval invasion. |
| T-PT-WIZ | Smooth wizard (playtest 8) | 0 | T-WORLD | VERIFIED | `overworld.gd` step chaining, `run_hybrid_playtest.gd`. |
| T-PT-LABELS | Wizard labels and fire magic (playtest 9) | 1 | T-WORLD | VERIFIED | `wizard_labels.gd`, `magic.py`, `tests/test_fire_magic.py`, `run_hybrid_wizard.gd`. |
| T-PT-RL | Training readiness: interface, evaluation, small measured experiment | 2 | T-PT-AI | PARTIAL | `sim_api.py`, `scripts/rl_experiment.py`, `docs/TRAINING_PROGRAMME.md`. The learned policy is not better; the programme is recorded. |

Compiling OpenRA is not by itself the hybrid military milestone. T-MIL stays source-derived adapted.

## Direction ratified 2026-10-11 (documentation only)

| ID | Outcome | Priority | Depends | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| T-DIRECTION | Ratified direction and roadmap documented; owner review pending | 0 | none | DOCS DONE, AWAITING OWNER APPROVAL | `docs/DuelMasterBattle_Design_v0_5.md`, `DECISION_REGISTER.md`, `ROADMAP_NEXT_RUN.md` |
| T-M1 | Campaign profiles, drafted-tech unlocks, primitive start (roadmap M1) | 1 | T-DIRECTION approved | NOT STARTED | `docs/ROADMAP_NEXT_RUN.md` |
| T-M2 | First Mindustry industrial-to-unit slice (roadmap M2) | 1 | T-M1 | NOT STARTED | `docs/ROADMAP_NEXT_RUN.md`, `MINDUSTRY_PROVENANCE.md` |
| T-M3 | Live-settlement quest + dungeon + duel slice (roadmap M3) | 1 | T-M1 | NOT STARTED | `docs/ROADMAP_NEXT_RUN.md` |
| T-M4..M6 | VP/eras, catastrophe overlay, Widelands/OpenRA completion | 2 | M1 | NOT STARTED | `docs/ROADMAP_NEXT_RUN.md` |
