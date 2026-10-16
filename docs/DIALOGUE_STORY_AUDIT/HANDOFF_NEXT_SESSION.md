# Handoff: dialogue and story audit (paused 16 Oct 2026)

Branch: `analysis/dialogue-story-audit` (cut from `main` at `1b9513dd`). Analysis only: no gameplay, dialogue, quest or neural-network file was changed. Do not merge into `main`.

## Done

- **Extractor** `scripts/extract_inventory.py` reads every dialogue JSON, Mira's lines, Trial zone text, the legacy story templates and the Python-embedded text, and writes `generated/inventory.json` (608 lines, 145 choices/topics/replies, 13 skill checks, 188 Python text literals).
- **Runtime probes** `scripts/probe_runtime.py` (`probe_lib.py`, `probes_story.py`, `probes_party.py`): 32 small checks (P01 to P46) that drive the real game code on seed 507 and write `generated/runtime_probes.json`.
- **Static analysis** `scripts/analyze_static.py` writes `generated/static_findings.json` (29 findings).
- **Hand-written content** `scripts/curated.py`: outcomes, characters, rules, legacy systems, 20 defects (DEF-01 to DEF-20), 8 opportunities, plain-English probe summaries.
- **Workbook** `Wizard_World_Dialogue_Workbook.xlsx` from `scripts/build_workbook.py`: 16 sheets (README, A_Index, B_Dialogue, C_Choices, D_Outcomes, E_Characters, F_Rules, G_Checks, H_Flags_Facts, I_Selection, J_Ideology, K_Trial, L_System_Text, M_Runtime_Checks, N_Defects, O_Legacy).
- **Diagrams** `diagrams/01..12*.md` from `scripts/build_diagrams.py` (hand-written overview plus a tree generated from the data).
- Baseline: the 14 narrative/quest/Trial/party test files passed (209 tests) before any audit file was written (`scripts/_baseline_tests.log`).

## Still to do (in this order)

1. `scripts/validate_inventory.py`: check the inventory against the source. Every `lines` string in each dialogue JSON appears in B_Dialogue; every choice id in C_Choices; every `events.py` and `run.py` literal appears in K_Trial or L_System_Text; the numbers quoted in `curated.py` and `common.py` (start Aspects, thresholds, bands, timings, Mira's parameters) still match the code and `config.json`; every `{placeholder}` is accounted for. Fail loudly on any mismatch.
2. `scripts/run_all.py`: extract, analyse, probe, build workbook, build diagrams, validate (the workbook README already tells people to run it).
3. `STORIES_SUMMARY.md`: brief plain-English summary of each story, its endings, and how skills, regard and worldviews affect it.
4. `DEFECTS_AND_OPPORTUNITIES.md`: readable version of `curated.DEFECTS` / `OPPORTUNITIES` plus the static findings, kept separate from the inventory.
5. `README.md` in this folder: how to navigate the workbook and diagrams, and how to regenerate.
6. Re-run `extract_inventory.py`, `analyze_static.py`, `probe_runtime.py`, `build_workbook.py`, `build_diagrams.py` once more, then open the workbook in Excel and check widths, filters, hyperlinks (B to C, D to B, A to diagrams) and that Mermaid renders on GitHub.
7. Spot checks I had not finished: P43 and the late-joiner path reads correctly; `K_Trial` event-to-zone mapping column is filled; `E_Characters` sample table; the `J_Ideology` stranger/mentor notes (the stranger row text is clumsy, tidy it).
8. Present the results to the owner as a walk-through: overview of quests and endings first, then how to use the workbook and diagrams, then the stories as choose-your-own-adventure.

## Findings worth leading with

DEF-01 creed question lost if the conversation is closed; DEF-02 duplicate ‘What should I do now?’; DEF-03 Patrol can never be done; DEF-04 a log from an empty store; DEF-07/08/09/17 multiplayer shared-state problems (failed-check memory, times-spoken-to, first reaction, double granite); DEF-10 worldview scores never read; DEF-11 seven skill checks cannot fail; DEF-06 Mira's `you_died_again` never spoken. Nothing was fixed.

## Notes and cautions

- `docs/release_notes.md` has an uncommitted change that predates this work. The project handoff says it is never committed, so it was deliberately left out of every commit.
- Run scripts from any folder; they find the repo through `scripts/common.py`. They use system `python` (3.14, openpyxl and pytest installed).
- Probes P34 to P38, P41, P44 to P46 run with the real exploration timings (`real_timing=True`); the others shorten them so the stranger arrives sooner.
- `generated/` holds regenerable outputs and is committed so the numbers can be inspected without running anything.
