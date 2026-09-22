# G06 Early Historic Transition Checkpoint

**Status:** `EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN`  
**Gate:** G06 remains **IN_PROGRESS** (not PASS)  
**Branch:** `phase/g06-historic-mvp`

## Build

| Field | Value |
|---|---|
| Branch | `phase/g06-historic-mvp` |
| Tip commit | *a4d01f2ed936645ba669f3a9cdd57a465a7292ab* |
| T103 | Rockfall/Person continuity |
| T104 | Atomic EraService + Historic industry |
| T105 | TransitionPresenter + Chronicle |
| T106 | FX-ERA fixture + launcher + responsive overlays + **map geometry** |

## Fixture

| Field | Value |
|---|---|
| Fixture | **FX-ERA** |
| Seed | **507** (same G05 continuity world / Rockfall @ node:35) |
| Checkpoint | Near-threshold Prehistoric; winner at **9 VP** with one **ready settlement order** |
| Provenance | `ConstructionService` road + settlement expansion from FX-VILLAGE/prehistoric; stock credited at warehouses; command log in `board.fx_era.provenance` |

## Pre-transition

| Field | Value |
|---|---|
| Winner | `faction:2` (player) @ **9 VP** |
| Loser | `faction:1` @ **5 VP** (expected collapse) |
| Start node | `node:35` (`settlement:3`) |
| Expected scoring action | Click **Complete founding → 10 VP** (Wait one turn) |
| Scoring order | `board.fx_era.scoring_order_id` targeting `scoring_node_id` |

## Expected transition outcome

| Field | Value |
|---|---|
| Trigger | Automatic on 10 VP (no debug button) |
| Winner | `faction:2` survives |
| Collapse | `faction:1` → ruins |
| Fission | None at this boundary |
| Historic cores | Prefer player start: **`settlement:3` @ `node:35`**, plus second ranked core |
| Legacy sites | Later expansion settlements retain Prehistoric industry |
| Historic industry | `settlement:3` cross-terrain chain operational |

## Continuity anchors

| Field | Value |
|---|---|
| Known Person IDs | `board.fx_era.known_person_ids` (e.g. `person:16`…) |
| Rockfall | `rockfall:1` **blocking**; quest `quest.blocked_exit_boulder` |
| Same LocalArea | No 48×48 regenerate |

## Launch / reset

```bash
DMB_SAVE_SLOT=fx_era_manual_1 bash tools/play_fx_era.sh
# Layout check (portrait):
DMB_RESOLUTION=450x800 DMB_SAVE_SLOT=fx_era_layout_check bash tools/play_fx_era.sh
# Landscape:
DMB_RESOLUTION=960x540 bash tools/play_fx_era.sh
```

**Required visible panel (if absent, build is not ready):**

```
┌────────────────────────────────────┐
│ FX-ERA • Prehistoric               │
│ faction:2 — 9 / 10 VP              │
│ Test action: Wait one turn         │
│ [Complete founding → 10 VP]        │
│ [World Map]                        │
│ [Chronicle]                        │
└────────────────────────────────────┘
```

Also: **M** opens World Map; **C** opens Chronicle (same paths as the buttons).

## Responsive UI fix (prior)

**Root cause:** World Map / Chronicle used hard-coded panel sizes (`460×420`, `420×480`) and `PRESET_CENTER` offsets wider than a `450×800` viewport; map draw used fixed `origin=(200,200)` / `size=18`.

**Layout changes:** shared `DmbResponsiveModal`; expand-fill Map/Chronicle; FX panel compact; HUD stacked on narrow widths.

### Viewport verification

| Viewport | FX panel on-screen | Map on-screen / large | Chronicle on-screen | Notes |
|---|---|---|---|---|
| 450×800 | PASS | PASS (≥~400px usable width) | PASS | Primary portrait |
| 720×1280 | PASS | PASS | PASS | Rect assert in `run_fx_era_ui.gd` |
| 960×540 | PASS | PASS | PASS | Compact landscape |
| 1280×720 | PASS | PASS | PASS | Desktop landscape |

Automated: `godot --headless --path godot_project --script res://client/tests/run_fx_era_ui.gd` → `FX_ERA_UI_OK`

## World Map geometry fix (this retest)

**Root cause:** `_node_pixel()` averaged touching hex centres. One-touch nodes landed on hex centres (covering numbers); two-touch nodes landed on edge midpoints; roads therefore cut through hex interiors.

**Geometry representation:** Python `HexBoard.node_map_position()` / `map_coordinates()` export integer cube corners as fractional axial `(cx/3, cz/3)`. `export_world_map` schema v2 includes `map_position` on all 54 nodes and the 72 topology `edges`. Godot applies the same fit transform as hexes — **no** centre-average fallback for the canonical board.

**Symbol legend (on-map):**

| Symbol | Meaning |
|---|---|
| ■ small square | Settlement (faction colour) |
| ▣ / octagon+ring | City / Historic core |
| square + gold ring | Legacy site |
| grey ✕ | Ruin |
| faction line | Road (exact edge A→B) |
| ◆ magenta | Hazard (upper-right of hex; `×N` if stacked) |
| ◎ white/cyan | You (John); offset if sharing a settled vertex |
| dark roundel + number | Production token (always drawn) |

Formations/carts are **omitted** from the strategic presentation layer (`presentation.formations/carts = omitted`).

**Tests:** `tests/sim/test_world_map_geometry.py` (wired into T106 check) — 54 unique coords, 72 edge sides, one-touch ≠ centre, seed-507 tokens/hazards/John, post-transition site kinds.

**Screenshots:**

- Before (centre-average bug): `layout_captures/world_map_450x800_before_geometry.png`
- After (exact corners): `layout_captures/world_map_450x800.png` / `world_map_450x800_geometry.png`

```bash
DMB_RESOLUTION=450x800 DMB_SAVE_SLOT=fx_era_map_check bash tools/play_fx_era.sh
```

### Remaining visual limits

- Terrain cues are sparse placeholder strokes (not full art).
- FX-ERA panel still covers the top-left of the village while open (compact by design).
- Overworld building labels / Magic button are separate Overworld HUD.

## Manual checklist (≈10–15 min)

1. Confirm FX-ERA panel is visible (badge + three buttons). If not → **stop**; build not ready.
2. At **450×800**: panel fully on-screen; status/time not overlapping buttons.
3. Click **World Map** → large centred modal; **numbers clear in centres**; **roads on edges only**; **settlements on corners**; **hazards offset**; legend visible; Close → Close.
4. Click **Chronicle** → fills usable area with margins, no horizontal scroll needed → Close.
5. Optionally resize / relaunch at **960×540** and repeat Map/Chronicle.
6. Walk Prehistoric node:35; talk to a worker; inspect Rockfall.
7. Click **Complete founding → 10 VP** → Wait commits → transition → panel shows Historic; reopen Map and confirm Historic core / legacy / ruin symbols.
8. Confirm same LocalArea / same Person; save/reload does not re-transition.

## Verification layers

| Layer | Meaning |
|---|---|
| PROCESS LAUNCH | Godot window + sidecar started |
| HUMAN CONTROL SURFACE | Panel/buttons visible & usable (`run_fx_era_ui.gd` / live retest) |
| RESPONSIVE LAYOUT | Map/Chronicle/FX fit at 450×800 and landscape sizes |
| MAP GEOMETRY | Exact HexBoard corners; roads on edges; legend |

A process launch alone is **not** sufficient for this checkpoint.

## Known defects / limits

- Second Historic core may be mono-terrain; node:35 core is operational.
- Normal-start → 10 VP pacing deferred (T108/T112).
- `run_g05_smoke.gd` may still hang in this environment; Python dialogue/quest suite remains PASS. Keep separate from FX-ERA UI work.

## Progress state

```
G06 = IN_PROGRESS
T103–T106 = DONE
EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN
```

Do **not** proceed to T107 until Joe accepts this checkpoint.
