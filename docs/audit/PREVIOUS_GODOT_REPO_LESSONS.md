# Previous Godot Repo Lessons

Audit of `/home/joe/Projects/WideRTS`, `/home/joe/Projects/GodotGames`, and related Cursor workflows. Patterns to reuse and mistakes to avoid for Duel Master Battle.

## What worked — reuse these patterns

### Test-first milestone gates
- Every milestone has explicit acceptance criteria; no milestone is complete until tests pass.
- Write tests before or alongside implementation; never weaken tests to make progress.
- Commit only after relevant tests + smoke checklist pass.
- Source: WideRTS `02-test-first-development.mdc`, GodotGames `milestone-workflow.mdc`.

### Deterministic simulation logic
- Authoritative rules live in a pure, headless-capable core (`sim/` in Godot, separate Python modules).
- UI is a window into state — it reads state and submits legal actions only.
- All randomness from an explicit seeded RNG stored in game state.
- Source: WideRTS `03-godot-sim-authority.mdc`, GodotGames `game-architecture.mdc`.

### sim/client separation
- `sim/` = `RefCounted` classes, no Node/scene dependencies for rules.
- `client/` = scenes, buttons, visuals; never re-derives feedback or win logic.
- Source: WideRTS `04-godot-boundary.mdc`.

### Headless Godot testing
- Custom `SceneTree` test runner (`run_tests.gd`) + lightweight `TestCase`/`TestAssert` base.
- Single entry point: `"$GODOT" --headless --path godot_project --script res://sim/tools/run_tests.gd`
- Run `--import` once after adding new `class_name` globals.
- Wrap commands in `timeout`; propagate exit codes via wrapper scripts.
- Source: WideRTS `docs/verification/local_verification.md`, GodotGames `scripts/invoke-godot-headless.sh`.

### Golden fixtures for Python/Godot parity
- Generate JSON fixtures from Python tests; Godot tests load the same files.
- Prevents silent drift between prototype and Godot port.

### Smoke tests
- Headless contract smokes for rules + UI wiring.
- UI smoke must drive real UI actions (buttons/exposed methods), not bypass UI to call game state.
- Manual playtest checklist for checks that need a visible window.
- Source: WideRTS three-track verification model.

### Bot diagnostics
- Test bot legality separately: legal code generation, legal guesses only, stops at 12.
- Random legal bot first; solver bot only after playable slice works.
- Source: WideRTS `run_bot_smoke.gd` pattern.

### Process cleanup
- **Known stale Godot process issue**: direct Godot CLI invocations can leave orphan processes.
- Always use wrapper scripts that wait for exit and propagate exit code.
- Scoped cleanup only:
  ```bash
  pgrep -af godot || true
  pkill -f 'Godot.*DuelMasterBattle' || true
  ```
- **Never** run broad `pkill -f Godot` / `pkill -f godot`.
- Source: WideRTS `10-run-verification-and-logging.mdc`, GodotGames `Invoke-GodotHeadless.ps1`.

### Git hygiene
- Feature branches (`feature/duel-mastermind-build`); commit per milestone.
- Heavy `.gitignore`: `.godot/`, caches, `build/`, `.venv/`, logs.
- Never commit generated junk, export presets with secrets, or local user data.
- Source: WideRTS `06-git-branch-and-review-policy.mdc`.

### Honest verification
- Five statuses: passed | failed | errored | timed out | not run.
- Never claim deployment, manual playtest, or milestone complete without evidence.
- Source: WideRTS `07-final-report-format.mdc`.

## What not to repeat

| Mistake | Why it hurt | Our guard |
|---------|-------------|-----------|
| Rules logic in UI | Drift, untestable UI | sim/client split; UI smoke fails if unwired |
| Second parallel GameState | Inconsistent state | One authoritative `DuelGameState` |
| Copy-paste donor merges | Fragile imports | Reimplement patterns, not files |
| Weakening tests to progress | False confidence | Milestone blocked until green |
| Broad Godot process kill | Kills unrelated editors | Scoped `pkill -f 'Godot.*DuelMasterBattle'` |
| Committing `.godot/` cache | Bloated repo, merge pain | `.gitignore` |
| Claiming deploy without build | Misleading status | Honest verification in final report |
| Over-investing in prototype UI | Delays playable Godot slice | tkinter minimal; Godot is primary |
| Solver bot before playable game | Delays acceptance test | Random bot only for vertical slice |
| Hand-copied test expected values | Python/Godot drift | `shared_fixtures/` JSON parity |

## Screenshot / visual verification
- Headless dummy renderer cannot capture viewport textures.
- Use SubViewport pixel smokes or windowed capture for visual checks.
- For this project: scripted UI smoke (headless) + `docs/MANUAL_PLAYTEST.md` for human verification.

## Recommended tool paths (this machine)
- Godot 4.4.1: `/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64`
- Export templates: `~/.local/share/godot/export_templates/4.4.1.stable/` (installed)
- Python 3.10 + tkinter (built-in)
