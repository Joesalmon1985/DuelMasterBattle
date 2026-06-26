# Release Notes — Real-Time Wizard Ward Duel

## Current branch — real-time mobile duel

### Gameplay
- **Real-time duels** with independent cast windows (`DmbRealtimeDuelSim`)
- Global **Easy / Medium / Hard** difficulty selection
- Encounters: Blue Apprentice, Thorn Adept, Mirror Mage, Archmage Duel, Eightfold Warden (boss)
- 1–8 locus support; PRD terminology (Essence, Locus, Fracture, Echo, Fade)
- Result states: Victory, Defeat, Clash, Stalemate
- Last Stand on boss encounter (Eightfold Warden)
- Aggregate-only feedback (no positional leak in UI payload)

### UI
- Portrait **3-zone duel layout** (rival ward / impact / player action)
- Composite wizard + ward barrier visuals
- Gem Cast button, cast timer ring, feedback chips
- Collapsed history peek + slide-up history sheet
- Modal help (`?`) — no persistent help text during play
- `DmbVisualTheme` + `docs/ART_BIBLE.md` art direction

### Visual QA
- `tools/capture_visual_qa.sh` — 15 screenshot states at 720×1280
- `tools/visual_qa_report.py` — metrics + montage grid
- `docs/VISUAL_QA.md` — rubric and workflow
- `qa/screenshots/`, `qa/reports/`, `qa/montages/`

### Technical
- `DmbDifficultyProfile` separate from encounters
- Python + Godot rules parity updates
- Real-time sim tests + updated UI smoke tests
- Android export preset added (requires local Godot Android templates)
- `tools/generate_composite_sprites.py` — 2× layered PNG generator
- Draft sprite generator retained for legacy icons

### Legacy
- `DmbSequentialDuelGame` retained for regression tests (alternating-turn prototype)

### Manual QA
See [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md) and PRD §27.5.
