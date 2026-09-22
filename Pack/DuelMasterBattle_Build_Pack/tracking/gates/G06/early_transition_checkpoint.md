# G06 Early Historic Transition Checkpoint

**Status:** `EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN`  
**Gate:** G06 remains **IN_PROGRESS** (not PASS)  
**Branch:** `phase/g06-historic-mvp`

## Build

| Field | Value |
|---|---|
| Branch | `phase/g06-historic-mvp` |
| Tip commit | *(filled after commit — see git tip)* |
| T103 | Rockfall/Person continuity |
| T104 | Atomic EraService + Historic industry |
| T105 | TransitionPresenter + Chronicle |
| T106 | FX-ERA fixture + launcher + **responsive overlay UI fix** |

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

## Responsive UI fix (this checkpoint retest)

**Root cause:** World Map / Chronicle used hard-coded panel sizes (`460×420`, `420×480`) and `PRESET_CENTER` offsets wider than a `450×800` viewport; map draw used fixed `origin=(200,200)` / `size=18`.

**Layout changes:**

- Shared `DmbResponsiveModal` (`responsive_modal.gd`): full-screen dim → MarginContainer safe margins → expand-fill Panel.
- World Map / Chronicle rebuild onto that shell; canvas/list use `SIZE_EXPAND_FILL`.
- Map `_on_draw_map` fits hex axial bounds to canvas with padding; markers scale with hex size (clamped).
- Nodes prefer `touching_hexes` averages from `export_world_map` (fallback scatter only if links missing).
- FX-ERA panel: compact top-left, vertical Map/Chronicle buttons (≥48px), hidden while modals open.
- Status + Time HUD stacked on the left for narrow widths (no side-by-side overlap).

### Viewport verification

| Viewport | FX panel on-screen | Map on-screen / large | Chronicle on-screen | Notes |
|---|---|---|---|---|
| 450×800 | PASS | PASS (≥~400px usable width) | PASS | Primary portrait |
| 720×1280 | PASS | PASS | PASS | Rect assert in `run_fx_era_ui.gd` |
| 960×540 | PASS | PASS | PASS | Compact landscape |
| 1280×720 | PASS | PASS | PASS | Desktop landscape |

Automated: `godot --headless --path godot_project --script res://client/tests/run_fx_era_ui.gd` → `FX_ERA_UI_OK`  
(asserts `global_rect` inside viewport for FX / Map / Chronicle / Close / ≥48px buttons; map canvas min size vs viewport).

Screenshots (real Godot GLES frames):

`Pack/DuelMasterBattle_Build_Pack/tracking/gates/G06/layout_captures/`

- `village_{450x800,960x540,1280x720}.png`
- `world_map_{450x800,960x540,1280x720}.png`
- `chronicle_{450x800,960x540,1280x720}.png`

Recapture: `bash tools/capture_fx_era_layout.sh`

### Remaining visual limits

- Settlement/road markers use average of touching hex centres (true board geometry), not exact Catan vertex coordinates; fine for strategic readability.
- FX-ERA panel still covers the top-left of the village while open (by design — compact, not full-screen).
- Overworld building labels / Magic button are separate Overworld HUD and can still crowd landscape tops; not part of this modal fix.

## Manual checklist (≈10–15 min)

1. Confirm FX-ERA panel is visible (badge + three buttons). If not → **stop**; build not ready.
2. At **450×800**: panel fully on-screen; status/time not overlapping buttons.
3. Click **World Map** → large centred modal, full 19-hex board readable, Close visible → Close.
4. Click **Chronicle** → fills usable area with margins, no horizontal scroll needed → Close.
5. Optionally resize / relaunch at **960×540** and repeat Map/Chronicle.
6. Walk Prehistoric node:35; talk to a worker; inspect Rockfall.
7. Click **Complete founding → 10 VP** → Wait commits → transition → panel shows Historic.
8. Confirm same LocalArea / same Person; save/reload does not re-transition.

## Verification layers

| Layer | Meaning |
|---|---|
| PROCESS LAUNCH | Godot window + sidecar started |
| HUMAN CONTROL SURFACE | Panel/buttons visible & usable (`run_fx_era_ui.gd` / live retest) |
| RESPONSIVE LAYOUT | Map/Chronicle/FX fit at 450×800 and landscape sizes |

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
