# Prompt: start the Wizard Mode implementation (Milestone A)

Copy everything below the line into a new Claude Code session opened in `/home/joe/Projects/DuelMasterBattle`.

---

You are implementing Wizard Mode for DuelMasterBattle, an approved programme whose specification is already committed in this repository. You have no memory of the planning conversations; everything you need is in the files named below. This session covers **Milestone A only**. Do not start Milestone B.

**Step 1. Read the specification, in this order, before running anything else.** Open the planning branch's documents through the main checkout without changing its branch:

```bash
cd /home/joe/Projects/DuelMasterBattle
git fetch origin '+refs/heads/feature/wizard-settlement-stories:refs/remotes/origin/feature/wizard-settlement-stories'
git show origin/feature/wizard-settlement-stories:docs/WIZARD_IMPLEMENTATION_HANDOFF.md
```

Then, from the implementation worktree once it exists (Step 2), read `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md` (section 0 and Milestone A in full; skim the rest), `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md` (sections 1, 2, 3, 6, 12, 15 in full), `docs/WIZARD_STORY_INTEGRATION_CONTRACT.md` (all), `docs/ledger/WIZARD_STORIES_PROGRESS.md` (all), and `WizardRTSHybrid/CLAUDE.md` and `WizardRTSHybrid/AGENTS.md`. Treat the handover's section D (boundaries) as absolute.

**Step 2. Create the implementation branch and worktree** exactly as the handover's section C says: fetch the latest `feature/wizard-settlement-stories`, discover its current HEAD (do not assume a SHA), confirm the commit subject begins with `stories(plan): final handover`, confirm that `feature/wizard-mode-implementation` does not already exist locally or on origin (if it does, follow the handover's section I instead of recreating it), create the branch and the worktree `/home/joe/dmb_runs/wt_wizard_implementation` from `origin/feature/wizard-settlement-stories`, verify `BASE_OK`, push with `-u`, and verify the remote ref. Never base the branch on `main`, on `feature/neuroevolution-plan`, or on any older commit. Never touch `/home/joe/dmb_runs/wt_wizard_stories` or the main checkout's branch. Record the planning HEAD SHA and the new branch's SHA in the ledger's session log.

**Step 3. Establish the baseline (task A.1).** From the implementation worktree, run the baseline commands in the handover's section F, record the counts and every failure verbatim in `WizardRTSHybrid/docs/evidence/narrative/a/baseline.md` and in the ledger, and classify any failure as pre-existing. Do not fix pre-existing failures in this task.

**Step 4. Work through A.2, A.3, A.4 and A.5 in order,** exactly as the execution plan defines them: the narrative state container created only by `server.py` (no change to `wizard_rts/world.py`); the simulation's own workers as named, talkable characters with the `persons` join; basic save and load with the pause menu and the client-timed autosave; the wrap-up. For each task: make the expected changes, run its verification commands and the quick set in rule 8, run its headed demonstration through the real Godot scene (`run_hybrid_launch.gd`, registered as `launch` in `WizardRTSHybrid/scripts/run_headed_suite.sh`), store screenshots under `WizardRTSHybrid/docs/evidence/narrative/a/`, tick the ledger with evidence, commit (`stories(A.<n>): <what>`, one task per commit, never `git add -A`) and push.

**Step 5. Stop at Owner Checkpoint A.** When A.5's "Done when" holds, update the ledger's session log, commit, push, and report: the branch and final commit SHA, the planning HEAD you started from, baseline counts and pre-existing failures, the files changed per task, test and headed results with evidence paths, anything that deviated from the plan, and any core-simulation change you believe is needed (written into the contract's section 4 table, not made). Do not begin Milestone B until the owner approves.

Rules that override anything else you might infer: the game must stay one integrated world (`HybridWorld`); the faction AIs must never read narrative state; the content catalogue is frozen; the neuroevolution branch, its worktree, its files and its baselines are off limits; no training-gate work; headless tests never replace the headed Godot demonstration for a playable claim; report measured results honestly, including failures.
