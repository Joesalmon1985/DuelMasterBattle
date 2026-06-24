# Duel Master Battle

Two-player duelling Mastermind: 4 pegs, 10 colours, Mastermind feedback, Human vs Bot vertical slice in Godot 4.4.x.

## Status
Under active development on branch `feature/duel-mastermind-build`.

## Quick start (when implemented)
```bash
# Python rules tests
cd python_prototype && python -m pytest -q

# Godot rules tests
tools/run_godot_tests.sh

# Godot UI smoke
tools/run_godot_ui_smoke.sh

# Launch game
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
"$GODOT" --path godot_project
```

## Docs
- [docs/PLAN.md](docs/PLAN.md)
- [docs/RULES.md](docs/RULES.md)
- [docs/MILESTONES.md](docs/MILESTONES.md)
