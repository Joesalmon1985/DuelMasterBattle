# G02 playtest handoff — FX-CARGO factions, cargo and construction

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Tested revision:** *(stamp after commit)*  
**Save slot:** `g02_playtest` · recovery: `_recovery`

## Launch (verified)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g02.sh --direct
```

Portrait **450×800**. Economy panel is collapsible top-right.

## FIX (presentation state machine)

`SyncPresentation` now atomically ACKs a transition and persists full leg metadata
(`phase`, `presenting_node`, `from_node`/`to_node`, `local_from`/`local_to`/`local_pos`,
`onward_phase`, progress/duration, `last_consumed_sequence`). Pending is removed only
after Python accepts the matching sequence. Duplicate ACKs are idempotent; stale/out-of-order
ACKs are ignored. RequestView cannot restart a consumed entrance.

## Controls checklist

| Control | Where | Use for |
| --- | --- | --- |
| **Start delivery** | Economy | Load haul; cart walks to exit (~64 px/s Game Time) |
| **Wait** | bottom | ≤1 road edge; depart then fully hide through doorway |
| **Travel** (follow) | exit | Enter once, cross once; no left↔right loops |
| **Block** / **Clear** | Economy | Route hazard on `node:2` |
| **Pause** | bottom | Freezes Game Time + cart motion |
| **Save** / **Load** | bottom | Mid-journey resume without replaying consumed entrance |

## Suggested play sequence

1. **Start delivery** — cart approaches Exit · Road (World Turn unchanged).
2. **Wait** — cart departs and disappears through the exit.
3. Follow to **node:2** — west entrance once, cross east once, wait (no looping).
4. **Wait** / follow to **node:3** — entrance once, walk to Construction Site, short unload, idle/delivered.
5. Block/Clear and Save/Load mid-walk preserve cargo + presentation progress.

## Evidence

| Check | Result |
| --- | --- |
| `python3 tools/check.py --gate G01` | PASS |
| `python3 tools/check.py --gate G02` | PASS (pytest journeys + `run_g02_cart_followthrough.gd` + smoke + G01 regressions) |
| `recordings/cart_journey.webm` | prior depart/arrive stills |

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

**Not claimed as human gate PASS.** **T049 remains NOT_STARTED.**
