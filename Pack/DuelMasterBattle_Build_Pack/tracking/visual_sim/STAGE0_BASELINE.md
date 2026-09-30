# Visual Simulation QA Kernel — Stage 0 Baseline

**Status:** GATE PASSED (baseline recorded; zero product code changes)  
**Recorded:** 2026-09-30  
**Platform:** Linux (this host); **not** Windows-certified  

## Branch / identity

| Item | Value |
| --- | --- |
| Implementation branch | `work/visual-sim-qa` |
| Tip SHA | `a2766b1aae6bc48e1b2e92ce1965aadf77f4d1b5` |
| Comparison baseline (`main`) | `9c66ce00342698dc2900c9f7b03c18101221f799` |
| Ancestry | `main` is ancestor of polish tip; branch cut from polish tip |
| Worktree | `/home/joe/Projects/DuelMasterBattle-visual-sim-qa` (clean) |
| Original checkout | `/home/joe/Projects/DuelMasterBattle` left on `work/current-main-polish` with dirty tree preserved (4 modified dialogue/batch files + ~62 untracked `.uid`/compiled packs). Those untracked packs were **not** loaded into this baseline. |

## Toolchain

| Tool | Version |
| --- | --- |
| Python | 3.12.3 |
| Godot (used) | 4.4.1.stable.official (`/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64`) |
| Godot also present | 4.5.2 (not used for baseline) |
| `project.godot` features | `["4.4"]` |
| Windows | Not run |

## Command / projection path (verified from source)

```
PlayLatest / windows_playtest
  → g05_shell.tscn (_boot)
  → SidecarLauncher → tools/run_sidecar.py
  → WorldClient ↔ WorldSim.dispatch (CommandRouter)
  → TurnRunner / services mutate WorldState
  → read_view / export_overworld_area
  → WorldLayerPresenters.apply_area + Overworld entities
  → scene nodes (soldier/cart/hazard/construction overlays; buildings as tiles/signs)
```

**Fixture vs production:** `load_fixture` / `DMB_FIXTURE` arrange initial state. After boot, Travel/Wait/AdvanceGame/leases go through the same `WorldSim.dispatch` path as play. Player seat skips `PolicyService`; faction AI acts on Wait/Travel stages.

**Save:** `WorldState.to_dict` / `SaveCoordinator` / schema v2 snapshot. Formations, buildings, orders, units, battles, rng, ids, research, tech_draft, diplomacy are present in serializer at this tip (polish P1). Formations are **not** in `INDUSTRY_FIELDS` / `read_view` player view list used by g05.

## Known defects relevant to this kernel

| ID | Evidence | Implication |
| --- | --- | --- |
| R07 residual | `local_battle.gd` extends `RefCounted`; `g05_shell._maybe_host_local_battle` does `LocalBattle.new()` + `add_child` and never `OpenBattleLease`/`bind_lease`. g04 holds RefCounted without `add_child` and opens lease correctly. | Attended g05 local battle host broken. Offscreen/AI contact path works. |
| No client military cmds | CommandRouter has Travel/Wait/AdvanceGame/leases; no MoveFormation/Engage | Formation move is AI policy via Wait — ordinary for this game |
| No Construct command | Same; construct is AI `action_kind=construct` | Ordinary construction is autonomous faction path |
| Identity harvest gap | Soldiers set `unit_id`/`person_id` meta; construction uses node name; completed buildings are Overworld tiles/signs | Harvester must walk layers + Overworld |
| Formations omitted from view | `INDUSTRY_FIELDS` has units/battles/orders not formations | Authority observe must read WorldState/sidecar inspect, not only player view |

## Bounded probe results (EXECUTED)

### FX-MVP seed 507 — industry then turns
- After 120× `AdvanceGame`(1000ms): 12 units, 4 formations.
- After +60× `Wait`: 2 battles (`wipe`), orders present, soldiers retained.
- After alternate 60s industry + 120 Wait: `road:committed` observed; **0 new buildings**; settlement construct not observed in this bound.

**Slice reachability (Stage 0 assessment):**
- **Slice A (strategic/offscreen):** reachable via production Wait after industry — contact + wipe without inventing QA combat.
- **Slice A (attended local lease in g05):** blocked by R07 until minimal G04-reuse host repair.
- **Slice B:** road construction order → commit is reachable on production Wait. Settlement/city body not observed in 120 Wait bound; Stage 2 should start with committed construction order (road) and scaffold lifecycle, and escalate to settlement if naturally reached without QA Construct API.

## Test commands / results

| Command | Result |
| --- | --- |
| `PYTHONPATH=. python3 -m pytest tests/sim/test_polish_*.py tests/sim/test_t061_movement.py tests/sim/test_t032_orders.py tests/sim/test_g05_visual_layers.py tests/sim/test_semantic_visuals.py -q` | **30 passed** |
| `PYTHONPATH=. python3 -m pytest tests/sim -q` | **501 passed, 0 failed** (48.12s) |
| Godot `--import` (4.4.1) | exit 0 |
| `godot --headless -s res://client/tests/run_g05_smoke.gd` | **G05_SMOKE_OK** |
| `godot --headless -s res://client/tests/run_polish_spellbook_review.gd` | **POLISH_SPELLBOOK_REVIEW_OK** |
| Headed `g05_shell.tscn` (DISPLAY=:0, 15s timeout) | Process did not emit a boot OK line to stdout before timeout; display present. **Not** treated as headed PASS. Windows not run. |

## Boundaries for later stages

1. Authority must come from the same WorldSim/sidecar that drives Godot — no shadow sim.
2. Expected contracts independent of projection/harvest dicts used as actual.
3. Scenario class: `PRODUCTION_JOURNEY` \| `ARRANGED_STATE`.
4. Bulk evidence under `qa/visual_sim/out/<run_id>/` (gitignore); contracts checked in under `qa/visual_sim/contracts/`.
5. Do not load original checkout’s untracked compiled packs into kernel runs.
6. Do not SHA-stamp handoff docs after every commit.

## Stage 0 gate

**PASSED.** Baseline written; boundaries verified; product/gameplay code unchanged in this stage.
