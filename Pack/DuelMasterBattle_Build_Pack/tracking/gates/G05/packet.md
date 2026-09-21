# G05 — Procedural village / quest / duel playtest

**Status:** AWAITING_HUMAN  
**Stop point:** T096  
**Scenario:** FX-VILLAGE  
**Branch:** `feature/g05-village-quest`  
**Launch:** `bash tools/play_g05.sh`  
**Deterministic board seed:** **507**

## Generated world slice

| Field | Value |
|-------|-------|
| Board seed | 507 |
| Topology | 19 hexes / 54 nodes / 72 edges |
| Selected node | `node:35` |
| Settlement | `settlement:3` |
| Faction | `faction:2` |
| Adjacent travel | `node:29` / `node:30` / `node:40` (real topology) |
| Shortage factory | `building:26` |
| Working factory | `building:25` |
| Mara | `person:10` |

## UX interaction repair (this return)

- Industry workers use Overworld `TILE_SCALE` (4) and register into the shared
  `WorldInteractionLabel` system (one person ID → one actor → movement + Observe/Talk).
- Occupational standing labels (`Woodcutter`, `Miner`, `Carrier`, …) from job/sprite.
- Buildings expose player-safe Observe/Inspect text from `IndustryProjection.player_building_observation`
  (G03 building_focus filtered for play).
- Local exits map to real adjacent nodes; `Travel` advances World Turn once and returns without reroll.

## What you should verify

- Workers look like normal-sized people with following labels
- Click moving workers → useful observation; nearby → Talk
- Buildings explain purpose/state (quiet factory vs muster)
- Paths leave the settlement; travel out and return
- Quest routes (demon / sluice) still work

## Automated evidence

```bash
python3 tools/check.py --gate G05 --json-report Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05/check_report.json
```

Latest report: **PASS** (includes pointer/semantic + topology travel cumulative proofs).

Agents cannot self-PASS. Only Joe's explicit `G05 PASS — <commit>` clears this gate.

## Architecture

See `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md`.
