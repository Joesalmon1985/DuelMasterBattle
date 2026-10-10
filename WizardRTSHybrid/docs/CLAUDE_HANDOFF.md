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

## Next task

Phase G, systematic coverage. Write `scripts/import_widelands_programs.py`: parse the Lua production-site, worker and immovable definitions (buildcost, inputs, programs: consume, produce, sleep, animate, callworker, mine, findobject, findspace, walk, plant, createware, return, call, return=skipped unless economy needs) into JSON like `import_openra_rules.py` does, so `programs_data.py` stops being hand-transcribed and the catalogue can count executable definitions. Then add sheep and wool (Empire sheepfarm: wheat + water -> wool), fisher, gamekeeper, marble and gold, bricks, flags and donkeys, patrol and repair, a God Mode menu coverage catalogue, AI prospecting. Keep `tests/test_logistics.py` conservation and the headed scripts green. B1 is still the missing C++ compiler. Do not rerun bare cmake.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
