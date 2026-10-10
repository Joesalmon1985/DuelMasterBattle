# State of play — WizardRTSHybrid

Branch `feature/wizard-rts-hybrid-v02`. This is an honest inventory of what you can launch and play, what is only scaffolding, and what is missing. A sprite on screen is not a feature; the feature catalogue (`docs/feature_catalogue.json`, rebuilt by `scripts/build_catalogue.py`) counts functionality, not files.

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
| Combat | OpenRA numbers from `wizard_rts/data/openra_rules.json` (92 actors, 45 weapons): range, reload, burst, projectile flight, Versus armor, turrets. A Widelands soldier can fight OpenRA units and buildings. Buildings burn 15 s, then are removed with their roads. |
| Six factions | Red, Blue, Green, Yellow, Purple, Orange, each a full economy and army, colour rings (strategic dots when zoomed out). |
| AI | `wizard_rts/ai.py`: builds to a plan, repairs roads, queues recruits, defends, sends squads attack-moving. Personalities differ. Uses the same commands as God Mode. |
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
| AI | Cannot rebuild a mine (no prospecting), no repair, no expansion or new settlements. A faction whose warehouse falls does not come back. |
| Content coverage | 8 of 237 Widelands buildings and 6 of 131 wares tested; see the catalogue. Importer for Lua programmes is not written. |
| Art | Terrain is one meadow tile; faction colour is a ring, not a player-colour sprite remap; other tribes' sprites not imported; unit sprites reuse rifleman/tank/soldier for every faction. |
| God Mode UI | No per-worker, garrison or training panels; most original menus are unmapped (no menu catalogue yet). |
| Long run | 30-minute headless multi-seed run passes; a 30-minute headed run is not done. |

## Commands that must pass

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd
```

With the sim running on `HYBRID_SIM_PORT` (a fresh sim for each script): `run_hybrid_walk.gd`, `run_hybrid_visual.gd`, `run_hybrid_duel.gd`, `run_hybrid_forestry.gd` (`HYBRID_SPEED=4`), `run_hybrid_food.gd` (`HYBRID_SPEED=10`), `run_hybrid_god.gd`, `run_hybrid_war.gd` (`HYBRID_SPEED=20`). Expect `HYBRID_WALK_OK`, `HYBRID_VISUAL_OK`, `HYBRID_DUEL_OK`, `HYBRID_FORESTRY_OK`, `HYBRID_FOOD_OK`, `HYBRID_GOD_OK`, `HYBRID_WAR_OK`, `HYBRID_COORDS_OK 2424`. Long run: `py -3 WizardRTSHybrid/scripts/long_run.py --minutes 30 --seeds 507 11 23`.

## Evidence

`docs/evidence/walk`, `duel`, `gallery`, `forestry`, `food`, `god_mode`, `war`, `long_run/report.html`.

## Blockers

- **B1** Widelands source build: no C++ compiler / nmake. Lab only.
- **B2** OpenRA skirmish screenshot not saved. Engine builds.

## Next programme

Sheep and wool, fishers and gamekeepers, then marble/gold/bricks, flags and donkeys, a Lua importer so programmes come from the source instead of hand transcription, a menu coverage catalogue for God Mode, patrol and repair, AI prospecting and expansion, a headed 30-minute run with periodic shots, and the remaining tribes' art.
