# Stage 1 — Minimal kernel gate

**Status:** PASSED  
**Date:** 2026-09-30  
**Branch:** `work/visual-sim-qa`  
**Platform:** Linux; Godot 4.4.1 OpenGL; Python 3.12.3; Windows not run

## Evidence

| Check | Result |
| --- | --- |
| `pytest tests/sim/test_visual_sim_kernel.py` | 7 passed (positives + missing/dup/stale/wrong/hidden/blank negatives) |
| `tools/run_visual_sim_qa.py sim --contract smoke_boot.json` | VISUAL_SIM_SIM_OK — Layer1 authority, class ARRANGED_STATE |
| `tools/run_visual_sim_qa.py godot --contract smoke_boot.json` | VISUAL_SIM_GODOT_OK — Layers 1+2+3; 79 entities; nonblank 1280×720 shot; `index.html` review row |

## Notes

- Dummy `--headless` renderer cannot capture viewport textures; kernel uses `--rendering-driver opengl3` on DISPLAY for Layer3.
- Read-only `sim_id` / `sim_kind` / `sim_role` metas added on layer presenters.
- Bulk out under `qa/visual_sim/out/` (gitignored).
