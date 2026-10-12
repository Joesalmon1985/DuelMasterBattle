# Start here — visual playtest (8 chapters)

## Launch

- **Windows:** double-click [`Play Visual Review.bat`](../Play%20Visual%20Review.bat)
- **Six factions / one settlement (review only):** [`Play Six-by-One Review.bat`](../Play%20Six-by-One%20Review.bat) — isolated slot `g05_review_six_one`
- **Linux:** `./tools/play_visual_review.sh`

This opens the real integrated game (`g05_shell`, FX-MVP seed **507**) with an **isolated save slot** `g05_visual_review` and session flag **`DMB_PLAYTEST_REVIEW=1`**. Normal **Play Latest** does not set the review flag.

## In-game

1. Click **Spellbook** (bottom-right) or press **B**.
2. Open the **Review** tab → **Start review**.
3. Use diagnostic tabs (**Here**, **Industry**, **Economy**, **Factions**, **Conflict**, **History**, **Evidence**) as read-only references — scroll long pages; use **More detail** for raw IDs.
4. On the HUD (no book required): **Wait** once per World Turn; **Watch world** / **Pause** / speed for observation (Wait + Game Time). Opening the book pauses watching.
5. Safe book controls: **Load chapter checkpoint**, **Wait once**, **Close and watch**, **Capture issue** (PNG+JSON), **Replay**, **Next**, **Clear / Unclear / Broken**.

**Grimoire (G)** remains normal gameplay magic — unchanged.

## Eight chapters (~25–30 min)

| # | Focus | Spellbook detail |
|---|--------|------------------|
| 1 | Move, talk, travel once | Here |
| 2 | Cart delivery → building | Economy |
| 3 | Factory → soldier | Industry |
| 4 | Technology round | Factions |
| 5 | Hazard → recovery | Conflict |
| 6 | Hostile contact | Conflict |
| 7 | Ward duel | Evidence (if needed) |
| 8 | Save/reload + near-era | History |

Chapter tasks and checkpoint IDs live in [`godot_project/content/polish/visual_review_chapters.json`](../godot_project/content/polish/visual_review_chapters.json). Checkpoints are seeded under `.dmb_saves/` from `Pack/.../tracking/polish/checkpoints/seed507/`. **Load chapter checkpoint** copies the production save into the review slot then loads it. **Next** stays on the current chapter if the checkpoint load fails.

## After each chapter

Pick **Clear**, **Unclear**, or **Broken**. Optional: **Capture issue** (writes `logs/polish_review/issue_*.json` **and** `.png`).

## Normal play check

Launch **Play Latest Integrated Game.bat** — spellbook shows **player-safe Info** only (no Review/debug tabs). Owner approval stays pending until you finish the walk.
