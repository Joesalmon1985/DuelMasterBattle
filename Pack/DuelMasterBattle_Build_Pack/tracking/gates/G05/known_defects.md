# G05 known defects

**Status:** repaired for AWAITING_HUMAN (playable Overworld host).

## Resolved in this repair

- `g05_shell.gd` now boots the Python sidecar and hosts production `overworld.tscn`
  with a Python-exported FX-VILLAGE area (Mara, factory, demon, sluice entrance).
- `run_g05_playable.gd` replaces the trivial `is_booted()` smoke; gate G05 requires it.
- Village Test Menu `DetailsContent/HeaderRow/IdLabel|NameLabel` paths fixed;
  FX-VILLAGE is a selectable Python-backed entry launching the same shell.

## Non-blocking / residual

- Ensemble-only commits noted under G04 remain a separate follow-up.
- Demon manifestation uses a cave-troll world sprite as a stand-in; identity is
  still `cube:demon` / StartHazardDuel lease (not a second Godot combat owner).
- Full authored sluice room art is a compact Overworld projection of mechanisms;
  puzzle state remains Python `PuzzleService` lease.
- Save/reload mid-duel checkpoint polish can still be exercised manually.
