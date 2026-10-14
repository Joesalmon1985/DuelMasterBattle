# Neuroevolution programme: task progress

Tasks are defined in `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`; the design is `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`. Tick a task only when its "Done when" holds and its tests pass; write the evidence (test command and result, or an evidence path) on the same line. Keep the newest session note at the top of the session log.

Legend: `[ ]` not started, `[~]` in progress (say what is left), `[x]` done.

## M0 Freeze the catalogue and prepare the machine
- [x] T0.1 Verify the environment — Python 3.14.0, numpy 2.4.0, `git status --short` shows only `docs/release_notes.md`; the 7-file subset gave `67 passed in 100 s` (plan expected 64; the subset has grown since)
- [x] T0.2 Optional packages (psutil) — psutil 7.2.2 installed
- [x] T0.3 C compiler for the native A* kernel (N03) — `winget install BrechtSanders.WinLibs.POSIX.UCRT` worked first try (gcc 16.2.0, user PATH; open a new shell to see it); `pytest tests/test_native_astar.py` -> 1 passed, not skipped
- [x] T0.4 Windows fixes for `resource` imports (`sysinfo.rss_mb`) — `wizard_rts/sysinfo.py` (psutil, resource, ctypes; all three probes agree at ~18 MB); also fixed `perf_gate.py`, a fourth script importing `resource` that the plan did not list; `bench_full_game.py` now uses it too; `bench_sim.py --minutes 2` prints JSON (82.7x realtime, 64 MB), `run_civilisation_tournament.py --seeds 507 --minutes 3 --jobs 1` exit 0 (peak_rss_mb 71/74)
- [x] T0.5 Re-record hash baselines — NOT needed: on Windows/Python 3.14.0 `hash_gate.py check` is OK for `docs/perf/hash_baseline_v4.json` (seeds 507, 11, 23, full length) and `hash_baseline_v4_campaign_plus.json` (seeds 507, 11), and `tests/test_hash_baseline.py` passes. The Linux-recorded hashes reproduce bit for bit here, so no `_v4_windows` files and no platform switch in the test (finding for the determinism work: Linux and Windows agree)
- [x] T0.6 Roster manifest, `freeze.py`, `freeze_content.py`, `CONTENT_FREEZE.md`, `test_content_freeze.py` — `roster-1.0.0` written: 582 entities (486 buildings, 96 units), 168 cards, 33 hand cards, 128 wares, 22 items, 11 liquids, 99 excluded (11 D27 decoys among them), `roster_sha256` c0c611eb...; `pytest tests/test_content_freeze.py` -> 27 passed (6 planned tests; the importer test is one case per script); `coverage_report.py --check` exit 0. Found and fixed a pre-existing Windows bug: `coverage_report.py --check` read the csv with the cp1252 default and always failed on names containing a typographic apostrophe (now utf-8)
- [x] T0.7 Importer guards — `wizard_rts/freeze_guard.py`; all 20 `scripts/import_*.py` (the plan said 23; there are 20) exit 3 "content is frozen" without `DMB_UNFREEZE=1`; `--reason` is stripped from argv so the importers' own parsers never see it; `DMB_UNFREEZE=1 ... --reason test` passes the guard (checked on `import_mindustry_defs.py`, which then stopped at its own missing-`external/` check). Caution for later sessions: `import_openra_rules.py` has no argparse, so `--help` does NOT stop it; do not use it as a dry-run
- [x] T0.8 Documents, full suite on Windows, ledger. **OWNER CHECKPOINT (waiting for the owner)** — plan v2 rows P6/P7/P9/P11 marked superseded in `docs/ledger/LEDGER.md`. Full suite (`pytest WizardRTSHybrid/tests -q --ignore=test_five_minutes.py`, Windows, Python 3.14.0, gcc on PATH): **3 failed, 1054 passed, 18 skipped in 988 s (16 min 28 s)**. The 3 failures: (1) `test_generic_buildings.py::test_lua_durations_and_ware_names` was caused by this milestone (the T0.7 guard stops the importer module loading); fixed in the test (unfreeze for the import only) and re-run green. (2, 3) `test_puzzle_parity.py::test_generated_puzzles_match_for_80_seeds` and `::test_logic_matches_step_by_step` are PRE-EXISTING Windows failures, not caused by this milestone: the fixture is opened with `gzip.open(FIX, "rt")` (cp1252 default on Windows), so em dashes arrive as mojibake; no puzzle code or fixture was touched (one-line fix, `encoding="utf-8"`, left for the owner to approve). 18 skips are environmental (no Godot binary, no `external/mindustry` clone, no Red Alert content, a few naval cases skipped by design)

## M1 Environment hardening
- [x] T1.1 Visibility model (`neuro/vision.py`), heuristic AI and `HybridEnv` use it; baselines re-recorded; before/after tournament evidence — `visibility.py` gained `memory_of/refresh/reveal/remember/visible_units/known_enemy_buildings/visible_regions` (bucketed scan, no measurable slowdown: 75.5x -> 75.9-76.4x realtime); scouts (`workers.py`) and spies (`openra_abilities.py`) feed the memory; `HybridEnv.observe` (`enemy_capitals`, `threats`, `known_enemy_buildings`), `legal_actions['attack']` (remembered buildings + visible units + visible nests) and a new `not_visible` check on the `order` op use it; `ai._known_targets` reads the memory only (no free home capitals, no 32-tile awareness). Tests `test_neuro_vision.py` (12), `test_visibility.py` updated (an explored cell is no longer a sighting). Evidence `WizardRTSHybrid/docs/evidence/neuroevo/m1_vision/COMPARISON.md`: 40 min VP identical (plus 7.0 / baseline 6.17); 120 min within noise, wars still happen. Baselines re-recorded as `docs/perf/hash_baseline_v5.json` (showcase/baseline AI, diverged at minute 12 as expected) and `hash_baseline_v5_campaign_plus.json` (now 60 min); v4 files kept as history; `test_hash_baseline.py` checks both v5. KNOWN GAPS (not in the plan's T1.1 scope, listed for the owner): the heuristic AIs still read global state for guard-post direction (`ai._posts`, expansion distance to enemy command centres) and local force counts (`ai._nearest_enemy_unit`, `ai_plus.force_near`); a remembered building that no longer exists is silently dropped from the AI's target list
- [x] T1.2 Split successors are controlled (N07) — `history.split` adds the successor to `ai_factions` (heuristic parent) or to `agent_successors[parent]` (agent parent); `HybridEnv.seats_of/seats`, `step` accepts actions for and returns observations, rewards (0.0) and terminated flags of successor seats, `info['seats']`. `test_neuro_successor.py` (5): AI successor drafts within 60 s, agent successor is not played by the AI, accepts a draft command, rejects foreign targets, recursion works
- [x] T1.3 Alive means not collapsed — `HybridEnv._alive` = `history` state != collapsed; `observe['alive']` follows it; `info['faction_states']`. The existing elimination test passes unchanged (a lone-settlement faction collapses within the 1 s step); new tests: a faction that loses its capital building but holds another settlement stays alive, a faction with nothing left is terminated with the penalty
- [x] T1.4 Full action surface in `HybridEnv` — ops `belt upgrade configure link_power trade propose respond` as planned plus `break_treaty` (an existing mechanic H8 needs); `nest_policy` deliberately NOT exposed (it only steers the heuristic AI). Every op checks ownership first (payload parsed before ownership so a malformed payload is always `malformed:*`; the handler now also catches `IndexError`/`AttributeError`); trade partners must be remembered, in sight or allied (`unknown_partner`); `order` needs a visible/remembered target. `legal_actions` gained masks `upgrade configure link_power propose break_treaty respond trade`; `step(observe=False)` returns `{}`. Audit: with these, every public command of `HybridWorld` (build road queue cancel move stop rally demolish dismantle convert waterway belt enhance upgrade configure draft deploy ability order) and the trade/diplomacy commands are reachable; not reachable by design: God-only commands (`grant_card`, pose/speed, hazard duels). `test_neuro_actions_env.py` (21 passed); with sim_api, industry, nests/trade, vision, successor tests 110 passed
- [ ] T1.5 Episode runner (`neuro/episode.py`) with end reasons, checkpoints, validation
- [ ] T1.6 Full suite, hash gate, ledger. **OWNER CHECKPOINT**

## M2 Observation layer and candidates
- [ ] T2.1 Static tables (`KIND_INDEX`, `KIND_STATIC`, `KEY_WARES`, `WARE_GROUPS`, `CARD_FEATURES`, `obs_schema_hash`)
- [ ] T2.2 Per-decision feature assembly with caches; shape, finiteness, extreme-preservation and no-hidden-information tests
- [ ] T2.3 Candidate generation (`neuro/candidates.py`), 95% acceptance test, timing

## M3 Networks and controller
- [ ] T3.1 Genome layout and networks (`neuro/nets.py`), round-trip and shape tests, exact genome size recorded here: ______
- [ ] T3.2 Controller (`neuro/controller.py`), decision log, `play` command, determinism test. **OWNER CHECKPOINT**

## M4 Fitness, league, manifest, curriculum configuration
- [ ] T4.1 Fitness (`neuro/fitness.py`) with table-driven tests
- [ ] T4.2 Manifest and versions (`RULES_VERSION`, `neuro/manifest.py`, compatibility rule; records the catastrophe level and scale)
- [ ] T4.3 League (`neuro/league.py`): opponent mixer, champion archive, behaviour grid, promotion decision (with the optional retention rule)
- [ ] T4.4 Catastrophe curriculum configuration (N10, `neuro/curriculum.py`, one rung C0 = scale 1.0; the calibration study that stood here moved to T10.1)

## M5 Evolution loop, persistence, CLI, launchers, reports
- [ ] T5.1 Workers (`neuro/workers.py`): spawn pool, heartbeats, wall cap, repro.json
- [ ] T5.2 Evolution loop (`neuro/evolve.py`) and imitation seeding (`neuro/imitation.py`); smoke test
- [ ] T5.3 Persistence (`neuro/persist.py`): model export/import, checkpoints, pruning
- [ ] T5.4 CLI (`train_ai.py`), code copy per run, `--run auto`, `--hours`, champion copy to `neuro/models/`
- [ ] T5.5 Windows launchers (`Train AI.bat`, `Stop AI Training.bat`, `AI Training Status.bat`, `Evaluate Best AI.bat`, `Prove Evolution Overnight.bat`), keep-awake
- [ ] T5.6 Session report (`LAST_SESSION_REPORT.md`) and `status`
- [ ] T5.7 Storage test, full suite, `smoke` demonstrated. **OWNER CHECKPOINT**

## M6 First proof of evolution (60-minute games)
- [ ] T6.1 Overnight proving run
- [ ] T6.2 Judgement against the acceptance rule; report `docs/evidence/neuroevo/m6_proof/report.md`. **OWNER CHECKPOINT**

## M7 Performance pass (hash-equal)
- [ ] O1 command-centre / settlement caches
- [ ] O2 logistics request index
- [ ] O3 idle-site wake-up heap
- [ ] O4 spatial hash for scans
- [ ] O5 event log subscription filter
- [ ] O6 native A* measured (if the compiler was installed)

## M8 Tactical controller
- [ ] N11 implemented, ablation report, default decided

## M9 The 240-minute programme
- [ ] First overnight `Train AI.bat` session and report read by the owner
- [ ] Session reviews every 5 sessions under `docs/evidence/neuroevo/progress/`

## M10 Catastrophe curriculum (stage 2; starts only on the owner's decision after M9)
- [ ] T10.1 Outbreak calibration study (formerly T4.4; proposes the ladder, owner approves). Evidence `docs/evidence/neuroevo/m10_calibration/`
- [ ] T10.2 Retention wiring (games at earlier levels, retention rule in promotion, per-level report)
- [ ] T10.3 First level increase and each later rung. **OWNER CHECKPOINT before every increase**

Catastrophe level in force for all training until the owner says otherwise: **C0 (default cadence, `outbreak_interval_scale` 1.0)**.

## Session log (newest first)
- 2026-10-14 (Claude Sonnet 5.5): owner approved M0 and gave new direction. Done: explicit utf-8 for the puzzle and ward parity fixtures (`test_puzzle_parity.py`, `test_ward_parity.py`: 11 passed; commit `d60f092a`). Decision N10 recorded (design 0.6 and 7.8, 8.5, 9.x, 10.x, 12, 13 M4/M9/M10, 14, 15 Q2; execution plan 0, T1.5, T4.2-T4.4, T5.x, T6.1, M9, new M10, appendix; register N01/N10): catastrophe difficulty is a progressive curriculum; stage 1 trains at the default setting; calibration study moved from M4 to M10; nothing removed.
- 2026-10-14 (Claude Sonnet 5.5): M0 complete (T0.1-T0.8); stopped at the M0 OWNER CHECKPOINT. Deviations from the plan text: 67 not 64 tests in the T0.1 subset; 20 importers not 23; `perf_gate.py` also needed the `resource` fix; no hash re-record needed (Windows matches the Linux baselines); fixed a Windows encoding bug in `coverage_report.py --check`. Not started: M1.
- 2026-10-14 (Claude Fable 5.1): `work/mechanics-completion-v4` merged at `1b404a8b` on the owner's request (conflicts: v4's 168-card system kept over PR #17's rule; register renumbered D33/D34). Merged-tree checks: 84 tests passed (sim API, VP/eras, outbreaks, content graph, coverage, NN, hash baseline, visibility, ware classes, draft reachability, determinism); roster now 582 entities / 168 cards; 40-minute bench 79 s. No implementation task started.
- 2026-10-14 (Claude Fable 5.1): plan and execution plan written and approved; no task started. Benchmarks in `WizardRTSHybrid/docs/evidence/neuroevo/bench_240/`.
