# Local settlement presentation

**Status:** CANONICAL companion to [`CANONICAL_GAME_ONTOLOGY.md`](CANONICAL_GAME_ONTOLOGY.md).  
Implements the Village Foundation spatial grammar.

## Pipeline

```text
strategic node
+ touching hex directions
+ actual settlement / buildings
            ↓
persisted LocalArea (schema v2)
            ↓
perimeter resource sites
+ built core
+ internal paths
+ strategic exits
```

## Rules

1. **Primary / resource sites** occupy **perimeter sectors** derived from the
   orientation of their touching strategic hex relative to the node.
2. **Civic / processing / manufacturing** occupy the **built core** near map centre.
3. Primaries are **not houses**. Presentation uses terrain props (trees, rocks,
   logs, open ground) — never ordinary wall/roof/door footprints.
4. Worker routes are illustrative, but **waypoints must come from real site
   entrances** on that spatial grammar.
5. **Occupation** is the stable player-facing job label; **activity** is what
   they are doing now. Never brand a person as “Carrier” merely for carrying.
6. Fixtures may arrange healthy baseline (`FX-VILLAGE`) or shortage quest
   (`FX-VILLAGE-QUEST`). Presentation must not invent quest landmarks in baseline.

## Implementation

- `sim/dmb/world/settlement_layout.py` — sector math, anchors, occupation/dialogue helpers
- `sim/dmb/world/fx_village_world.py` — applies grammar when building FX village
- `sim/dmb/world/overworld_export.py` — primary vs structure drawing; baseline dialogue
- Local projection schema version **2**

Do not regress primary extraction sites into generic houses.
