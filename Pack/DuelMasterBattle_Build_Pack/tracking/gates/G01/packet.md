**Tested implementation commit:** `5d27fcef4d65c23155fc391eaef8f733dece943a`  
**Handoff HEAD:** `b3c5efe16e517121dbd9cd081b63cf58081cd8bb`

# G01 playtest handoff — linked arrivals, doorway travel, T019 recovery

**Status:** AWAITING_HUMAN (do not start T025)  
**Scenario:** FX-CLOCK · **Seed:** 7  

## What this repair fixed

- Linked exits commit **node + area + position + facing** together in Python Travel; Home east → Road west arrival `[1.5,5]` facing right; return → Home `[12,5]` facing left.
- Stale `SyncPose` from the source node is rejected (`STALE_NODE` / `STALE_POSE`).
- Walking outward through the doorway auto-requests Travel once; wizard holds at a safe boundary while pending; input must release/move inward before another auto-travel.
- Coordinates outside the map are blocked; rejected travel stays inside the source hold cell with an explanation.
- T019: coordinated `_recovery` checkpoint (periodic + after Travel/Wait); Bridge fail restarts the sidecar and restores the checkpoint with reported rollback — not “reload an old manual save”.

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

Menu: **G01 FX-CLOCK  (Python-backed runtime playtest)**  
Direct portrait: `bash tools/play_g01.sh --direct`  
Landscape: `bash tools/play_g01.sh --direct --landscape`

## Save / recovery

- Playtest slot: `g01_playtest` · recovery slot: `_recovery`
- Seed: `7`
- Bridge fail button exercises automatic checkpoint recovery

## Automated

- `python3 tools/check.py --task T019` → PASS  
- `python3 tools/check.py --task T020` → PASS  
- `python3 tools/check.py --gate G01` → PASS (`G01_BRIDGE_PLAY_OK arrivals=ok`)

**Not claimed as human gate PASS.**

## Checklist

| Step | Expect |
| --- | --- |
| Walk out east doorway | Auto Travel; hold; arrive Road at west facing inward |
| Walk into Road then return west | Arrive Home east entrance facing inward; +1 turn each |
| Hold stick across transition | Exactly one Travel; no instant bounce-back |
| Walk off map edge | Blocked |
| Bridge fail | Auto recovery + rollback message |
| Save/load after arrival | Pose/node preserved |

Reply `G01 PASS — <commit>` or `G01 FIX_REQUIRED — <symptom>`.
