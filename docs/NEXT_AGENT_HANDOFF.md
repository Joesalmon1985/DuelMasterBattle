# Next agent handoff

## RESTART NOTE, 15 Oct 2026 (M0-M8 done except where marked; ready for the owner's decision before M9): read this first

**Branch** `feature/neuroevolution-plan`; never merge to `main`; `docs/release_notes.md` is always modified locally and must never be committed (never `git add -A`; stage `docs/`, `WizardRTSHybrid/`, `train_ai.py`, the `.bat` launchers).

**Done and evidenced** (ledger `docs/ledger/NEUROEVO_PROGRESS.md`, newest entries first in its session log): M0-M5 (infrastructure, observation, candidates, networks 87,430 floats, controller, fitness/league/manifest/curriculum, workers, evolution loop, imitation lineage, persistence, CLI, launchers, reports); M6 run and judgement; M7 partly; M8 implemented and ablated. Full Windows suite on the final code: **1212 passed, 19 skipped, 0 failed (1,680 s)** (run `cd WizardRTSHybrid; py -3 -m pytest tests`, 27 minutes). `train_ai.py smoke` passes (130 s).

**M6 result: FAIL by the pre-registered rule, with evidence of learning** (`docs/evidence/neuroevo/m6_proof/report.md`). 23 generations of 60-minute games in 4 hours (planned 8): final best against generation-0 best +1.9 [90% lower bound -0.8], 4 of 8 seeds. But the random-start lineage's final mean beat its own starting genome by +15.4 [+11.7], 6/6 seeds, so the loop learns; the imitation lineage did not improve on its seed (-1.2). Neural seats are still about 40 fitness points worse than the heuristic AI; no champion was ever promoted, so `neuro/models/` is empty and `Evaluate Best AI.bat` has nothing to evaluate.
**Owner decision needed before trusting an overnight run**: (a) accept the current state and start `Train AI.bat` (full240) knowing that a 240-minute generation (population 24, 4 seeds) takes roughly 1.5-2 hours so one night is only 4-5 generations; (b) rerun M6 once more with more games per entry (the next lever; evaluation noise 9.3 vs spread between children 12.0) or a lower-dimensional search (heads' output layers and temperatures only); (c) start with 60-minute games (`--config proving60 --run <name> --no-models` still never writes models; drop `--no-models` to let promotions reach `neuro/models/`).

**What changed after the first pause (all committed; see the session log):** scouting candidate (M5); expansion sites no longer need explored ground (the main fix: without it a faction could not found a settlement for 25 minutes); Adam step 0.02 -> 0.006 in `proving60` and `full240`; the anchor guard in `evolve.py` (each lineage re-evaluates its best-known mean on the same games as the new parent and reverts a worse parent; a deviation from design 7.1, owner to confirm); M7: territory lookups and the cached `tech.cards()` (hash gate OK on both v5 baselines; O2-O5 not done, the 800 s target not measured); M8: `neuro/tactical.py` N11 works (constructed-fight test: all four orders accepted) but the on/off ablation shows no effect (+0.0, 37 orders in 12 games) and N11 is untrained in any genome, so it is NOT adopted; `scripts/ablate_tactical.py`, `scripts/compare_genomes.py`, `scripts/judge_proof.py` exist.
**Not done:** M7 O2-O5 and a 240-minute re-measurement on an idle machine; a trained-N11 test (needs a run with `tactical: true`); the M9 first overnight session and the session reviews; **M10 must not be started** (owner decision N10; level C0 only).

**How to run:** `Train AI.bat` (8 h, full240, resumes the current run if code/versions/config match, else starts a new run seeded from `neuro/models/best_ai.json` if it exists); `py -3 train_ai.py train --run NAME --config proving60 --hours 8 --workers 14 --keep-awake --no-models` for 60-minute proofs. Run long jobs **detached** (PowerShell `Start-Process` with redirected output); a tool-managed background command can be killed. `py -3 train_ai.py stop` stops gracefully (partial generations are used when at least 4 children finished). Earlier attempts are in `%USERPROFILE%\dmb_runs\neuro\proving-attempt1`, `proving-attempt2` and `proving` (attempt 3).
**Key findings:** victory points equal standing settlements (plus conquests), so fitness only varies once settlements are founded; random genomes stay at 1 VP; the imitation genome (shadow games of the heuristic, ridge fit of the head output layers, wait shift -0.6) reaches 1-4 VP per seat, the heuristic 4-7. Children differ from their parent by 3-8 points, measurement error is 7-13: the search is noise-limited, so more games per entry or fewer searched dimensions are the levers. Worker design: one subprocess per game from the run's frozen code copy.
**Rules:** content roster frozen (`docs/CONTENT_FREEZE.md`, `scripts/freeze_content.py --check`); catastrophe level C0 only; report negative results exactly; update the ledger per task; commit per task and push; hash gate for any simulator change. **Machine:** Windows 11, Python 3.14, gcc on the user PATH, 8 cores / 16 threads, 32 GB; timings taken while a training run is active are not comparable.

## 14 Oct 2026: content freeze and hierarchical neuroevolution (APPROVED; implementation starts at task T0.1)

**Read first, in this order:** `docs/EXECUTION_PLAN_NEUROEVOLUTION.md` (the task-by-task guide you execute), `docs/ledger/NEUROEVO_PROGRESS.md` (which tasks are done), then `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md` (the design the tasks implement). Branch `feature/neuroevolution-plan`, cut from `origin/main` at `fd6e3d80`. The owner approved the plan and all its recommended defaults on 14 Oct 2026 (register D33/D34, N01-N09).

Summary of the milestones (details and acceptance in the execution plan):

1. **M0 Freeze**: `wizard_rts/freeze.py` + `data/content_freeze.json` generated by a new `scripts/freeze_content.py` (the counting logic exists in `WizardRTSHybrid/docs/evidence/neuroevo/scripts/count_entities.py`: on the merged tree 582 entities, 168 generated cards, prototype roster sha256 `7afaf3ae...`), `tests/test_content_freeze.py`, importer guards (`DMB_UNFREEZE=1 --reason`), `docs/CONTENT_FREEZE.md`, decision rows D33/D34, re-recorded hash baselines, Windows fixes for the three scripts that `import resource`.
2. **M1 Environment hardening**: visibility model (`neuro/vision.py`) for observations and the heuristic AI; `HybridEnv` action surface extended to all 245 building kinds, 252 Mindustry kinds, belt/upgrade/configure/link_power/trade/propose/respond; **fix the uncontrolled split-successor bug** (`ai.ai_quantum` skips factions not in `world.ai_factions`; `history.split` never adds the successor); alive = not collapsed; `neuro/episode.py` with end reasons and 30-minute checkpoints.
3. M2 observation layer, M3 networks and controller, M4 fitness/league/manifest plus the outbreak calibration study, M5 evolution loop/persistence/CLI (`train_ai.py train|resume|evaluate|status|export|smoke|play`), M6 the first proof of evolution on 60-minute games (acceptance in plan section 12), M7 hash-equal performance pass, M8 tactical controller, M9 the 240-minute programme.

Measured on this PC (Ryzen 7 5800X, Python 3.14, no compiler, pure-Python A*): a 240-minute six-faction `plus` game takes about 1,000-1,100 s of one core (about 14x real time on average, 45x early, 10x late, 530-590 buildings at the end); zero outbreaks occurred at the default cadence in both benchmark games, so the training cadence is an owner decision (plan section 8.5, Q2). Evidence: `WizardRTSHybrid/docs/evidence/neuroevo/`. Reproduce: `py -3 WizardRTSHybrid/scripts/bench_full_game.py --minutes 240 --seed 7 --out <dir>`.

Rules unchanged: never `git add -A`; never merge into `main` without the owner; kill exact PIDs, never `pkill -f` a pattern in your own command line. The repository holds both `docs/RELEASE_NOTES.md` and `docs/release_notes.md`, which collide on Windows and always show as modified; do not commit or "fix" that.

## 12 Oct 2026: autonomous civilisation run (kept)

**Read first:** `docs/AUTONOMOUS_CIVILISATION_RUN_STATUS.md` (ledger, measurements, stop points). Branch `feature/hybrid-playtest-fixes-v03`;
nothing merged to `main`. Rules: never `git add -A`; never `pkill -f`/grep-kill a pattern that is in your own command line (kill exact PIDs).

## What this run added (all in the one HybridWorld, headless and in Godot)
- D22 inexhaustible mineral sites; miner quest caused by a real gallery collapse (`disruption.py`, `story.py`).
- Workplace disruptions, settlement unrest (`society.py`), splits with cooldown, militia in every command centre, Concrete capitals.
- Tech v2: 33 cards, offers of up to 7 every 4 game minutes (3-minute window); world-VP eras (6/8/8 VP, 75-minute stall guard).
- Settlers (Prehistoric expansion), war lodge warriors, OpenRA infantry/vehicles, Mindustry crawler/nova; trade caravans (`trade.py`).
- Blight nests: outbreaks as immobile hostile actors whose health bars are cubes (`nests.py`, era table in `data/outbreaks.json`).
- Improved AI `ai_plus.py` (policy per faction: `world.ai_policy`, env `HYBRID_AI_POLICY=baseline|plus|mixed`).
- Tournament runner `WizardRTSHybrid/scripts/run_civilisation_tournament.py --help` (paired mirrored seeds, CSV/JSONL/HTML).
- Godot: solid trees/rocks, decluttered labels, quest objective line, outbreak status, nest drawing, spectator HUD,
  `launch_scenario.sh autoplay`, headed tests `run_hybrid_autoplay.gd`, `run_hybrid_playtest2.gd`.
- Art: OpenRA vehicles/defences (`scripts/import_openra_units.py`), Mindustry blocks/units (`scripts/import_mindustry_art.py`).

## Headless commands
```
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --mode war --seeds 507 11 23 --minutes 60 --jobs 2 --report-dir ~/dmb_runs/x
python3 -m pytest WizardRTSHybrid/tests -q          # 338 passed at 7695535, ~38 min on the T460
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --mode crisis [--wizard-pilot] --seeds 507 11 23 --minutes 60 --report-dir ~/dmb_runs/y
WizardRTSHybrid/scripts/run_headed_suite.sh playtest2 autoplay outbreak
WizardRTSHybrid/scripts/launch_scenario.sh autoplay
```

## Next steps (in order)
1. Decide or measure the Modern -> Dystopian pace (0/12 in 90 min after the split tuning; `vp.ERA_VP_THRESHOLDS`).
2. Record outbreak unrest in the split chronicle, then tune splits further if the owner wants them rarer.
3. Late-game speed for 16x in Godot with large armies.
4. Licensed art for the new units (status item 15).

## Earlier handoff (kept)
# Next agent handoff (updated 12 October 2026)

**Branch:** `feature/hybrid-playtest-fixes-v03`. **Last verified commit:** see `git log -1`. Nothing is merged to `main`. The owner's untracked files in `docs/` and `godot_project/content/` are untouched; **do not `git add -A`** (legacy `tests/sim` rewrites `godot_project/content/compiled/*`: restore with `git checkout -- godot_project/content/compiled` before committing; `batch.t133.valid.json` was already modified by the owner).

## State
Authority: `docs/IMPLEMENTATION_RUN_STATUS.md` (completed / partial / blocked / not started). Direction: `docs/DuelMasterBattle_Design_v0_5.md`, `docs/DECISION_REGISTER.md` (D01-D21).

Done and tested: M1, M2 (and the AI placing the line), M3 (story slice, puzzle port with GDScript parity, headed UI), M4 (VP, eras, cycle reset on the same land, headed `eras`), M5 (outbreaks, headed), six headless environments, a NumPy training harness. **Partial:** M6 breadth (see `WizardRTSHybrid/docs/COVERAGE.md`), training results: the dungeon and cross-system policies did **not** learn (`WizardRTSHybrid/docs/TRAINING_PROGRAMME.md`, bottom). **Not started:** builder worker and mine workers, liquids and routers, most OpenRA content, `train.py --domain rts` re-run with the new strategy reward.

## Commands
```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py     # (earlier run) 312 passed at 6ab0a4c; see the top section for the current count
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
