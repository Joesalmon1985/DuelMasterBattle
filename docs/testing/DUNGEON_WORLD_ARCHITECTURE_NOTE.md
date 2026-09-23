# Full-board dungeon spatial test — architecture note

## Source

- Branch tip selected: `phase/g06-g12-autoqa` @ `1aa2205413db8c05a3fb879e647e65a7c8ad7f2f` (2026-09-23)
- Newest legitimate development line (G09 policy library); includes historic MVP world systems via ancestry.
- Test branch: `test/full-board-dungeon-spatial`

## Board authority (production)

| System | Class / file | Notes |
|--------|----------------|-------|
| Strategic hex board | `DmbHexBoard` → `godot_project/sim/world/hex_board.gd` | **19** land hexes (radius-2 Catan), **54** nodes, **72** edges. Not 17. |
| World sim | `DmbWorldSim` → `world_sim.gd` | Snake setup places **6** faction settlements + roads; seeds dungeon towers. |
| Factions | `DmbFactions` → `factions.gd` | wardens, levy, kilns, drovers, ironmoot, tithe |
| Catan state | `DmbCatanState` → `catan_state.gd` | settlements, roads, reserved nodes |
| Local maps | `DmbSettlementLayout` + `DmbNodeProjection` | Wild 17×13; steading 49×37–73×55; town 81×61–113×85 |
| Production dungeons | `DmbDungeons` + `DmbDungeonMap` | Separate `dg_*` areas entered via door (loading transition) |
| PuzzleKit | `DmbPuzzleKit` + `DmbPuzzleRooms` + `DmbPuzzleProjection` | Catalogue rooms max **15×13**; Overworld kit session already exists |
| Client bridge | `WorldFlow` + `WorldPlay` + `overworld.gd` | Real node travel via `wn_<nid>` |

## Coastal rule (topology, not screen)

A node is coastal when `board.nodes[nid].hexes.size() < 3` (perimeter of the land mass toward the surrounding sea). Matches existing hex-board tests (18 one-hex + 12 two-hex coast nodes).

## Terrain → wizard dungeon candidates (fixture)

| Terrain / condition | Dungeon |
|---------------------|---------|
| forest | GW Rootbound Sanctuary |
| hills | BR Kiln Warrens |
| coastal land node | UB Drowned Archive |
| mountains | WB Ossuary Mine |
| BG Rotgarden | **no production mapping** — test-only load |

## Fixture-only additions

- `wizard_dungeon_spec.gd` — structured copy of `WIZARD_DUNGEON_SPATIAL_SPEC.txt`
- `dungeon_world_fixture.gd` — candidates, metrics, fit validation
- `embedded_dungeon.gd` — stamp 53×32 reservation + rooms into a node area (no `dg_*`)
- `dungeon_world_test` scene — launcher shell, strategic debug, size profiles
- `DmbSettlementLayout.FORCE_DIMS` — temporary size override; cleared on reset

Production `dg_*` dungeon loading is **not** removed or replaced.
