# G05 — Procedural village / quest / duel playtest

**Status:** AWAITING_HUMAN  
**Stop point:** T096  
**Scenario:** FX-VILLAGE  
**Branch:** `feature/g05-village-quest`  
**Candidate build:** see `acceptance.json` / HEAD at handoff  

## What to play

1. Launch without reading optional hints.
2. Talk to Mara (factory worker). Explain in your own words why work stopped.
3. On one save, clear the ridge demon via the retained duel and confirm Route A / real output.
4. On a fresh save, solve the sluice dungeon and confirm Route B dialogue does **not** claim the demon was cleared.
5. Try world-resolved and destroyed-target scenario snapshots.
6. Drop/recover the sluice handle; save/reload mid dialogue, puzzle, or duel if practical.

## Automated evidence (necessary, not decisive)

```bash
python3 tools/check.py --gate G05
```

Agents cannot self-PASS the experience question. Only Joe's explicit  
`G05 PASS — <commit>` clears this gate.

## Packet contents

| File | Purpose |
|---|---|
| `launch.txt` | Exact launch commands |
| `reset.md` | Reset / isolated slots |
| `scenarios/` | Fresh + two solutions + world-resolved + destroyed-target |
| `known_defects.md` | Known defects |
| `optional_hints.md` | **Separate** optional hints — read after trying |
| `check_report.json` | Gate check output |
| `fx_village_record.json` | Scenario runner record |
| `acceptance.json` | AWAITING_HUMAN record |

## Experience question

Would you want to meet these people and solve another such problem?
