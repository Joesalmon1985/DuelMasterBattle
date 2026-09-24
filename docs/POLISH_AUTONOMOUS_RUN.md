# DuelMasterBattle — autonomous P0–P9 run (authoritative execution instruction)

**Status:** ACTIVE execution override for branch `work/current-main-polish`  
**Recorded:** 2026-09-24  
**Comparison baseline SHA:** `9c66ce00342698dc2900c9f7b03c18101221f799`  
**Sources:** `docs/DuelMasterBattle_Full_Run_Cursor_Prompt.txt`, `docs/DuelMasterBattle_Visual_Playtest_Review.md`, `docs/DuelMasterBattle_Current_Main_Polish_Plan.md` (technical criteria), execution/final-readiness safeguards.

This document is the persistent instruction for Cursor. After context compaction, **read this file and** `Pack/DuelMasterBattle_Build_Pack/tracking/polish/run_state.json` **and continue**. Do not restart the audit. Do not reintroduce P0-only stopping.

---

## Execution override (conspicuous)

The following staged-run clauses are **superseded for this run**:

- “P0 only” / harness-docs-only
- “STOP after each phase”
- “P1 requires Joe to request it”
- “start from an owner-accepted predecessor”
- “three failed attempts means stop the whole overnight”

**Continue P0→P9 automatically.** Preserve technical requirements, design rules, tests, evidence honesty, and historical Gxx records. Owner approval remains pending until Joe reviews.

**Finish:** working game + one easy launcher + in-spellbook guided review + replay-verified checkpoints + inspected screenshots + short owner checklist. A P0 commit alone is **not** the finish.

---

## Internal statuses

| Status | Meaning |
| --- | --- |
| `BASELINE_RECORDED_WITH_DEFECTS` | Expected P0 result; authorized repairs may begin |
| `AUTO_PHASE_VERIFIED` | Phase acceptance items have evidence |
| `PENDING_DEPENDENCY` | Named cross-phase item awaiting its prerequisite |
| `OWNER_REVIEW_PENDING` | Subjective judgment deferred to Joe (not PASS) |
| `BLOCKED` | Concrete failing prerequisite or missing capability |
| `AUTO_READY_FOR_OWNER_REVIEW` | Final only after integrated checks and readiness safeguards |

---

## Phase outcomes

| Phase | Required result |
| --- | --- |
| P0 | Verify current truth, small real baseline, classify failures, reliable capture/replay contract |
| P1 | Command-path RNG, durable serialization/rollback, initial/new-era drafting, ordered turn/round |
| P2 | Readable world/events, filtered player views; mount SpellbookHost; page/binder/input/pause contract |
| P3 | Conserved stock/trade/cart/construction; spellbook economy review |
| P4 | Real industry → persistent Person/soldier; industry/people review |
| P5 | Policy obs/assignment/diplomacy; seven-card draft; six tech consumers; faction/tech review |
| P6 | Local/offscreen conflict; hazard cadence/treatment/recovery; conflict/hazard review |
| P7 | Wizard actions, inventory/puzzle, full retained Ward via pointer |
| P8 | Era/collapse/legacy/history/cycle; true save/reload; era/persistence review |
| P9 | Integrated journey, multi-seed checks, final visuals, owner launch/review packet |

Detailed Q01–Q30 and screenshot/SB matrices in the polish plan remain **binding**. Naming an evidence ID does **not** satisfy it.

---

## Execution and final-readiness safeguards

1. This summary supplements the full technical plan and full-run prompt. Their detailed acceptance requirements remain binding.
2. Give every test, Godot launch, capture and simulation batch an **explicit timeout**. On hang: preserve diagnostics, clean up only processes started by this run, investigate, continue useful work.
3. Before `AUTO_READY_FOR_OWNER_REVIEW`, launch the final owner entry point and perform **all eight chapters through actual controls**. Verify checkpoint loading, Close and watch, Wait once, Replay, Next and issue capture. Writing the launcher/checklist alone is insufficient.
4. Final readiness requires no failing mandatory tests, missing required evidence, unresolved dependencies or critical/high integration defects. Subjective readability may remain `OWNER_REVIEW_PENDING`. Broken controls, clipped essential UI and incorrect state cannot be deferred as subjective.
5. The historical 15 failures are a **comparison baseline**. Record and resolve **actual current** failures; do not assume the count remains fifteen.
6. Persisted docs must use readable Markdown tables (proper separators).

After three unsuccessful attempts at the same fix: retain the failing reproduction, re-diagnose, change approach, continue. This is a diagnosis checkpoint, not automatic termination of the run.

---

## Spellbook review (summary)

- Entry: `Play Visual Review.bat` (+ Linux equivalent); flag `DMB_PLAYTEST_REVIEW=1`; isolated review saves.
- Reuse `spellbook_host.gd` / model / binders; do **not** mount old gate fixture mutators as owner controls.
- Eight chapters (~25–30 min); SB01–SB08 at 450×800, 1280×720, 960×540 (+ retained spellbook sizes).
- Ordinary Play Latest must not expose privileged pages.

Full detail: sections 6–9 of `docs/DuelMasterBattle_Full_Run_Cursor_Prompt.txt` and `docs/DuelMasterBattle_Visual_Playtest_Review.md`.

---

## Design constraints (unchanged)

Travelling wizard in autonomous historical simulation; no faction-command UI; Person↔Unit linkage; illustrative workers; no teleporting goods; retain Ward Duel `game_board` / `DmbBattleSim`; no quest content / finished art / retraining / parallel simulation. Reuse semantic placeholders and existing spellbook assets.

---

## Run state

Update after each milestone:

`Pack/DuelMasterBattle_Build_Pack/tracking/polish/run_state.json`
