# G05 known defects / notes — full Prehistoric world

**Status:** AWAITING_HUMAN — full-board exploration (no active quest)

## This checkpoint

| Item | Result |
|------|--------|
| Board | 19 hexes / 54 nodes / 72 edges from normal prehistoric loader |
| LocalArea | 48×48 for every ordinary strategic node |
| Quest | Disabled in baseline; `FX-VILLAGE-QUEST` archived |
| Settlements | Shared `project_node` projector; ≥2 visitable cores |
| Roads vs trails | Passage from authoritative road edges only |
| Industry | Normal C04/C06 starting-core bootstrap; industrial catalogue IDs |

## Known limitations (non-blocking)

- Soft-contiguous countryside between nodes still discrete LocalArea loads on Travel
- Settlement display names are provisional (`Settlement F-N`); place-naming later
- City density variant not yet authored beyond settlement occupancy
- Industry worker actors are presentation-bound via WorkerController (not static area NPCs)
- Decorative housing density still light outside the civic core

Do not expose internal IDs in ordinary player-facing labels.
