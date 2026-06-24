# Duel Master Battle

Two-player **duelling Mastermind**: 4 pegs, 10 colours, Mastermind feedback (exact + colour-only), max 12 guesses. This release delivers a playable **Human vs Bot** vertical slice in Godot 4.4.1.

## Quick start — play the game
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```
Press **Human vs Bot** → set 4 secret pegs → **Lock code** → watch bot guess → guess the bot's code → result → **New game**.

## Run tests
```bash
# Python rules (24 tests)
cd python_prototype && python3 -m pytest -q

# Generate golden fixtures (after rule changes)
PYTHONPATH=. python3 tests/generate_fixtures.py

# Godot rules tests
tools/run_godot_tests.sh

# Godot UI smoke (full Human vs Bot flow via real UI actions)
tools/run_godot_ui_smoke.sh

# Process check / cleanup
tools/godot_check.sh
tools/godot_cleanup.sh
```

## Python prototype (optional)
```bash
cd python_prototype && python3 run_prototype.py
```

## Web export (built locally, not deployed)
```bash
tools/export_web.sh
# Output: godot_project/build/web/index.html
# See docs/DEPLOY_CLOUDFLARE_PAGES.md
```

## Project structure
```
shared_fixtures/     JSON golden files (Python generates, Godot consumes)
python_prototype/    Pure rules + minimal tkinter UI
godot_project/
  sim/               Authoritative rules (headless-testable)
  client/            UI scenes (non-authoritative)
tools/               Test runners, export, Godot cleanup
docs/                Rules, milestones, playtest checklist
```

## Docs
- [Game rules](docs/RULES.md)
- [Manual playtest](docs/MANUAL_PLAYTEST.md)
- [Test strategy](docs/TEST_STRATEGY.md)
- [Release notes](docs/RELEASE_NOTES.md)
- [Previous repo lessons](docs/audit/PREVIOUS_GODOT_REPO_LESSONS.md)

## Acceptance status
| Criterion | Status |
|-----------|--------|
| Python rules tests | pass |
| Godot rules tests | pass |
| Godot UI smoke test | pass |
| Playable Human vs Bot in Godot | yes |
| Web export built | yes (local) |
| Android export built | no (docs only) |
| Manual playtest | not performed in CI; user should run locally |

## License
See repository for license terms.
