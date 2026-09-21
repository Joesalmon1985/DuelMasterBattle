# G05 known defects / notes — visual integration

**Status:** AWAITING_HUMAN — full board + G01–G04 layers

## This checkpoint

| Item | Result |
|------|--------|
| Topology | Unchanged from `85fca3c` (19/54/72) |
| Quest | Still disabled; sluice helpers gated to FX-VILLAGE-QUEST |
| Carts | Faction accent + Catan cargo pips from `cargo_lots` |
| Soldiers | Geometric △■● with unit_id + person_id |
| Hazards | Existing catastrophe cubes exported; Challenge → retained duel |
| Industry | Factory meter bars from Python meters |
| Map | M opens read-only strategic map (pauses) |

## Remaining gaps (honest)

- Full **LocalBattle** lease host inside Overworld when stepping onto an active
  battle node is not as complete as standalone `g04_battle_shell` yet.
  Soldiers + READY battle state are present; animated lease combat is next.
- World-map node dots are schematic, not true board geometry for nodes.
- Processor recipe Inspect UI is data-ready (`industry_overlay`) but not a
  dedicated dialogue card yet.
- Dev-layers toggle panel is minimal (map reveal_all path exists; checkbox UI later).

Do not expose internal IDs in ordinary player-facing labels.
