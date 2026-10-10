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

Verified: 57 Python tests, all 7 headed scripts (`scripts/run_headed_suite.ps1`), 30-minute x 3 seeds long run (`scripts/long_run.py`, report `docs/evidence/long_run/report.html`), 124 of 124 runnable Widelands production sites in the bench.

Tribes per faction: Red and Orange Barbarians, Blue Empire, Green Frisians, Yellow Atlanteans, Purple Amazons (`wizard_rts/tribes.py`). The tribe-aware AI planner exists (`ai.tribe_step`, `_resolve`, `tribes.inputs_for`): it resolves the soldier wares of the tribe into a small dependency chain, builds missing buildings one at a time (mines on deposits, extra quarries when granite runs dry), then the tribe barracks. Barbarians recruit well. Peace runs (`world.ai_aggressive=False`) show Blue, Green, Yellow and Purple building their chains, but by minute 90 no tribe barracks has produced a Widelands soldier: Green lacks a fur_garment producer (tailor not runnable), Blue never afforded its barracks (marble columns), supply chains are slow. In war the Barbarians still overrun everyone around minute 20.

## Next task

1. Debug why tribe barracks starve (peace run `/tmp`-style script: print each tribe barracks stock vs `soldier_wares`, and each smithy's `shortages`); make the resolver add producers for unproducible wares by switching to alternate producers or enabling the blocking commands; verify with a test that every tribe recruits a Widelands soldier within 60 game minutes in peace.
2. Balance war: stagger AI aggression (attack only after the squad threshold AND minute 25), so six factions survive long enough for the six-colour battle to be even.
3. Military/training sites from the Lua, unsupported worker commands (fish, breed, scout, swimming), per-building headed verification, God Mode menu catalogue, player-colour sprite remap. Checkpoint every 20-30 minutes. B1 is still the missing C++ compiler.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
