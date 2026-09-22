# G05 — Full world + simple persistent boulder quest

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Play:** `bash tools/play_g05.sh` — seed **507**, FX-VILLAGE  
**Branch:** `refactor/canonical-ontology-g05`

## Revised G05 definition

Full explorable Prehistoric world (19/54/72) + one simple persistent village
quest: a durable boulder blocks one real topology exit; John observes it, asks
a living factory worker for help; the worker moves it; the path opens; save/
load and leave/return preserve IDs.

### Original G05 prototype (superseded)

Shortage / demon / sluice / Route A–B — archived as `FX-VILLAGE-QUEST`. Not the
current human acceptance scenario.

## Binding (seed 507)

| Field | Value |
|-------|-------|
| Start | `node:35` Settlement 2-1 |
| Blocked exit | `node:35.south` → `node:29` |
| Boulder | `boulder:1` |
| Worker | `person:16` (Factory worker, workplace `building:25` Skirmisher Yard) |
| Quest | `quest.blocked_exit_boulder` — offered → active/intervention → completed |
| Cause | `exit_blocked_by_boulder` |

## Human acceptance checklist

- [ ] South path obviously blocked by labelled Boulder
- [ ] Observe/Inspect copy correct; Travel rejected without World Turn
- [ ] Talk → ask worker → worker walks → boulder slides aside
- [ ] Path traversable; same worker acknowledges; boulder remains beside path
- [ ] Save/load and leave/return preserve boulder, person, quest IDs
- [ ] Rest of board still explorable; G01–G04 layers intact

**Experience question:** Does talking to a person cause a simple, understandable change in a persistent world?

## Evidence

- Tests: `tests/sim/test_boulder_quest.py` (+ G05 full-world / foundation / visual regressions)
- Docs: `gates/G05.md`, `EXECUTION_AMENDMENTS.md`, this packet
- Living-world long-run evidence retained under `long_run/` / `long_run_report.md`

## Stop

Do **not** start G06 / T097 until Joe PASSes this gate. Agents must not self-PASS.
