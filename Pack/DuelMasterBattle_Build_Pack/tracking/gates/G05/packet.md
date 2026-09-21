# G05 — Coherent Prehistoric living-world slice (canonical ontology)

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06 until Joe PASSes G05  
**Scenario:** FX-VILLAGE (setup profile for the normal production runtime)  
**Branch:** `refactor/canonical-ontology-g05`  
**Launch:** `bash tools/play_g05.sh`  
**Deterministic board seed:** **507**

## Ontology baseline

Read [`docs/CANONICAL_GAME_ONTOLOGY.md`](../../../../../docs/CANONICAL_GAME_ONTOLOGY.md) first.  
Implementation notes: [`docs/review/ONTOLOGY_IMPLEMENTATION_REPORT.md`](../../../../../docs/review/ONTOLOGY_IMPLEMENTATION_REPORT.md).

This return is the first G05 candidate built on the consolidated ontology (Person-linked units, no presentation-minted People, one Person → one actor, buildings as entities / industry as process).

## Generated world slice

| Field | Value |
|-------|-------|
| Board seed | 507 |
| Topology | 19 hexes / 54 nodes / 72 edges |
| Selected node | `node:35` |
| Settlement | `settlement:3` |
| Faction | `faction:2` |
| Adjacent travel | real topology exits (e.g. `node:29` / `node:30` / `node:40`) |
| Shortage factory | `building:26` |
| Working factory | `building:25` |
| Mara | `person:9` (seed 507) |

## What this slice must demonstrate

| Layer | Expectation |
|-------|-------------|
| WORLD | Real generated board; World Turns + Game Time |
| PEOPLE | Persistent workers + Mara; one ID per Person; Observe/Talk; occupational labels |
| ECONOMY | Catan warehouse + carts + primary extraction + processors + military factory; working vs blocked |
| BUILDINGS | Player-safe Observe/Inspect; layered knowledge; no raw processor/route IDs |
| EXPLORATION | Walk to path → Travel adjacent node → return; IDs stable |
| QUEST | Shortage from real sim; demon/sluice routes change real state; production resumes |
| DUNGEON/DUEL | Retained leased systems; one world before/after |

## UX / ontology repair (this return)

- Workers are real `job:site_worker` Persons; projection may tag activity `role=carrier` for presenters — **not** a Person species.
- `WorkerController` updates registered Person actors (shared `WorldInteractionLabel`); does not mint People.
- Military `UnitState.person_id` linkage + save schema 2 migration (G04 regressions green).
- Buildings use `IndustryProjection.player_building_observation` (distant / nearby / inspect).
- Topology Travel advances exactly one World Turn.

## What you should verify manually

1. You feel you are in **one settlement in a living world**, not a quest demo island.
2. Moving workers: normal-sized sprites, occupational labels that follow them, clickable Observe/Talk.
3. Buildings: non-empty labels; quiet vs working factory readable without debug IDs.
4. Paths lead to real adjacent places; travel out and return; Mara/factory IDs unchanged.
5. Shortage quest still solvable (demon duel / sluice); production visibly resumes.
6. Optional: if any soldier is visible, Talk/Observe treats them as a Person.

## Automated evidence

```bash
python3 tools/check.py --gate G05 --json-report Pack/DuelMasterBattle_Build_Pack/tracking/gates/G05/check_report.json
```

Latest report: **PASS** (G05 cumulative + G01–G04 regressions).  
Capture: `play_inspect.png` (agent viewport sanity).

Agents cannot self-PASS. Only Joe's explicit `G05 PASS — <commit>` clears this gate.

## Architecture

- [`docs/CANONICAL_GAME_ONTOLOGY.md`](../../../../../docs/CANONICAL_GAME_ONTOLOGY.md)
- [`docs/INTEGRATED_RUNTIME_ARCHITECTURE.md`](../../../../../docs/INTEGRATED_RUNTIME_ARCHITECTURE.md)
