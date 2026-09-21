# G05 — Living Prehistoric world + natural long-run visual test

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Foundation commit:** `a9323e7` (visual layers) → living-world + long-run pass  
**Play (normal):** `bash tools/play_g05.sh` — seed **507**, FX-VILLAGE  
**Play (long-run observer):** `bash tools/play_long_world.sh` — FX-LONG-WORLD  
**Play (staged layers demo):** `bash tools/play_world_layers.sh` — FX-WORLD-LAYERS (not autonomy proof)  
**Branch:** `refactor/canonical-ontology-g05`

## Human acceptance

> Villages look busy (geometric workers with carry cycles). Natural geography is
> obvious in every LocalArea. The **ordinary** seeded world, advanced only with
> Wait + AdvanceGame, produces roads, units, formation movement, and a real
> battle with casualties — without staged FX-WORLD-LAYERS cheating.

## What this pass adds

| Area | Delivered |
|------|-----------|
| Workers | Geometric WorkerController; occupation + activity labels; carry pips from projected resource |
| Nature | Dense `natural_props` per touching hex; geometric nature presenters; ambient animals (no IDs) |
| Industry | Settlement cubes cleared at start; all settlements hire workers; single-terrain local craft fallback |
| Military | Produced units auto-form; AI selects military moves; contact opens real battles |
| Long-run | `FX-LONG-WORLD` + `tools/play_long_world.sh` + `tools/run_long_world.py` |
| Observer | Fast-forward / event log / follow-major (dev only; not in normal play) |

Quest content remains **archived**. No T097.

## Evidence

- Long-run report: `long_run_report.md`
- Visual language: `docs/WORLD_VISUAL_LANGUAGE.md`
- Tests: `tests/sim/test_natural_world.py`, full-world suite, deterministic long-run ×2

## Known limitations / design decisions needed

- **No new settlements or cities** within 200 World Turns (placement/economy).
- **No cart deliveries** in the soak (`no_cart_activity` flag).
- LocalBattle mount in Overworld is present for active battle nodes but thinner
  than standalone `g04_battle_shell`.
- Confirm retaining `recipe.local.{terrain}` for single-hex settlement industry.

## Stop

Do **not** start G06 / T097 until Joe PASSes this gate.
