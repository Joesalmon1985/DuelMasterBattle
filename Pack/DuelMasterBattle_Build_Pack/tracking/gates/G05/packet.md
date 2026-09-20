# G05 — Procedural village / quest / duel playtest

**Status:** AWAITING_HUMAN  
**Stop point:** T096  
**Scenario:** FX-VILLAGE  
**Branch:** `feature/g05-village-quest`  
**Launch:** `bash tools/play_g05.sh`  
**Deterministic board seed:** **507**

## Generated world slice (not a mini-game)

| Field | Value |
|-------|-------|
| Board seed | 507 |
| Topology | 19 hexes / 54 nodes / 72 edges |
| Selected node | `node:35` |
| Settlement | `settlement:3` |
| Faction | `faction:2` |
| Touching terrains | woodland, ore_mountains, clay_mountains |
| Wood hex | `hex:1,0` |
| Demon / ore hex | `hex:1,1` |
| Clay hex | `hex:0,1` |
| Primary woodland | `building:21` |
| Primary ore | `building:22` |
| Primary clay | `building:23` |
| Working processor | `building:24` (Clay works) |
| Shortage Route A processor | `building:37` (Ridge works) |
| Route B processor | `building:38` (Sluice works) |
| Working factory | `building:25` (Muster factory) |
| Shortage factory | `building:26` (Village factory) |
| Mara | `person:10` |

FX-VILLAGE uses `BoardBuilder.generate` + `WorldSetupService`, then binds IndustryService
channels to the settlement’s real touching hexes. A working wood+clay factory runs
while the shortage wood+ore route waits under the demon; sluice enables the alternate
processor for the shortage factory.

## What you should see

- One settlement in a larger simulated world
- Existing character sprites (no orange debug people)
- No duplicate workers (one person ID → one actor)
- Live carriers on the working chain; waiting carriers on the blocked chain
- Real buildings from settlement state
- Game Time / mouse-hold / SyncPose / retained duel preserved

## Automated evidence

```bash
python3 tools/check.py --gate G05 --json-report Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05/check_report.json
```

Includes world-integrity + one-actor-per-person + live-economy proofs in
`run_g05_cumulative.gd`, plus G01–G04 regressions. Latest report: **PASS**.

Agents cannot self-PASS. Only Joe's explicit `G05 PASS — <commit>` clears this gate.

## Architecture

See `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md`.

## Experience question

Would you want to meet these people and solve another such problem?
