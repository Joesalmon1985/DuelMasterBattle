# Kickoff prompt for a FUTURE implementation session

**Do not use this until the owner has reviewed and approved the revised direction (`DuelMasterBattle_Design_v0_5.md`, `DECISION_REGISTER.md`, `ROADMAP_NEXT_RUN.md`).** Edit the "Authorised scope" line to the milestones the owner approves.

---

Repository: `Joesalmon1985/DuelMasterBattle`, branch `feature/hybrid-playtest-fixes-v03` (verify the latest branch and HEAD; keep any uncommitted owner files untouched; do not merge to `main`).

**Authorised scope:** M1 (campaign profiles, drafted-tech unlocks, primitive start) and then M2 (first Mindustry industrial-to-unit slice) from `docs/ROADMAP_NEXT_RUN.md`. [Owner edits this line.] Do nothing outside the authorised milestones.

Start by reading, in order: `docs/DuelMasterBattle_Design_v0_5.md`, `docs/DECISION_REGISTER.md`, `WizardRTSHybrid/AGENTS.md`, `docs/ARCHITECTURE_CONTRACT.md`, `docs/CURRENT_STATUS_AND_GAPS.md`, `docs/ROADMAP_NEXT_RUN.md`, `WizardRTSHybrid/docs/MINDUSTRY_PROVENANCE.md`, `WizardRTSHybrid/docs/PROJECT_STATUS.md`. D01–D20 are closed; use the S-item defaults as configurable constants and say so.

Work rules:
1. Run the baseline first and record the counts: Python suite, the Ward Duel test, `ai_report.py` for three seeds, and the headed suite. Do not weaken or delete any existing test.
2. M1: add campaign/developer/test profiles; gate God Mode and the training commands; add `tech.py` and card data; filter the build menu and `check_placement`; make the AI use only unlocked content; keep today's start as the `test_showcase` fixture; implement the tests and the headed script listed in the roadmap.
3. M2: choose and pin a Mindustry release or commit at least two weeks old; record SHA in `sources/manifest.json`, `SOURCE_REUSE.md`, `LICENSES.md`; inspect the real Mindustry items, ores, drills, conveyors, power, liquids, crafters, unit factories, units and tech tree (list in `MINDUSTRY_PROVENANCE.md`); write an importer that produces data from the pin; implement drill, conveyor, power graph, crafter and unit factory as buildings/entities in the one world; spawn units into `world.units`; use produced Widelands goods for machine costs; add conservation, backpressure, power-outage, card-gating and determinism tests; add the headed industry script with screenshots.
4. No Java runtime, no second army or economy engine, no large copied Java, no free goods, no hidden workers. Mark art placeholders as such.
5. Commit milestone by milestone on the feature branch, update `PROJECT_STATUS.md`, `TASK_LEDGER.md`, `STATE_OF_PLAY.md`, `SOURCE_REUSE.md`, `WORK_LOG.md`; report test counts, headed evidence paths, and anything not done honestly.
6. Do NOT start quests/dungeons (M3), VP/eras (M4), catastrophes (M5) or M6 unless the authorised scope names them. Stop at the end of the authorised scope and ask for review.
