# Next agent handoff (updated 12 October 2026)

**Branch:** `feature/hybrid-playtest-fixes-v03`. **Last verified commit:** see `git log -1` (`feat(hybrid): M1 ... M3 story core`, `d3f7375`). Nothing is merged to `main`. Owner's untracked files in `docs/` are untouched; **do not `git add -A`** (legacy `tests/sim` rewrites `godot_project/content/compiled/*` when run: restore with `git checkout -- godot_project/content/compiled` before committing).

## State
Authority: `docs/IMPLEMENTATION_RUN_STATUS.md` (completed / partial / blocked / not started). Direction: `docs/DuelMasterBattle_Design_v0_5.md`, `docs/DECISION_REGISTER.md` (D01-D21).

Done and tested: M1 (profiles, tech cards), M2 (Mindustry slice, D21), M3 Python core (puzzle port with GDScript parity, settlements, story bridge). **Not done:** M3 headed Godot (story UI: NPC, dialogue, dungeon view, duel board), M4, M5, M6, the headless environments other than `HybridEnv`, all neural training. See the status file for the exact list.

## Commands
```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py     # about 16 min; last full run 177 passed, 2 failed (both fixed afterwards, rerun to confirm)
python3 -m pytest WizardRTSHybrid/tests/test_story_slice.py WizardRTSHybrid/tests/test_puzzle_parity.py -q   # M3 core, about 35 s
python3 -m pytest WizardRTSHybrid/tests/test_industry_mechanics.py WizardRTSHybrid/tests/test_industry_slice.py -q   # M2, about 2 min
python3 -m pytest tests/sim -q          # legacy, 507 passed in 37 s (then git checkout -- godot_project/content/compiled)
WizardRTSHybrid/scripts/run_headed_suite.sh campaign campaign_dev industry god      # headed; needs DISPLAY; HYBRID_SHOT_DIR for screenshots
WizardRTSHybrid/scripts/run_headed_one.sh <script.gd> ENV=VAL ...                    # one headed script with full output
GODOT_PARITY=1 python3 -m pytest WizardRTSHybrid/tests/test_puzzle_parity.py -q      # re-export from the real GDScript and compare
python3 WizardRTSHybrid/scripts/build_consolidated_design.py                         # regenerate the consolidated design after editing parts
```
Godot: `~/godot451/Godot_v4.5.1-stable_linux.x86_64`. A mid-run source edit can fail an in-flight pytest; do not edit while the full suite runs.

## Very next actions
1. M3 headed: Godot story UI over the existing ops (`talk`, `choose`, `enter`, `dungeon_move`, `dungeon_interact`, `duel_begin`, `duel_guess`, `duel_abandon`; snapshot `entities` with `class npc/landmark`, `story` block). Fixture: `HYBRID_PROFILE=developer HYBRID_FIXTURE=story`. Write `client/tests/run_hybrid_story.gd` (real input, screenshots under `docs/evidence/m3/`), and `scripts/launch_scenario.sh story`.
2. M4: VP ledger and eras on `wizard_rts/settlements.py` (stable ids and chronicle exist), thresholds, upgrade command (the S08 cost function and in-place identity exist in `industry/commands.py`), collapse/split, cycle reset.
3. M5 outbreaks, then the headless environment adapters and the neural harness, then M6 breadth.
