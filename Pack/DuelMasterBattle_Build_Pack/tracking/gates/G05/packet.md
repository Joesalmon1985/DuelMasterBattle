# G05 — Village Foundation checkpoint (quest paused)

**Status:** FIX_REQUIRED (Village Foundation human sanity check)  
**Stop point:** T096 — do **not** start T097 / G06  
**Play fixture:** `FX-VILLAGE` — **healthy baseline**, quest disabled  
**Quest fixture (preserved):** `FX-VILLAGE-QUEST`  
**Branch:** `refactor/canonical-ontology-g05`  
**Launch:** `bash tools/play_g05.sh`  
**Seed:** **507**

## Purpose of this checkpoint

Establish a plain, believable working village **without** shortage-quest pressure.

Acceptance question:

> If I know nothing about the quest, does this place make common sense as a functioning settlement?

Do **not** ask Joe to solve the shortage quest on this return.

## Spatial grammar

```text
                 NORTH / OUTSKIRTS
              [resource extraction]

[resource]        VILLAGE CORE         [resource]
                  centre / warehouse
                  workshops / factories

                 SOUTH / ROAD OUT
```

Primaries sit on perimeter sectors from touching-hex orientation.  
Core holds centre, warehouse, processors, factories.  
See `docs/LOCAL_SETTLEMENT_PRESENTATION.md`.

## What you should verify

1. Looks like a settlement, not a test grid of houses  
2. Resource sites look like woodland / ridge / pits — not cottages  
3. Occupations stable (Woodcutter / Miner / Clay worker / Factory worker)  
4. Talking to ordinary workers is ordinary speech — no quest/guide promises  
5. Workers originate from sensible workplaces with pauses, not perpetual ants  
6. Paths leave the settlement; Travel out and return preserves IDs  
7. No demon, sluice entrance, or shortage-quest Mara dialogue in baseline  

## Quest content

Preserved under `FX-VILLAGE-QUEST` / `mode=quest`. Not deleted. Re-enable after foundation passes.

## Automated

```bash
python3 -m pytest tests/sim/test_village_foundation.py -q
python3 tools/check.py --gate G04   # regressions
bash tools/play_g05.sh
```

Agents cannot self-PASS G05. Quest gate remains unresolved.
