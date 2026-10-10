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

## Findings since the last checkpoint

Peace-run diagnosis: tribe barracks starve because their weapon chains need things the interpreter cannot yet do. Atlanteans' tabard needs `corn` (cornfield `seed_corn`/`ripe_corn` objects: only wheat and beech exist), Frisians' fur_garment has no runnable producer, coal and iron ore are finite (one 5x5 field each) and rations are scarce, so smelters and smithies idle. The planner now adds extra producers (charcoal kilns, quarries) when a wanted ware is at 0. Aggression is gated: AI squads march only after 20 game minutes (`ai.ATTACK_AFTER_MS`); in the long run armies reach 20-34 units, then four factions fall between minutes 20 and 40.

## Next task

1. Generalise fields: make `STAGE_TABLES` and the `findobject`/`plant` attributes data-driven from the imported immovables (`widelands_defs.json` `immovables` with `attributes`, `programs` animate/transform) so corn, barley, rye, blackroot, cassava, reed, grapes and berries work; then more tribe soldier chains become possible. Add a bench criterion for them.
2. Tribe barracks recruiting test in peace (all five tribes within 60 game minutes), then balance war.
3. Military/training sites from the Lua, unsupported worker commands (fish, breed, scout, swimming), per-building headed verification, God Mode menu catalogue, player-colour sprite remap. Checkpoint every 20-30 minutes. B1 is still the missing C++ compiler.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
