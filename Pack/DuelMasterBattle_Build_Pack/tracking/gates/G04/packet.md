# G04 — Battles, wizard power and catastrophe (FIX resubmission)

**Status:** AWAITING_HUMAN  
**Candidate commit:** (set at commit time)  
**Platform:** Linux 6.8, Godot 4.4.1 (Windows launcher wired, not executed here)

## Why this resubmission

Joe returned `G04 FIX_REQUIRED` — three stationary white squares / uninteractable red
dots; not a playable handoff. This candidate:

- Fixes unit visuals (triangle/square/hexagon, faction colours, HP bars, cues)
- Opens a real local battle lease with pursuit/LOS/hostility graph and checkpoints
- Provides Destroy / Shield / Atk Spd / Range / Cast HUD controls wired to Python
- Places labelled demon diamond manifestations and a real Channel×3 duel (no win button)
- Uses async projections; casualties/treatment survive save/load

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g04_battle.sh          # seed 404, save g04_battle
bash tools/play_g04_hazard.sh          # seed 408, save g04_hazard
bash tools/playtest.sh                 # menu options for G04
```

Portrait default 450×800. Landscape: `bash tools/play_g04_battle.sh --resolution 1280x720`

## Controls

**Battle**
1. Watch Red vs Blue (comparable prehistoric era; all three unit types).
2. Tap a unit to select (yellow outline). HUD Cast does not move the wizard.
3. Destroy / Shield / Atk Spd / Range then **Cast** (keys 1/2/3 + Enter as supplements).
4. Pause/focus freezes combat; Save/Load uses isolated `g04_battle`.

**Hazard**
1. Three red diamonds near the wizard: hex:a / hex:b / hex:c with cube counts.
2. Tap a diamond → **Treat (duel)** → Channel three times (or Falter).
3. Success removes only that cube; other hexes stay; Visit ledger persists across Wait/Save/Load.
4. Terminal destructive tests use separate slot `g04_hazard_terminal`.

## Manual checklist

1. Units show distinct shapes/colours and fight (approach, HP drop, death).
2. Destroy and each buff affect the selected living unit with feedback.
3. Leave/return or Save/Load — casualties remain.
4. Hazard duel opens, Channel×3 clears one cube only; treated hex cannot be re-treated this visit.
5. Walking remains responsive while combat runs.

## Automated evidence

- `python3 tools/check.py --task T076` / `--gate G04` → PASS
- `run_g04_playable.gd` → `G04_PLAYABLE_OK` (combat + destroy + hazard duel via bridge)
- Rendered captures: `screenshot_battle_450x800.png`, combat_00–03, `screenshot_hazard_450x800.png`, hazard_selected/duel/channel, `screenshot_1280x720.png`

## Known limits

See `known_defects.md`. Windows not run on this host.

## Human acceptance

Reply `G04 PASS — <build/commit>` or `G04 FIX_REQUIRED — <symptom>`.
