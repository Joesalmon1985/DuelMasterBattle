**Tested implementation commit:** `(pending stamp)`  
**Handoff HEAD:** `(pending stamp)`

# G01 playtest handoff — playable wizard FX-CLOCK (FIX_REQUIRED repair)

**Status:** AWAITING_HUMAN (do not start T025)  
**Scenario:** FX-CLOCK  
**Seed:** 7  

## What is now playable

Top-down FX-CLOCK local area with wizard (John), terrain/blockers, selectable person (unknown → Mira on interact), glowing exit to a distinct adjacent area. HUD and pointer controls live on a screen-space `CanvasLayer`; the playfield is fitted into the region between HUD and controls (no Camera2D scroll displacing UI). Clock/projection refreshes update labels only and no longer rebuild/reset local pose. Movement stops during pause, focus loss and bridge failure; UI clicks do not walk the wizard. Save no longer persists the ephemeral save-pause token.

## Exact launch (fresh terminal)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

**Menu:** press **`G01 FX-CLOCK  (Python-backed runtime playtest)`**.

Direct:

```bash
bash tools/play_g01.sh --direct
```

## Isolated save / reset

- Slot: `g01_playtest`
- File: `/home/joe/Projects/DuelMasterBattle/.dmb_saves/g01_playtest.json`
- Reset: quit completely, optionally delete that file, relaunch. Load restores node/pose/clocks; Game Time continues when the save was unpaused.

## Automated results (agent-run)

- `python3 tools/check.py --task T020` → PASS (playable pytest + `G01_PLAYABLE_OK` + `G01_BRIDGE_PLAY_OK`)
- `python3 tools/check.py --gate G01` → PASS (cumulative + scene checks + screenshots)
- Screenshots: `screenshot_450x800.png`, `screenshot_720x1280.png` (desktop capped to 720×1011), `screenshot_1280x720.png`, alias `screenshot_wizard.png`
- Menu entry and direct launch both exercised via `play_g01.sh` / capture of `g01_shell.tscn`

**Not claimed as human gate PASS.**

## Graphical note

Requested portrait `720×1280` was constrained by the host display to **720×1011**; evidence is filed as `screenshot_720x1280.png` with that actual pixel size. `450×800` and `1280×720` matched requested sizes.

## 10–15 minute checklist

| Step | Do | Expect |
| --- | --- | --- |
| Move | Pad/drag | Wizard moves; blockers; **World Turn unchanged**; pose survives clock ticks |
| Observe afar | Tap distant person | Label **unknown** |
| Approach/interact | Close + ✦ | Reveals Mira/guide |
| Travel | On exit + ✦ | Pending → ack; other area; **World Turn +1** |
| Wait | Press / hold | One turn per press |
| Invalid | Invalid exit | Rejected; node/turn unchanged |
| Pause/focus | Pause / alt-tab | Time frozen; no walk; no catch-up |
| Save/load | Save → quit → relaunch → Load | Restored; Game Time continues |
| Bridge fail | Bridge fail | Pause; no Godot sim fallback |

## Remaining defects

- D001–D003 deferred.
- ObjectDB “1 resource” on some exits: residual; no owned sidecar left after Menu/close.
- Desktop may clamp extreme portrait heights; use `450×800` or landscape if needed.

Reply `G01 PASS — <commit>` or `G01 FIX_REQUIRED — <symptom>`.
