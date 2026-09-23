# Dungeon World Spatial Report

## Source

| Field | Value |
|-------|-------|
| Source branch | `phase/g06-g12-autoqa` |
| Source SHA | `1aa2205413db8c05a3fb879e647e65a7c8ad7f2f` |
| Source date | 2026-09-23 11:07:05 +0100 |
| Why selected | Newest legitimate development tip (G09 policy library); includes historic MVP world/board systems via ancestry. Not stale `main`. |
| Test branch | `test/full-board-dungeon-spatial` |
| Final SHA | `1bef86a` (fixture commit); branch tip via `git rev-parse origin/test/full-board-dungeon-spatial` |
| Spec followed | `docs/testing/WIZARD_DUNGEON_SPATIAL_SPEC.txt` |
| Architecture note | `docs/testing/DUNGEON_WORLD_ARCHITECTURE_NOTE.md` |
| Metrics JSON | `docs/testing/DUNGEON_WORLD_SPATIAL_METRICS.json` |

## Board

Production strategic board (not a mock):

| Metric | Value |
|--------|-------|
| Hex count | **19** (standard Catan radius-2 land board) |
| Node count | **54** |
| Edge count | **72** |
| Note on “17 hexes” | The task text asked for 17; this repository’s authoritative `DmbHexBoard` is **19** land hexes. The fixture uses the real board. |

### Settlements (seed 507)

| Faction | Node | Touching hexes |
|---------|------|----------------|
| wardens | 17 | 4, 12, 13 |
| levy | 14 | 3, 11, 12 |
| kilns | 8 | 1, 7, 18 |
| drovers | 1 | 0, 3, 4 |
| ironmoot | 19 | 5, 14, 15 |
| tithe | 3 | 0, 1, 2 |

All six are distinct factions on distinct nodes.

## Dungeon candidates

Fixture exaggerates coverage: for each settlement, every node belonging to hexes touching that settlement is evaluated.

| Settlement faction | Candidate count | Types observed |
|--------------------|-----------------|----------------|
| wardens | 12 | BR, GW, UB, WB |
| levy | 7 | BR, GW, UB, WB |
| kilns | 12 | BR, GW, UB |
| drovers | 1 | GW |
| ironmoot | 6 | GW, UB |
| tithe | 3 | BR, GW, WB |

- Total candidates: **41**
- Multi-type candidates: **25** (example: node 0 → GW+WB on forest+mountains+fields)
- Coastal (UB) uses topology: `node.hexes.size() < 3`, not screen edges
- Full dump: `docs/testing/dungeon_world_captures/board_dump.txt`

### Terrain mapping (production)

| Type | Terrain / rule | Production assigned? |
|------|----------------|----------------------|
| GW | forest | yes |
| BR | hills | yes |
| UB | coastal land node | yes (topology) |
| WB | mountains | yes |
| BG | — | **NO — unassigned** |

## Node size comparison (specimen node 0, GW, seed 507)

Reservation **53×32** (verified against PuzzleKit catalogue max room **15×13**).

| Profile | Fit | Dungeon % of tiles | Free tiles | Exits clear | Rooms reachable |
|---------|-----|--------------------|------------|-------------|-----------------|
| 65×49 | OK | **53.2%** | 1489 | yes | yes |
| 73×55 | OK | **42.2%** | 2319 | yes | yes |
| 81×61 | OK | **34.3%** | 3245 | yes | yes |

### Qualitative note

- **65×49**: mathematically fits, but the dungeon occupies over half the local map — exterior roads/settlement feel compressed.
- **73×55**: best balance for this experiment — clear exterior ring, readable approach, still walkable without feeling empty.
- **81×61**: most comfortable exterior, longest traversals; useful upper bound, not required for fit.

**Recommendation (evidence only — production unchanged):** prefer **73×55** for further design playtests of embedded five-room dungeons.

## Dungeon spec validation

| Design | Five rooms | Object labels | Mechanism labels | Wizard marker | 53×32 envelope |
|--------|------------|--------------|------------------|---------------|----------------|
| GW Rootbound Sanctuary | yes | yes | yes | yes | yes |
| BR Kiln Warrens | yes | yes | yes | yes | yes |
| UB Drowned Archive | yes | yes | yes | yes | yes |
| WB Ossuary Mine | yes | yes | yes | yes | yes |
| BG Rotgarden Vault | yes (test-only node) | yes | yes | yes | yes |

BG remains **unassigned** in production terrain maps (`TERRAIN_TO_TYPES` has no BG; shell “Test BG Rotgarden” is fixture-only).

## Embedded PuzzleKit result

- Specimen: node **0**, type **GW**, interactive kit room `embedded_gw_specimen`
- Reused **generic PuzzleKit kinds** (not five bespoke engines): ordered levers/sequence, item pickup, pressure plate + heavy drop, receptacle install, dynamic gate, NPC lines, goal tile
- Spec labels mirrored (`ITEM:item.gw.sun_seed`, `MECH:gw.channel_plate`, `GATE:gw.living_gate`, `WIZARD:wizard.gw.treefolk`, …)
- Flow: season levers → sun seed → channel plate (water) → install seed → living gate → Elder Court
- Known limitations: visual dressing is placeholder; only GW specimen is fully interactive; other types are geometric/label prototypes; fixture relocates `player_start` to the dungeon approach so the centred wild spawn cannot block the 53×32 reservation

## Production dungeon behaviour

- `DmbDungeonMap` / `dg_*` entrance loading **unchanged** and still covered by `run_dungeon_flow.gd` (PASS)
- `FORCE_DIMS` is fixture-only and cleared after projection
- Campaign `adventure.save` not written (`Adventure.test_mode`)

## Automated tests run

| Suite | Result |
|-------|--------|
| `sim/tools/run_tests.gd` (33 cases incl. new spatial) | **33 Passed, 0 Failed** |
| `client/tests/run_dungeon_flow.gd` | **ALL PASSED** |
| `client/tests/run_world_loop.gd` | **ALL PASSED** |
| `client/tests/run_puzzle_walk.gd` | **PASS** |
| `sim/tools/check_scripts.gd` | New fixture scripts compile; pre-existing failures remain in `run_fx_era_layout_capture.gd` and `run_g11_gallery.gd` (unrelated) |

## Screenshots

Headless session could not capture interactive Godot window pixels. Geometric evidence:

- `docs/testing/dungeon_world_captures/board_dump.txt`
- `docs/testing/DUNGEON_WORLD_SPATIAL_METRICS.json`

Manual screenshots for the handoff checklist should be taken from the playable launcher (TEST A–I).

## Launch

```bash
# Linux
cd /home/joe/Projects/DuelMasterBattle
DMB_SEED=507 DMB_RESOLUTION=450x800 ./tools/play_dungeon_world_test.sh
# or 720x1280
DMB_RESOLUTION=720x1280 ./tools/play_dungeon_world_test.sh
```

Windows: `Play Dungeon World Test.bat`
