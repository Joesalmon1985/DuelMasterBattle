# Next agent handoff

## INTEGRATION, 15 Oct 2026: training, multiplayer and the wizard campaign are all on `main`

The owner asked on 15 Oct 2026 for the three workstreams to be brought together and merged into `main`. `main` now holds, in this order:

1. `feature/neuroevolution-plan` (62 commits): hierarchical neuroevolution, `train_ai.py`, the content freeze. Restart note: the next section of this file.
2. `feature/wizard-mode-implementation` (14 commits beyond its fork from the neuro branch at `4b67f55c`): the settlement-stories plan, the wizard campaign, narrative, dialogue, quests, save and load, the responsive UI. Entry: `docs/WIZARD_IMPLEMENTATION_HANDOFF.md`, ledger `docs/ledger/WIZARD_STORIES_PROGRESS.md`.
3. `feature/mobile-lan-multiplayer` (5 commits from `143797ba`): LAN host and client, PvP Ward duels, Android packaging. Entry: `docs/MOBILE_LAN_MULTIPLAYER.md`.

Two conflicts, both resolved by keeping both sides:

- `WizardRTSHybrid/wizard_rts/workers.py`: one import line (`flow`, `visibility` from the neuro branch; `hold` from the wizard branch).
- `godot_project/client/scenes/hybrid_world.gd`: the wizard HUD, pause menu, zoom, save and autosave (wizard branch) and the LAN client (multiplayer branch) share one scene script. The wizard `_on_menu` dispatches to the LAN menu (`_mp_on_menu`, Continue or Leave) in a LAN game; autosave and the quit-save are skipped when `mp` is true because the host owns the world. The LAN hotkeys (C, Y, N) are read after the pause menu and before the zoom keys.

Verification on the merged tree (Windows 11, Python 3.14, Godot 4.5.1): 

- Python: `python -m pytest WizardRTSHybrid/tests --ignore=WizardRTSHybrid/tests/test_five_minutes.py`: **1372 passed, 20 skipped, 1 failed** (34 min, sharing the CPU with the headed runs). The failure, `test_lan_multiplayer.py::test_bad_json_and_oversize_lines_do_not_kill_the_host`, was a bug carried in from the multiplayer branch, not a merge effect: `net/host.py` read `t_op` and `message` after a bad-JSON reply, where they were unbound, so the host thread died and both clients timed out. Fixed here (both are bound before the parse); `test_lan_multiplayer.py` and `test_lan_story_shared.py` then pass 17 of 17.
- Godot headless (Godot 4.5.1, after `--import`): `run_lan_parse.gd` loads all eight LAN and world scripts and the net duel mirror checks pass (`HYBRID_LAN_PARSE_OK`); `run_hybrid_coords.gd` passes.
- Headed, each against a fresh simulator: `launch` (campaign profile: pause menu, a conversation, autosave), `campaign`, `wizard` and the LAN `two_clients` acceptance (two wizards on screen, a declined challenge, a full human-versus-human Ward duel through the real board, back to the world) all **PASS**. Screenshots were written to a scratch folder, not to the evidence tree.
- Rest of the headed suite, run on the merged tree on 15 Oct 2026 (branch `fix/post-merge-followups`, Windows 11, 1920x1080, Godot 4.5.1, shots and saves in a scratch folder): **PASS** `walk visual duel forestry food god war terrain naval mcv campaign_dev story tutorial ui conversation camera apprentice_win apprentice_lose autoplay playtest2`, and `outbreak`, `eras`, `inspector` on a second run (see below). **FAIL, pre-existing:** `playtest` ("found a clear 13-tile run for the wizard", the same message as in the wizard ledger) and `industry` (two checks, `mdy:silicon_smelter is drawn in its role colour` and `the dagger's light triangle is drawn on its tile`; identical on the tip of `feature/wizard-mode-implementation` at `1b049237`, so not a merge effect). `campaign_dev` and `eras`, listed as pre-existing failures in the wizard ledger, pass on the merged tree. **Transient:** in the first run `outbreak` and `eras` exited after about 30 seconds without any marker or error line (the Godot process ended before the script could print its verdict) and `inspector` failed one screenshot comparison ("facing buttons change the rendered sprite"); all three passed when rerun alone immediately afterwards (36 s, 48 s, 64 s), so they are flaky on this machine, not merge effects. The owner was using the desktop at the time of the first run, which can take the window out of front (the known no-draw pitfall).
- Not verified here: the Android APK, physical phones, and a training run on the merged tree.
- Fixed on `fix/post-merge-followups`: the LAN status line (`_mp_status`) no longer sits on the campaign HUD card or the top bar. `hybrid_world.gd` lays it out in `_mp_relayout()` (called at build, on every viewport resize and from `relayout_ui()`): under the top bar (its minimum height, which is known before the first layout pass), to the right of the HUD card, right-aligned with word wrap, sized by the same physical-pixel metrics as the HUD. `run_lan_two_clients.gd` now asserts the three rectangles are disjoint at 720x1280 and at 1280x720 (`HYBRID_LAN_STATUS_LAYOUT`) and writes `lan_two_wizards_landscape.png` beside `lan_two_wizards.png`; `two_clients` PASS (a full duel, stalemate by exhaustion, 10 casts) and `parse` PASS after the change. The committed evidence shots in `WizardRTSHybrid/docs/evidence/lan/` still show the old placement.
- Windows pitfall, not fixed: `run_headed_suite.sh` and `run_lan_headed.sh` end each simulator or host with `kill` on the Git Bash job, which only ends the `env.exe` wrapper; the `python3.exe` launcher and the real `python.exe` underneath keep running (one tree per headed test, found 30 of them after one suite run). List them with `Get-CimInstance Win32_Process | ? CommandLine -match 'wizard_rts'` and stop exact PIDs; the fix would be `taskkill //PID $pid //T //F` on Windows in both scripts.
- Follow-up noticed, not fixed: at 720x1280 the campaign HUD card (`campaign_hud.gd`, placed at y = 58 physical px) overlaps the bottom of the top bar (menu and Magic buttons end at y = 86); the HUD assumes the bar is 58 px tall, which only holds in landscape.

The "never merge to `main`" rule in the sections below was the standing rule for the agents on those branches; it was lifted for this one merge by the owner's instruction. It stands again for whatever comes next: work on a branch, and let the owner decide the merge.


## RESTART NOTE, 15 Oct 2026 (M0-M8 built; M6 judged FAIL; M9 setup ready, no training started): read this first

**Branch** `feature/neuroevolution-plan`; never merge to `main`; `docs/release_notes.md` is always modified locally and must never be committed (never `git add -A`).
**State:** full Windows suite **1212 passed, 19 skipped, 0 failed** (`cd WizardRTSHybrid; py -3 -m pytest tests`, 28 minutes); freeze check clean; hash gates OK on both v5 baselines; `train_ai.py smoke` finishes in about 2 minutes. `Train AI.bat` (config `full240`) is ready to run on a clean tree (it refuses on uncommitted changes under `WizardRTSHybrid/`, `sim/`, `train_ai.py`; `neuro/models` is excluded). **No overnight training has been run by the owner yet and `neuro/models/` is empty.**

**M6 result (owner checkpoint, `docs/evidence/neuroevo/m6_proof/report.md`): FAIL by the pre-registered rule, with evidence of learning.** Run `proving` (attempt 3, 23 generations, 4 of the planned 8 hours): final best against generation-0 best on 8 held-out seeds x 2 legs +1.9 [90% lower bound -0.8], 4/8 seeds. But the random-start lineage's final mean beat its own start by +15.4 [+11.7], 6/6 seeds (`scripts/compare_genomes.py`); the imitation lineage did not move (-1.2). Neural seats are still about 40 fitness points below the heuristic AI; no champion has ever been promoted. Earlier attempts (`proving-attempt1/2`) were stopped after 5 generations each; their folders are in `%USERPROFILE%\dmb_runs\neuro\`.
**Decision wanted from the owner:** rerun M6 (more games per entry, or a lower-dimensional search over the heads' output layers and temperatures) or accept the imitation seed and go to M9. The owner also suggested (and I agree) strengthening the imitation step first: record hundreds of heuristic games, train all head layers by gradient descent (needs a small backprop implementation; start with the heads on frozen encoders), check on held-out games how close it gets to the heuristic, then evolve from there with the anchor guard.

**M7:** O1 (territory lookups) and an unplanned fix (`tech.cards()` was rebuilt on every call, 9% of a late-game profile) are done and hash-equal; O2-O5 not done (judged too risky); the 240-minute speed (target 800 s) was not measured on an idle machine. **M8:** N11 implemented, engagement proven in a constructed fight (all four orders accepted by the simulator); ablation on/off made no difference (identical fitness over 12 paired games, 37 orders), so it is not adopted by the rule; a trained N11 needs a run with `tactical: true`. **M10 must not be started** (owner decision N10); everything stays at catastrophe level C0.

**Changes made during M6 that deviate from the written design (all in the ledger session log):** H5 "scout" candidate; expansion sites no longer need explored ground; `adam_lr` 0.006; the anchor guard in `evolve.py` (each lineage keeps its best-known mean, re-evaluates it with the new parent on the same games and reverts if the parent is worse); imitation fits all nine heads and shifts the wait score to -0.6. Workers are one subprocess per game from the run's frozen code copy (`neuro/workers.py`).

**Running things:** `py -3 train_ai.py train --run proving --config proving60 --hours 8 --workers 14 --keep-awake --no-models` (60-minute games, 7-10 minutes per generation, writes nothing to `neuro/models`); `Train AI.bat [hours]` (240-minute games, a generation will take roughly 1.5-2 hours, so one night is 4-5 generations; not yet timed on an idle PC). Start long runs **detached** (`Start-Process` from PowerShell with redirected output). Stop with `py -3 train_ai.py stop --run NAME` (graceful) or `--now`. A run resumes only if the code hash, versions and config name match its manifest; any code change starts a new run seeded from `best_ai.json`. Judge a proving run with `scripts/judge_proof.py`; compare genomes with `scripts/compare_genomes.py`; tactical ablation `scripts/ablate_tactical.py`.
**Key findings:** victory points equal standing settlements, so fitness is sparse (a random genome stays at 1 VP for 60 minutes, heuristics reach 4-7); children differ from their parent by 3-8 fitness points against a measurement error of 7-13, so a gradient estimate in up to 15,000 dimensions from a few mirrored pairs is mostly noise; timing measurements are unreliable while a training run is using the CPU.
**Rules:** the content roster is frozen (`docs/CONTENT_FREEZE.md`, `scripts/freeze_content.py --check`); report negative results exactly; update the ledger per task; commit per task and push. Machine: Windows 11, Python 3.14, gcc on the user PATH, 8 cores / 16 threads, 32 GB.

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
