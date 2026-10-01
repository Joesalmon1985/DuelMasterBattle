# Visual Sim QA — Iteration 2 gates

**Branch:** `work/visual-sim-qa`  
**Working tree:** dirty (instrumentation + UI clip/HUD repairs in progress)  
**Windows:** NOT_RUN

## Gate 1 — Defects verified + baseline

| Defect (from 03b730a review) | Status after iter2 |
| --- | --- |
| Boot-only screenshots | Fixed path: multi-checkpoint kernel modes |
| HUD/spellbook overlaps despite PASS | HUD strip + spellbook content clip/insets; structural overlap check |
| Dict-only marked visible | Harvester `dict_only_no_node`; not counted as visible |
| Node-backed all outside viewport | Camera/canvas → viewport transform |
| Cart labels as bodies | Labels `sim_role=label`; bodies unique by instance |
| Authority from shadow sim | Live sidecar `visual_sim_authority` / view fields; session bind |
| `or True` lease assert | Removed; `assert_lease_closed` real |
| Vacuous duplicate negative | Meta-test: disabling checker breaks negative |
| Scaffold assert without render | Requires render scaffold bodies |
| Soak sim-only | Long profile scopes cheap checks separately |
| `profile long` stub | Implemented |
| Shutdown resource errors | Classified; investigated; still leak warning on exit |

**Baseline:** `qa/visual_sim/out/_baseline_prod_iter2.txt` — 30 production polish/orders/movement/visual tests PASS.  
**Visual unit/slices:** 14 PASS (`test_visual_sim_{kernel,stage3,slices}`).

## Gate 2 — Evidence pipeline

Live session binds session_id + world_version across authority JSON, render harvest, and PNG.  
Evidence: `qa/visual_sim/out/smoke_iter2_1280/` (sidecar=true, dict_only explicit, node_backed counted separately).

## Gate 3 — Oracle negatives

`VISUAL_SIM_ORACLE_OK` — `qa/visual_sim/out/oracle_iter2c/`  
healthy PASS; duplicate/hidden/moved/missing with expected codes; solid screenshot FAIL; restore healthy PASS.

## Gate 4 — Pilot (32 captures)

Command: `DISPLAY=:0 python3 tools/run_visual_sim_qa.py pilot --run-id pilot_iter2`  
Results: see `qa/visual_sim/out/pilot_iter2/summary.json` and `index.html`.

## Gate 5 — Expanded + long

Command: `DISPLAY=:0 python3 tools/run_visual_sim_qa.py profile long`  
Snapshot replay: **BLOCKED** until save→load preserves field inventory + next-command equivalence.

## Pruning

`python3 tools/run_visual_sim_qa.py prune --dry-run`  
Retain failures; keep pilot + first completed long screenshots; later PASS runs may prune.
