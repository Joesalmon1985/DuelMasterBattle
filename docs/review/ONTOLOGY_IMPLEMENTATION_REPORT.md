# Ontology implementation report

**Branch:** `refactor/canonical-ontology-g05`  
**Starting commit (G05 tip + review docs):** `3124555a521d77e875d974710ef2dffa9b3c9758`  
**Parent G05 preserve commit:** `c8acb8f`  
**Baseline before dirty work:** `ff23066`  
**Docs commit:** `f1d94cb`  
**Schema/migration commit:** `d7e8293`  
**Godot one-actor commit:** `5b3b19e`  
**Current tip:** `fe2a62030ac1aaa0e42a51efb37f052744780d15`

## Decisions implemented

See [`docs/CANONICAL_GAME_ONTOLOGY.md`](../CANONICAL_GAME_ONTOLOGY.md).

| ID | Decision | Status |
|---|---|---|
| D01 | Soldiers are Persons | done |
| D02 | UnitState + `person_id` | done |
| D03 | Unit death ⇒ Person death | done |
| D04 | NPC = shorthand only | docs |
| D05 | Observe + Talk for living Persons | done (Talk via person or unit→person) |
| D06–D07 | Occupation ≠ activity | done |
| D09–D10 | Fixtures=setup; one actor | done for G05 workers |
| D16 | No presentation-created People | done (`job:site_worker`) |
| D19 | Carts = `cart:*` only | docs; journey purge deferred |

## CONCEPT | OLD | NEW | STATUS

| CONCEPT | OLD REPRESENTATION | NEW CANONICAL REPRESENTATION | STATUS |
|---|---|---|---|
| Person | `state.people` | same + optional `unit_id` | done |
| worker | Person + job | Person + Employment; activity separate | done |
| carrier | presentation_only Person | activity on employed site workers; projection may tag `role=carrier` | done |
| leader | profile flag | LeadershipRole on Person | affirmed |
| soldier | Unit + `person_name` | Unit + `person_id` → Person | done |
| formation | unit ID set | unchanged | keep |
| building | Building entity | Building + industry processes | done (player observations) |
| processor | industry binding | process on Building | docs |
| factory | building + meter | same | docs |
| cart | cart:* (+ person:cart journeys) | cart:* only | debt: G01 journeys |
| quest participant | Person binding | Person + QuestBindings | keep |
| hazard | cube:* | unchanged | keep |
| local area | projection | lazy persist | keep |
| fixture | specialised loaders | setup profiles | audit ongoing |

## Schema changes

- Save schema **1 → 2** (`sim/dmb/persistence/migrate.py`)
- Living units require `person_id`; migration creates Persons for legacy units
- Idempotent; covered by `tests/sim/test_canonical_ontology.py`

## Systems retired / adapted

- `IndustryProjection.sync_carrier_jobs` no longer mints `job:carrier` presentation People
- Real `job:site_worker` employment drives carrying/waiting animation
- Projection `role=carrier` is an **activity tag for presenters/tests**, not Person identity
- Godot: `bridge_talk` / `bridge_challenge` routed; WorkerController `layout_diagnostic` restored for G03; dynamic person registry preserved on rebuild

## Remaining deliberate debt

- Soft-contiguous art between nodes
- Civilian consumption economy for processed goods
- Full purge of `person:cart` from G01/G02 journey demos
- Battle Overworld soldier actor fully sharing PersonPresenter (identity bridge exists; combat sprites still specialised)
- Some FX shells remain specialised setup UIs (semantics now production services)

## Tests / gates

- `tests/sim/test_canonical_ontology.py` + updated t019/t020/t021/t055/u05
- `python3 tools/check.py --gate G05` → **PASS** (includes G01–G04 regressions)
- Manual: `bash tools/play_g05.sh`; viewport capture `gates/G05/play_inspect.png`

## Documentation superseded

- [`PROPOSED_CANONICAL_ONTOLOGY.md`](PROPOSED_CANONICAL_ONTOLOGY.md) → superseded by `docs/CANONICAL_GAME_ONTOLOGY.md`
- Joe decision register marked accepted for consolidation
- Roadmap: ontology consolidation → revised G05 → **then** T097–T106 / G06 (not started)

## Stop condition

**G05 = AWAITING_HUMAN.** Do not mark PASS. Do not start T097.
