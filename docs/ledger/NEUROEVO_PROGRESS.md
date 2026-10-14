# Neuroevolution programme: task progress

Tasks are defined in `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`; the design is `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`. Tick a task only when its "Done when" holds and its tests pass; write the evidence (test command and result, or an evidence path) on the same line. Keep the newest session note at the top of the session log.

Legend: `[ ]` not started, `[~]` in progress (say what is left), `[x]` done.

## M0 Freeze the catalogue and prepare the machine
- [ ] T0.1 Verify the environment
- [ ] T0.2 Optional packages (psutil)
- [ ] T0.3 C compiler for the native A* kernel (N03)
- [ ] T0.4 Windows fixes for `resource` imports (`sysinfo.rss_mb`)
- [ ] T0.5 Re-record hash baselines
- [ ] T0.6 Roster manifest, `freeze.py`, `freeze_content.py`, `CONTENT_FREEZE.md`, `test_content_freeze.py`
- [ ] T0.7 Importer guards
- [ ] T0.8 Documents, full suite on Windows, ledger. **OWNER CHECKPOINT**

## M1 Environment hardening
- [ ] T1.1 Visibility model (`neuro/vision.py`), heuristic AI and `HybridEnv` use it; baselines re-recorded; before/after tournament evidence
- [ ] T1.2 Split successors are controlled (N07)
- [ ] T1.3 Alive means not collapsed
- [ ] T1.4 Full action surface in `HybridEnv` (`belt upgrade configure link_power trade propose respond`, `observe=False`)
- [ ] T1.5 Episode runner (`neuro/episode.py`) with end reasons, checkpoints, validation
- [ ] T1.6 Full suite, hash gate, ledger. **OWNER CHECKPOINT**

## M2 Observation layer and candidates
- [ ] T2.1 Static tables (`KIND_INDEX`, `KIND_STATIC`, `KEY_WARES`, `WARE_GROUPS`, `CARD_FEATURES`, `obs_schema_hash`)
- [ ] T2.2 Per-decision feature assembly with caches; shape, finiteness, extreme-preservation and no-hidden-information tests
- [ ] T2.3 Candidate generation (`neuro/candidates.py`), 95% acceptance test, timing

## M3 Networks and controller
- [ ] T3.1 Genome layout and networks (`neuro/nets.py`), round-trip and shape tests, exact genome size recorded here: ______
- [ ] T3.2 Controller (`neuro/controller.py`), decision log, `play` command, determinism test. **OWNER CHECKPOINT**

## M4 Fitness, league, manifest, calibration
- [ ] T4.1 Fitness (`neuro/fitness.py`) with table-driven tests
- [ ] T4.2 Manifest and versions (`RULES_VERSION`, `neuro/manifest.py`, compatibility rule)
- [ ] T4.3 League (`neuro/league.py`): opponent mixer, champion archive, behaviour grid, promotion decision
- [ ] T4.4 Outbreak calibration study (N01); chosen `outbreak_interval_scale`: ______ (evidence `docs/evidence/neuroevo/m4_calibration/`)

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

## Session log (newest first)
- 2026-10-14 (Claude Fable 5.1): `work/mechanics-completion-v4` merged at `1b404a8b` on the owner's request (conflicts: v4's 168-card system kept over PR #17's rule; register renumbered D33/D34). Merged-tree checks: 84 tests passed (sim API, VP/eras, outbreaks, content graph, coverage, NN, hash baseline, visibility, ware classes, draft reachability, determinism); roster now 582 entities / 168 cards; 40-minute bench 79 s. No implementation task started.
- 2026-10-14 (Claude Fable 5.1): plan and execution plan written and approved; no task started. Benchmarks in `WizardRTSHybrid/docs/evidence/neuroevo/bench_240/`.
