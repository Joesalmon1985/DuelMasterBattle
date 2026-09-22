# Ontology + full Prehistoric world (G05)

**Branch:** `refactor/canonical-ontology-g05`  
**Gate:** G05 = **AWAITING_HUMAN** (full-board exploration; **no active quest**)  
**Do not start T097.**

## What landed

| Area | Result |
|------|--------|
| Ontology | Person↔Unit; no presentation-minted People; one actor |
| Board | `load_prehistoric_world` — 19/54/72 |
| LocalArea | 48×48 via `LocalProjectionService.project_node` |
| Industry | Normal C04/C06 bootstrap; industrial catalogue IDs |
| Quest | Disabled in baseline; `FX-VILLAGE-QUEST` archived |
| Travel | Automated BFS reaches all 54 nodes |

## Play

```bash
bash tools/play_g05.sh
```

Start: `node:35` / `settlement:3` (seed 507).

## Acceptance

Joe walks the board; agents do not self-PASS.
