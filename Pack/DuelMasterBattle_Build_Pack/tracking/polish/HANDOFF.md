# Polish autonomous run — handoff

**Branch:** `work/current-main-polish`  
**Comparison baseline:** `9c66ce00342698dc2900c9f7b03c18101221f799`  
**Status:** `OWNER_REVIEW_PENDING` (not owner PASS; not Windows-certified from this Linux run)

## Start here

1. Double-click **[Play Visual Review.bat](../../../../Play%20Visual%20Review.bat)** or run `./tools/play_visual_review.sh`
2. Read **[docs/START_HERE_VISUAL_PLAYTEST.md](../../../../docs/START_HERE_VISUAL_PLAYTEST.md)**
3. In-game: **Spellbook** (or **B**) → **Review** → **Start review**
4. Walk the eight chapters; mark Clear / Unclear / Broken; use Capture issue as needed

Ordinary play remains **Play Latest Integrated Game.bat** (no privileged review pages).

## What was repaired (authoritative)

| Area | Change |
| --- | --- |
| P1 RNG | `WorldSim.dispatch` syncs bank from `state.rng` (no stale overwrite) |
| P1 save | `WorldState` serializes `research` / `tech_draft` / `diplomacy` |
| P1 draft | Prehistoric boot deals seven cards; interrupt discard skips new-era hands |
| P2/P9 spellbook | `SpellbookHost` + review binder; `DMB_PLAYTEST_REVIEW=1` |
| P3 trade | Policy auto-accept/dispatch when carts available |
| P4/P5 tests | Formation setup + era unit catalogue assertions |
| P5 tech | Six modifiers applied to industry/carts/units |
| P5 policies | FX-MVP assigns `policy-im-build/trade/war` |
| P6 hazards | Placement on turn boundary; `hazard_treat` executes |
| P6 battle | LocalBattle lease bind/tick (no RefCounted `add_child`) |
| P6 diplomacy | Allies not treated as hostile in movement |
| P7 sluice | Restored mechanisms in `puzzle.json` |
| P2 exits | Cardinal exits when topology absent |

## Tests

- `python -m pytest tests/sim -q` → **501 passed, 0 failed** (Linux)
- Multi-seed Wait smoke 507–512: OK with trained brains + active draft
- Godot: `run_polish_spellbook_review.gd` → `POLISH_SPELLBOOK_REVIEW_OK`

## Evidence

- Instruction: `docs/POLISH_AUTONOMOUS_RUN.md`
- Run state: `Pack/.../tracking/polish/run_state.json`
- P0 frames B01–B03 @ 450×800 / 1280×720 / 960×540 + `review.md` (label clutter recorded; **MANUAL REVIEW REQUIRED** for aesthetics)
- SB02 review-book frames under `tracking/polish/P9/.../final/`
- Checkpoints: `tracking/polish/checkpoints/seed507/` + seeded `.dmb_saves/`

## Remaining for Joe / later automation

- Subjective readability of labels/controls (V01–V04 clutter still visible in B01)
- Complete SB03–SB08 matrix at all sizes
- Full pointer Ward / era / save-quit-relaunch personal sequence on Windows 4.5.1
- Paired PROMOTION_SEEDS policy behavioural report (fixed artifacts; no retraining)
- Do **not** treat this as `AUTO_READY_FOR_OWNER_REVIEW` until you finish the eight-chapter walk and remaining mandatory captures

## Honest gate

Mandatory **sim** suite is green. Guided review **launcher + book + chapters + checkpoints** exist. Owner approval and remaining visual matrix are still pending.
