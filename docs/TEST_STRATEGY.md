# Test Strategy

## Principles
- Test-first: write tests before or alongside implementation.
- No milestone complete until relevant tests pass.
- Pure game logic tested heavily; UI tested via scripted smoke.
- Python and Godot share `shared_fixtures/` JSON — no hand-copied expected values where fixtures apply.
- **Archmage Duel** is the regression anchor for legacy 4-slot / 10-colour / 12-attack behaviour.

## Python (pytest)
```bash
cd python_prototype && python3 -m pytest -q
```

### Coverage
- Variable-slot feedback (1–4 pegs)
- `validate_code_for_ruleset` — slot count + magic pool
- `DuelRuleset` / encounter catalog — pool subset validation, `effective_max_attacks()`
- Alternating game flow per encounter (including Blue Apprentice 1-slot smoke)
- `compute_result` with configurable `max_attacks`
- Solver candidate counts per encounter (e.g. 4, 20, 64, 10_000)
- Golden fixture generation into `shared_fixtures/`
- NN scaffold (optional train skipped by default)

## Godot rules tests (headless)
```bash
export GODOT=/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
tools/run_godot_tests.sh
```

First-time import after new `class_name` scripts:
```bash
timeout 120s "$GODOT" --headless --path godot_project --import
```

### Modules (`sim/tools/run_tests.gd`)
| Script | Focus |
|--------|--------|
| `test_code.gd` | Constants + ruleset pool validation |
| `test_feedback.gd` | Variable-length scoring |
| `test_encounters.gd` | Four built-ins; Archmage vs legacy constants |
| `test_fixtures.gd` | Shared JSON parity |
| `test_game_state.gd` | Alternating flow; 1-slot + 4-slot |
| `test_solver_bot.gd` | Candidate counts; opening guess |
| `test_assets.gd` | Art paths |

### Coverage
- Same fixture cases as Python via `DmbFixtureLoader`
- Ruleset-driven bots; legal guesses in encounter pools

## Godot UI smoke test (headless)
```bash
tools/run_godot_ui_smoke.sh
```

### Flows (must both pass)
1. **Blue Apprentice** — 1 slot, 4 attack magics in picker, enemy tell, one human + one bot row
2. **Archmage Duel** — 4 slots, 10 magics, alternating path to finished + restart

Uses `ui_load_encounter()`, `ui_get_slot_count()`, `ui_get_visible_magic_count()`, `EncounterSession` via game board.

Must drive real UI actions. **Must fail if controls are unwired**, even when pure rules work.

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

## Reference counts (encounter branch)
- Python: **53 passed**, 1 skipped (typical)
- Godot rules: **7 modules** pass
- UI smoke: **ALL PASSED**
