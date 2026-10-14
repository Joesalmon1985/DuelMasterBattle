# Wizard settlement stories: task progress

Tasks are defined in `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md` (milestones A to G); the design is `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`; the audit is `docs/WIZARD_NARRATIVE_AUDIT.md`; boundaries and interface assumptions are `docs/WIZARD_STORY_INTEGRATION_CONTRACT.md`; the handover for the implementation agent is `docs/WIZARD_IMPLEMENTATION_HANDOFF.md` (startup prompt: `docs/prompts/START_WIZARD_MODE_IMPLEMENTATION.md`). This ledger is separate from `NEUROEVO_PROGRESS.md` and never edits it. Tick a task only when its "Done when" holds and its verification commands pass; write the evidence (command and result, or an evidence path under `WizardRTSHybrid/docs/evidence/narrative/<milestone>/`) on the same line. Keep the newest session note at the top of the session log.

Legend: `[ ]` not started, `[~]` in progress (say what is left), `[x]` done.

**Status: planning COMPLETE and approved (14 October 2026). Implementation NOT STARTED.** Implementation happens on `feature/wizard-mode-implementation` in `/home/joe/dmb_runs/wt_wizard_implementation`, created from the final pushed HEAD of `feature/wizard-settlement-stories` (handover section C). Milestones run in order; each later milestone starts only after the owner approves the previous checkpoint. Record owner approvals in the session log.

## Planning (branch `feature/wizard-settlement-stories`)
- [x] Audit, plan, execution plan, contract and this ledger written from `4b67f55c` (14 Oct 2026)
- [x] Revision after the owner's review: Ward Duel 3x3, work interruption, mortal characters, archetypes, resilience policies, tutorial expiry, save policy, milestones A to G (14 Oct 2026)
- [x] Final pass: R1 to R5 resolved and applied; genuine-duel verification rule; A.5 wrap-up; G.4 illness task; handover and startup prompt written (14 Oct 2026)

## A Verify the integrated launch
- [ ] A.1 Baseline test counts and launch audit evidence (`a/baseline.md`; pre-existing failures listed)
- [ ] A.2 Narrative state container and tick (`story.story_quantum` hook; `server.py` enables; no `world.py` change)
- [ ] A.3 The simulation's own workers as characters: identity, link, `persons` join, Godot talk target; `run_hybrid_launch.gd`
- [ ] A.4 Basic save and load (`persist.py`, `save`/`load` ops, pause menu, quit save, client-timed autosave, `--load`)
- [ ] A.5 Wrap-up: quick set, hash and determinism tests, headed `launch story duel wizard campaign`, owner hand launch. **OWNER CHECKPOINT A**

## B Playable magic tutorial
- [ ] B.1 Wizard progression state; Flame gating in `campaign`; cycle-reset carry-over
- [ ] B.2 Duel tiers `duel.tutorial_3x3`/`duel.wizard_3x3`; `opponents.json`; the story Ward lease with Python verification and checkpoints; palette from `tutorial.palette`
- [ ] B.3 Godot hosts the board for story leases; `duel_resolve`/`duel_checkpoint` routing; `run_hybrid_duel_lease.gd` (interface smoke)
- [ ] B.4 Minimal residents; the temporary tutorial cast; lessons `meet`, `colours`, `weave`, `told_ward`, `hidden_ward`, `world`; unlock rule; notes fallback; Lessons panel; `run_hybrid_tutorial.gd` with genuine casts. **OWNER CHECKPOINT B**

## C One complete live-world quest
- [ ] C.1 The miner is the mine's own worker (one actor); the healer is a resident
- [ ] C.2 Building interaction and the work interruption (`workers.summon/release`, the one core change W1); `ask_out`, `end_talk`; `run_hybrid_quest.gd`
- [ ] C.3 Journal, accept, decline, objective text
- [ ] C.4 The warden is a Ward Duel (R2); Mastermind board removed from `story_ui.gd`; Mastermind kept for environments and tests; `story_agent` wins Ward duels
- [ ] C.5 Wrap-up: the first vertical slice played end to end. **OWNER CHECKPOINT C**

## D Persistent characters and living-world contingencies
- [ ] D.1 Archetype library (schema, loader, 88 profiles converted, names); seeded assignment
- [ ] D.2 Residents: routines by role, households, configurable caps and budget (R4), "Call for <name>"
- [ ] D.3 Mortality and the link watcher (home destroyed, caught in the fighting, fire, settlement destroyed, departure); `magic.find` includes residents (W2); illness deferred to G.4 (R3)
- [ ] D.4 Quest resilience policies (`living.py`) on the existing stories and the tutorial; evidence landmarks; inherited and acknowledgement lines
- [ ] D.5 Tutorial expiry at 30 game minutes with grace; departure; the notes; the replacement teacher; `tutorial_late` headed variant. **OWNER CHECKPOINT D**

## E Three dynamic stories per settlement
- [ ] E.1 Template v2 schema, loader, validator (lifecycle-outcome check), full graph runtime, facts, packs, effect registries
- [ ] E.2 Migrate the two families and the tutorial to templates; archive `data/story/*.json`
- [ ] E.3 Settlement context with version cache; casting for every role kind (lazy residents, every settlement eligible)
- [ ] E.4 Director: slots, eligibility, scoring, selection, refill; rumours and journal in Godot; `observe`, `travel_hint`; `narrative_report.py`; `run_hybrid_stories.gd`
- [ ] E.5 World effects one at a time (`clear_disruption`, `cure_region`, `caravan`, `diplomacy_offer`, `unrest_delta`); separation tests. **OWNER CHECKPOINT E**

## F Existing authored story integration
- [ ] F.1 Workbook converter, role map, default contingency blocks, 20 structures, 112 cast files; castability report
- [ ] F.2 Dialogue Factory export adapter (narrative pack, worldview replies)
- [ ] F.3 Pilot casts in play (E36B, E53A, E56A); coverage; playthrough harness. **OWNER CHECKPOINT F (dialogue review; Factory expansion decision)**
- [ ] F.4 Expansion (remaining archetypes, further casts) only after the checkpoint

## G Scale, polish and verification
- [ ] G.1 Movement and presentation polish from the owner's playtest notes
- [ ] G.2 Performance and scale report (6/12/24/48 settlements; residents; on versus off)
- [ ] G.3 Save and load reliability; 180-minute long game
- [ ] G.4 Outbreak illness for residents (deferred from D.3 by R3)
- [ ] G.5 End-to-end acceptance scenario (`run_hybrid_acceptance.gd`, genuine duels) and the adverse-case tests. **OWNER CHECKPOINT G (final)**

## Session log (newest first)
- 2026-10-14 (Claude Fable 5.1), third session (final planning pass): owner decisions R1 to R5 applied (Flame/Frost/Vine configurable; warden to Ward Duel in C; ordinary mortality from the start, illness in G.4; lazy residents in every settlement with configurable limits; manual, quit and client-timed autosave with atomic writes); genuine-duel rule added to the execution plan (debug finish only for interface smoke); A.5 wrap-up and G.4 added, acceptance renumbered G.5; handover `docs/WIZARD_IMPLEMENTATION_HANDOFF.md` and startup prompt `docs/prompts/START_WIZARD_MODE_IMPLEMENTATION.md` written. No code changed; no neuroevolution file touched; implementation branch not created (the implementation agent creates it).
- 2026-10-14 (Claude Fable 5.1), second session: planning revision only, no code changed, no neuroevolution file touched. Re-audited the duel implementations (`duel/ward.py`, `sim/dmb/adventure/{mastermind,duels}.py`, `godot_project/sim/*.gd`, `game_board.gd`, `duel_lease_adapter.gd`, `progression.json`), the worker programme model (`workers.py`), the people registry lifecycle, the save paths, the Godot launch path and the 88-profile CSV. Decisions applied: Ward Duel through the existing lease mechanism with a 3x3 tier; one additive `workers.py` change for the summon; residents as narrative-owned mortal Persons; archetype library from the 88 profiles; milestones A to G around playable slices; no training-gate work and no `world.py` change. The neuroevolution branch advanced to `cb2f538e` (T1.5 episode runner) during this session; nothing of it conflicts with the plan (contract section 6.2).
- 2026-10-14 (Claude Fable 5.1), first session: planning only. Worktree `/home/joe/dmb_runs/wt_wizard_stories`, branch `feature/wizard-settlement-stories` from `origin/feature/neuroevolution-plan` `4b67f55c`. Audit of story, quest, dialogue, settlement and tutorial assets; measured the legacy story layer in AI worlds (audit section 2.4). Evidence: `WizardRTSHybrid/docs/evidence/narrative/audit/results.txt` (story layer 0.31-0.32% of profiled wall on seeds 507 and 11; one quest per 60 game minutes; faction-only hash and `world.rng` identical with the layer off for 40 minutes; full `state_hash` differs from minute 1 by snapshot shape).
