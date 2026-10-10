# State of play — WizardRTSHybrid

Last verified commit: `52fc8ea` on `feature/wizard-rts-hybrid-v02` (merged to `main` when this note ships).

This is an honest inventory of what you can launch and enjoy today, and what the next programme still has to build. Imported sprites are not full Widelands or OpenRA gameplay.

## How to launch

From `WizardRTSHybrid`, start one simulator:

```
$env:HYBRID_SIM_PORT = "8765"
py -3 -m wizard_rts.server
```

From the repo root, in a second window (Godot 4.5.1, Forward+ required for screenshots):

```
godot --path godot_project --rendering-method forward_plus res://client/scenes/hybrid_world.tscn
```

Or use `WizardRTSHybrid/scripts/launch_hybrid.ps1` if `GODOT` or `.dmb_windows_local.json` is set.

Controls: WASD / arrows. Space / Enter / Z / E next to the purple hazard opens the retained Ward Duel. Restart the simulator before a clean walk or duel. Only one process may own port 8765.

## What works in play

| Area | Status |
| --- | --- |
| Continuous 20×20 hex world, wizard walk, camera follow | Works. Headed walk crosses 20 hexes. |
| Autonomous game clock while idle | Works. Five-minute smoke: produce and deliver counters move. |
| Retained Ward Duel from the route hazard | Works. Pauses `game_ms`, one outcome, pose restored. |
| Widelands-derived warehouse stock list | Works for counts. |
| OpenRA-derived unit / building damage math | Unit HP in combat; buildings have `hp` and `damage_building`. |
| Imported Widelands + OpenRA sprites on the red settlement | Visible in play. Gallery: `docs/evidence/gallery/`. |
| Shared building health fields | In sim and snapshot; health bar draws when HP &lt; max. |

## What is only partial

| Area | Reality |
| --- | --- |
| Economy | Logs are still minted on a timer. No real tree chop. Carrier unloads incorrectly (warehouse credit at processor end of one polyline). |
| Military | `order` op: a tank/infantry/soldier walks to an enemy building and fires through `damage_building`; at 0 HP the producer/processor stops. Weapon table and greedy movement are provisional. Godot has no click-to-order UI yet. |
| Factions | Two (Red / Blue), not six. |
| Terrain | Repeated meadow tiles. No deposits, water, snow rules, or placement constraints. |
| God Mode | Not in the HUD. No launcher with Wizard / God entry. |
| Refinery | Still placed in the default showcase; exclusion from hybrid rules is planned, not done. |
| Full civilian / military content | Feature catalogue and dual-mode launcher from the full programme are not implemented yet. |

## Tests that currently pass

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd
```

With the sim running:

```
godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_hybrid_walk.gd
godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_hybrid_visual.gd
godot --path godot_project --rendering-method forward_plus --script res://client/tests/run_hybrid_duel.gd
```

Expect `HYBRID_WALK_OK`, `HYBRID_VISUAL_OK`, `HYBRID_DUEL_OK`, `HYBRID_COORDS_OK 2424`.

## Evidence

- Walk: `docs/evidence/walk/`
- Duel: `docs/evidence/duel/duel_open.png`
- Mashup review: `docs/evidence/gallery/REVIEW.md`
- Asset provenance: `godot_project/client/hybrid/art/catalogue.json`, `docs/LICENSES.md`, `docs/ASSET_INVENTORY.md`

## Blockers

- **B1** Widelands source build: no C++ compiler / nmake. Lab only; play does not need it.
- **B2** OpenRA skirmish screenshot not saved. Engine builds.

## Next programme (not done)

Approved order: feature catalogue → dual-mode launcher → terrain → Widelands worker programs → logistics → goods-fed OpenRA recruitment → six factions → God Mode UI → endurance tests. See the Cursor plan `hybrid_gameplay_programme` and `docs/CLAUDE_HANDOFF.md`.

Immediate next coding task: Godot click-to-order UI for the `order` op, then the feature catalogue and dual-mode launcher.
