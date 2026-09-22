# G08 Morning Review — AUTO_READY_FOR_OWNER_REVIEW

**Gate:** G08 — Narrative breadth, presentation and authoring tools  
**Status:** `AUTO_READY_FOR_OWNER_REVIEW`  
**Human acceptance:** PENDING — do **not** invent `PASS` or `accepted_by`  
**Overnight policy:** continuation to T143+ permitted without equating automation to PASS

## Candidate

- Branch: `phase/g06-g12-autoqa`
- Fixture sample: `FX-CONTENT-SAMPLE` (seed 808) — `godot_project/content/fixtures/content_sample/fx_content_sample.json`
- Launch: `bash tools/play_g08_sample.sh`
- Auto report: `tracking/gates/G08/auto/result.json`
- Dialogue text sample: `tracking/gates/G08/dialogue_preview.md`
- Screenshots: `tracking/gates/G08/screenshots/` (real Godot frames)

## Automated evidence

| Suite | Result |
|---|---|
| Content authoring pipeline (T133) | PASS |
| 16 quest templates / 8 families (T134–T135) | PASS |
| 8 dungeons + 4 rivals (T136) | PASS |
| ≥1200 baseline dialogue + integrity (T137) | PASS |
| 4-era semantic assets + audio palettes (T138) | PASS |
| Debug inspectors / narrative tools (T139–T140) | PASS |
| Corpus / coverage matrix (T141) | PASS |
| `tools/run_auto_gate.py --gate G08` | AUTO_READY_FOR_OWNER_REVIEW |

## Sample coverage (objective)

- All eight quest families (2 templates each)
- Eras: Historic + Modern (also Prehistoric/Future in dialogue corpus)
- Dungeons: cave + sluice (all eight layouts authored)
- All four recurring rivals
- Branches: displaced-target, dead-target, already-world-resolved, full-cycle
- Village/content tools, changed-line preview path, failure-bundle export
- Accessibility: label_scale + reduced_motion declared in asset manifest / sample

## Owner playtest focus

1. Play the stratified sample across families / two eras / two dungeons.
2. Read displaced / dead / world-resolved / full-cycle dialogue; check for leaks and no-effect choices.
3. Try four rival samples; toggle label scale / reduced motion.
4. Village panel: load seed, preview a changed line, export a failure bundle.

## Known limits

- Semantic placeholder art/audio only (G10 overnight policy).
- Baseline dialogue is coverage-first unique lines; literary polish is for owner revision.
- Headed Godot sample uses FX-ERA shell frames for layout evidence; content graphs are validated in Python corpus tools.
- G05–G07 remain without human PASS; do not invent acceptance.
