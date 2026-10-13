# Runbook: how to resume and re-run everything from the v2 run

All commands run from the repository root. Logs and large outputs go to `~/dmb_runs/` (set `DMB_RUNS` to move it); nothing large is committed.

## Start of a session
```
git status; git log --oneline | head -5            # branch work/ubuntu-autonomous-v2
cat docs/ledger/LEDGER.md docs/ledger/QUESTIONS.md
python3 WizardRTSHybrid/scripts/smoke_gate.py       # ~3 min: content checks, fast tests, 5-minute state-hash equality
```

## Gates
| Gate | Command | Notes |
| --- | --- | --- |
| Full test suite | `python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py -p no:cacheprovider` | about 45 min on the T460 with other jobs running |
| Behaviour-preserving optimisation | `python3 WizardRTSHybrid/scripts/hash_gate.py check --baseline WizardRTSHybrid/docs/perf/hash_baseline.json` (also `hash_baseline_mid.json` 50 min x2 seeds, `hash_baseline_late120.json`) | baselines were recorded from commit 11b70b2; a legitimate behaviour change must re-record and say so |
| Performance | `python3 WizardRTSHybrid/scripts/perf_gate.py record` then `check` | only comparable on the same idle machine |
| Godot proofs | `~/godot451/Godot_v4.5.1-stable_linux.x86_64 --headless --path godot_project --script res://client/tests/run_hybrid_{facing,building_states,inspector}.gd`; headed: `WizardRTSHybrid/scripts/run_headed_suite.sh inspector` | needs `--import` once after new art |
| Catalogue / assets | `python3 WizardRTSHybrid/scripts/audit_catalogues.py --list`, `audit_assets.py --write`, `make_asset_ledger.py --check` | |

## Long jobs (always through the supervisor)
```
python3 WizardRTSHybrid/scripts/autorun/supervisor.py --name NAME --stall-s 3600 -- <command...>     # touch ~/dmb_runs/NAME/STOP to stop
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --nocards --pairing all-plus --seeds 101 102 103 --minutes 120 --jobs 3   # P2 acceptance; resumes from per-game files
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --draft --mode war --minutes 90 --seeds 507 11 --jobs 2 --era-vp-step 2        # P3/P12
python3 WizardRTSHybrid/scripts/catastrophe_study.py --v2 --seeds 1 2 3 4 --minutes 90 --scale 0.12 --jobs 2 --limits 99:8 --out ~/dmb_runs/cat_study
python3 WizardRTSHybrid/scripts/draft_collect.py --seeds 1000-1035 --minutes 45 --jobs 2        # imitation data
python3 WizardRTSHybrid/scripts/draft_train.py --out ~/dmb_runs/draft_models/scorer_v1.json       # held-out split by seed
python3 WizardRTSHybrid/scripts/draft_swap_eval.py --model ~/dmb_runs/draft_models/scorer_v1.json --seeds 3000-3011 --minutes 45 --jobs 2
python3 WizardRTSHybrid/scripts/content_report.py --seeds 4000-4011 --minutes 45 --jobs 2
python3 WizardRTSHybrid/scripts/modern_probe.py --minutes 50;  python3 WizardRTSHybrid/scripts/nocards_probe.py --minutes 60
python3 WizardRTSHybrid/scripts/profile_late.py --warm 90 --window 2 --nocards
```

## Switches (world attributes, all default off or old behaviour)
`nocards` (foundation only, no drafting), `cardset = "v2"` + `draft_v2` (generated cards, era-start ring draft), `HYBRID_CARDSET=v2` for the sim server, `diplomacy_enabled`, `nest_policy {faction: ignore|selfish|coop}`, `loss_outbreaks_per_era`, `loss_outbreaks_total`, `era_vp_end`, `era_vp_step`, `era_sustain_ms`, `neural_drafters {faction: DraftScorer}`, `draft_recorder []`.

## Machine notes
Ubuntu T460: 4 threads, 15 GB, no GPU, about 18 GB free disk; Python 3.12, NumPy 1.26, no PyTorch/Numba/PyPy. A C compiler exists: the optional A* kernel builds into `~/.cache/dmb_native` (set `DMB_NO_NATIVE=1` to force the Python search). The Windows PC is untested in this run (probe, `.ps1` wrapper, cross-OS hash test pending).
