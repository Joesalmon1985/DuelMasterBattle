# C14 — Tests, performance, training gates and release

Source: GDD §§190–200, 201–231 and Volume XXIII. This contract describes tests to implement, not test results already obtained.

## Test entrypoints and evidence

T003 pins the checkout's supported tooling. T004 creates wrappers with these logical contracts; map to existing commands when present rather than replacing a working suite:

| Entrypoint | Required behaviour |
|---|---|
| `python tools/check.py --task Tnnn` | Run changed-domain tests plus its boundary regressions; nonzero on fail, skip or missing required test |
| `python tools/check.py --gate Gnn` | Run that gate's cumulative unit/integration/schema/headless requirements and save a machine-readable report |
| `python tools/run_scenario.py --fixture FX-NAME --record OUT` | Use production runtime; record seed/manifest/commands/time/results and failure bundle |
| `python tools/check.py --release` | Full suite, content/asset validation, replay, packaging smoke and gate status |

These scripts do not exist in this pack; creating/mapping them is an early task. Reports state exact command, tool version, commit SHA, manifest hashes, test names/counts, pass/fail/skip, duration and evidence path. A test command exiting 0 with zero tests is a failure. No fabricated test logs. Godot headless import/parse is necessary but does not establish usable scenes; run scripted scenes and human tests separately.

Meaningful tests: source-rule table cases; pure algorithms with independently calculated expected values; cross-system command chains; conservation/replay properties; save/crash boundary tests; headless scene assertions; manual gameplay. Avoid mock-only chains where a fake economy directly injects the expected army. Test-only seed setup is permitted before normal execution, with fixture flags visible in the report.

## Required scenario families

FX-CLOCK, FX-CARGO, FX-INDUSTRY, FX-BATTLE, FX-HAZARD, FX-VILLAGE, FX-ERA, FX-SOLO, FX-CYCLE, FX-RECOVERY and FX-RELEASE are specified in [the fixture book](../reference/fixtures.md). Each test refers to a fixture version/hash. Include a known failure seed and command trace when fixing a real bug; reduce it to the smallest useful regression without rewriting the implementation as the test.

Expected coverage: all 34 GDD invariants, every Volume XXIII acceptance row, catalogue completeness, all public verbs, both ordinary/full-cycle dispositions, every typed effect's invalid and duplicate path. `source_coverage.json` maps descriptive GDD sections to owners/tasks/gates; rule-level assertions live in task cards and fixture tests.

## Performance and endless-state tests

Initial targets are engineering budgets to measure at G07/G10, not user-locked limits: 19 hexes/54 nodes, six factions, 250 operational buildings, 2,000 individual units, 1,000 living NPCs, 100 active quests and three full cycles. Standard desktop target 60 rendered FPS, p95 main-frame ≤16.7 ms at 1280×720, p95 world accounting ≤25 ms per 100 ms boundary, normal turn ≤250 ms, save ≤2 seconds, startup ≤10 seconds. Record actual hardware and separate render, IPC and simulation time. Failure produces a measured optimisation task rather than hiding/deleting units or lowering live-state counts silently.

Stress 10,000 persistent unit records without full rendering and a locally dense battle separately. Off-screen resolver has its 120-second simulated bound and a wall-time watchdog that yields/resumes its calculation while world remains paused; it never declares victory on a performance timeout. When military population grows during long stationary play, retain all identities/production; optimise formation indexing, spatial partitioning and projection culling. Do not introduce an undeclared population/army cap.

Checkpoint history compaction pins all live references. Test ≥20 cycles headlessly at accelerated legal scheduling for state growth trends, then three complete detailed replay cycles for continuity. Global counters/IDs must not overflow JSON precision. Any changed tick batching must reproduce the same events/depletion/meters and obey interruptions.

## Neural promotion gate

First prove the heuristic can regularly reach 10 VP on training-free evaluation seeds; do not train around an engine deadlock. Each candidate policy then runs ≥200 fixed held-out paired seeds against the same opponent/baseline configurations, with seat assignment balanced and all choices/time recorded. Promotion requires:

1. Zero accepted illegal actions, no crashes/nontermination and no malformed inference result; proposed invalid outputs are separately reported and must be fixed before promotion.
2. Terminal-catastrophe count no greater than the paired heuristic baseline on the identical seed set.
3. Winning/10-VP triggering performance at least 90% of the nonzero heuristic baseline rate; report both counts, difference and binomial uncertainty rather than calling a tiny difference improvement.
4. No material score exploitation, gifting, cost bypass or loop farming; replay sample winning/losing trajectories and verify ledger invariants.
5. Runtime inference p95 ≤20 ms on the target CPU; timeout/exception uses the legal heuristic within the same seat budget.

Choose three accepted policies with distinct measured build/trade/war/treatment proportions or outcome profiles, not merely different filenames. Use at least a 10-percentage-point difference in one action-family share over the evaluation set as the initial diversity target, provided it does not harm other gates. If this proves incompatible with competence, report the evidence for human revision rather than faking diversity. The author does not promise qualification within a given dollar budget. Training is a bounded empirical phase.

## Packaging and offline operation

First release: Windows x64. Export a Godot release binary/data pack and package a Python sidecar with its interpreter/dependencies and compiled data/models in one distributable folder/ZIP. The launcher resolves bundle-relative paths; saves/config/logs go to the platform user-data directory, not the installation folder. No console/server setup, Python installation, model download, account, API key or network fetch is required to play.

Use a platform-matched packaging environment. [PyInstaller bundles the interpreter/dependencies but produces platform-specific output](https://pyinstaller.org/en/stable/operating-mode.html); the Windows sidecar must be built/tested for Windows. [Godot's Windows export workflow](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_windows.html) supplies the release application/data package. Choosing tools does not establish a successful combined build. T001 records available platforms; a Windows runner or Joe's Windows machine may be required at packaging time. Do not claim a Linux-only smoke test proves the Windows deliverable.

Clean-machine checks: unzip to a path containing spaces/non-ASCII; launch without developer tools or PATH modifications; disconnect internet while permitting loopback; start/load/play/quit; confirm no orphan sidecar; move install folder and repeat; make install read-only and verify saves; corrupt current save and recover backup; sidecar crash pauses/recoveries correctly. Antivirus/signing/distribution work is not silently claimed done. Local packaging is authorised by the build task; public upload/store publishing requires explicit user instruction at that time.

## Gate discipline and defect handling

Ten manual breaks are in `gates/` and the owner guide. A gate packet contains playable build/launch instructions, tested commit/manifest, seed/save, automated report, exact human steps and known defects. Statuses: PASS, FIX_REQUIRED, BLOCKED. Only Joe records manual PASS; agents cannot infer it from silence or automated checks. On failure, repair and rerun affected automated checks and the failed manual steps. Do not broaden testing indefinitely after the concrete defect is resolved.

A task is complete only with actual implementation/content, its checks and receipt. A stub, TODO, skipped check, untrained model, placeholder final asset or substituted fake data remains incomplete. Allow up to three focused repair attempts per unresolved failure, then write a compact blocker with evidence/next diagnostic instead of burning an unlimited budget. Human playtest gates intentionally stop the long run. Infrastructure/cost constraints may stop it earlier; report exactly what is needed.
