# Start here — visual playtest (8 chapters)

## Launch

- **Windows:** double-click [`Play Visual Review.bat`](../Play%20Visual%20Review.bat)
- **Linux:** `./tools/play_visual_review.sh`

This opens the real integrated game (`g05_shell`, FX-MVP seed **507**) with an **isolated save slot** `g05_visual_review` and session flag **`DMB_PLAYTEST_REVIEW=1`**. Normal **Play Latest** does not set the review flag.

## In-game

1. Click **Spellbook** (bottom-right) or press **B**.
2. Open the **Review** tab → **Start review**.
3. Use diagnostic tabs (This place, Economy, Factions/tech, Conflict/hazards, History, Evidence) as read-only references.
4. Safe controls only: **Load chapter checkpoint** (when configured), **Wait once**, **Close and watch**, **Capture issue**, **Replay chapter**, **Next chapter**, and **Clear / Unclear / Broken**.

**Grimoire (G)** remains normal gameplay magic — unchanged.

## Eight chapters (~25–30 min)

| # | Focus | Spellbook detail |
|---|--------|------------------|
| 1 | Move, talk, travel once | This place |
| 2 | Cart delivery → building | Economy |
| 3 | Factory → soldier | Economy / units |
| 4 | Technology round | Factions/tech |
| 5 | Hazard → recovery | Conflict/hazards |
| 6 | Hostile contact | Conflict/hazards |
| 7 | Ward duel | Evidence (if needed) |
| 8 | Save/reload + near-era | History |

Chapter tasks and checkpoint IDs live in [`godot_project/content/polish/visual_review_chapters.json`](../godot_project/content/polish/visual_review_chapters.json). Checkpoints are seeded under `.dmb_saves/` from `Pack/.../tracking/polish/checkpoints/seed507/`. **Load chapter checkpoint** copies the production save into the review slot then loads it.

## After each chapter

Pick **Clear**, **Unclear**, or **Broken**. Optional: **Capture issue** (writes `logs/polish_review/issue_*.json`).

## Normal play check

Launch **Play Latest Integrated Game.bat** — spellbook shows **player-safe Info** only (no Review/debug tabs).
