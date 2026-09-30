# Stage 2 — Slices + oracle gate

**Status:** PASSED  
**Date:** 2026-09-30  
**Branch:** `work/visual-sim-qa`  
**Platform:** Linux; Godot 4.4.1 OpenGL; Python 3.12.3; **Windows not run** (not certified)

## Journeys

| Slice | Class | Result |
| --- | --- | --- |
| B construction | PRODUCTION_JOURNEY | PASS — committed `road` via Wait after AdvanceGame |
| A combat attended | PRODUCTION_JOURNEY | PASS — PENDING battle → `OpenBattleLease` → `CloseBattleLease` on production command path |

## g05 local host repair (related)

[`g05_shell.gd`](godot_project/client/scenes/g05_shell.gd): stop `add_child` on RefCounted `LocalBattle`; open `OpenBattleLease`, `bind_lease`, checkpoint, `CloseBattleLease` (G04 reuse).

## Oracle challenge

| Check | Result |
| --- | --- |
| Python disposable manifest mutations | PASS (`test_visual_sim_slices` / `test_visual_sim_kernel`) |
| Godot disposable scene reharvest | `VISUAL_SIM_ORACLE_CHALLENGE_OK` (dup/hide/move/remove on frozen layer presenters) |
| Headed 450×800 / 1280×720 smoke | `VISUAL_SIM_GODOT_OK` nonblank shots |

## Commands

```text
PYTHONPATH=. python3 -m pytest tests/sim/test_visual_sim_slices.py tests/sim/test_visual_sim_kernel.py -q
GODOT=… DISPLAY=:0 godot --rendering-driver opengl3 --script res://client/tests/run_visual_sim_oracle_challenge.gd
DISPLAY=:0 python3 tools/run_visual_sim_qa.py godot --resolution 450x800|1280x720
```
