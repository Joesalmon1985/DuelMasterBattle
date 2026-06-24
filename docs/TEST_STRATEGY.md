# Test Strategy

## Principles
- Test-first: write tests before or alongside implementation.
- No milestone complete until relevant tests pass.
- Pure game logic tested heavily; UI tested via scripted smoke.
- Python and Godot share `shared_fixtures/` JSON — no hand-copied expected values where fixtures apply.

## Python (pytest)
```bash
cd python_prototype && python -m pytest -q
```

### Coverage
- Code length validation (must be 4)
- Colour range validation (0–9)
- Duplicate colour behaviour (allowed; feedback edge cases)
- Exact match feedback
- Colour-only match feedback
- Duplicate colour feedback edge cases
- Winning guess detection
- 12-guess limit
- Simultaneous solve / draw logic
- Illegal guess rejection
- Bot legal guesses only
- Golden fixture generation into `shared_fixtures/`

## Godot rules tests (headless)
```bash
export GODOT=/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
tools/run_godot_tests.sh
# Equivalent:
timeout 600s "$GODOT" --headless --path godot_project --script res://sim/tools/run_tests.gd
```

First-time import after new `class_name`:
```bash
timeout 120s "$GODOT" --headless --path godot_project --import
```

### Coverage
- Same cases as Python via `shared_fixtures/` loader
- Bot legality + 12-guess stop

## Godot UI smoke test (headless)
```bash
tools/run_godot_ui_smoke.sh
# Equivalent:
timeout 300s "$GODOT" --headless --path godot_project --script res://client/tests/run_ui_smoke.gd
```

Must drive real UI actions (buttons / exposed UI methods). **Must fail if UI controls are not wired**, even when pure rules work.

## Manual playtest
See [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md). Run only if visible Godot window available; otherwise document scripted smoke pass and list steps for user.

## Process cleanup
```bash
tools/godot_check.sh    # inspect
tools/godot_cleanup.sh  # scoped kill
```

Never broad `pkill -f godot`.

## Verification statuses
passed | failed | errored | timed out | not run — never collapse.
