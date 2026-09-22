# G06 Early Historic Transition Checkpoint

**Status:** `EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN`  
**Gate:** G06 remains **IN_PROGRESS** (not PASS)  
**Branch:** `phase/g06-historic-mvp`

## Build

| Field | Value |
|---|---|
| Branch | `phase/g06-historic-mvp` |
| Tip commit | *(fill after T106 commit)* |
| T103 | Rockfall/Person continuity |
| T104 | Atomic EraService + Historic industry |
| T105 | TransitionPresenter + Chronicle |
| T106 | FX-ERA fixture + launcher |

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
| Expected scoring action | **Wait** → commits staged settlement order → **10 VP** |
| Scoring order | `board.fx_era.scoring_order_id` targeting `scoring_node_id` |

## Expected transition outcome

| Field | Value |
|---|---|
| Trigger | Automatic on 10 VP (no debug button) |
| Winner | `faction:2` survives |
| Collapse | `faction:1` → inert ruins |
| Fission | None at this boundary (multi-faction start; sole survivor marked for later mandatory fission) |
| Historic cores | Prefer player start: **`settlement:3` @ `node:35`**, plus second ranked core (often `settlement:4` @ `node:27`) |
| Legacy sites | Later expansion settlements retain Prehistoric industry (e.g. `settlement:8+`) |
| Historic industry | `settlement:3` cross-terrain chain operational (`recipe.historic.his_04` class) |

## Continuity anchors

| Field | Value |
|---|---|
| Known Person IDs | See `board.fx_era.known_person_ids` (workers on node:35, e.g. `person:16`…) |
| Rockfall | `rockfall:1` status **blocking**; quest `quest.blocked_exit_boulder` offered |
| Same LocalArea | Transition must not regenerate 48×48; structures upgrade in place |

## Launch / reset

```bash
bash tools/play_fx_era.sh
# optional:
DMB_SEED=507 DMB_SAVE_SLOT=fx_era bash tools/play_fx_era.sh
```

Reset: delete Godot user save slot `fx_era` / restart with a fresh seed env; or relaunch without loading a prior Historic save.

## Manual checklist (≈10–15 min)

1. Launch FX-ERA; walk Prehistoric core at node:35 briefly.
2. Talk to a known worker; confirm dialogue is truthful.
3. Inspect Rockfall (still blocking).
4. Press **Wait (complete founding → 10 VP)**.
5. Confirm transition presentation (~4s; Esc/Skip OK).
6. Confirm Historic labels/shapes on the **same** LocalArea.
7. Talk to the same Person again.
8. Open **Chronicle** (button or `C`).
9. Travel to a legacy Prehistoric expansion site; confirm old-era industry still marked LEGACY.
10. Save / reload; confirm transition does **not** repeat.

## Known defects / limits

- Full normal-start → 10 VP pacing remains deferred to T108/T112 (autonomous cart/settlement growth risk).
- Second Historic core may lack cross-terrain recipe if its hexes are mono-terrain (`no_cross_terrain_recipe`); primary core at node:35 is validated operational.
- Godot transition overlay is prototype geometry (acceptable per T105).
- G05 Godot headless smoke may still hang in this environment; Python Rockfall/dialogue suites are the regression authority.

## Progress state

```
G06 = IN_PROGRESS
T103–T106 = DONE
EARLY_TRANSITION_CHECKPOINT = AWAITING_HUMAN
```

Do **not** proceed to T107 until Joe accepts this checkpoint.
