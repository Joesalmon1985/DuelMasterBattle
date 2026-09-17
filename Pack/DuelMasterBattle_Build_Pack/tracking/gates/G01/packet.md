**Tested implementation commit:** `(pending)`  
**Handoff HEAD:** `(pending)`

# G01 playtest handoff — navigation / portrait FIX_REQUIRED repair

**Status:** AWAITING_HUMAN (do not start T025)  
**Scenario:** FX-CLOCK  
**Seed:** 7  

## What changed in this repair

- Fixture tree layout with a clear corridor from spawn → NPC → east exit (and return on the road). Full-tile trees; ground drawn under props; collision matches visible blockers.
- Action button labels the current verb: Observe / Interact / Travel / Move closer (unknown identity preserved; selection cleared after travel).
- Launcher defaults to **450×800 portrait**; `--landscape` → 1280×720.
- Bridge play test walks the real route (no teleport beside the exit).

Preserved: CanvasLayer HUD, local-pose sync across clock refreshes, save-pause token strip.

## Exact launch (fresh terminal)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

**Menu:** **G01 FX-CLOCK  (Python-backed runtime playtest)**  

Direct portrait: `bash tools/play_g01.sh --direct`  
Landscape: `bash tools/play_g01.sh --direct --landscape`

## Isolated save / reset

- Slot: `g01_playtest` → `.dmb_saves/g01_playtest.json`
- Seed: `7`
- Reset: quit, optionally delete that file, relaunch

## Automated results

- `python3 tools/check.py --task T020` → PASS
- `python3 tools/check.py --gate G01` → PASS
- Screenshots (actual pixels): `screenshot_450x800.png` (450×800), `screenshot_1280x720.png` (1280×720), alias `screenshot_wizard.png` (450×800)

**Not claimed as human gate PASS.**

## Checklist

| Step | Expect |
| --- | --- |
| Move pad | Clear path to NPC/exit; trees block only their tiles; World Turn unchanged |
| Action button | Shows Observe / Interact / Travel / Move closer as appropriate |
| Observe / interact | unknown → Mira; no debug IDs |
| Travel / return | Walk into exit glow; +1 turn each accepted journey |
| Portrait launch | Opens 450×800 by default |

## Remaining defects

- D001–D003 deferred; residual ObjectDB “1 resource” on some exits.

Reply `G01 PASS — <commit>` or `G01 FIX_REQUIRED — <symptom>`.
