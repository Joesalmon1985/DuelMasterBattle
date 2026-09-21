# G05 — Fully explorable Prehistoric world

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Play fixture:** `FX-VILLAGE` — full Prehistoric board, **no active quest**  
**Archived quest fixture:** `FX-VILLAGE-QUEST` (prototype shortage / demon / sluice)  
**Branch:** `refactor/canonical-ontology-g05`  
**Launch:** `bash tools/play_g05.sh`  
**Seed:** **507**

## Human acceptance

> Starting inside a real settlement, I can walk out and explore the entire
> generated board. Every strategic node becomes a same-sized, persistent local
> area whose geography and population reflect the real board state.

## Starting placement

| Field | Value |
|-------|-------|
| Start node | `node:35` |
| Settlement | `settlement:3` — Settlement 2-1 (faction:2) |
| Board | 19 hexes / 54 nodes / 72 edges |
| LocalArea | **48 × 48** for every ordinary strategic node |

Other core settlements (visit these):

| Settlement | Node | Faction |
|------------|------|---------|
| Settlement 1-1 | `node:2` | faction:1 |
| Settlement 1-2 | `node:12` | faction:1 |
| Settlement 2-2 | `node:27` | faction:2 |

Constructed roads (seed 507): `node:2↔5`, `node:12↔17`, `node:35↔29`, `node:27↔21`.

## LocalArea generation rules

1. **One projector:** `LocalProjectionService.project_node(node_id)` / `export_overworld_area`.
2. **Derived kind** (presentation only): settlement/city if active settlement on node; else wilderness with road or trail approaches from incident edges.
3. **Geography:** touching hex terrains stamp perimeter sectors from real board geometry; deterministic from `world seed + node_id`.
4. **Persisted:** layout stored in world state after first generation; dynamic people/carts/units rebound on revisit.
5. **Exits:** every `board.adjacent_nodes` neighbour → one reachable exit; passage=`road` iff authoritative road edge, else `trail`.
6. **Settlements:** same path places centre / warehouse / processors / factories / primaries (primaries toward relevant terrain edge).

## What you should verify

1. Walk the starting settlement — civic middle, resource edges that match terrain.
2. Leave on a path; wilderness nodes show geography, not blank grass + labels.
3. Follow a constructed road vs ordinary trail (visually distinct).
4. Enter another settlement; real faction buildings and workers.
5. Return by a different route; home layout persists.
6. No demon, sluice entrance, factory-shortage Mara, or Route A/B UI.

## Automated

```bash
python3 -m pytest tests/sim/test_g05_full_world.py tests/sim/test_village_foundation.py -q
python3 tools/check.py --gate G05   # includes G01–G04 regressions
bash tools/play_g05.sh
```

Agents cannot self-PASS G05.

## Archived prototype quest

Shortage / demon / sluice material is **not** part of this gate. See
`optional_hints.md` (archived) and fixture `FX-VILLAGE-QUEST` if needed later.
