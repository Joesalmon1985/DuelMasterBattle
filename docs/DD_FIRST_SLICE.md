# Dungeon Run + First Slice (P2: Zones A, B, D through the Cave Trolls)

Implements the run model from [DEATHTRAP_OVERHAUL_PLAN.md](DEATHTRAP_OVERHAUL_PLAN.md)
§4.1–§4.3 and the first playable Deathtrap slice (report §20): entrance → fork →
galleries → pit → lower route. Fire comes from the red book; Stone waits for the
Dwarf's test (P3).

## Run model (`adventure.gd`, save v2)

- Permanent: spells, weave, world flags, `dungeon_knowledge` (area → seen/entered).
- Per-run (`state["run"]`): area/pos, visited, inventory, gems, conditions,
  contestants, run flags, fights.
- `start_run()` → Crystal Entrance. `fail_run(reason)` → knowledge upgrades to
  entered, run fights un-marked as defeated (re-fightable), everything else
  wiped, John wakes at the Trial gate. Old v1 saves migrate (run null, knowledge
  empty).
- Dungeon pickups use `"run_pickup": true` (tracked as run flags, so Fire and the
  ring come back next attempt; `learn_spell`/`grow_weave` are idempotent).
- Run flags: `adv.set_run_flag` / `run_flag`; entities gate on
  `"requires_run_flag"`; NPCs switch lines via `"lines_run_flag"`.

## Conditions → duels

`adv.player_mods()` maps conditions (John only): wounded −1 max cast each
(floor 6 of 10), poisoned +2s min cast, slowed −10s max window. The overworld
attaches them to `pending_battle["player_mods"]`; `game_board` applies them to
John's combatant. Sources in this slice are all player-chosen: pit jump
(wounded), black-book vial (poisoned).

## Zones

| Area | Passages | Contents |
|---|---|---|
| `dd_entrance` | 1, 270 | aid box (run pickup, Sukumvit note), stone table, crystal sign |
| `dd_fork` | 66, 119 | painted arrow, footprint evidence, east alcove fly + looted box |
| `dd_galleries` | 293, 382 | statue riddle (any answer continues; correct answer unverified), petrified Knight, bell, chest, torch, guard dog |
| `dd_pit` | 154, 22, 184 | Throm + pit choice (lower / lower-him→join-or-betray / jump) as run flags; contestant states ahead→uneasy_ally/betrayed |
| `dd_lower` | 194, 138, 52, 169, 288 | red book (Fire, weave 2), black book vial, Throm, Cave Troll duel, bone ring, dwarfish door (P3 tease, no exit) |

Losing any dungeon battle calls `fail_run` and reloads the gate (report §13:
fast restart, notes kept). Throm's betrayal *state* is implemented; p.149 stays
`NEEDS_PAGE_IMAGE_CHECK` and builds no content on it.

## Engine additions

- NPC/pickup `"choice_event"` → story event after lines/text (uses the existing
  `choose_async` dialogue; test drives with `ui_dialogue_choose`).
- `"on_win_run_flag"` on enemies (troll → `troll_down`, Throm → wounded).
- sign/door/logs now block movement (physical; also makes `_face` turn instead
  of stepping onto them). Test BFS routes around exits via `ui_is_exit`
  (stepping on one mid-path triggers travel).
- Bestiary: `guard_dog` (1-slot Water), `cave_troll` (2-slot Fire/Water);
  art via `tools/build_pixel_assets.py` (+ dog, troll, box, red/black books, ring).

## Tests

- `sim/tests/test_trial_run.gd` — start/fail/resume, reset-vs-kept semantics,
  v1→v2 migration, condition→mods mapping.
- `tools/run_dungeon_flow.sh` — entrance → fork → fly → galleries → riddle →
  torch → dog → pit choice → lower → Fire → poison → mods-in-request → rigged
  troll loss → gate restart (knowledge/spells kept, fights+pickups reset) →
  second run → troll win → ring. Also in `run_all_checks.sh`.
- Headed captures 11d–11f (entrance, pit, books).
