# G05 — Procedural village / quest / duel playtest

**Status:** AWAITING_HUMAN  
**Stop point:** T096  
**Scenario:** FX-VILLAGE  
**Branch:** `feature/g05-village-quest`  
**Launch:** `bash tools/play_g05.sh` → playable Overworld + G01–G03 clocked industry

## What you should see immediately

- Terrain / village streets
- Player character near the quiet factory
- Mara (authoritative Python person id)
- Factory door labeled quiet/working from Python shortage state
- Live workers/carriers on real production connections (WorkerController)
- Ridge manifestation (demon cube)
- Sluice works entrance
- Interaction labels + keyboard / mouse-hold / touch movement
- Game Time advancing while unpaused (industry progresses)

## What to play

1. Launch without reading optional hints.
2. Confirm carriers move when production is active; mouse click/hold steers John on empty ground.
3. Walk to Mara; observe / talk. Infer why work stopped (no debug causal dump).
4. On one save, challenge the ridge manifestation (retained GameBoard duel). Confirm factory resumes via real industry rates and Mara acknowledges Route A; demon is gone.
5. On a fresh save, enter the sluice works; pick up the handle; push the box; place handle; open gate/actuator. Confirm Route B dialogue does **not** claim the demon was cleared.
6. Drop/recover the handle; save/reload; re-enter village — entity IDs / pose must stay stable.
7. Optional: world-resolved / destroyed-target scenario snapshots under `scenarios/`.

## Automated evidence (necessary, not decisive)

```bash
python3 tools/check.py --gate G05
```

Includes `run_g05_playable.gd` and **`run_g05_cumulative.gd`** (game_ms, IndustryService
blockage/restore, carriers, SyncPose, pause freeze, Route A/B solutions). G01–G04
regression smokes are also mandatory on this gate.

Agents cannot self-PASS the experience question. Only Joe's explicit  
`G05 PASS — <commit>` clears this gate.

## Same presentation path

- `tools/play_g05.sh` → `g05_shell.tscn` (Python + Overworld + ClockDriver)
- Village Test Menu → **FX-VILLAGE (Python-backed)** → same shell

## Experience question

Would you want to meet these people and solve another such problem?
