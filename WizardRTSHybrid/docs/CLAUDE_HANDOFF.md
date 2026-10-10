# Handoff

## Works

Read `docs/STATE_OF_PLAY.md` first; it is the current inventory. In short: one continuous world with the wizard and the retained duel; six factions with real economies (forestry with persistent trees and physical workers, quarry, finite mines, smelting, ax workshop, sawmill) carried by road carriers; construction sites, roads, recruitment queues that consume delivered goods; OpenRA-rule combat; AI commanders; God Mode over the same commands; headed tests for all of it.

## Does not

Widelands does not compile here (`docs/BLOCKERS.md` B1). OpenRA's PathFinder and bot are not executing; the hybrid has its own A* and AI shaped after them. No food chain, farms, animals, marble, gold, bricks, flags, donkeys. Programme data is hand-transcribed from Lua, not imported. See the missing table in `STATE_OF_PLAY.md`. Do not describe provisional pieces as Widelands or OpenRA.

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

Phase B continued: the food chain. Add farm (plant/harvest wheat fields with growth stages), hunter and gamekeeper with wild animals as world entities, well, tavern making rations, then switch mines to `consume=ration` (`programs_data.py` has the note). Reuse `workers.py`: add object classes next to trees and rocks, add worker programmes, keep the conservation test in `tests/test_logistics.py` passing for every new ware. After that: a Lua importer for programmes (`scripts/import_widelands_programs.py`, modelled on `scripts/import_openra_rules.py`), flags and donkeys, then the God Mode menu catalogue. B1 is still the missing C++ compiler. Do not rerun bare cmake.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
