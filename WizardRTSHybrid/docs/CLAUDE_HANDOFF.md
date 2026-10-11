# Handoff

## Session 3 (Ubuntu) - read `docs/PLAYTEST_FIXES.md` first

Joe played the game for the first time; real play outranked passing tests. All nine observations are fixed with regressions that look at what
is drawn (headed tests with screenshots): trees, smooth movement and visible wares, the war factory, stuck-walker diagnosis, MCV/command-centre
territory expansion, 4 s burning destruction, AI diagnosis and rebuild, smooth wizard, wizard labels with fire magic. Branch
`feature/hybrid-playtest-fixes-v03` (from `6096997`), never merged into `main`.

New modules: `territory.py` (command centres, MCV deploy), `magic.py` (fire), `diagnostics.py` (stuck report). New Godot: `client/hybrid/wizard_labels.gd`;
`hybrid_art.gd` has the motion layer, cargo, footprint buildings and burning ruins. New scripts: `ai_report.py`, `rl_experiment.py`, `make_evidence.py`,
`import_ware_art.py`, `import_openra_overlays.py`, `import_openra_mcv.py`, `shp_td.py`, `mix_read.py`. Decisions: `DECISIONS.md` D7, D8.

Rules learned that must not be forgotten:
- A defect Joe sees is not fixed until a headed test (screenshot or rendered-state assertion) shows it fixed. Two of the nine were pure rendering.
- Never iterate a `set` of strings to decide anything and never use wall-clock budgets in the simulation: `tests/test_determinism.py` catches it across processes.
- Route searches are the cost: shared routes, a count budget per quantum with fair rotation, bounded and cooled-down failing searches. Check `ai_report.py`'s worst step (it was 15.7 s).
- `tests/conftest.py` switches the faction AIs off; anything about the AI must enable `world.ai_enabled` itself.
- The headed naval and wizard GUI scripts click with real mouse events and are timing-sensitive on a loaded machine; run them alone when in doubt.

Next tasks, highest value first:
1. Joe's second playtest. Likely asks: the war factory should show a vehicle rolling out of the open door; carriers carrying wares in their hands (needs the Widelands loaded carrier sheets); player-colour sprite remap; MCV un-deploy.
2. AI: outposts are logistics islands (no road or ware transfer between settlements); no naval invasion; defence orders repeat each decision; the strongest faction always snowballs (add comeback/alliance behaviour or tune aggression).
3. Learning: the score and episode length make a passive expanding policy look good (`TRAINING_PROGRAMME.md`). Rework the reward (buildings completed, army strength), lengthen episodes to 25+ minutes, then imitation from the scripted AI's `ai_*` decisions, then PPO (needs a framework: ask Joe before installing PyTorch).
4. Tribe economies and the other items of the session 2 list below still stand.


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

## Session 2 (Ubuntu) - what changed and what is next

Read `docs/WINDOWS_HANDOVER.md` first, then `docs/DECISIONS.md` D5 and D6. New modules: `grid.py`, `terrain.py`, `mapgen.py`, `resources.py`, `sim_api.py`; Godot `client/hybrid/terrain_view.gd`. Widelands and OpenRA source are in sparse pinned checkouts under `external/` (`scripts/setup_external.sh`).

Next task (highest value first):
1. **Tribe economies.** Every faction now fields OpenRA infantry (Blue from its own Empire chain, the others after the 25-minute ax fallback, DECISIONS D6b). The real work left is to make the tribe chains deliver so the fallback is not needed: Blue (Empire) and the Barbarians already do; Green (Frisians), Yellow (Atlanteans) and Purple (Amazons) stall on tribe wares: `fur_garment` (needs a hunter/fur chain and the sewing room), `trident_light` and `tunic`/`bread` (cassava chain). Use `/tmp`-style diagnostics: run 60 minutes of peace (`world.ai_aggressive = False`) and print `world.status_text(b)` for each `wl:` building (see `HybridWorld.status_text`). Likely fixes: planner should also resolve inputs of existing makers (iron, coal, rations), more mines when deposits are used up (done once, check), and the AI should place tribe farms and gardens on fertile land (`terrain.build` caps).
2. Frisian ponds (clay pit, aqua farm, charcoal burner, dikes): pond immovables and a `terraform` worker command.
3. OpenRA ship, yard and player-colour sprites (extract on Windows with `OpenRA.Utility --png`), then replace the placeholders in `hybrid_art.gd`.
4. Remaining naval units (destroyer needs a radar dome, cruiser the advanced tech building, transport amphibious landings).
5. Gymnasium/PettingZoo adapters over `HybridEnv`, and a trainer, only after you approve the dependency.

Older notes below are from session 1 and are kept for history.

## Checkpoint (latest)

Verified: 57 Python tests, all 7 headed scripts (`scripts/run_headed_suite.ps1`), 30-minute x 3 seeds long run (`scripts/long_run.py`, report `docs/evidence/long_run/report.html`), 124 of 124 runnable Widelands production sites in the bench.

Tribes per faction: Red and Orange Barbarians, Blue Empire, Green Frisians, Yellow Atlanteans, Purple Amazons (`wizard_rts/tribes.py`). The tribe-aware AI planner exists (`ai.tribe_step`, `_resolve`, `tribes.inputs_for`): it resolves the soldier wares of the tribe into a small dependency chain, builds missing buildings one at a time (mines on deposits, extra quarries when granite runs dry), then the tribe barracks. Barbarians recruit well. Peace runs (`world.ai_aggressive=False`) show Blue, Green, Yellow and Purple building their chains, but by minute 90 no tribe barracks has produced a Widelands soldier: Green lacks a fur_garment producer (tailor not runnable), Blue never afforded its barracks (marble columns), supply chains are slow. In war the Barbarians still overrun everyone around minute 20.

## Findings since the last checkpoint

Peace-run diagnosis: tribe barracks starve because their weapon chains need things the interpreter cannot yet do. Atlanteans' tabard needs `corn` (cornfield `seed_corn`/`ripe_corn` objects: only wheat and beech exist), Frisians' fur_garment has no runnable producer, coal and iron ore are finite (one 5x5 field each) and rations are scarce, so smelters and smithies idle. The planner now adds extra producers (charcoal kilns, quarries) when a wanted ware is at 0. Aggression is gated: AI squads march only after 20 game minutes (`ai.ATTACK_AFTER_MS`); in the long run armies reach 20-34 units, then four factions fall between minutes 20 and 40.

## Latest checkpoint

Generic immovables landed (`wizard_rts/imm.py`): any field, bush or tree of any tribe is an object run from its imported Lua programme (animate / remove / transform, `harvest` and `fall` on `callobject`); workers can `findobject` and `plant` any attribute the immovables carry (ponds excluded). Runnable production sites: 138 of 178; bench 138 of 138; 57 Python tests, the full headed suite, 1656 art items. Cornfields, barley, reeds, grapes, berries, bees and rare trees now work, which unblocks more tribe soldier chains.

## Progress note

Mine deposits were raised 5x (30 per node) because coal and iron ran dry by minute 40 and starved every smithy. In peace, Blue now has armor_helmet and spear_wooden in its warehouse but never builds its barracks (needs marble, marble columns, cloth: the cost-ware resolver does not reach them), Yellow's barracks lacks tabards (spidercloth), Green lacks a fur_garment producer, Purple's initiation site is not built yet.

## Next task

1. Re-run the peace diagnostic (`/tmp/dbg2.py` style: 70 game minutes, `ai_aggressive=False`) to see which tribe barracks now get their soldier wares; fix what starves (Frisian fur_garment producer, rations and coal supply, marble columns); add `tests/test_tribe_recruit.py` asserting every tribe recruits one Widelands soldier within 60 game minutes in peace.
2. Military/training sites from the Lua, remaining worker commands (fish, breed, scout, swimming), per-building headed verification (`run_hybrid_generic.gd`), God Mode menu catalogue for the original UIs, player-colour sprite remap. Checkpoint every 20-30 minutes. B1 is still the missing C++ compiler.

## First files

1. `docs/STATE_OF_PLAY.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/BLOCKERS.md`
4. `wizard_rts/world.py`
5. `godot_project/client/scenes/hybrid_world.gd`
6. `docs/SOURCE_REUSE.md`
