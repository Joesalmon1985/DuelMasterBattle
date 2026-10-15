# Wizard Mode implementation handover

For a new agent that has never seen the planning conversation. Read this file first, then the documents in section B in order. Approved by the owner on 14 October 2026. The planning branch is `feature/wizard-settlement-stories`; the implementation branch you will create is `feature/wizard-mode-implementation`.

---

## A. Project objective

DuelMasterBattle's active game is the wizard-led RTS hybrid in `WizardRTSHybrid/` (Python simulation `wizard_rts/`, Godot 4.5 presentation in `godot_project/`). Six faction AIs build settlements, run economies and fight on one authoritative `HybridWorld`. Wizard Mode (`scripts/launch_scenario.sh campaign`) already drops the player into that world as a wizard who walks, inspects things and burns them.

The finished Wizard Mode experience: **launch the real RTS game, appear as the wizard beside a real settlement while the factions keep playing, meet a teacher who lives there, learn the three-colour, three-slot Ward Duel (Flame, Frost, Vine), walk through the settlement, talk to its real workers and residents (ask a worker to come out of a building, which genuinely interrupts production), accept a quest that arises from the settlement's actual circumstances (a collapsed mine gallery, an outbreak, a dispute), complete it through dialogue, a dungeon and a Ward Duel, and watch a legitimate consequence appear in the continuing simulation (coal flows again; the AI never learns why). Later milestones give every settlement three distinct storylines cast on its own inhabitants, persistent mortal characters, and reliable save and load.** One integrated game, not an RPG attached to an RTS.

## B. Authoritative documentation (read in this order)

Binding (the specification; when they disagree, the execution plan wins over the plan, and the code and tests win over both, after which the document is fixed):

1. `docs/WIZARD_IMPLEMENTATION_HANDOFF.md` (this file): boundaries, branch, first task, validation.
2. `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`: working rules (section 0, read every session), milestones A to G with per-task expected changes, dependencies, verification commands and completion criteria, Appendix A (files), Appendix B (checkpoints).
3. `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`: the design: architecture (section 1), the duel and tutorial (2), the first slice (3), characters and archetypes (4), residents and mortality (5), linked characters (6), quest resilience (7), building interaction and the worker summon (8), effects and faction separation (9), the director (10), templates and dialogue (11), save and load (12), examples (13), performance (14), owner decisions Q1 to Q8 and R1 to R5 (15).
4. `docs/WIZARD_STORY_INTEGRATION_CONTRACT.md`: what you may change, what you must not, interface assumptions, the two shared-file changes (W1 `workers.py`, W2 `magic.py`), and foreseeable merge conflicts with the other workstream.
5. `docs/ledger/WIZARD_STORIES_PROGRESS.md`: the task checklist you maintain.

Background (read when a task touches the area; not binding where they disagree with the above):

6. `docs/WIZARD_NARRATIVE_AUDIT.md`: the inventory of existing systems, with sections 9 to 13 on duels, the worker programme model, lifecycle facilities, save, and the launch path; measured numbers in 2.4.
7. `WizardRTSHybrid/CLAUDE.md`, `WizardRTSHybrid/AGENTS.md`, root `CLAUDE.md`: repository conventions.
8. `docs/DECISION_REGISTER.md` (D02, D03/D07, D10, D11, D14, D19, D22, D33, D34), `docs/CONTENT_FREEZE.md` (the frozen catalogue), `docs/CANONICAL_GAME_ONTOLOGY.md`, `docs/ARCHITECTURE_CONTRACT.md`.
9. Historical and superseded: everything about the Catan-era game (`sim/dmb` economy and map rules, `godot_project/sim/world/`, `DD/`, `docs/FIRST_ADVENTURE.md`, `docs/SETTLEMENTS_AND_DUNGEONS.md`, `docs/VILLAGE_SYSTEM_CURRENT_STATE.md`); reuse their assets as the plan says, never their rules.

Decisions already made and not to be reopened: the retained Ward Duel is the one duel (Mastermind stays only for environments and tests that need it); the starting palette is Flame, Frost, Vine (configurable); residents are mortal from their introduction, outbreak illness arrives in G.4; residents are created lazily in any settlement and persist wherever the wizard is; saves are manual, on quit, and client-timed autosave about every five real minutes; no change to `world.py`; no training-gate or baseline work.

## C. Git branch and worktree

Repository: `/home/joe/Projects/DuelMasterBattle` (the main checkout, on `main`; leave it there). Existing worktrees: `/home/joe/dmb_runs/wt_wizard_stories` (the planning agent's; **do not use or modify it**), `/home/joe/dmb_runs/wt_base` (unrelated). The main checkout's fetch refspec only fetches `feature/wizard-rts-hybrid-v02`, so other branches must be fetched explicitly, as below.

Create the implementation branch from the **final pushed HEAD of `feature/wizard-settlement-stories`**, discovered at run time (never from `main`, never from `feature/neuroevolution-plan`, never from the commit the planning branch originally diverged from):

```bash
cd /home/joe/Projects/DuelMasterBattle
git status --short | head            # note any local changes; do not touch them
git fetch origin '+refs/heads/feature/wizard-settlement-stories:refs/remotes/origin/feature/wizard-settlement-stories'
git show -s --format='%H %ci %s' origin/feature/wizard-settlement-stories
#   expected subject: begins with "stories(plan): final handover"; record the SHA in the ledger's session log
test -f "$(git rev-parse --show-toplevel)/.git" || true   # (informational)
git ls-remote origin refs/heads/feature/wizard-mode-implementation     # must print NOTHING on first creation; if it prints a SHA, go to section I instead
git worktree list                                                      # must not already list wt_wizard_implementation; if it does, go to section I
git worktree add -b feature/wizard-mode-implementation /home/joe/dmb_runs/wt_wizard_implementation origin/feature/wizard-settlement-stories
cd /home/joe/dmb_runs/wt_wizard_implementation
git rev-parse --abbrev-ref HEAD                                        # feature/wizard-mode-implementation
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/feature/wizard-settlement-stories)" && echo BASE_OK
ls docs/WIZARD_IMPLEMENTATION_HANDOFF.md docs/prompts/START_WIZARD_MODE_IMPLEMENTATION.md docs/ledger/WIZARD_STORIES_PROGRESS.md
git push -u origin feature/wizard-mode-implementation
git ls-remote origin refs/heads/feature/wizard-mode-implementation      # now prints the same SHA as HEAD
```

If `BASE_OK` does not print, stop: remove the worktree (`git worktree remove /home/joe/dmb_runs/wt_wizard_implementation` and `git branch -D feature/wizard-mode-implementation` from the main checkout) and repeat the fetch. Never run `git checkout`, `git reset` or `git rebase` in the main checkout or in another worktree. All later work happens in `/home/joe/dmb_runs/wt_wizard_implementation`; `git push` after every committed task (the upstream is set by `-u` above; later pushes with `git push` are refused by the refspec only if you push from the wrong directory, so always push from the implementation worktree).

## D. Technical boundaries

You may change: everything under `WizardRTSHybrid/wizard_rts/narrative/` and `wizard_rts/data/narrative/` (new); `wizard_rts/story.py`, `story_agent.py`, `story_fixture.py`, `dungeon_agent.py`, `mastermind_solvers.py`, `wizard_pilot.py`, `puzzle/**`, `duel/**`, `magic.py`, `server.py`, `envs/{quest,dungeon,duel,outbreak}_env.py`, `envs/_world_cache.py`; `godot_project/content/source/duel_rules/progression.json` (adding tiers only); `godot_project/client/hybrid/*.gd`, `client/scenes/hybrid_world.gd`, `client/scripts/game_board.gd` (the optional reveal flag only), `client/tests/run_hybrid_*.gd`; `WizardRTSHybrid/scripts/{run_headed_suite.sh,launch_scenario.sh}` and new scripts; `tools/dialogue_generation/**`; the wizard tests listed in the contract; the five planning documents and the ledger.

You must not change: `wizard_rts/world.py`, `sim_api.py`, `visibility.py`, `ai.py`, `ai_plus.py`, `ai_industry.py`, `history.py`, `freeze.py`, `freeze_guard.py`, `sysinfo.py`, `WizardRTSHybrid/neuro/**`, `train_ai.py`, `docs/perf/hash_baseline*.json`, `tests/test_neuro_*.py`, `test_hash_baseline.py`, `test_content_freeze.py`, `test_sim_api.py`, `tests/conftest.py`, `test_determinism.py`, `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`, `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`, `docs/ledger/NEUROEVO_PROGRESS.md`, `docs/CONTENT_FREEZE.md`, the branch `feature/neuroevolution-plan` and any worktree of it. Never run `scripts/import_*.py` (the catalogue is frozen; `DMB_UNFREEZE` is not yours to set). Never add buildings, units, wares, liquids, resources or cards. Never merge anything into `main`, `feature/neuroevolution-plan` or `feature/wizard-settlement-stories`.

Shared simulation files: exactly two changes are sanctioned, both in the contract's section 4. **W1 `wizard_rts/workers.py`** (task C.2): `summon`, `release`, a `summoned` branch in `worker_quantum`, a `prog_interrupted` guard in `production_quantum`; additive, inert unless a wizard op calls `summon`. This is the highest-risk edit in the programme: the other workstream has also touched `workers.py` (two lines for `visibility.reveal`), so keep the change in its own commit, touch no existing line except the one `waiting_worker` branch, and run `test_hash_baseline.py`, `test_determinism.py`, `test_forestry.py`, `test_logistics.py`, `test_programme_failure.py` and `test_widelands_sweep.py` before and after. **W2 `wizard_rts/magic.py`** (task D.3): residents as fire targets.

If a task appears to need any other change to the core simulation (`economy.py`, `logistics.py`, `construction.py`, `military.py`, `industry/**`, `regions.py`, `disruption.py`, `society.py`, `trade.py`, `diplomacy.py`, `territory.py`, `settlements.py`, `lifecycle.py`, `terrain.py`, `tech.py`, `vp.py`, `world.py` and the forbidden list above): first try to compose existing APIs inside `wizard_rts/narrative/`; if that is impossible, write the need as a new row in the contract's section 4 table (file, change, why unavoidable, smallest form, proof it changes nothing else), record it in the ledger, finish every other part of the task, and stop at the next report to ask the owner. Do not make the change on your own authority.

Architecture rules that hold everywhere: one world (`HybridWorld`), one clock, one quest state owner (`QuestService`), one Person per human and at most one actor drawn per Person, typed effects with receipts, Python owns rules and Godot presents, the faction AIs read only the world (plan section 9.2), sorted iteration and seeded `random.Random` (never `world.rng`, never the wall clock) in narrative code, nothing new appended to `world.events`.

## E. First implementation milestone

Begin with **Milestone A, task A.1**, and execute A.1, A.2, A.3, A.4, A.5 in that order as written in the execution plan. Do not start B, and do not start tasks from several milestones at once. Milestone A delivers: baseline evidence; the narrative state container that exists only when `server.py` creates it; the simulation's own workers as named, talkable characters; basic save and load with the pause menu and autosave; a headed `launch` test; checkpoint A.

## F. Validation requirements

Environment, verified on 14 October 2026 by the planning agent: Ubuntu laptop, Python 3.12.3, Godot at `~/godot451/Godot_v4.5.1-stable_linux.x86_64` (the launcher and `run_headed_suite.sh` default to it), the laptop screen is smaller than 1920x1080. All commands from the implementation worktree root.

Baseline test commands (task A.1; every file below exists today):

```bash
python3 -m pytest WizardRTSHybrid/tests/test_story_slice.py WizardRTSHybrid/tests/test_quest_env.py WizardRTSHybrid/tests/test_dungeon_env.py WizardRTSHybrid/tests/test_duel_env.py WizardRTSHybrid/tests/test_outbreak_env.py WizardRTSHybrid/tests/test_puzzle_parity.py WizardRTSHybrid/tests/test_ward_parity.py WizardRTSHybrid/tests/test_fire_magic.py WizardRTSHybrid/tests/test_content_freeze.py WizardRTSHybrid/tests/test_hash_baseline.py WizardRTSHybrid/tests/test_determinism.py -q
python3 -m pytest tests/sim/test_t083_quest_runtime.py tests/sim/test_t084_dialogue.py tests/sim/test_t080_aspects.py tests/sim/test_t028_people.py tests/sim/test_u05_retained_ward_duel.py -q
PYTHONPATH=tools python3 -m pytest tools/dialogue_generation/tests -q
WizardRTSHybrid/scripts/run_headed_suite.sh story duel wizard campaign
```

The first command takes several minutes (`test_hash_baseline` and `test_determinism` run multi-minute worlds); `WizardRTSHybrid/tests/conftest.py` sets `HYBRID_AI=0` for unit tests. The headed suite starts a simulator per script on a free port and prints `PASS <name>` or `FAIL <name>`; screenshots go to `WizardRTSHybrid/docs/evidence/ubuntu/` by default (`HYBRID_SHOT_DIR` overrides; use `WizardRTSHybrid/docs/evidence/narrative/<milestone>/` for this programme's evidence).

Known pre-existing failures: **none verified.** The planning sessions did not run the suites (they only read code and ran two measurement scripts). A.1 establishes the baseline; anything failing before A.2 changes code is recorded in the ledger as pre-existing with the failure text, not fixed silently and not counted against this programme.

Verified by the planning agent (facts you can rely on): the launcher, the hybrid scene, the hazard duel lease and board hosting, the Ward Duel parity port, the worker programme model, the people registry lifecycle API, the `HybridEnv` pickle format, and the measured numbers in the audit's section 2.4. Planned or assumed (to be proven by your tests): every number in the execution plan's "Done when" clauses, the performance targets, the castability estimates for the workbook, and the claim that W1 leaves every hash baseline unchanged (test it).

Commands and files that **do not exist yet** and are created by the tasks that name them: `wizard_rts/narrative/**`, `tests/test_narrative_*.py`, `tests/test_wizard_*.py`, `client/tests/run_hybrid_{launch,duel_lease,tutorial,quest,stories,acceptance}.gd`, the headed suite names `launch`, `duel_lease`, `tutorial`, `quest`, `stories`, `acceptance`, `scripts/launch_scenario.sh campaign --load`, `scripts/{build_archetypes,build_story_templates,validate_narrative,narrative_report,play_stories}.py`, `data/narrative/**`, the tiers `duel.tutorial_3x3` and `duel.wizard_3x3`, the env switches `HYBRID_LOAD_SLOT`, `HYBRID_AUTOSAVE_SECONDS`, `HYBRID_NARRATIVE_UNLOCK_MS`, `HYBRID_TUTORIAL_EXPIRE_MS`, and the server fixtures `stories` and `acceptance`.

Gameplay claims need the real UI: a playable milestone is accepted only when its headed script passes through the actual Godot scene and, for duels, plays genuine casts through the board's input helpers (execution plan rule 9). `ui_debug_finish_duel` is for interface smoke tests only.

## G. Progress tracking

Maintain `docs/ledger/WIZARD_STORIES_PROGRESS.md`: tick a task only when its "Done when" holds and its verification commands passed, with the evidence (command and result or an evidence path) on the same line; mark half-finished tasks `[~]` with what is left; add a session-log entry at the top of the log at the end of every session with the commit SHAs. Small, reviewable commits: one task per commit when practical, message `stories(<task id>): <what>` plus the attribution line the harness requires; never `git add -A`; never commit `external/`, `runtime/`, saves, anything under `~/dmb_runs`, or `docs/release_notes.md`. Push after every committed task.

## H. Owner checkpoints

Stop after completing A.5 and report: the implementation branch and commit SHA, the baseline counts with pre-existing failures, what A.2 to A.4 changed (files), the test and headed results, the evidence paths, and anything that deviated from the plan. **Do not begin Milestone B until the owner approves checkpoint A.** Every later session works one milestone at a time in the same way (B after A is approved, C after B, and so on), with the checkpoint reports listed in the execution plan's Appendix B.

## I. Recovery and continuation

At the start of any session after the first:

```bash
cd /home/joe/dmb_runs/wt_wizard_implementation || { echo "worktree missing: see section C, but check git branch --list and git ls-remote first"; }
git status --short            # uncommitted work from an interrupted session: read it before touching it
git log --oneline -15         # the last completed tasks are in the subjects: stories(<task id>)
git fetch origin '+refs/heads/feature/wizard-mode-implementation:refs/remotes/origin/feature/wizard-mode-implementation'
git status -sb | head -1      # ahead/behind origin; push anything unpushed before new work
sed -n 1,80p docs/ledger/WIZARD_STORIES_PROGRESS.md   # the first unticked task in milestone order is the current task
```

If the branch exists on origin but the worktree does not: `cd /home/joe/Projects/DuelMasterBattle && git fetch origin '+refs/heads/feature/wizard-mode-implementation:refs/remotes/origin/feature/wizard-mode-implementation' && git worktree add /home/joe/dmb_runs/wt_wizard_implementation feature/wizard-mode-implementation` (or `-b feature/wizard-mode-implementation ... origin/feature/wizard-mode-implementation` if no local branch exists), then verify `git rev-parse HEAD` equals the remote SHA. If the ledger and the log disagree, the log and the code are right: run the verification commands of the task the log says was last done, fix the ledger, and continue from the next task. Never redo a task whose commit exists and whose verification passes; if its verification fails now, record that as a regression and fix it before moving on. Never start a milestone whose checkpoint has not been approved by the owner (the ledger's session log records approvals; if it does not, ask).
