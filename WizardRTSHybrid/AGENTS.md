# WizardRTSHybrid agents

This file is the restart contract. Status, tasks, and evidence live in the docs it names. Do not treat chat history as project memory.

## Objective

One continuous walkable world. The player is the existing Overworld wizard. Two factions run an economy and a military clock while the wizard walks or waits. A real route hazard opens the retained duel board. Python owns the world. Godot presents it.

Widelands, OpenRA, and the OpenRA Mod SDK are full local source labs under `external/`. Normal play must not read those trees. If original code is required at runtime, it is copied into this package and listed in `docs/LICENSES.md`.

## Architecture constraints

- Python `HybridWorld` is the only live simulation. It embeds DuelMasterBattle `WorldState` and `ClockService`.
- Godot `hybrid_world.gd` extends `overworld.gd`. Keyboard, mouse steer, collision, interact, and camera follow stay there.
- Crossing a hex writes the player hex. It does not call `TurnRunner` Travel or Wait and it does not change scene.
- `AdvanceGameTime` is `ClockService.request_advance` from elapsed time. Pause token `hazard_duel` yields zero quanta. `tick_duel_clock` is not used to move `game_ms`.
- Hex ownership is `cube_round` of the tile center. There is no exclusive 48 by 48 square per hex.
- Do not call a DuelMasterBattle cart or formation Widelands or OpenRA. Provenance strings are on the snapshot.
- Do not implement Mindustry. Do not advance build-pack T143. Merges to `main` only when Joe asks for them.

## Repo layout

- `wizard_rts/` — authoritative world, stock port, damage port, local JSON server.
- `tests/` — Python checks. `test_five_minutes.py` is a wall-clock script, not part of the quick suite.
- `sources/manifest.json` — pinned upstream URL, branch, SHA, licence, build command.
- `scripts/` — recreate clones, launch, test, package.
- `external/` — gitignored full clones.
- `docs/` — living record and engine maps.
- Godot presentation: `godot_project/client/scenes/hybrid_world.gd` and `client/hybrid/`.

## Build and test

From the repo root, with `py -3` (the repo `.venv` Python is blocked by Application Control on this machine):

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 WizardRTSHybrid/tests/test_five_minutes.py
WizardRTSHybrid/scripts/launch_hybrid.ps1
```

Headed scripts: forestry, God Mode (real mouse events), six-faction war; see `docs/STATE_OF_PLAY.md`. Use a fresh sim per script. Godot coordinate check: `godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd`.

Headed walk and duel scripts need the sim on `HYBRID_SIM_PORT` (default 8765) and `--rendering-method forward_plus` so the viewport readback is not black. The Compatibility renderer returns an empty image.

## Reuse and licensing

Prefer executing an upstream algorithm, then a separate process, then a source-derived port. Do not reimplement from a class-name summary when the source can be packaged. Widelands is GPL-2.0-or-later. Do not paste GPL-2-only files into this tree. The stock port is a small derivative and is attributed in `docs/LICENSES.md`. OpenRA is GPL-3.0-or-later.

## Commits

Commit verified milestones on the current feature branch (`feature/hybrid-playtest-fixes-v03` since session 3; `feature/wizard-rts-hybrid-v02` before). Never commit `external/`, `runtime/`, `dist/`, secrets, or unrelated dirty spellbook and content files. An unfinished experiment stays unverified in the ledger.

## Playtest rule (session 3)

A defect the owner sees in play is fixed only when a headed Godot test (a screenshot or an assertion on the rendered state) shows it fixed; a green
Python suite does not close it. Never decide anything in the simulation by iterating a salted-hash container or by wall-clock time
(`tests/test_determinism.py`). Read `docs/PLAYTEST_FIXES.md` and `docs/DECISIONS.md` D7, D8.

## Failed experiments

Add a row to `docs/BLOCKERS.md`: upstream file and symbol, what was tried, the exact error, whether it is an environment problem or an incompatibility, and the next approach. Do not retry a failed fix without new evidence named in that row.

## Restart

1. Read this file, then `docs/PROJECT_STATUS.md`, `docs/TASK_LEDGER.md`, `docs/BLOCKERS.md`, and `docs/CLAUDE_HANDOFF.md`.
2. Check `git status` and the latest commit. Trust the repo and the evidence files where a doc disagrees.
3. Rerun the baseline commands in `docs/PROJECT_STATUS.md`.
4. Take the highest-priority actionable task in the ledger.
