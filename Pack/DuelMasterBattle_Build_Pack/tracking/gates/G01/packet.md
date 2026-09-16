# G01 playtest handoff

**Gate:** G01 — Local controls, clocks and reliable startup (10–15 minutes)  
**Status:** AWAITING_HUMAN — stop before T025  
**Prepared:** 2026-09-16  

## Automated acceptance (T001–T024)

All of T001–T024 are marked DONE with receipts. Re-verified on this host:

| Range | Result |
| --- | --- |
| T001–T005, T007–T024 | `python3 tools/check.py --task Tnnn` → **PASS** |
| T006 | Tracking suite updated for G01-blocking resume; **PASS** after that fix |
| G01 automated suite | `python3 tools/check.py --gate G01` → **PASS** |
| FX-CLOCK | `python3 tools/run_scenario.py --fixture FX-CLOCK …` → **PASS** |
| Godot sidecar smoke | `run_g01_smoke.gd` → **G01_SMOKE_OK** |

**Outstanding failures for this gate:** none required. Deferred (not G01 blockers): missing `openpyxl`, sprite-facing audit, Wine/Windows packaging until T155–T160.

## Build

- Branch: `BuildPackV03`
- Commit: `66260569c7b20d1e982586687715273f6f3637a0`
- Godot: **4.4.1** native Linux (`/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64`)
- Python: **3.12.3** via `python3`

## Exact launch command (verified)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

Equivalent:

```bash
cd /home/joe/Projects/DuelMasterBattle
source tools/find_godot.sh
"$GODOT" --path godot_project res://client/scenes/g01_shell.tscn
```

This starts the loopback Python sidecar and the G01 FX-CLOCK shell. Python owns durable world state; legacy Godot world tick/save writers are blocked.

## Reset / isolated test save

- **Seed:** 7 (FX-CLOCK)
- **Isolated save slot:** `g01_playtest`
- **Save file path:** `/home/joe/Projects/DuelMasterBattle/.dmb_saves/g01_playtest.json`
- **Reset:** quit the game, delete that save if you want a clean slot, then relaunch `bash tools/play_g01.sh`. Fresh launch always starts at `node:1` with turn 0 until you Load.

## On-screen diagnostics (required for G01)

Top of the shell shows:

- **World Turn**
- **Game Time** (ms and seconds)
- **Node** (current strategic node)
- paused / world_version

Buttons include **Travel adjacent**, **Wait**, **Invalid travel**, **Observe**, **Pause**, **Resume**, **Save (g01_playtest)**, **Load**, and **Bridge fail**.

## Playtest steps (match Joe’s table)

1. Startup/controls — drag local area; Observe far vs near (walk toward the right of the green pad).
2. Local movement 20s — World Turn unchanged; Game Time advances while unpaused.
3. Travel adjacent — World Turn +1; node changes after acknowledgement.
4. Wait once, then hold — one turn per distinct press.
5. Invalid travel — rejected; no node/turn change.
6. Pause 10s / focus away — Game Time frozen; no catch-up on return.
7. Save → quit completely → relaunch → Load — node and counters restored; closed time adds nothing.
8. Bridge fail — pauses with no Godot sim fallback; recover by relaunch + Load.

## How to record the result

- `G01 PASS — <tested commit>`
- or `G01 FIX_REQUIRED — <action; expected; actual>`

Do not start T025 until an explicit Joe PASS is recorded.
