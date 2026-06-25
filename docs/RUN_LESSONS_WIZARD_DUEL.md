# Run Lessons — Wizard Duel / Solver / Art (2026-06-24)

Brief retrospective from `feature/wizard-duel-solver-art` on top of the working `feature/duel-mastermind-build` baseline.

## What worked well

- **Baseline verification before branching** — Running pytest + Godot rules + UI smoke on the old branch first made it clear later failures were new work, not a pre-existing break.
- **Three-track plan with a non-negotiable core** — Treating wizard picker + solver as the deliverable, and NN/art as optional depth, kept the game playable when solver tests ran slow.
- **Checkpoint commits per track** — Five logical commits (A → B → C → docs → NN) made recovery easy if a later track stalled.
- **Click-slot overlay picker** — In-scene `PanelContainer` (not OS popup) worked in headless UI smoke and matched the spec.
- **Shared bot contract + `register_feedback`** — Same interface for RandomBot (no-op) and SolverBot in Python and Godot kept game_state wiring simple.
- **Python-first solver + fixtures** — `generate_fixtures.py` emitting `solver_cases.json` gave Godot parity tests without duplicating solve expectations.
- **Runtime PNG load via `DmbArt`** — Avoided Godot import-pipeline issues in headless runs; graceful null on missing files prevented crashes.
- **UI smoke hooks on `GameBoard`** — `ui_is_picker_open`, `ui_action_pick_magic`, slot value getters proved picker flow without bypassing UI.
- **Time-boxed NN** — Scaffold + shape/forward tests in default pytest; full training behind env flag — did not block release.

## What was challenging

- **Godot headless + new `class_name` scripts** — `DmbBotFactory` / `DmbSolverBot` were not visible until preload or cache update; early runs failed with “not declared in scope.”
- **GDScript solver performance** — Full minimax over thousands of candidates caused **timeout (exit 124)** on rules tests mid-run; needed pool cap (100) and reduced Godot solve coverage (one representative secret in sim tests).
- **Python solver tests runtime** — Representative-secret solve loop in pytest took ~4 minutes; acceptable for CI but worth marking or splitting if the suite grows.
- **Sandbox vs full permissions** — Godot crashed (signal 11) in sandbox when user data dir/logs failed; full permissions + `.godot_user` fixed it.
- **JSON fixture types in Godot** — `opening_guess` from JSON compared as floats; int comparisons avoided false failures.
- **Art integration scope** — 17 assets generated quickly; board-level wizard sprites and point icons in headers deferred to avoid polish blocking gameplay.

## Sensible lessons for the next run

1. **Run Godot tests with full permissions and a project-local `GODOT_USER_DATA_DIR`** in automation scripts if sandbox flakes appear.
2. **Preload new sim scripts in dependents** (`const _X = preload(...)`) when headless runs before editor refresh — or document “open project once in editor” after adding globals.
3. **Cap solver work in GDScript up front** (candidate pool, single representative solve in Godot tests; full solve matrix stays in Python).
4. **Keep minimax / NN / art off the critical path** — ship picker + solver + green smoke first; push optional tracks in separate commits.
5. **Extend UI smoke when changing input** — any new interaction (picker, difficulty dropdown) needs a hook or real control assertion before claiming done.
6. **Document performance trade-offs** in RULES or bot docs when capping minimax (not “optimal,” responsive Expert).
7. **Regenerate fixtures after bot changes** — `PYTHONPATH=. python3 tests/generate_fixtures.py` before Godot fixture tests.
8. **Manual playtest remains separate** — smoke passing ≠ visual playtest; say so in release notes.

## Verification commands (reference)

```bash
cd python_prototype && python3 -m pytest -q
cd .. && tools/run_godot_tests.sh
tools/run_godot_ui_smoke.sh
tools/godot_cleanup.sh && tools/godot_check.sh
```

Final green run on this branch: **37 passed, 1 skipped** (pytest); **6/6** Godot rules; **UI SMOKE: ALL PASSED**.
