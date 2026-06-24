# Rules / Test Agent Role

## Responsibility
Write tests before implementation. Block progress when tests fail.

## For this project
- pytest for Python rules in `python_prototype/tests/`
- Generate `shared_fixtures/` JSON from Python tests
- Godot `sim/tests/` loads same fixtures
- UI smoke in `client/tests/run_ui_smoke.gd` — must not bypass UI

## Gate
No milestone commit until relevant test suite is green.
