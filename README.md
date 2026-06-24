# Duel Master Battle

Two-player **duelling Mastermind** reskinned as a **wizard duel**: 4 magical points (Shield, Body, Staff, Mind), 10 magic types, Hit/Weakness feedback, max 12 guesses. Playable **Human vs Bot** in Godot 4.4.1.

## Quick start — play the game
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```
Press **Human vs Bot** → click each point slot to open the magic picker → **Cast pattern** → watch enemy attacks → attack the enemy pattern → result → **New duel**.

**Difficulty:** Easy (random) · Normal · Hard · Expert (default, strongest solver).

Draft placeholder sprites live under `godot_project/assets/` (see `docs/ART_ASSET_MANIFEST.md`).

## Run tests
```bash
cd python_prototype && python3 -m pytest -q
PYTHONPATH=. python3 tests/generate_fixtures.py   # after rule changes
tools/run_godot_tests.sh
tools/run_godot_ui_smoke.sh
tools/godot_check.sh && tools/godot_cleanup.sh
```

Regenerate draft sprites:
```bash
python3 tools/generate_draft_sprites.py
```

Evaluate bot difficulty (Python only):
```bash
cd python_prototype && python3 scripts/evaluate_bots.py
```

## Project structure
```
shared_fixtures/     JSON golden files
python_prototype/    Pure rules, solver, NN experiment (Python only)
godot_project/
  sim/               Authoritative rules + bots
  client/            Wizard-duel UI
  assets/            Draft PNG sprites/icons
tools/               Test runners, sprite generator
docs/                Rules, playtest, NN experiment, art manifest
```

## Docs
- [Game rules](docs/RULES.md)
- [Manual playtest](docs/MANUAL_PLAYTEST.md)
- [NN experiment](docs/NN_BOT_EXPERIMENT.md)
- [Art manifest](docs/ART_ASSET_MANIFEST.md)
- [Release notes](docs/RELEASE_NOTES.md)

## License
See repository for license terms.
