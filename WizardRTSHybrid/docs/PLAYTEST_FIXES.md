# Playtest fixes (branch `feature/hybrid-playtest-fixes-v03`)

Source: Joe's first substantial manual playtest of the Ubuntu checkpoint `6096997`. A passing test suite had not caught any of
these, so every fix below has a regression that looks at what the player sees (a headed Godot test with screenshots) as well as
the simulation. Nothing was rewritten: the Python `HybridWorld`, the Godot client, the Widelands economy, the OpenRA military,
the six factions, God Mode, Wizard Mode and the Ward Duel are the same code with these changes.

Evidence: `docs/evidence/playtest/` (headed shots), `docs/evidence/wizard/`, `docs/evidence/ai_report/` (AI runs). Test commands are in
the last section.

## The nine observations

### 1. Workers skip from tile to tile; carried wares are invisible

- **Root cause.** The renderer interpolated with the `move_progress` value of the *latest* snapshot only. Godot polled the simulation
  at up to 10 Hz with a 614 KB JSON reply (about 90 % of it static trees), so on the laptop it ran at about 7 fps with a blocking
  round trip in the frame. Carriers had no progress field at all, so they teleported one tile every 500 ms. Nothing drew a ware
  except the log in a lumberjack's hands, because only one ware sprite had ever been imported.
- **Fix.**
  - A presentation-only motion layer (`hybrid_art.gd: begin_frame, _motion`): each worker, carrier, animal and unit has a visual
    position that glides towards its authoritative tile (or the interpolated position between two tiles) at the speed the snapshot
    reports (`move_ms`), never more than half a tile per frame, snapping only after a teleport (> 4 tiles). The simulation is untouched
    and keeps its grid, four directions, collision and pathfinding. Facing comes from the direction of travel.
  - The poll is 0.2 s, not every frame, and the reply is a *delta*: trees and rocks (changed ones only) travel separately
    (`HybridWorld.tree_delta`), 614 KB becomes about 120 KB (`entity_ids` is only sent to clients that ask). `pose` replies are light.
  - All 128 Widelands wares plus `plank` were imported from `data/tribes/wares` (`scripts/import_ware_art.py`, catalogue ids
    `widelands.ware.<ware>`). A worker's `carrying` and a carrier's `cargo` are drawn above the figure with that ware's own picture.
- **Files.** `godot_project/client/hybrid/hybrid_art.gd`, `godot_project/client/scenes/hybrid_world.gd`, `wizard_rts/world.py`,
  `wizard_rts/server.py`, `scripts/import_ware_art.py`, `godot_project/client/hybrid/art/*`.
- **Tests.** `run_hybrid_playtest.gd` (worst per-frame step 0.44 tile for workers and carriers, no figure faster than half a tile per
  frame, several figures glide over 10+ frames, every carried ware has its own sprite, plank and log differ).

### 2. Trees are chopped but remain standing; no visible growth

- **Root cause (rendering, not simulation).** `hybrid_art.gd _item_for` returned `items[definition]` for any tree whose
  definition existed (`widelands.beech` is the *mature* picture) *before* it looked at the stage. Every sapling, pole, old tree and
  felled tree was drawn as the same full tree, so a felled tree "remained". The simulation was correct: the felled stage lasts 30 s,
  then `remove_tree`, one log, a separate carrier (`tests/test_forestry.py` already followed it).
- **Fix.** The stage sprite always wins (`beech_sapling/pole/mature/old`, `fallentree`); the generic picture is only the fallback.
- **Tests.** `run_hybrid_forestry.gd` now follows the same tree entity and asserts the sprite the renderer *selects* at each stage
  (old while chopped, fallen tree when felled, gone afterwards, `_sapling.png` when planted, `_pole.png` when grown), not just stocks;
  `run_hybrid_playtest.gd` checks every beech stage maps to its own file.

### 3. War factory sprite oversized, with a black rectangle

- **Root cause.** OpenRA draws a WEAP as the `idle` frame of `weap.shp` (the base, with the bay left open and black) *plus* the
  `WithProductionDoorOverlay` frames `build-top` from `weap3.shp` laid over it. The first import kept only the base. It was also drawn
  at three screen pixels per source pixel (a cell is 24 px, a tile 64 px: 12 % too big) on a single blocked tile, and the picture
  alternated between `idle` and `damaged-idle` once a second (a two-frame loop meant for damage).
- **Fix.** `weap3.shp` (in `mods/ra/bits`) is decoded with a new SHP reader (`scripts/shp_td.py`, checked against the earlier
  extraction: identical pixel counts) and added as `weap-top-0000..0009.png`. The building is drawn as base + door (closed while idle,
  opening and closing while a tank is being built; frame 1 only below 50 % HP), one source cell per tile, on a **real footprint**:
  the war factory blocks a 3x2 area and the barracks a 2x2 (`construction.GROUND_FOOTPRINT`, also for the starting buildings);
  roads and carriers use the door tile (bottom middle) and units leave through the row in front of it. Ring and health bar are sized to
  the footprint; God Mode picks by footprint.
- **Files.** `scripts/import_openra_overlays.py`, `scripts/shp_td.py`, `hybrid_art.gd _draw_footprint_building`, `construction.py`,
  `world.py`, `lifecycle.py`, `god_mode.gd`.
- **Tests.** `tests/test_playtest_fixes.py` (footprints for all six factions, exit tile in front), headed `weap_idle_door_closed.png`.

### 4. Workers walking on the spot in front of buildings

- **Investigation.** `diagnostics.py` records, for every worker, carrier and unit, the tile, destination, task, path, progress,
  animation, cargo, blocked reason and time without progress (`stuck_report`). Over 60 game minutes of peace no worker was ever walking
  without changing tile. 184 of 227 carriers were idle, and one was blocked by the wizard's hazard sitting on a road (reported with that
  reason).
- **Root cause.** Presentation again: the sheet animator advanced walking frames from the wall clock whenever a sprite had a frame
  rate, regardless of state, so every idle carrier and every worker waiting at a door played the walking loop in place.
- **Fix.** A figure that is not moving shows a still frame (`_static`); working animations (`hack`, `dig`, `plant`...) still play.
- **Tests.** `run_hybrid_playtest.gd` ("idle carriers show a still frame"); the stuck report is part of the AI report
  (`stuck_final`) and the AI behaviour test.

### 5. Territory cannot be expanded

- **Design (see `DECISIONS.md` D7).** The first warehouse of each faction is its immobile command centre and sets a build square of
  34 tiles. The war factory builds an **MCV**: a recipe of delivered wares (`log 3, plank 8, granite 5` in total, of which the vehicle
  needs `plank 6, granite 4` and the rest is the starter kit it carries). It is a real queue item, a unit that walks with the normal
  pathfinder, can be selected, commanded and destroyed, and has a **Deploy** command (God Mode button, `deploy` op, AI). Deploying
  consumes it exactly once and creates a command centre (Construction Yard art, a warehouse in the simulation) with a 16-tile build
  square whose store receives exactly the vehicle's cargo: nothing is teleported.
- **Separation.** A centre may only be deployed where `Chebyshev distance > radius_new + radius_other + buffer` for **every** centre of
  any faction (friendly and enemy), buffer 4 (`HybridWorld.cc_buffer`). Also checked: map bounds, ground terrain and build caps for
  the whole 3x3 footprint, trees, roads, units in the way, a free access tile.
- **Economy of an outpost.** An outpost is its own logistics island (roads connect buildings to its command centre; carriers work
  there; wares are never moved between islands). The AI builds woodcutters, foresters, a sawmill, a quarry and a turret there.
- **Files.** `wizard_rts/territory.py`, `construction.py`, `world.py`, `ai.py`, `server.py`, `god_mode.gd` (Deploy, territory outlines).
- **Tests.** `tests/test_territory.py` (production only from real deliveries with exact ware accounting, deploy consumes the unit once,
  friendly/enemy overlap, terrain, boundary, obstacles, territory follows the new centre, a remote settlement builds and ships goods).

### 6. Destroyed buildings stay too long

- **Root cause.** `lifecycle.RUIN_MS = 15 000` and the renderer showed the ordinary building sprite.
- **Fix.** `lifecycle.begin_destruction`: at 0 HP the building is marked `destroyed`, production and queued orders stop at once, the
  Widelands `destroyed_building` fire sheet plays (OpenRA structures keep their darkened picture with the same fire) for 4 s, then
  `purge_building` releases collision, roads, carriers, worker, stock and logistics, and the AI sees the loss.
- **Tests.** `tests/test_playtest_fixes.py::test_destruction_lifecycle_four_seconds`, headed `building_burning.png`.

### 7. Inert AI

See "AI diagnosis" below.

### 8. Jerky wizard

- **Root cause.** The Overworld step loop ended each tile on a stopped frame and discarded the left-over time; `_arrived()` then did a
  blocking `pose` round trip that returned the whole world; the camera followed a stuttering position.
- **Fix.** The next tile starts in the same frame with the leftover time carried over (`overworld.gd`), `pose` is a light call, polling
  is a delta. Authoritative position, collision, the duel and mode switches are unchanged.
- **Tests.** `run_hybrid_playtest.gd` (121 frames, 21 tiles, 0 stalled frames, largest step 28 px against 32 px allowed for the longest
  frame, camera lag 0).

### 9. Wizard interaction labels

- **Reuse.** `client/world/world_interaction_label.gd` and `sim/world/world_interaction_resolver.gd` are used unchanged with the same
  semantic contract. `client/hybrid/wizard_labels.gd` binds them to hybrid entities. A few salient entities near the wizard carry a
  passive label (at most six, trees only within 3 tiles); a click on any entity opens its label: far shows the description
  (OBSERVATION), within 3 tiles it speaks and offers "Burn it with fire magic" (RESPONSES).
- **Fire magic.** `wizard_rts/magic.py`, op `fire` by stable id, range re-checked from the authoritative player tile. Buildings
  take lethal damage through the normal path (burning, removal, logistics); units die through `kill_unit`; workers through
  `worker_abort` (carried ware lost, hut replaces them after 30 s); carriers through `kill_carrier` (road gets a new one after 20 s);
  trees through `remove_tree` (a lumberjack that reserved it gives up); rocks and animals are removed with their reservations.
- **Tests.** `tests/test_fire_magic.py`, headed `run_hybrid_wizard.gd` (real mouse events).

(Numbering in the playtest message: items 1 and 8 of this list are its items 1 and 8; the message's 9 interaction items are 9-10 of
the programme text.)

## Performance found on the way

A long war run had single simulation steps of up to 8.9 s (an army's first marches: hundreds of unshared A* searches) which would
have frozen the client and exceeded its 4 s reply timeout. Now: shared routes for units with the same goal, one full search per
quantum (deterministic count budget), an integer-indexed A*, bounded failed road searches with cool-downs, and a coarser
expansion-site sweep. Worst step in 25 game minutes of war: 0.34 s.

## Test commands

```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
WizardRTSHybrid/scripts/run_headed_suite.sh            # all headed scripts, including playtest, wizard, mcv
python3 WizardRTSHybrid/scripts/ai_report.py --minutes 40 --seeds 507 11 23
```
