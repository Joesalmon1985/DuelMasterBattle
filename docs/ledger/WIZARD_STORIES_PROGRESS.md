# Wizard settlement stories: task progress

Tasks are defined in `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`; the design is `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`; the audit is `docs/WIZARD_NARRATIVE_AUDIT.md`; boundaries are `docs/WIZARD_STORY_INTEGRATION_CONTRACT.md`. This ledger is separate from `NEUROEVO_PROGRESS.md` and never edits it. Tick a task only when its "Done when" holds and its tests pass; write the evidence (command and result, or an evidence path under `WizardRTSHybrid/docs/evidence/narrative/`) on the same line. Keep the newest session note at the top of the session log.

Legend: `[ ]` not started, `[~]` in progress (say what is left), `[x]` done.

**Gate: no implementation task starts until the owner approves the plan.**

## Planning (this branch)
- [x] Audit, plan, execution plan, contract and this ledger written on `feature/wizard-settlement-stories` from `4b67f55c` (14 Oct 2026)

## W0 Baseline, package skeleton, isolation harness
- [ ] W0.1 Baseline test counts on this branch
- [ ] W0.2 Package skeleton and the gate in `world.py` (shared change S1, see the contract)
- [ ] W0.3 Faction-equivalence and cost evidence (`narrative_evidence.py equiv|cost`)
- [ ] W0.4 Performance harness (`test_narrative_perf.py`)

## W1 The person link (first vertical slice)
- [ ] W1.1 `casting.person_for`, link fields, relink
- [ ] W1.2 The miner quest binds the mine's real worker; one actor in the snapshot; Godot talk target
- [ ] W1.3 Rebind on replacement; death suspends
- [ ] W1.4 Narrative log instead of `world.events`
- [ ] W1.5 Wrap-up. **OWNER CHECKPOINT**

## W2 Story-graph runtime and template v2
- [ ] W2.1 Template v2 schema, loader, validator
- [ ] W2.2 Graph runtime (`narrative/graph.py`)
- [ ] W2.3 Facts and dialogue packs
- [ ] W2.4 Migrate `gallery_collapse` and `outbreak_treatment` to templates; archive `data/story/*.json`

## W3 Settlement context, director, first four archetypes
- [ ] W3.1 Settlement context with version cache
- [ ] W3.2 Casting for every role kind (workers, carriers, units, buildings, household, other faction)
- [ ] W3.3 Director: slots, eligibility, scoring, selection, refill; `narrative_report.py`
- [ ] W3.4 Offer, accept, journal, observe ops
- [ ] W3.5 Wrap-up: three-settlement showcase test. **OWNER CHECKPOINT**

## W4 Living stories, save and load
- [ ] W4.1 Living policies (rebind, suspend, resolve, fail, ownership, era, reload, no duplicates)
- [ ] W4.2 Wizard Mode save and load (`server.py`), cycle-reset carry-over of wizard state
- [ ] W4.3 Scripted playthrough harness (`play_stories.py`, `test_narrative_playthrough.py`)

## W5 Dialogue pipeline and the three-cast pilot
- [ ] W5.1 Workbook converter, role map, 20 structure templates, casts E36B/E53A/E56A
- [ ] W5.2 Dialogue Factory export adapter (narrative pack format)
- [ ] W5.3 Coverage validator and fallback audit
- [ ] W5.4 Wrap-up. **OWNER CHECKPOINT (dialogue review)**

## W6 Tutorial and the transition
- [ ] W6.1 Wizard state and known spells (campaign-only gating in the wizard path)
- [ ] W6.2 Mentor and lessons L1-L6; unlock rule (essential lessons OR `unlock_after_ms`, default 20 game minutes)
- [ ] W6.3 Wrap-up. **OWNER CHECKPOINT (tutorial)**

## W7 Godot presentation
- [ ] W7.1 Worker as talk target, rumours, journal, lessons; `run_hybrid_stories.gd`, `run_hybrid_tutorial.gd`

## W8 Archetype library and scale
- [ ] W8.1 Remaining archetypes (fifteen in total) and the five world effects
- [ ] W8.2 Scale and performance report (6/12/24/48 settlements; on versus off)

## W9 Integration
- [ ] W9.1 Sync with `feature/neuroevolution-plan` at an agreed checkpoint; shared-change patch S1+S2 handed over with evidence
- [ ] W9.2 Final gates. **OWNER CHECKPOINT (merge)**

## Session log (newest first)
- 2026-10-14 (Claude Fable 5.1): planning only. Worktree `/home/joe/dmb_runs/wt_wizard_stories`, branch `feature/wizard-settlement-stories` from `origin/feature/neuroevolution-plan` `4b67f55c`. Audit of story, quest, dialogue, settlement and tutorial assets; measured the legacy story layer in AI worlds (see the audit section 2.4). No code changed; no neuroevolution file touched.
