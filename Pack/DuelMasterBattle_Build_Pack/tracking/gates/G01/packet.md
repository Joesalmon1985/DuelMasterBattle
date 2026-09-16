# G01 playtest packet

**Gate:** G01 — Local controls, clocks and reliable startup  
**Status:** AWAITING_HUMAN  
**Prepared:** 2026-09-16  
**Seed:** 7  
**Fixture:** FX-CLOCK  

## Build

- Branch: `BuildPackV03`
- Commit: ec13d237d5fd5ae088d26c36af106bbf99c53a52
- Godot: 4.4.1 native Linux (`toolchain.json`)
- Python: 3.12.3 (`python3`)

## Launch (verified on this host)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g01.sh
```

This opens `res://client/scenes/g01_shell.tscn`, starts the loopback Python sidecar, and enables the migrated runtime (legacy Godot world tick/save writers blocked).

## What to try (10–15 min)

1. Drag in the local area with one pointer; use **Observe far**.
2. Press **Travel → node:2** once; confirm turn increments and destination changes only after acknowledgement.
3. Press **Wait** once; hold briefly and confirm it does not repeat; invalid travel is rejected by the shell/server.
4. **Pause** / **Resume**; save, quit completely, relaunch and **Load**.
5. Press **Bridge fail**; confirm pause with no Godot sim fallback.

## Automated evidence

- `python3 tools/check.py --task T007` … `T023`: PASS (per-task reports under this folder as `check_T0xx.json`)
- `python3 tools/check.py --task T024` / `--gate G01`: see `automated_report.json`
- FX-CLOCK production entry: `fx_clock_record.json` (PASS)
- Godot smokes: `run_g01_smoke.gd` (sidecar+view), `run_g01_local_area.gd` (no speculative exit)

## Known defects (do not block G01 automation; may affect feel)

1. Dialogue factory still missing host `openpyxl` — deferred until a required acceptance check needs it.
2. Sprite facing mirror audit still has recorded failures — deferred until required.
3. Wine/Windows executable testing and packaging — **DEFERRED_NOT_PASSED** until T155–T160; not claimed here.
4. G01 shell is a constrained migrated slice (Travel/Wait/pause/save/bridge-fail), not full village gameplay (that remains G05).

## Optional hints (try inference first)

- If the shell says sidecar failed, confirm `python3 tools/run_sidecar.py` starts and writes `.dmb_endpoint.json`.
- Saves land under `.dmb_saves/` at the repo root.

## How to record your result

Reply `G01 PASS — <commit>` or `G01 FIX_REQUIRED — <what happened and what you expected>`.
