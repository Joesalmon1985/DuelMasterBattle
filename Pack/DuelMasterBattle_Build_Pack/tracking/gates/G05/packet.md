# G05 — Full world + simple persistent rockfall quest

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Candidate commit:** *(pending)*  
**Play:** `bash tools/play_g05.sh` — seed **507**, FX-VILLAGE  
**Branch:** `refactor/canonical-ontology-g05`

## Dialogue universe (production)

Active sources (top-level only):

- `content/source/dialogue/settlement_normal.json`
- `content/source/dialogue/boulder_quest.json`

Archived (not loaded by `LineCatalog.load()`):

- `archive/shortage/` — Mara / factory-shortage / Route A–B
- `archive/aspect/` — Aspect-tagged prose
- `archive/onboarding/` — instructional lines

Ordinary Talk uses person context (occupation / workplace / activity).
Rockfall is an overlay after Inspect. Aspect lines require explicit `aspect_id`.

Audit: `docs/review/G05_STARTING_VILLAGE_DIALOGUE_AUDIT.md`  
Matrix: `tracking/gates/G05/dialogue_matrix.md`

## Binding (seed 507)

| Field | Value |
|-------|-------|
| Start | `node:35` |
| Blocked exit | `node:35.south` → `node:29` |
| Obstruction | `rockfall:1` |
| Helper | any eligible village worker via dialogue |
| Quest | `quest.blocked_exit_boulder` |

## Human checklist

- [ ] Talk to every visible Person before Rockfall — occupational, no shortage/Aspect
- [ ] Inspect Rockfall → workers offer clear + job question
- [ ] Job question is truthful; does not clear rocks
- [ ] Chosen worker clears; others may note someone is dealing with rocks
- [ ] Completion line only after path open; then ordinary dialogue
- [ ] South corridor walkable after clear
