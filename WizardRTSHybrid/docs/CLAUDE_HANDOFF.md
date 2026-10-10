# Handoff

## Works

Read `docs/STATE_OF_PLAY.md` first; it is the current inventory. In short: one continuous world with the wizard and the retained duel; six factions with real economies (forestry with persistent trees and physical workers, quarry, finite mines, smelting, ax workshop, sawmill) carried by road carriers; construction sites, roads, recruitment queues that consume delivered goods; OpenRA-rule combat; AI commanders; God Mode over the same commands; headed tests for all of it.

## Does not

Widelands does not compile here (`docs/BLOCKERS.md` B1). OpenRA's PathFinder and bot are not executing; the hybrid has its own A* and AI shaped after them. No sheep, fishers, marble, gold, bricks, flags, donkeys. Programme data is hand-transcribed from Lua, not imported. See the missing table in `STATE_OF_PLAY.md`. Do not describe provisional pieces as Widelands or OpenRA.

## Architecture

`AGENTS.md` and `docs/DECISIONS.md`. Python `wizard_rts/world.py` owns the world. Modules: `workers.py` (trees, worker and building programme interpreter), `programs_data.py` (Widelands data), `logistics.py` (roads, transfers, carriers), `construction.py` (menu, sites, roads, queues), `military.py` + `rules.py` + `data/openra_rules.json` (OpenRA rules), `ai.py` (commanders), `lifecycle.py` (ruins, corpses). Godot: `client/scenes/hybrid_world.gd` extends Overworld; `client/hybrid/god_mode.gd`, `hybrid_art.gd`.

## Rebuild

- Labs: `WizardRTSHybrid/scripts/setup_external.ps1`
- OpenRA: `dotnet build OpenRA.slnx -c Debug` in `external/openra` with .NET 10.
- Mod SDK: `make.cmd all` with `dotnet` on `PATH`.
- Widelands: blocked until a C++ compiler exists. Command in `docs/original_runs/WIDELANDS.md`.
- Hybrid: `scripts/launch_hybrid.ps1`

## Test

Commands are in `docs/PROJECT_STATUS.md` and `docs/STATE_OF_PLAY.md`. One sim process on port 8765. Headed shots need `--rendering-method forward_plus`.

## Evidence

- `docs/evidence/walk/walk_start.png`, `walk_middle.png`, `walk_end.png`
- `docs/evidence/duel/duel_open.png`
- `docs/evidence/gallery/` and `REVIEW.md`
- `docs/original_runs/`

## Checkpoint (latest)

Verified: 55 Python tests, headed walk/visual/duel/forestry/food/god/war all PASS (`scripts/run_headed_suite.ps1`). 124 of 124 runnable Widelands production sites pass the bench (`verify_generic_buildings.py`), including tribe barracks (`recruit` command spawns a Widelands soldier) and `return=... when/unless` conditions.

In progress, partly landed: **tribes per faction** (`wizard_rts/tribes.py`: Red/Orange Barbarians, Blue Empire, Green Frisians, Yellow Atlanteans, Purple Amazons). Done: tribe starter stock, tribe-specific rifleman cost (`construction.recipe_for` uses the tribe barracks' consume line), gold/stone deposits per faction. NOT done: the tribe-aware AI planner. Until it exists, non-Barbarian factions cannot make their soldier wares, so their OpenRA barracks stall and only Barbarians (Red, Orange) recruit; the six-faction war is therefore lopsided. The God Mode test uses Orange for that reason.

## Next task

Write the tribe-aware AI planner in `ai.py`: for a faction's tribe, resolve the soldier wares (`wl_defs.soldier_wares`) through `tribes.producers()` into a dependency-ordered list of missing buildings (recursing over each building's inputs and over missing build-cost wares), place the first affordable one near the warehouse on a deposit if it mines (`world.resources`), connect its road, one site at a time. Then build the tribe barracks. Verify with `long_run.py`: every tribe must reach `recruited > 0` by minute 30 without free goods; add `tests/test_tribe_ai.py`. After that: military/training sites from the Lua, unsupported worker commands (fish, breed, scout, swimming), per-building headed verification, God Mode menu catalogue, player-colour sprite remap. Checkpoint every 20-30 minutes. B1 is still the missing C++ compiler.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
