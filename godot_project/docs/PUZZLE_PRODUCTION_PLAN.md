# Puzzle test mode → production runtime (correction plan)

## Where the two implementations diverge

PRODUCTION (campaign, `main`): `DmbPuzzleGen` records → `DmbPuzzleLogic.act`
→ `DmbDungeonMap.area_for` projection → `overworld.tscn` renders kinds
(fire/pickup/creature/wizard/npc/corpse/sign/door/logs/trigger/exit) with real
pixel art → `WorldPlay.interact_puzzle` (real dialogue/items/spells, real
battle via `start_battle_request`, `rebuild()`) → state in
`Adventure.puzzle_state("dungeon/puzzle")`.

BRANCH (`puzzle-system-pass`): `DmbPuzzleRooms` (50 data-only rooms) +
`DmbPuzzleKit` (rich logic: levers/plates/receptacles/beams/pits/teleports/
hazards/sequences/throw/npc/critter/guardian/choice) → rendered by a PARALLEL
mini-runtime (`puzzle_test_room.tscn/gd`: coloured rectangles, green-`P`
player, own movement/inventory/interaction/HUD, fake battle text).

Same concept (data-driven puzzle → area → play), two renderers, two
controllers, two inventories. The kit vocabulary is a strict superset of the
8 production templates; the old templates serve only campaign dungeons (not
the same puzzles → no conflict, leave them alone).

## Architecture after (smallest clean unification)

`DmbPuzzleRooms` + `DmbPuzzleKit` = ONE authoritative logic (sim layer owns
rules + visual-state description). NEW `DmbPuzzleProjection` (sim layer):
kit room + kit state → overworld-compatible area dict (mirrors
`DmbDungeonMap.area_for`). `WorldPlay` gains `puzzle_area()` +
`interact_kit_puzzle()` + `on_kit_step()`; `overworld.gd` gains generic hooks
only (puzzle-area branch in `load_area`, kit step call, one new `deco`
visual-only entity kind, `Adventure.test_mode` suppressing `save()`).
No puzzle-ID-specific logic anywhere outside room data.

> The puzzle test launcher is a bootstrap into production gameplay, not a
> separate puzzle runtime. Human playtesting must use the same renderer,
> controller, Adventure state and puzzle implementation used by the campaign.

## Phases

1. Projection: `sim/world/puzzle_projection.gd` (rows→dungeon tiles, entities
   → sign/door/logs/pickup/npc/creature/deco/exit via `Kit.visual()` state).
2. Runtime hooks: `load_area` puzzle branch, `is_walkable` agreement,
   `on_kit_step` (relocate/wound/battle/solved), `interact_kit_puzzle`
   (actions_for → dialogue choose → Kit.act → consume/grant/learn/relocate/
   real battle → rebuild), `deco` kind, goal-reached solved flow, Drop/Throw
   UI for plates/gaps, kit `tick` hook if hazards need it.
3. Bootstrap: menu → fresh disposable Adventure (`test_mode`, seed items/
   spells, set location) → `overworld.tscn`; pause menu gains
   Reset / Puzzle-menu; campaign save untouched (save() no-op + restore on
   exit). Delete `puzzle_test_room.tscn/gd` (+runner if unused). Keep
   menu + bat. Label `room_shots/` sim-debug output as such.
4. Tests `client/tests/run_puzzle_production.gd`: A launcher→overworld,
   B real John textured, C production tile/entity layers, D scene action
   mutates kit state, E visual transitions (gate/plate/receptacle/sequence/
   hazard/teleport/item), F real battle round-trip, G reset, H all 50 load.
5. QA: scripted-in-production walkthroughs + REAL viewport captures
   (initial/mid/solved) for a mechanical spread; .bat left ready for human.

## Open decisions (defaults I'll take unless told otherwise)

- Save isolation: `Adventure.test_mode` flag → `save()` no-op; exit restores
  campaign via `load_game()`. (Alternative: backup/restore save file.)
- Goal tile: reached → solved dialogue offering Replay / Puzzle menu / Next.
- Throw/Drop: inventory sheet gains Drop (puzzle areas only); Throw via
  facing-direction prompt where a room needs it.
- Screenshots: attempt real `Viewport.get_texture().get_image()` captures
  windowed; if the sandbox has no GL, say so plainly. No Pillow-as-proof.
