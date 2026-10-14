# Wizard settlement stories: task progress

Tasks are defined in `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md` (milestones A to G); the design is `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`; the audit is `docs/WIZARD_NARRATIVE_AUDIT.md`; interface assumptions and foreseeable merge conflicts are `docs/WIZARD_STORY_INTEGRATION_CONTRACT.md`. This ledger is separate from `NEUROEVO_PROGRESS.md` and never edits it. Tick a task only when its "Done when" holds and its verification commands pass; write the evidence (command and result, or an evidence path under `WizardRTSHybrid/docs/evidence/narrative/<milestone>/`) on the same line. Keep the newest session note at the top of the session log.

Legend: `[ ]` not started, `[~]` in progress (say what is left), `[x]` done.

**Gate: no implementation task starts until the owner approves the revised plan.**

## Planning (this branch)
- [x] Audit, plan, execution plan, contract and this ledger written on `feature/wizard-settlement-stories` from `4b67f55c` (14 Oct 2026)
- [x] Revision after the owner's review: duel audit (Ward Duel chosen, 3x3 tier), worker/building interruption design, character lifecycle and mortality, archetype library, quest resilience policies, tutorial expiry and backups, save/load policy, milestones A to G (14 Oct 2026)

## A Verify the integrated launch
- [ ] A.1 Baseline test counts and launch audit evidence
- [ ] A.2 Narrative state container and tick (`story.story_quantum` hook; `server.py` enables; no `world.py` change)
- [ ] A.3 The simulation's own workers as characters: identity, link, `persons` join, Godot talk target; `run_hybrid_launch.gd`
- [ ] A.4 Basic save and load (`persist.py`, `save`/`load` ops, pause menu, `--load`)
- [ ] A.5 Wrap-up. **OWNER CHECKPOINT A**

## B Playable magic tutorial
- [ ] B.1 Wizard progression state; Flame gating in `campaign`; cycle-reset carry-over
- [ ] B.2 Duel tiers `duel.tutorial_3x3`/`duel.wizard_3x3`; `opponents.json`; the story Ward lease with Python verification and checkpoints
- [ ] B.3 Godot hosts the board for story leases; `duel_resolve`/`duel_checkpoint` routing; `run_hybrid_duel_lease.gd`
- [ ] B.4 Minimal residents; the temporary tutorial cast; lessons `meet`, `colours`, `weave`, `told_ward`, `hidden_ward`, `world`; unlock rule; notes fallback; Lessons panel; `run_hybrid_tutorial.gd`
- [ ] B.5 Wrap-up. **OWNER CHECKPOINT B**

## C One complete live-world quest
- [ ] C.1 The miner is the mine's own worker (one actor); the healer is a resident
- [ ] C.2 Building interaction and the work interruption (`workers.summon/release`, the one core change); `ask_out`, `end_talk`; `run_hybrid_quest.gd`
- [ ] C.3 Journal, accept, decline, objective text
- [ ] C.4 The warden is a Ward Duel; Mastermind board removed from `story_ui.gd`; `story_agent` wins Ward duels
- [ ] C.5 Wrap-up: the first vertical slice played end to end. **OWNER CHECKPOINT C**

## D Persistent characters and living-world contingencies
- [ ] D.1 Archetype library (schema, loader, 88 profiles converted, names); seeded assignment
- [ ] D.2 Residents: routines by role, households, caps, "Call for <name>"
- [ ] D.3 Mortality and the link watcher (home destroyed, caught in the fighting, fire, outbreak illness, settlement destroyed, departure); `magic.find` includes residents
- [ ] D.4 Quest resilience policies (`living.py`) on the existing stories and the tutorial; evidence landmarks; inherited and acknowledgement lines
- [ ] D.5 Tutorial expiry at 30 game minutes with grace; departure; the notes; the replacement teacher; `tutorial_late` headed variant
- [ ] D.6 Wrap-up. **OWNER CHECKPOINT D**

## E Three dynamic stories per settlement
- [ ] E.1 Template v2 schema, loader, validator (lifecycle-outcome check), full graph runtime, facts, packs, effect registries
- [ ] E.2 Migrate the two families and the tutorial to templates; archive `data/story/*.json`
- [ ] E.3 Settlement context with version cache; casting for every role kind
- [ ] E.4 Director: slots, eligibility, scoring, selection, refill; rumours and journal in Godot; `observe`, `travel_hint`; `narrative_report.py`; `run_hybrid_stories.gd`
- [ ] E.5 World effects one at a time (`clear_disruption`, `cure_region`, `caravan`, `diplomacy_offer`, `unrest_delta`); separation tests
- [ ] E.6 Wrap-up. **OWNER CHECKPOINT E**

## F Existing authored story integration
- [ ] F.1 Workbook converter, role map, default contingency blocks, 20 structures, 112 cast files; castability report
- [ ] F.2 Dialogue Factory export adapter (narrative pack, worldview replies)
- [ ] F.3 Pilot casts in play (E36B, E53A, E56A); coverage; playthrough harness
- [ ] F.4 Wrap-up. **OWNER CHECKPOINT F (dialogue review; Factory expansion decision)**
- [ ] F.5 Expansion (remaining archetypes, further casts) only after the checkpoint

## G Scale, polish and verification
- [ ] G.1 Movement and presentation polish from the owner's playtest notes
- [ ] G.2 Performance and scale report (6/12/24/48 settlements; residents; on versus off)
- [ ] G.3 Save and load reliability; 180-minute long game
- [ ] G.4 End-to-end acceptance scenario (`run_hybrid_acceptance.gd`) and the adverse-case tests. **OWNER CHECKPOINT G (final)**

## Session log (newest first)
- 2026-10-14 (Claude Fable 5.1), second session: planning revision only, no code changed, no neuroevolution file touched. Re-audited the duel implementations (`duel/ward.py`, `sim/dmb/adventure/{mastermind,duels}.py`, `godot_project/sim/*.gd`, `game_board.gd`, `duel_lease_adapter.gd`, `progression.json`), the worker programme model (`workers.py`), the people registry lifecycle, the save paths, the Godot launch path and the 88-profile CSV. Decisions applied: Ward Duel through the existing lease mechanism with a 3x3 tier; one additive `workers.py` change for the summon; residents as narrative-owned mortal Persons; archetype library from the 88 profiles; milestones A to G around playable slices; no training-gate work and no `world.py` change. The neuroevolution branch advanced to `cb2f538e` (T1.5 episode runner) during this session; nothing of it conflicts with the plan (contract section 6.2).
- 2026-10-14 (Claude Fable 5.1), first session: planning only. Worktree `/home/joe/dmb_runs/wt_wizard_stories`, branch `feature/wizard-settlement-stories` from `origin/feature/neuroevolution-plan` `4b67f55c`. Audit of story, quest, dialogue, settlement and tutorial assets; measured the legacy story layer in AI worlds (audit section 2.4). Evidence: `WizardRTSHybrid/docs/evidence/narrative/audit/results.txt` (story layer 0.31-0.32% of profiled wall on seeds 507 and 11; one quest per 60 game minutes; faction-only hash and `world.rng` identical with the layer off for 40 minutes; full `state_hash` differs from minute 1 by snapshot shape).
