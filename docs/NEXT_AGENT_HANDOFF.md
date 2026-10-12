# Next agent handoff (updated 12 October 2026)

**Branch:** `feature/hybrid-playtest-fixes-v03`. **Last verified commit:** see `git log -1`. Nothing is merged to `main`. The owner's untracked files in `docs/` and `godot_project/content/` are untouched; **do not `git add -A`** (legacy `tests/sim` rewrites `godot_project/content/compiled/*`: restore with `git checkout -- godot_project/content/compiled` before committing; `batch.t133.valid.json` was already modified by the owner).

## State
Authority: `docs/IMPLEMENTATION_RUN_STATUS.md` (completed / partial / blocked / not started). Direction: `docs/DuelMasterBattle_Design_v0_5.md`, `docs/DECISION_REGISTER.md` (D01-D21).

Done and tested: M1, M2 (and the AI placing the line), M3 (story slice, puzzle port with GDScript parity, headed UI), M4 (VP, eras, cycle reset on the same land, headed `eras`), M5 (outbreaks, headed), six headless environments, a NumPy training harness. **Partial:** M6 breadth (see `WizardRTSHybrid/docs/COVERAGE.md`), training results: the dungeon and cross-system policies did **not** learn (`WizardRTSHybrid/docs/TRAINING_PROGRAMME.md`, bottom). **Not started:** builder worker and mine workers, liquids and routers, most OpenRA content, `train.py --domain rts` re-run with the new strategy reward.

## Commands
```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py     # 312 passed, about 25 min
python3 WizardRTSHybrid/scripts/run_all_scenarios.py --suite smoke                                  # seconds; --suite envs systems training stress parity for more
python3 WizardRTSHybrid/scripts/train.py --domain duel dungeon outbreak quest fullgame --budget standard --seed 0   # bounded, opt-in, runs go to ~/dmb_runs
python3 -m pytest tests/sim -q          # legacy, 507 passed (then git checkout -- godot_project/content/compiled)
WizardRTSHybrid/scripts/run_headed_suite.sh [names]     # 17 headed scripts incl. campaign campaign_dev industry story outbreak eras; needs DISPLAY; HYBRID_SHOT_DIR
WizardRTSHybrid/scripts/run_headed_one.sh <script.gd> ENV=VAL ...
GODOT_PARITY=1 python3 -m pytest WizardRTSHybrid/tests/test_puzzle_parity.py WizardRTSHybrid/tests/test_ward_parity.py -q   # re-export from the real GDScript and compare
python3 WizardRTSHybrid/scripts/build_catalogue.py && python3 WizardRTSHybrid/scripts/make_coverage.py   # regenerate COVERAGE.md
python3 WizardRTSHybrid/scripts/build_consolidated_design.py                                        # after editing design parts
```
Godot: `~/godot451/Godot_v4.5.1-stable_linux.x86_64`; Godot sim tests `--headless --path godot_project --script res://sim/tools/run_tests.gd` (32 pass). Do not edit sources while a pytest run or a headed suite is running. Never `pkill -f` a pattern that matches your own shell; kill by pid.

## Lessons from this run
- The live client numbers its own clock sequence; a hand-made `advance` sequence is silently ignored. Pressing G (God Mode) pauses the clock. The AI drafts for any faction the player does not control, so a test that needs an open offer must `control` the faction first and use `HYBRID_DRAFT_MS`.
- Developer pacing switches: `HYBRID_DRAFT_MS`, `HYBRID_ERA_MS`, `HYBRID_ERA_VP`, `HYBRID_FIXTURE`, `HYBRID_FIXTURE_FACTION` (developer profile only).
- The S04 era threshold of 10 VP was not reached in 40 game minutes on three seeds; the default is 6 until the owner decides.

## Very next actions
1. Fix the dungeon policy (richer observation: entity roles and the first unsolved puzzle; or train on the expert's macro verbs) and the cross-system policy (imitate `treat_first`/`story_first` before REINFORCE). Report held-out numbers against the scripted baselines; do not ship weights as a game dependency.
2. M6 breadth in the order of `docs/ROADMAP_NEXT_RUN.md`: builder worker, mine workers, liquids and routers, more OpenRA buildings and units; update `feature_status.json` evidence only with a test.
3. Owner decisions outstanding: S04 threshold (6 vs 10), S05 draft cadence, what the Modern and Dystopian eras should unlock beyond cards.
