# G06 Early Historic Transition Checkpoint

**Status:** `EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN`  
**Gate:** G06 remains **IN_PROGRESS** (not PASS)  
**Branch:** `phase/g06-historic-mvp`

## Build

| Field | Value |
|---|---|
| Branch | `phase/g06-historic-mvp` |
| Tip commit | `f724717585d88d0e5dac2b9a037ffb3ce4be39e5` |
| T103 | Rockfall/Person continuity |
| T104 | Atomic EraService + Historic industry |
| T105 | TransitionPresenter + Chronicle |
| T106 | FX-ERA fixture + launcher + **control surface fix** |

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
```

**Required visible panel (if absent, build is not ready):**

```
┌────────────────────────────────────┐
│ FX-ERA • Prehistoric • 9 / 10 VP  │
│ Test action: Wait one turn         │
│ [Complete founding → 10 VP]        │
│ [World Map] [Chronicle]            │
└────────────────────────────────────┘
```

Also: **M** opens World Map; **C** opens Chronicle (same paths as the buttons).

## Manual checklist (≈10–15 min)

1. Confirm FX-ERA panel is visible (badge + three buttons). If not → **stop**; build not ready.
2. Walk Prehistoric node:35; talk to a worker; inspect Rockfall.
3. Click **World Map** → map opens, Game Time paused → **Close** → resumes.
4. Press **M** → same map path.
5. Click **Chronicle** (or **C**) → opens → close.
6. Click **Complete founding → 10 VP** → Wait commits → transition → panel shows Historic.
7. Confirm same LocalArea / same Person; save/reload does not re-transition.

## Verification layers

| Layer | Meaning |
|---|---|
| PROCESS LAUNCH | Godot window + sidecar started |
| HUMAN CONTROL SURFACE | Panel/buttons visible & usable (`run_fx_era_ui.gd` / live retest) |

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
