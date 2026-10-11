# Project status

Branch `feature/hybrid-playtest-fixes-v03` (session 3, playtest fixes; see `docs/PLAYTEST_FIXES.md`). Honest inventory: `docs/STATE_OF_PLAY.md`. Hand-over to the Windows machine: `docs/WINDOWS_HANDOVER.md`. Last updated at the end of session 2 (Ubuntu ThinkPad T460).

## What works

One authoritative Python world (`HybridWorld`) on a square-grid terrain derived from Widelands rules, shown by Godot and also runnable headless. Six factions (five Widelands tribes) with physical economies on that terrain: forestry on arable land with terrain-dependent tree growth, quarries on real rocks, mines on real finite deposits (`ActMine`), fishing on finite breedable fish, farming, food, smelting, ax making, road logistics with construction sites served first, goods-fed OpenRA recruitment, OpenRA-rule combat with target filters and several weapons per unit, naval yards and submarine pens on the coast, patrol boats and submarines (cloak and detection), AI commanders and fleets, God Mode with a placement ghost, deposit overlay, tile inspector, status text, worker inspection, clock buttons and naval menus, Wizard Mode on the same world with the retained Ward Duel, and a headless training interface (`HybridEnv`).

## What is partial or missing

See `docs/STATE_OF_PLAY.md` (partial and missing tables) and section 8 of `docs/WINDOWS_HANDOVER.md`. Blocked as before: Widelands compile (B1), OpenRA skirmish screenshot (B2); neither is needed for play.

## Commands (Ubuntu; on Windows use `py -3`)

```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
python3 WizardRTSHybrid/scripts/bench_sim.py --minutes 5
python3 WizardRTSHybrid/scripts/long_run.py --minutes 30 --seeds 507 11
WizardRTSHybrid/scripts/launch_hybrid.sh god          # or wizard
WizardRTSHybrid/scripts/run_headed_suite.sh [walk visual duel forestry food god war terrain naval playtest wizard mcv]
python3 WizardRTSHybrid/scripts/ai_report.py --minutes 40 --seeds 507 11 23     # per-faction behaviour report with checks
python3 WizardRTSHybrid/scripts/rl_experiment.py baseline|train|eval              # numpy-only learning experiment
```

Regenerate data: `import_widelands_terrain.py`, `import_widelands_programs.py`, `import_openra_rules.py`, `import_terrain_textures.py`, `import_assets.py`, `verify_generic_buildings.py`, `build_catalogue.py`; source checkouts: `setup_external.sh`.

## Verified in session 2

Python: see the count in `docs/WORK_LOG.md`. Headed on Ubuntu (Forward+, Intel HD 520): terrain, walk, naval; other scripts as listed in STATE_OF_PLAY. Long run: 30 game minutes x seeds 507 and 11 with six AI factions, no problems. Headless speed: standard map about 55x realtime.

## Verified in session 3

Python: 123 tests. Headed on Ubuntu (Forward+): all twelve headed scripts pass: eleven (walk, visual, duel, forestry, food, god, war, terrain, naval, playtest, mcv) in one final run on an idle machine, and `wizard`, which failed once in that run on a racy click (the scripted AI was still moving the soldier it had just spawned), was made deterministic (AI frozen, click retried) and then passed twice in a row. AI: three seeds x 40 game minutes of war, all ten behaviour checks pass (`docs/evidence/ai_report/final_40m_war_seeds_507_11_23`). Details and before/after evidence: `docs/PLAYTEST_FIXES.md`.

## Next task

Make every tribe's OpenRA infantry flow in peace (iron and ration supply for the non-Barbarian tribes), then the Frisian ponds, then OpenRA ship art on Windows. Details in `docs/CLAUDE_HANDOFF.md`.
