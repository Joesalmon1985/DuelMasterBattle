# G05 known defects / notes — rockfall quest

**Status:** AWAITING_HUMAN — full board + simple rockfall quest

## Fixed this pass

| Item | Result |
|------|--------|
| Stale south-road collision after clear | Fixed via `Overworld.sync_dynamic_obstacle` on `_apply_world_layers` |
| Python Travel after clear | Already correct; unchanged |
| Godot walkability after clear | `run_g05_rockfall_walk.gd` + `test_rockfall_walkable.gd` |

## Remaining gaps (honest)

- Cleared stone pieces are non-solid (path usability first); optional aside-tile
  solidity can be added later without new quest logic.
- Full **LocalBattle** lease host inside Overworld is still less complete than
  standalone `g04_battle_shell`.
- World-map node dots remain schematic.

Do not expose internal IDs in ordinary player-facing labels.
