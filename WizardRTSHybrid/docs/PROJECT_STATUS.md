# Project status

Branch: `feature/wizard-rts-hybrid-v02` at `52fc8ea`, cut from `feature/wizard-rts-hybrid` at `5785e03`. Unrelated spellbook and content edits stay unstaged. Build-pack T143 is not advanced. Honest inventory: `docs/STATE_OF_PLAY.md`.

## What works

See `docs/STATE_OF_PLAY.md` (authoritative). Headline: six AI-driven factions with physical forestry, quarry, mining, smelting, ax making, road logistics, construction, goods-fed recruitment and OpenRA-rule combat in one world; God Mode over the same commands; 45 Python tests; headed scripts for walk, duel, forestry, God Mode (real mouse events) and a six-faction war; a 30-minute multi-seed headless run with an HTML report.

## What is partial or blocked

See the missing table in `docs/STATE_OF_PLAY.md`. Blocked: Widelands compile (B1), OpenRA skirmish screenshot (B2).

## Commands

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 WizardRTSHybrid/tests/test_five_minutes.py
py -3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
py -3 WizardRTSHybrid/scripts/long_run.py --minutes 30 --seeds 507 11 23
py -3 WizardRTSHybrid/scripts/build_catalogue.py
py -3 WizardRTSHybrid/scripts/import_openra_rules.py
py -3 WizardRTSHybrid/scripts/import_assets.py
```

Godot 4.5.1 console, Forward+, one fresh sim per script (`$env:HYBRID_SIM_PORT`): `run_hybrid_walk.gd`, `run_hybrid_visual.gd`, `run_hybrid_duel.gd`, `run_hybrid_forestry.gd`, `run_hybrid_god.gd`, `run_hybrid_war.gd`, and `--headless ... run_hybrid_coords.gd`. Set `HYBRID_SHOT_DIR` to save PNGs, `HYBRID_SPEED` for the sim clock multiplier.

## Next task

The food chain (see `docs/CLAUDE_HANDOFF.md`).
