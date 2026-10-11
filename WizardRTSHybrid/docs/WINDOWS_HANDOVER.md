# Windows handover

Written on the Ubuntu ThinkPad T460 at the end of session 2. Branch `feature/wizard-rts-hybrid-v02`. **Commit: see `git log -1` after you pull; the SHA at the time of writing is recorded in the last line of this file.** The Windows agent was stopped during session 2; nothing here needs merging, only pulling.

## 1. Get the checkpoint

```
git fetch origin
git checkout feature/wizard-rts-hybrid-v02
git pull --ff-only origin feature/wizard-rts-hybrid-v02
```

Do not merge into `main`, do not force-push. `external/` is gitignored: on Windows it already holds the full Widelands and OpenRA clones; the importers also work on the sparse checkouts Ubuntu used (`scripts/setup_external.sh` documents them).

## 2. Run the simulation and the tests (no Godot)

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 WizardRTSHybrid/scripts/bench_sim.py --minutes 5            # headless throughput and state hash
py -3 WizardRTSHybrid/scripts/render_terrain.py 507 standard terrain.png   # look at the generated map
py -3 WizardRTSHybrid/scripts/render_terrain.py 507 wmf:The_Big_Lake lake.png   # a translated genuine Widelands map
```

Expected on Ubuntu (4 cores): about 100 tests pass in 6 to 8 minutes; standard map about 55x realtime headless; map generation 3 s; peak memory about 60 MB. `HYBRID_TERRAIN=0` runs the flat legacy world for comparison (57 old tests pass in it).

## 3. Start the game

```
$env:HYBRID_SIM_PORT = "8765"
py -3 -m wizard_rts.server                       # terminal 1, from WizardRTSHybrid (optional: $env:HYBRID_SEED, $env:HYBRID_MAP = small|standard|large|wmf:The_Big_Lake|wmf:Egyptian_Mandala_v1.2)
WizardRTSHybrid/scripts/launch_hybrid.ps1 -Mode God      # or -Mode Wizard
```

Double-click `Play Hybrid God Mode.bat` or `Play Hybrid Wizard Mode.bat` in the repository root (they call `launch_hybrid.ps1`, which waits for the simulator before it starts Godot). Ubuntu equivalent: `WizardRTSHybrid/scripts/launch_hybrid.sh god|wizard`. Press **G** or the purple button to switch modes; the simulator is one process, so the world, terrain, buildings, units and the wizard position never reset.

## 4. Inspect the new terrain

God Mode: the **Sites** button colours the land by what the simulation lets you build (green big, light green medium, yellow small, orange mine, blue ring port), the **Deposits** button (coal black, iron orange, gold yellow, stones white, fish cyan dots, live amounts), hover any tile for terrain, height, build capability and deposit, the minimap shows the real terrain, the placement ghost turns red where the simulation would refuse. Select a building: **Status** says why it is working or stopped. Click a civilian worker to inspect it. Clock buttons 1x to 16x.

## 5. Test the naval systems

God Mode, choose Blue, build **Naval yard** on water beside the shore (the ghost is a 3x3 block), road it to the warehouse, select it and queue a **Patrol boat** (paid for with planks and iron that the economy delivers). Locked entries (destroyer, cruiser, transport, missile submarine) say why. A ship refuses orders onto land; infantry and tanks refuse water. Automated: `tests/test_naval.py` (13 tests), headed `run_hybrid_naval.gd`.

## 6. Graphical tests

```
WizardRTSHybrid/scripts/run_headed_suite.ps1                 # walk visual duel forestry food god war terrain naval
WizardRTSHybrid/scripts/run_headed_suite.ps1 -Only terrain,naval
```

Each script needs a fresh simulator (the suite starts one per script) and Forward+. `naval` needs `HYBRID_ALLOW_SPAWN=1` on the simulator (the suite sets it) because the test spawns an enemy ship. Shots go to `HYBRID_SHOT_DIR`.

## 7. What was and was not verified graphically

Verified headed on Ubuntu (Forward+, Intel HD 520, 1280x720): all nine scripts of `run_headed_suite` pass (walk, visual, duel, forestry, food, god, war, terrain, naval). The laptop's usable screen is smaller than 1920x1080, so `run_hybrid_visual.gd` prints `HYBRID_VISUAL_SKIP` for its 1920x1080 shot: **run it on Windows** to get that image.

Needs Windows: all 1920x1080 and larger screenshots; a 30-minute headed run with periodic shots; large-map (`HYBRID_MAP=large`, 800x480) frame rate; extraction of the **OpenRA ship, naval yard, submarine and player-colour sprites** from the Red Alert content packages (`OpenRA.Utility --png`; the current ships and yards are labelled placeholder shapes in `hybrid_art.gd`); judging the terrain blending and water animation by eye on the real GPU.

## 8. Unfinished (do not describe the hybrid as complete)

- Art: OpenRA ship and yard sprites (placeholders now); other tree species look like beech; no terrain transition masks beyond a soft colour blend; faction colour is a ring, not a player-colour remap; Widelands animations for most imported buildings are idle frames.
- Naval: destroyer, cruiser, transport, missile submarine, amphibious landings, ports, Widelands civilian ships (replaced by OpenRA ships by design), naval AI is basic.
- Economy: Barbarians and Empire recruit OpenRA infantry from their own chains; Frisians, Atlanteans and Amazons recruit after a 25-minute hybrid ax fallback because their own chains still stall (see `docs/CLAUDE_HANDOFF.md`). Frisian ponds (clay pit, aqua farm, charcoal burner), gamekeeper, scouts, ferries are not implemented. 153 of 178 production sites run.
- Military: no aircraft, walls, formations, veterancy, repair; only Red Alert rules are imported (no Tiberian Dawn, Dune 2000, Tiberian Sun).
- God Mode: no per-worker command panels, garrisons, training; no menu catalogue for every original screen.
- Headless: no Gymnasium or PettingZoo adapter, no learner (by design, tonight), determinism is tested for single-process runs on one machine.
- Terrain: no `.wmf` importer for real Widelands maps (the generator produces the maps); square grid, not Widelands geometry (DECISIONS D5).

## 9. Where to look next

`docs/STATE_OF_PLAY.md` (inventory), `docs/TASK_LEDGER.md` (ids and acceptance), `docs/DECISIONS.md` (D5, D6), `docs/WORK_LOG.md`, `docs/CLAUDE_HANDOFF.md` (next task). Key code: `wizard_rts/terrain.py`, `mapgen.py`, `world.py`, `construction.py`, `military.py`, `ai.py`, `sim_api.py`; Godot `client/hybrid/terrain_view.gd`, `god_mode.gd`, `hybrid_art.gd`.
