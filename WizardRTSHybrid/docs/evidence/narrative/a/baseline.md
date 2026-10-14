# Milestone A, task A.1: baseline (before any code change)

Date: 2026-10-14. Worktree `/home/joe/dmb_runs/wt_wizard_implementation`, branch `feature/wizard-mode-implementation`, base commit
`6a8302a40455e58064d9b077571a194e2a8d708b` (= `origin/feature/wizard-settlement-stories`, subject `stories(plan): final handover ...`).
Python 3.12.3, Godot 4.5.1 (`~/godot451`), Ubuntu laptop (Intel HD 520, Wayland/XWayland). No code was changed before these runs.

| Command | Result |
| --- | --- |
| hybrid set (`test_story_slice test_quest_env test_dungeon_env test_duel_env test_outbreak_env test_puzzle_parity test_ward_parity test_fire_magic test_content_freeze test_hash_baseline test_determinism`) | **95 passed** in 294 s (`base_hybrid.log`) |
| legacy set (`tests/sim/test_t083 test_t084 test_t080 test_t028 test_u05`) | **23 passed** in 0.4 s (`base_legacy.log`) |
| `PYTHONPATH=tools pytest tools/dialogue_generation/tests` | **collection error (3 files): `ModuleNotFoundError: No module named 'openpyxl'`** (`base_dialogue.log`) |
| headed `run_headed_suite.sh story duel wizard campaign` | **PASS duel, PASS wizard, PASS campaign, FAIL story** (`base_headed.log`) |

## Pre-existing failures (not caused by this programme, not fixed in A.1)

1. **Dialogue-generation tests cannot be collected here**: `openpyxl` is not installed in this Python (the three modules `test_cli.py`, `test_e36b_pipeline.py`, `test_fixture_builder.py` import it). Environment gap, not a code failure. The `tools/dialogue_generation` tests therefore are NOT part of the verified baseline; they matter from F.2 onwards, and the owner should `pip install openpyxl` (or tell me to) before then. I installed nothing.
2. **Headed `story` fails on three assertions** that still describe the pre-D22 "exhausted deposit" mine: `the coal mine reports its deposit used up`, `the quest marker is drawn over the miner`, `the dialogue cites the real seam and stock`. Since D22 (12 Oct 2026) mines are inexhaustible and the story is triggered by a collapse, so the script's expectations are stale. Everything after those three checks in the script ran (screens 01 to 09 were produced). `run_hybrid_story.gd` is rewritten in C.4, which is where this gets fixed; until then `story` is expected to FAIL on exactly these three checks and any additional failure there is a regression.

## Environment notes

* A fresh worktree has no `godot_project/.godot` (gitignored), so every Godot script fails to parse (`Could not find type "DmbDuelRuleset"` ...). Fixed by `godot --headless --path godot_project --import` once (exit 0). Nothing to commit. Any new worktree needs the same step.
* The first headed attempt (before the import) hung for 10 minutes inside Godot without output; it was killed and rerun. Not a test result.

## Launch audit

`campaign` profile launches the real `HybridWorld` (headed `campaign` PASS: primitive start, gated tech; screenshot `baseline_campaign_start.png`); the story fixture draws the miner and mine in the real scene (`baseline_story_miner.png`).
