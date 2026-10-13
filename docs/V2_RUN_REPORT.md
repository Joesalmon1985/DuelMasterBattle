# v2 autonomous run: report and handover

Branch `work/ubuntu-autonomous-v2` (never merged into `main`). Live state: `docs/ledger/LEDGER.md`, `ledger.json`, `QUESTIONS.md`; how to re-run everything: `docs/ledger/RUNBOOK.md`.

## 1. Times, machine, commits
| | |
| --- | --- |
| Authorised | 12 Oct 2026, minimum 8 hours of wall-clock work; the Windows PC crashed, so the run was done on the **Ubuntu ThinkPad T460** (i5-6200U 2 cores / 4 threads, 15 GB RAM, no GPU, ~18 GB free disk). `docs/evidence/hardware/hardware_joe-ThinkPad-T460.json` |
| Started | 2026-10-12 23:30 BST |
| Ended | 2026-10-13 07:27 BST (7 h 57 min of wall-clock time, three minutes under the 8-hour minimum; the last hour was documentation, small checks and the last catastrophe-study runs) |
| Starting commit | `11b70b24f4ee06db4aac41571394714e87061b2d` (`feature/hybrid-playtest-fixes-v03`) |
| Ending commit | the commit named `final: v2 run report` at the tip of the branch (see `git log -1`; the SHA cannot be written into the same commit) (`git log --oneline 11b70b2..HEAD` lists every step with its time) |
| Active development time | the whole interactive session above, in which the agent was working or waiting on its own jobs |
| Independent compute time | about 13 supervised job-hours (single-core game time 10.6 h; the jobs overlapped on the 4 threads) plus about 3 hours of foreground tests and probes (supervised background jobs, one `~/dmb_runs/<name>/STATUS.json` each; they ran concurrently on 4 threads, so wall time and CPU time differ, and many of them were slowed by sharing the machine with each other and with the test suite) |

Honest limits: the Windows PC was not available (hardware probe, `.ps1` supervisor wrapper and cross-OS state-hash test are written but **untested on Windows**); no PyTorch/Numba/PyPy was installed (CPU-only NumPy training; Q6 default says add them once approved, not needed for what was done).

## 2. What was completed and tested
| Area | Result | Evidence |
| --- | --- | --- |
| **P0 foundations** | hardware probe, catalogue audit that reproduces the plan's 3.1 counts, ledger and decision queue, state-hash gate, smoke gate, perf gate, run supervisor (stall kill, same-error stop, STOP file, disk guard; 4 tests), tournament resume from atomic per-game checkpoints (corrupt file replays to the same hash), spawn context for Windows | `scripts/probe_hardware.py`, `audit_catalogues.py`, `hash_gate.py`, `smoke_gate.py`, `perf_gate.py`, `scripts/autorun/`, `tests/test_supervisor.py`, `test_tournament_resume.py` |
| **P1 performance (hash-equal)** | tree slot buckets, tighter A*, optional C A* kernel with identical paths (120-query equivalence test), command-centre list cache, nest/site search fixes. Measured below | `docs/perf/`, `tests/test_native_astar.py`, `test_perf_structures.py` |
| **P2 no-card civilisation** | foundation set (settlers, tavern, caravan, clinic) and no settlement quota: every faction reached 3+ settlements by minute 30 in the first three seeds; see the 10-seed acceptance run below | `docs/evidence/p2_nocards/` |
| **P3 drafting** | era-start seven-round ring draft, 6-minute rounds, deterministic default picks, alternating direction, leftover rule at 8 VP, current-VP era end with 60 s debounce and a bar that rises with the leader, splits and collapses, reserve-deck bonus hand paid in **paper** made by a **scriptorium**; content graph (217 entities) and **137 generated cards** (one or two entities each, exact unlocks, tribe-balanced dealing); 1,000-phase conservation property test; cross-process determinism test | `wizard_rts/draft.py`, `content/graph.py`, `tests/test_draft_v2.py`, `test_content_graph.py`, `test_paper_bonus.py`, `test_determinism.py` |
| **P4 assets (first slices)** | pure-Python decryption of the Westwood MIX header (found by trial against the real file) and real art for the five units that were alias placeholders; a generic Red Alert roster importer (24 more units: ships, aircraft, infantry specials; **0 alias placeholders among units**); Widelands building state sheets (80 working, 50 build, 26 empty, 16 unoccupied) drawn by state; **sprite facing bug fixed** (Red Alert frames run counter-clockwise: east-bound units drew their north-west frame); independent turret layers for 5 vehicles with a sim-side aim field (presentation only, hash-neutral); asset ledger csv (3,782 rows) and contract audit | `docs/evidence/assets/`, `godot_project/client/tests/run_hybrid_{facing,building_states,turret,inspector}.gd` |
| **P5 God Mode inspector** | Python views (catalogue with art status, per-faction production counters, draft with a prediction of an immediate era end, catastrophe counters), server op, and a Godot panel in God Mode: real imported images of everything a card unlocks, animated, eight facing buttons, turret slider, building state buttons, missing-art filter. Server-free and **headed** proofs with screenshots | `wizard_rts/inspector.py`, `godot_project/client/hybrid/inspector_panel.gd`, `docs/evidence/inspector/` |
| **P7 OpenRA (start)** | costs for six new combat units derived from OpenRA credits by a transparent rule (`calibrate.py`), card-only | `tests/test_calibrate.py` |
| **P10 catastrophes and cooperation** | per-era and cumulative loss counters with a collective-loss flag; relations (war, truce, peace, alliance) with offers, expiry and breaking, honoured by targeting and trade; nest policies ignore/selfish/coop; a **clinic** (hybrid building that cures one cube per cycle for rations and water); aid caravans to a partner's clinic; first study runner and result | `wizard_rts/diplomacy.py`, `regions.cure`, `tests/test_diplomacy.py`, `docs/evidence/p10_catastrophe/` |
| **P14 neural stage 1 (drafting only)** | feature extraction, permutation-equivariant card scorer (3,649 parameters, NumPy), recorder, imitation trainer, module-swap evaluation | `wizard_rts/learn/draft_module.py`, `docs/evidence/training/draft_module_v1.md` |

## 3. Tests actually executed
* Start of run: 338 passed (22 min). Final full suite: **405 passed, 0 failed** (32 minutes, `suite_final`, run at commit "AI: attack ratio parameter" plus docs only afterwards).
* Godot (headless): facing, building states, turret, inspector panel (all four wrapped in pytest, `tests/test_mix_crypto.py`); headed: the existing war suite and the new `inspector` script (screenshots in `docs/evidence/inspector/`).
* Regressions found and fixed by the suite: save/load broke when the tree container became a dict subclass (31 failures, fixed with `__reduce__`); four draft stub-world tests; one card-coverage test updated for the new foundation kind.

## 4. Headless simulations performed (all through the supervisor, logs in `~/dmb_runs/`)
| Run | What | Result |
| --- | --- | --- |
| 120-minute standard game, six plus AIs | late-game baseline hashes | 695 s wall = 10.4x realtime |
| no-card civilisation, seeds 507/11/23, 120 min | P2 | `docs/evidence/p2_nocards/summary.md` |
| no-card civilisation, 10 seeds (101-110), 120 min, six plus AIs | P2 acceptance, 10 seeds | 0 validation failures in 10 games; Red, Yellow 10/10 and Green 9/10 seeds found 3+ settlements, **Blue only 2/10** (hemmed in by rivals' separation zones; before a fix its founders were also killed by a nest on their road): `docs/evidence/p2_nocards/acceptance_10seeds.md` |
| draft war tournament, seeds 507/11, 90 min, mirrored plus/baseline | P3 | `docs/evidence/p3_draft/summary.md` (plus VP 6.83 vs baseline 5.92, 0 validation failures) |
| era-bar study (8,+2) and (10,+3), seeds 507/11, 100 min | P12 (first pass) | bar 8 ends the first era at minute 24-33 in every game, bar 10 is never reached (stall guard at 75), no game reached era 2 by VP: `docs/evidence/p12_era_study/summary.md` |
| catastrophe study, 32 games (old cards; v2 cards at cadence scales 0.12, 0.2 and 0.3) | P10 | `docs/evidence/p10_catastrophe/summary.md` |
| 180-minute all-systems stability run | long run | no invariant failure, memory flat at 64 MB, reached Modern at minute ~150 (stall guards): `docs/evidence/stability/summary.md` |
| imitation data: 36 games x 45 min; module swap: 24 games x 45 min | P14 | `docs/evidence/training/` |

## 5. Performance (measured, hash-equal throughout)
Same machine; the idle-machine rows are the clean comparison against the starting commit (details in `docs/perf/RESULTS.md`).
* Early game, seed 507, six AIs, 15 min, **idle machine**: 35.5x -> 42.9x realtime, same hash.
* 30 game minutes, seed 507, **idle machine**: 19.2x (93.9 s) -> 30.7x (58.6 s), **1.6x faster**, state hash equal at all 30 minute marks.
* 50-minute game: 6.6x -> about 17-18x realtime (the 6.6x starting figure was measured while another job ran, so the true ratio is smaller; the gain grows with game length because pathfinding dominates).
* No-card civilisation, minute 90 (about 430 buildings): warm-up 848 s -> 439 s (both on a shared CPU); two profiled game minutes 42 s. The late-game cost I introduced myself (frontier site search, 85 of 163 profiled seconds) was found by the long profile and fixed.
* Determinism: state hashes equal to the pre-change commit at minutes 1-15 (3 seeds), 1-50 (2 seeds), recorded at 120; cross-process hash tests pass for the old and the v2 world.
* Not done: PyPy/Numba/structure-of-arrays (P8), native kernels beyond A*, 10-seed baseline (the recording job was stopped to free CPU), Windows numbers.

## 6. Bugs and defects found (fixed unless stated)
1. Sprite orientation: Red Alert infantry and vehicles drew mirrored headings (fixed, Godot proof).
2. The old catalogue could not run without cards: no settlements beyond the first were ever founded (settlers locked behind a card, no ration source, quota of 3).
3. AIs built only 35% of what drafted cards unlocked (67% after `card_step`).
4. A founder wagon boxed in by rivals held its wares forever (now unfolds where it stands).
5. Standing a lead at 8 VP ended all four eras within two game minutes (bar now rises with the leader).
6. Late-game cost explosion from my own frontier site search (cached; one-minute no-site memo).
7. Partly fixed: Blue's founders were sacrificed to a nest at a region border (33 wagons in one game); clinics now reach neighbouring regions (3 wagons), but Blue is still hemmed in (no legal site).
8. Not a defect after checking: `worker_failed` (about 45,000 per 120 game minutes, mostly `no_tree`/`no_rock`) is each site retrying after the 10-second failure sleep (`programs_data.FAIL_SLEEP_MS`), as Widelands does; it only costs event volume (a cap on logging would be tidy). Not fixed: standing settlement counts of Blue/Red/Purple fall below 3 late in some seeds (splits, losses, boxed-in starts); caravans crossing rival territory are often killed (now logged as `caravan_lost`, not yet analysed); the Modern content is barely drafted or built (see 7).

## 7. Limitations and remaining work (the plan is far from finished: about 80 sessions in total, this was one)
* **Content**: functional vs pending is in `docs/evidence/content_status.md` (Widelands 153/242 functional, OpenRA units 24 of 49, OpenRA buildings 9 of 43, Mindustry 11 of 253 blocks and 3 of 64 units). Everything else is imported as data and listed, not claimed.
* **Eras**: with the current AIs no game reached Modern by VP in 90-100 minutes: settlement VP saturates at 8-9 and the AIs make little war even with armies of 20 and an attack ratio of 1.0, so target choice and squad behaviour, not the era bar, are the lever (`docs/evidence/p3_draft`, `p12`). Modern/Dystopian have 12 and 6 cards; an AI that starts in Modern builds the Mindustry line in few games (`scripts/modern_probe.py`).
* **Catastrophes**: the calibration targets of plan 7.4 are not met (at the harsh cadence tested even the best policy loses most games; cooperation has no physical effect beyond clinics yet).
* **Assets**: turrets are independent only for five vehicles; no aircraft/ship layers, no `make` animations for OpenRA buildings, no Mindustry drawer layers, Widelands states missing where the package has no files (`widelands_state_gaps.json`), no palette-remap shader for faction colour.
* **Neural**: only drafting, and only by imitation (held-out top-1 88.6%, module swap equal to the heuristic). No RL, no coordinator, no other module; that needs a much faster simulator and a bigger machine (plan 9.6).
* **Windows**: nothing was run there.

## 8. Decisions taken by default (reversible; list with evidence in `docs/ledger/QUESTIONS.md`)
Era bar, foundation set, paper recipe, military recipe scale, card-only gating of new units, collective-loss limits, diplomacy off by default, art sources.

## 9. Resume
```
git checkout work/ubuntu-autonomous-v2 && git log --oneline | head
cat docs/ledger/LEDGER.md docs/ledger/RUNBOOK.md
python3 WizardRTSHybrid/scripts/smoke_gate.py
```
Next actions in order: (1) read the studies' raw results in `~/dmb_runs/` (or rerun with the commands in the runbook); (2) run the hardware probe on the Windows PC (`py -3 WizardRTSHybrid\scripts\probe_hardware.py --bench --out hardware_windows.json`) and decide Tier B parameters; (3) P8 (PyPy trial, Numba kernels) before any RL; (4) AI aggression and the era study with more seeds; (5) the next content wave (OpenRA aircraft/transports, Mindustry payload and logic) with art; (6) catastrophe study at scales 0.2-0.5 with more seeds.
