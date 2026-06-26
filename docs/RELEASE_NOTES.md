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
- Portrait mobile layout (720×1280)
- Difficulty + encounter select on main menu
- Cast timers, pause, expandable history
- Settings: haptics, reduce motion, help text
- Attack animation layer (aggregate feedback reveal)

### Technical
- `DmbDifficultyProfile` separate from encounters
- Python + Godot rules parity updates
- Real-time sim tests + updated UI smoke tests
- Android export preset added (requires local Godot Android templates)
- Draft sprite generator extended for loci, enemy portraits, feedback icons

### Legacy
- `DmbSequentialDuelGame` retained for regression tests (alternating-turn prototype)

### Manual QA
See [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md) and PRD §27.5.
