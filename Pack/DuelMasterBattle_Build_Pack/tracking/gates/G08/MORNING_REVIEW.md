# G08 Morning Review — AUTO_READY_FOR_OWNER_REVIEW

**Gate:** G08 — Narrative breadth, presentation and authoring tools  
**Status:** `AUTO_READY_FOR_OWNER_REVIEW`  
**Human acceptance:** PENDING — do **not** invent `PASS` or `accepted_by`  
**Overnight policy:** continuation to T143+ permitted without equating automation to PASS

## Candidate

- Branch: `phase/g06-g12-autoqa`
- Fixture sample: `FX-CONTENT-SAMPLE` (seed 808) — Godot headed frames use **FX-ERA** seed 808 (same as `play_g08_sample.sh` / prior layout captures)
- Content graph: `godot_project/content/fixtures/content_sample/fx_content_sample.json`
- Launch: `bash tools/play_g08_sample.sh`
- Headed storyboard: `python3 tools/run_headed_storyboard.py --gate G08`
- Auto report: `tracking/gates/G08/auto/result.json`
- Visual report: `tracking/gates/G08/auto/visual_report.json`
- Montage: `tracking/gates/G08/auto/montages/g08_storyboard.png`
- Dialogue text sample: `tracking/gates/G08/dialogue_preview.md`

## Screenshot storyboard

| Checkpoint | Screenshot | What it proves | Automated result |
|---|---|---|---|
| Village panel | `auto/screenshots/01_village_panel_450x800.png` | Content-sample village shell | PASS |
| World map 450×800 | `auto/screenshots/02_world_map_450x800.png` | Map overlay portrait | PASS |
| Chronicle 450×800 | `auto/screenshots/03_chronicle_450x800.png` | Chronicle portrait | PASS |
| World map 1280×720 | `auto/screenshots/04_world_map_1280x720.png` | Map landscape | PASS |
| Chronicle 1280×720 | `auto/screenshots/05_chronicle_1280x720.png` | Chronicle landscape | PASS |
| Knowledge | `auto/screenshots/06_knowledge_1280x720.png` | Knowledge modal | PASS |
| Inventory | `auto/screenshots/07_inventory_1280x720.png` | Inventory modal | PASS |

Legacy layout frames also remain under `tracking/gates/G08/screenshots/` for comparison.

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
| Headed storyboard + visual validator | PASS (`visual_status`) |

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
