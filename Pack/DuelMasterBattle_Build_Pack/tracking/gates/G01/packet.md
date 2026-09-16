**Tested implementation commit:** `6252be79acbcd7d71f7ea5a748672622a79db3f5`  
**Handoff HEAD:** `f488762db57a25c70ab191073a1682f70e8d3020`

# G01 playtest handoff — playable wizard FX-CLOCK

**Status:** AWAITING_HUMAN (do not start T025)  
**Scenario:** FX-CLOCK  
**Seed:** 7  

## What is now playable

A top-down local area with a visible wizard (John), terrain/obstacles, a selectable person (unknown until interacted), and a glowing exit to an adjacent, visually distinct area (Home Clearing ↔ Stone Road). Controls use one pointer (on-screen pad + drag/tap). Python owns durable world state over the loopback sidecar; legacy Godot world tick/save writers stay blocked.

## Tested commit

`6252be79acbcd7d71f7ea5a748672622a79db3f5`

## Exact launch (fresh terminal)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

**Menu:** press **`G01 FX-CLOCK  (Python-backed runtime playtest)`**.

Direct (skips menu):

```bash
bash tools/play_g01.sh --direct
```

Godot binary is discovered automatically (validated fallback: `/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64`). No pre-set `$GODOT` required.

## Isolated save / reset

- Slot: `g01_playtest`
- File: `/home/joe/Projects/DuelMasterBattle/.dmb_saves/g01_playtest.json`
- Reset: quit completely, optionally delete that file, relaunch. Load restores node, pose, clocks and receipts. Closed time is not applied.

## Automated results (agent-run)

- `python3 tools/check.py --task T020` → PASS (playable command tests + `G01_PLAYABLE_OK`)
- `python3 tools/check.py --gate G01` → PASS (cumulative Python + packet + sidecar smoke)
- FX-CLOCK production scenario → PASS
- Screenshot: `tracking/gates/G01/screenshot_wizard.png` (viewport capture during launch)
- Graphical window was launched with OpenGL on Intel HD 520; sidecar printed `DMB_SIDECAR`

**Not claimed as human gate PASS.** Manual steps below remain for Joe.

## 10–15 minute checklist

| Step | What you do | Expected |
| --- | --- | --- |
| Move | Pad/drag the wizard | Visible movement; blockers respected; **World Turn unchanged** |
| Observe afar | Tap distant person / ✦ when far | Label **unknown**; no name |
| Approach/interact | Move close, ✦ | Reveals permitted role/name (Mira/guide); UI reflects accept |
| Travel | Stand on glowing exit, ✦ or tap | Pending text; destination after ack; **World Turn +1**; other area looks different |
| Wait | Press Wait once; hold | One turn per press; hold does not repeat |
| Invalid | Invalid exit button | Rejected; node/turn unchanged |
| Pause/focus | Pause 10s; alt-tab | Game Time frozen; no catch-up |
| Save/load | Save → quit → relaunch → Load | Node/pose/counters restored |
| Bridge fail | Bridge fail button | Pauses; no Godot sim fallback; recover via relaunch+Load |

HUD always shows **World Turn**, **Game Time**, **Node**. Dev panel is collapsible (logs do not cover the playfield by default).

## Remaining defects

- D001 openpyxl, D002 facing audit, D003 Windows/Wine — deferred, do not block G01.
- ObjectDB “1 resource still in use” on some headless exits: targeted cleanup added for sidecar/endpoint; residual warning may be engine-level. No accumulating owned sidecar left running after Menu/close.

Reply `G01 PASS — <commit>` or `G01 FIX_REQUIRED — <symptom>`.
