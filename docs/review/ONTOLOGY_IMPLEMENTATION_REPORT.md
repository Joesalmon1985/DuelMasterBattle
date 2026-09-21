# Ontology + Village Foundation implementation report

**Branch:** `refactor/canonical-ontology-g05`  
**Starting ontology tip:** `b418d5dcbe1c1895a876f92b2c0178ac62c4fe55`  
**This pass:** Village Foundation / common-sense presentation

## Checkpoint

G05 = **FIX_REQUIRED** (Village Foundation sanity check).  
Quest remains **disabled** in `bash tools/play_g05.sh` (`FX-VILLAGE` baseline).  
Quest preserved as **`FX-VILLAGE-QUEST`**. Do not start T097.

## Decisions implemented (this pass)

| Item | Status |
|---|---|
| Healthy baseline village launch | done |
| Quest behind FX-VILLAGE-QUEST | done |
| No quest contamination in ordinary dialogue | done |
| Canonical `public_occupation` | done |
| Primaries ≠ houses | done |
| Perimeter sources from touching-hex orientation | done |
| Built-core civic/industry packing | done |
| Humanoid display-height normalisation | done |
| Presentation-only worker rhythm pauses | done |
| `docs/LOCAL_SETTLEMENT_PRESENTATION.md` | done |

## CONCEPT | OLD | NEW | STATUS

| CONCEPT | OLD | NEW | STATUS |
|---|---|---|---|
| FX-VILLAGE | Always shortage quest | Healthy baseline | done |
| FX-VILLAGE-QUEST | (none) | Shortage quest scenario | done |
| primary site | House walls + door | Terrain props + sign | done |
| carrier label | Oscillating Carrier/Worker | Stable occupation + activity | done |
| worker dialogue | Unconditional quest.factory_shortage | Baseline occupation lines | done |
| local layout | Hardcoded grids / south packing | Settlement spatial grammar v2 | done |

## Spatial diagram (seed 507 / node:35)

```text
                    NORTH
              Woodland Cuttings (building:21)
                    sector=north

SW Clay Pits (23)          CORE                    SE Ore Ridge (22)
                           Settlement Centre (19)
                           Warehouse (20)
                           Clay Works (24)
                           Ridge Works (37)
                           Muster Yard (25)
                           Village Factory (26)

                    SOUTH / roads out
```

## Remaining debt

- Wider zoomed settlement capture of all three primaries in one frame
- Decorative housing scenery density
- Quest reintegration after foundation acceptance
- Generated person display names still technical (`Worker-site_worker:…`) — labels use occupation

## Tests

- `tests/sim/test_village_foundation.py`
- G04 gate PASS (incl. G01–G03 regressions)
- Humanoid scale Godot script PASS
- Village scenario suite PASS (quest tests on FX-VILLAGE-QUEST)
