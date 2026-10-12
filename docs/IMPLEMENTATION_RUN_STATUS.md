# Implementation run status

Run authorised by the owner on 11 October 2026 (M1-M6, Mindustry integration, neural/headless testing programme). Branch `feature/hybrid-playtest-fixes-v03` (nothing merged to `main`). Updated at each checkpoint; the restart point is `NEXT_AGENT_HANDOFF.md`. **Completed** = implemented and exercised by the named tests; **partial** = works for the cases named; **blocked**; **not started**. No score or screenshot below is estimated: each has a command.

## Milestones

| Item | Status | Evidence (tests are under `WizardRTSHybrid/tests`) | Gaps |
| --- | --- | --- | --- |
| P0 baseline, pins, importer structure, docs | **Completed** | Baseline before any change: 123 Python tests passed in 12 min 18 s on this machine (4 cores, Python 3.12.3, NumPy 1.26.4, no torch/gymnasium, Godot 4.5.1). `scripts/verify_pins.py`; `test_mindustry_pipeline.py` | Windows scripts not run here |
| D21 (no ore tiles, no second map pass) | **Completed** | `DECISION_REGISTER.md` D21/S10/S11, design v0.5, `ARCHITECTURE_CONTRACT.md` section 10, `MINDUSTRY_PROVENANCE.md` | |
| M1 campaign profiles, primitive start, drafting, gating | **Completed** | `test_campaign_tech.py` (15); headed `campaign`, `campaign_dev` (`docs/evidence/m1/`) | 16 cards; AI drafts by a fixed priority list |
| M2 Mindustry slice | **Completed** | `test_industry_mechanics.py` (20), `test_industry_slice.py` (4), `test_mindustry_pipeline.py` (17); headed `industry` (`docs/evidence/m2/`) | no liquids, routers, bridges, more units, art; upgrade only for hybrid mines |
| M2 AI uses the industry | **Completed (narrow)** | `ai_industry.py` hooked into `ai.economy_step`; `test_ai_industry.py` (2): once the three cards are drafted, era is Modern and the warehouse holds the goods, the AI places the drill-belt-smelter-factory line | one line per faction; no repair or expansion of the line |
| M3 live-settlement story | **Completed** (one vertical slice) | Python: `test_story_slice.py` (12), `test_puzzle_parity.py` (6, Godot-RNG-exact), `test_puzzle_exhaustive.py` (24). Headed `story` (`docs/evidence/m3/`) | one NPC, one dungeon, one duel; art placeholders |
| M4 VP, settlements, eras, cycle reset | **Completed** | `test_vp_eras.py` (17); headed `eras` (`docs/evidence/m4/`: four eras walked on the HUD, then cycle 1 on the same land, primitive start, no cards); `scripts/vp_report.py` | S04 threshold 10 not reached in 40 min on three seeds; working default is 6 (see DECISION_REGISTER). The Modern/Dystopian eras unlock only the Mindustry cards; no era-specific content beyond that |
| M5 outbreak regions | **Completed** | `test_outbreaks.py` (14); headed `outbreak` (`docs/evidence/m5/`) | overlay only; no cure research |
| M6 content breadth | **Partial** | Mindustry 11 of 214 blocks simulated; Widelands 153 of 237 buildings; OpenRA 2 buildings and 2 units (`docs/COVERAGE.md`, generated) | builder worker, mine workers, liquids, most OpenRA content not started |
| Headless environments | **Completed** (six) | `test_duel_env.py` (12), `test_dungeon_env.py` (8), `test_quest_env.py` (10), `test_outbreak_env.py`, `test_fullgame_env.py` (7), `test_sim_api.py` (strategy). Common `Env` contract: reset, step, legal mask, observe, encode, state hash, save, replay, trace. Seed splits train/validation/test | |
| Neural training programme | **Partial** (harness done, results mixed) | `test_nn.py` (5), `test_training_smoke.py` (4); standard-budget results in `TRAINING_PROGRAMME.md` and `WizardRTSHybrid/docs/evidence/training/` | Duel and outbreak/quest policies learn; **dungeon policy fails (5-10% vs expert 100%)**; cross-system REINFORCE policy is worse than every scripted baseline; strategy-domain `--domain rts` not run in this run |
| Ward Duel port | **Completed** (core) | `test_ward_parity.py` (5), exact against GDScript exports | real-time cast windows not ported |

## Launch commands (Ubuntu)

```
WizardRTSHybrid/scripts/launch_scenario.sh campaign     # primitive start, no God Mode
WizardRTSHybrid/scripts/launch_scenario.sh drafting     # developer profile, draft every 60 s
WizardRTSHybrid/scripts/launch_scenario.sh industry     # Modern fixture: drills -> belts -> power -> smelter -> factory -> dagger
WizardRTSHybrid/scripts/launch_scenario.sh story        # a dry mine, its miner, the gallery, four puzzles, the warden duel
WizardRTSHybrid/scripts/launch_scenario.sh outbreak     # cubes in the wizard's hex region, a healer
WizardRTSHybrid/scripts/launch_scenario.sh eras         # developer: era every 2 game minutes (HYBRID_ERA_MS/HYBRID_ERA_VP), then cycle reset
```

## Tests actually run (this run, this machine)

- Python hybrid suite: `python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py`: **312 passed, 0 failed** (about 25 min).
- Legacy `tests/sim`: 507 passed (34.8 s); `godot_project/content/compiled` restored afterwards.
- Godot sim (`--headless --script res://sim/tools/run_tests.gd`): 32 passed, 0 failed.
- Headed suite (`scripts/run_headed_suite.sh`, 17 scripts): all pass; `campaign_dev` failed in the first full pass because the test raced the AI's draft and a stale clock sequence, was fixed in the test (not weakened) and then passed; `eras` was added and passes.
- `scripts/run_all_scenarios.py --suite smoke`: ALL_OK (`docs/evidence/scenario_report.json`).
- Performance (`scripts/bench_sim.py`, 10 game minutes, six AI factions, seed 507): standard map 32x realtime, 58 MB peak, snapshot 774 KB / 18 ms; small map 37x realtime, 41 MB. Budget was >= 20x.
