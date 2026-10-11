# State of play — WizardRTSHybrid

Branch `feature/hybrid-playtest-fixes-v03` (from `feature/wizard-rts-hybrid-v02` at `6096997`). This is an honest inventory of what you can launch and play, what is only scaffolding, and what is missing. A sprite on screen is not a feature; the feature catalogue (`docs/feature_catalogue.json`, rebuilt by `scripts/build_catalogue.py`) counts functionality, not files.

## How to launch

From `WizardRTSHybrid`:

```
$env:HYBRID_SIM_PORT = "8765"
py -3 -m wizard_rts.server
```

From the repo root, in a second window (Godot 4.5.1, Forward+):

```
godot --path godot_project --rendering-method forward_plus res://client/scenes/hybrid_world.tscn
```

Or `WizardRTSHybrid/scripts/launch_hybrid.ps1 -Mode Wizard` / `-Mode God` (needs `GODOT` or `.dmb_windows_local.json`). Only one process may own port 8765. Restart the simulator for a clean world.

**Switch modes at any time with the purple HUD button or `G`.** Both call the same toggle. Wizard Mode: WASD / arrows, Space / E / Z beside the purple hazard opens the retained Ward Duel. God Mode: pick a faction (R B G Y P O), build menu, Road / Move / A-Move / Attack / Rally / Stop / Demolish tools, left click select, drag a box, right click to move or attack, `Ctrl+1..9` groups, minimap click, mouse wheel zoom, WASD / arrows pan, `S` stop, `A` attack-move, `Esc` cancel. Other factions stay autonomous.

## Session 3 (Ubuntu, 2026-10-11): fixes from the first manual playtest - read `docs/PLAYTEST_FIXES.md`

| Area | Status |
| --- | --- |
| Trees | Fixed (it was rendering): each growth stage draws its own sprite, felled trees draw the fallen-tree sprite and then vanish. `run_hybrid_forestry.gd` follows one tree and asserts the sprite the renderer selects at every stage. |
| Movement and cargo | Presentation-only glide layer (`hybrid_art.gd _motion`): workers, carriers, animals and units glide to their authoritative tile at their own speed; idle figures stand still (the "walking on the spot" was a walking loop on idle figures). All 128 Widelands wares are imported; carried wares show above workers and carriers. Snapshots are deltas for trees and rocks (614 KB to about 120 KB), polled every 0.2 s. |
| War factory | Base + the door overlay (`weap3.shp` decoded by `scripts/shp_td.py`), one OpenRA cell per tile, real footprints (war factory 3x2, barracks 2x2), units leave through the front row. Original art from the player's own Red Alert content (see LICENSES). |
| Destruction | 4 s Widelands fire sequence, production and orders stop at once, then collision, roads, workers, stock and logistics are released. |
| Command centres and MCV | Warehouse = immobile command centre (34 tiles). War factory builds an MCV from delivered wares (`log 3, plank 8, granite 5`); Deploy creates a 16-tile command centre; separation rule against every centre of every faction; the starter kit is the vehicle's cargo. God Mode: Deploy button, territory outlines. `tests/test_territory.py`, headed `run_hybrid_mcv.gd`. |
| Wizard labels and fire | Original label/resolver reused (`client/hybrid/wizard_labels.gd`): far click describes, near click offers fire; fire by stable id through the real lifecycles (`wizard_rts/magic.py`). `tests/test_fire_magic.py`, headed `run_hybrid_wizard.gd` with real mouse events. |
| Wizard movement | Steps chain without a stopped frame, light `pose` replies, camera sits on the wizard. |
| AI | Per-settlement economies, MCV expansion, supply-bottleneck response, navy planned ahead of the build gate, squads with retreat and retargeting, guard posts toward the nearest enemy, scouted targets, attack delay 12 minutes. Before (seed 507, checkpoint `6096997`): no movement or kills for 20 minutes, then four of six factions eliminated by minute 40, worst simulation step 15.7 s. After: all six alive at 40 minutes with 2-3 command centres each, ships built, kills on every side, worst step under 1 s on an idle machine. `docs/evidence/ai_report/`. |
| Stuck diagnostics | `diagnostics.py`: per entity tile, destination, task, path, progress, animation, cargo, blocked reason, stalled time. The only standing stall is the wizard's hazard on a road (a carrier waits for it, by design). |
| Training interface | `HybridEnv` gained Deploy, MCV and command-centre observations, expansion sites in the masks, a territory reward that pays for expansion; a numpy-only experiment and evaluation (`scripts/rl_experiment.py`, `docs/TRAINING_PROGRAMME.md`). Determinism now holds across processes (`tests/test_determinism.py`). |

Headed on Ubuntu: twelve scripts (`scripts/run_headed_suite.sh`): the nine of session 2 plus `playtest`, `wizard`, `mcv`. Python: see `docs/WORK_LOG.md` for the count.

## Session 2 additions (Ubuntu ThinkPad, 2026-10-10/11) - verified where stated

| Area | Status |
| --- | --- |
| Square-grid terrain (D5) | Works, default. `terrain.py`, `mapgen.py`, `grid.py`. 544x288 standard map (`small` 384x224, `large` 800x480), deterministic by seed. Classes, heights, build caps, shore depth, water bodies, resources with initial amounts. Python: `tests/test_terrain.py` (11). Headed: `run_hybrid_terrain.gd` passes on the T460 (Forward+): the Godot view matches the sim tile by tile on a sample, shots of water, mountain with deposits, farmland, overview, God Mode. |
| Real Widelands maps | `wl_map.py` reads `.wmf` maps (terrain v1/v2 with legacy names, heights, resources with initial amounts, start positions) and translates them to the square grid. Two six-player maps are shipped and run the full economy: `The_Big_Lake` and `Egyptian_Mandala_v1.2` (start with `HYBRID_MAP=wmf:The_Big_Lake`). Trees come from terrain rules, not from the map's object file. `tests/test_wl_map.py` (6). Two further maps with six or more players (Lesser Ring, Amoebae) were tried and removed: several starts are not joined by land or not buildable. |
| Six homelands | Each faction has a big meadow, a mountain with equal coal, iron, gold and stones, a lake and a grove; all six lakes join one inland sea by channels, and every capital reaches every other on foot (`tests/test_terrain.py`). |
| Terrain consequences | Buildings need the right buildcap (`water`, `unsuitable_terrain`, `no_mountain`, `no_deposit`, `no_rocks`, `no_fish` rejections), trees and fields grow on arable land only and die by `probability_to_grow`, mines follow `ActMine` (yield limit, `when_empty`), ground units use OpenRA locomotor speeds and cannot enter water, the wizard cannot enter water. |
| Fishing | Fisher huts (3 tribes) and the Atlantean fish breeder run on real fish: finite, weighted picks, bred back only up to the initial amount (`tests/test_fishing.py`, 4). Frisian ponds are not implemented. |
| Naval slice | Naval yard (OpenRA SYRD) and submarine pen (SPEN) are built on a 3x3 block of water beside the shore; patrol boat (PT) and submarine (SS) are paid for in delivered planks and iron and spawn on water; ships move on the naval locomotor only; torpedo, cannon and depth charge follow OpenRA target filters; submarines cloak, are found by DetectCloaked ranges, and surface for 2 s after firing; the AI builds yards and sends fleets. `tests/test_naval.py` (13). Headed `run_hybrid_naval.gd` drives it through the God Mode GUI. Ship and yard art are PLACEHOLDER shapes. Destroyer, cruiser, transport and missile submarine are shown locked with their reason. |
| Combat | Units carry every armament (not only the first), per-weapon cooldowns, OpenRA target-type filters on weapons and warheads. |

## Headed on Ubuntu (Forward+, Intel HD 520, 1280x720 window), end of session 2

`scripts/run_headed_suite.sh` passes all nine scripts: walk (a real land route), visual (the 1920x1080 shot is skipped on this screen: Windows), duel, forestry, food, god (real mouse events), war (marching, firefight, deaths, destroyed building, goods-fed production, all colours, 80 game minutes), terrain (the view equals the simulation tile by tile, deposits, wizard blocked by water), naval (God Mode GUI builds a yard on water, roads it, queues a boat paid in delivered goods, sails it, refuses a land order, fights). Python: 105 tests pass in about 7 minutes. Selected shots: `docs/evidence/ubuntu_selected/`, `docs/evidence/naval/`, `docs/evidence/maps/`. The laptop runs the terrain scene at about 7 fps with a full world; Windows frame rates are unmeasured.

## What works in play (all headed or tested)

| Area | Status |
| --- | --- |
| One continuous 20x20 hex world, wizard walk, retained Ward Duel | Works. `run_hybrid_walk.gd`, `run_hybrid_duel.gd`. Duel pauses `game_ms`; entity ids and pose are unchanged. |
| Forestry | Real. Lumberjack reserves a persistent old tree, walks (A*), chops 15 s, tree falls (felled sprite 30 s), log is carried home, a separate road carrier hauls it to the warehouse. Ranger walks to free ground, digs, plants, waters; saplings grow (55 s, 65 s, 72 s stages with death chances) into trees. `run_hybrid_forestry.gd`, `tests/test_forestry.py`. |
| Quarry | Stonemason cuts granite from a real rock that shrinks and disappears. |
| Mining | Coal and iron mines work finite 5x5 deposits (yield 33.33 %, when_empty 5 %) and each cycle eats one ration. |
| Food | Farmer plants and harvests wheat fields (growth stages); hunter kills real wild animals that wander and breed back; well draws a finite water field; bakery makes bread from wheat + water; tavern makes rations from bread/fish/meat. Headed `run_hybrid_food.gd`, `tests/test_food.py`. |
| Industry | Sawmill (source programme), smelting works (iron), ax workshop (ax). `tests/test_commands.py` follows an ax from ground to rifleman. |
| Logistics | Road graph, requests from warehouses, producer outputs pushed to warehouses, one carrier per road, wares conserved (seven wares tested over ten minutes). |
| Construction | Sites request their cost over roads, finish after 20 s. Roads built by command. |
| Recruitment | Barracks queue: rifleman = 1 ax, 30 s. War factory: tank = 2 granite + 1 plank, 30 s. Nothing is free; a queue with no goods stalls. |
| Combat | OpenRA numbers from `wizard_rts/data/openra_rules.json` (92 actors, 45 weapons): range, reload, burst, projectile flight, Versus armor, turrets. A Widelands soldier can fight OpenRA units and buildings. Buildings burn 4 s (Widelands fire sheet), then are removed with their roads. |
| Six factions | Red, Blue, Green, Yellow, Purple, Orange, each a full economy and army, colour rings (strategic dots when zoomed out). |
| AI | `wizard_rts/ai.py`: builds to a plan, repairs roads, queues recruits, defends, sends squads attack-moving. Personalities differ. Uses the same commands as God Mode. |
| Widelands import | `scripts/import_widelands_programs.py` parses all 237 buildings, 156 workers, 128 wares, 363 immovables, 16 critters from the Lua (no parse errors) into `wizard_rts/data/widelands_defs.json`. 138 production sites across the five tribes are **runnable on the generic interpreter**: each runs in an isolated bench (`scripts/verify_generic_buildings.py`, 138 of 138 make their wares or plant, recruit or breed), appears in the God Mode build menu under its tribe, and has imported art (1656 catalogue items). A worker role of any imported tribe works the same way. Supported: forestry, fields, rocks, game, mining, conversion. Not yet: fishing, water gathering by swimming, terraforming, breeding, scouting, ferries, military and training sites. |
| God Mode | Verified with real mouse events: `run_hybrid_god.gd` (button, faction, build, road, stock, barracks queue, box select, move, attack, back to Wizard Mode with pose and world unchanged). |
| Six-faction war | Verified headed: `run_hybrid_war.gd`; headless 30-minute multi-seed run with HTML report: `scripts/long_run.py`. |

## What is partial or missing

| Area | Reality |
| --- | --- |
| Food and ecology | No sheep or wool, no fisher, no gamekeeper, no cattle; animals have no diet or predators. |
| Marble, gold, bricks, tools | Not produced. |
| Logistics depth | No flags as objects, donkeys, priorities, rerouting around blocked roads (wares wait). |
| Construction | No builder worker; 20 s timer once wares arrive. |
| Workers | Hidden workers of mines, smelters and smithies are not entities. Worker training and assignment screens do not exist. |
| Military | No spread damage, formations, hierarchical pathfinder, aircraft, ships, veterancy, garrisons, patrol, repair. |
| AI | Cannot rebuild a mine (no prospecting), no repair. Expansion exists (MCV, up to three command centres); if the home warehouse falls a surviving outpost becomes the faction's capital, otherwise it is defeated. No fog of war beyond the scouting rule; no naval invasion. |
| Content coverage | Catalogue: 120 of 237 Widelands buildings and 70 of 131 wares tested in the bench (not yet in a headed play-through each); 58 production sites need unsupported commands; 59 military/training/warehouse/ship sites are not implemented; OpenRA 4 of 94 actors integrated. Only the hybrid core kinds have faction AI support. |
| Art | Terrain now uses Widelands textures per node (no transition blending yet); ships and naval yards are labelled placeholder shapes, not OpenRA sprites; faction colour is a ring, not a player-colour sprite remap; other tribes' sprites not imported; unit sprites reuse rifleman/tank/soldier for every faction. |
| God Mode UI | No per-worker, garrison or training panels; most original menus are unmapped (no menu catalogue yet). |
| Long run | 30-minute headless multi-seed run passes; a 30-minute headed run is not done. |

## Commands that must pass

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd
```

With the sim running on `HYBRID_SIM_PORT` (a fresh sim for each script): `run_hybrid_walk.gd`, `run_hybrid_visual.gd`, `run_hybrid_duel.gd`, `run_hybrid_forestry.gd` (`HYBRID_SPEED=4`), `run_hybrid_food.gd` (`HYBRID_SPEED=10`), `run_hybrid_god.gd`, `run_hybrid_war.gd` (`HYBRID_SPEED=20`). Expect `HYBRID_WALK_OK`, `HYBRID_VISUAL_OK`, `HYBRID_DUEL_OK`, `HYBRID_FORESTRY_OK`, `HYBRID_FOOD_OK`, `HYBRID_GOD_OK`, `HYBRID_WAR_OK`, `HYBRID_COORDS_OK 2424`. Long run: `py -3 WizardRTSHybrid/scripts/long_run.py --minutes 30 --seeds 507 11 23`. Regenerate data: `import_widelands_programs.py`, `import_openra_rules.py`, `import_assets.py`, `verify_generic_buildings.py`, `build_catalogue.py`.

## Evidence

`docs/evidence/walk`, `duel`, `gallery`, `forestry`, `food`, `god_mode`, `war`, `long_run/report.html`.

## Blockers

- **B1** Widelands source build: no C++ compiler / nmake. Lab only.
- **B2** OpenRA skirmish screenshot not saved. Engine builds.

## Next programme

Sheep and wool, fishers and gamekeepers, then marble/gold/bricks, flags and donkeys, a Lua importer so programmes come from the source instead of hand transcription, a menu coverage catalogue for God Mode, patrol and repair, AI prospecting and expansion, a headed 30-minute run with periodic shots, and the remaining tribes' art.
