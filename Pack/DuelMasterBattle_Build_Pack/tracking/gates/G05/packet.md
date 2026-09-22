# G05 — Full world + simple persistent rockfall quest

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Play:** `bash tools/play_g05.sh` — seed **507**, FX-VILLAGE  
**Branch:** `refactor/canonical-ontology-g05`

## Revised G05 definition

Full explorable Prehistoric world (19/54/72) + one simple persistent village
quest: a durable **Rockfall** (cluster of stones) blocks one real topology exit;
John inspects it, asks **any** eligible village worker for help; that worker
clears it; the path opens; save/load and leave/return preserve IDs.

### Original G05 prototype (superseded)

Shortage / demon / sluice / Route A–B — archived as `FX-VILLAGE-QUEST`.

## Binding (seed 507)

| Field | Value |
|-------|-------|
| Start | `node:35` Settlement 2-1 |
| Blocked exit | `node:35.south` → `node:29` |
| Obstruction | `rockfall:1` (5 stone pieces across the south approach) |
| Helper | **Not preselected** — any eligible employed worker on node:35 |
| Quest | `quest.blocked_exit_boulder` — offered → active/clearing → completed |
| Cause | `exit_blocked_by_rockfall` |

Eligible helpers include factory, primary/resource, and works workers with a
real workplace on the start node. Helper is bound only when John chooses
“Could you help clear the boulders from the path?”

## Human acceptance checklist

- [ ] South path clearly blocked by labelled **Rockfall** (several stones)
- [ ] Nearby Inspect: too heavy alone; *maybe one of the workers could help*
- [ ] Talk to **any** worker → several choices; occupation choice does not clear
- [ ] Ask chosen worker → that Person walks to rocks → stones slide aside
- [ ] Travel south succeeds (one World Turn); stones remain beside the path
- [ ] Completion dialogue only after clear; no special hidden Person ID needed

**Experience question:** Does talking to a person cause a simple, understandable change in a persistent world?

## Stop

Do **not** start G06 / T097 until Joe PASSes this gate. Agents must not self-PASS.
