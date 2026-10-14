# Implementation ledger (human summary)

> **Superseded in part (13 Oct 2026).** Branch `work/mechanics-completion-v4` changed the card system (168 cards, four eras of 42, 1-4 entities each), the faction floor of six, ware classes, visibility and the command tier. Where this file disagrees, `docs/ledger/V4_HANDOVER.md` and `docs/DECISION_REGISTER.md` section 5 (D26-D32) win. S05, S06, S13 and S14 below are stale.


Machine-readable twin: `ledger.json`. Run `work/ubuntu-autonomous-v2`, started 2026-10-12 23:30 BST from `11b70b2` on the Ubuntu laptop (the Windows PC crashed). Full report: `docs/V2_RUN_REPORT.md`; how to resume: `RUNBOOK.md`; owner questions: `QUESTIONS.md`.

| Milestone | Status | One line |
| --- | --- | --- |
| P0 | done_except_windows | probe, audits, hash/smoke/perf gates, supervisor, tournament resume (Windows parts untested) |
| P1 | partly_done | 1.6x faster at 30 min (idle), hash-equal; targets of 10.2 not yet met |
| P2 | partly_done | nocards works (no stalls, ledger balanced); Blue hemmed in, 2/10 seeds |
| P3 | partly_done | draft v2 + 137 generated cards + paper/bonus; default off |
| P4 | started | MIX decryption, 24+5 units of art, facing fix, building states, 5 turret layers |
| P5 | mostly_done | God Mode inspector with real art, headed proof |
| P6 | not_started | markets/ferries imported as data only |
| P7 | started | 6 calibrated units; 24/49 RA units functional |
| P8 | not_started | not started (PyPy, Numba) |
| P9 | not_started | not started (industrial index; AI barely drafts Mindustry) |
| P10 | started | clinic, diplomacy, nest policies, study runner; targets not met |
| P11 | not_started | not started |
| P12 | started | first pass: bar 8 vs 10, AIs do not reach era 2 |
| P13 | not_started | not started |
| P14 | started | drafting module by imitation only |
| P15 | not_started | not started |
| P16 | not_started | not started |
| P17 | started | content report loop started |
| P18 | not_started | not started |

Session log: see `git log --oneline 11b70b2..HEAD` (every commit has its time) and `docs/V2_RUN_REPORT.md`.

## V3 gameplay and asset programme (branch `work/gameplay-assets-v3`, 13 Oct 2026)
See `docs/V3_RUN_REPORT.md`: eras, Mindustry engine, OpenRA roster, Widelands completion, hybrid industry, coverage report and four-era scenario done; hash baselines, sea trade, hybrid-block art and performance work outstanding.

## Content freeze and hierarchical neuroevolution (branch `feature/neuroevolution-plan`, 14 Oct 2026)
**Approved by the owner 14 Oct 2026** (register D33/D34, N01-N09): `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md` (design, milestones M0-M9) and `docs/EXECUTION_PLAN_NEUROEVOLUTION.md` (task list for the implementing agent). Live task state: `docs/ledger/NEUROEVO_PROGRESS.md`. P6/P7/P9/P11 above are superseded (no more content imports); P14-P16 are replaced by M2-M9. Benchmarks and audits: `WizardRTSHybrid/docs/evidence/neuroevo/`.
