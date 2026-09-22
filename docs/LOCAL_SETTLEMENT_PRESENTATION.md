# Local settlement / LocalArea presentation

**Status:** CANONICAL companion to [`CANONICAL_GAME_ONTOLOGY.md`](CANONICAL_GAME_ONTOLOGY.md).  
Applies to **every ordinary strategic node** (48×48), not only the starting village.

## Pipeline

```text
strategic node_id
    + touching hex directions / terrain
    + settlement buildings (if any)
    + incident roads vs trails
            ↓
LocalProjectionService.ensure_layout  (persisted geography)
            ↓
export_overworld_area                 (live people/carts/units)
            ↓
Godot Overworld presentation
```

## Rules

1. **Same footprint** for every ordinary strategic node (`BASE_SIZE` = 48).
2. **Primary / resource sites** occupy **perimeter sectors** from touching-hex orientation.
3. **Civic / processing / manufacturing** occupy the **built core** near map centre.
4. Primaries are **not houses** — terrain props for woodland/ridge/pits/fields.
5. **Exits** = every topology neighbour; **road art** only for constructed road edges.
6. **Occupation** is stable; **activity** is momentary. No Carrier identity.
7. Baseline `FX-VILLAGE` has **no active quest**. Archived: `FX-VILLAGE-QUEST`.

## Implementation

- `sim/dmb/world/prehistoric_world.py` — full board loader
- `sim/dmb/world/industry_bootstrap.py` — normal starting-core industry
- `sim/dmb/world/settlement_layout.py` — sector math / anchors
- `sim/dmb/world/projection.py` — LocalProjectionService schema v3
- `sim/dmb/world/overworld_export.py` — rows + entities for any node
