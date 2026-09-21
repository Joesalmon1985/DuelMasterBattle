# Ontology implementation report

**Branch:** `refactor/canonical-ontology-g05`  
**Starting commit (G05 tip + review docs):** `3124555a521d77e875d974710ef2dffa9b3c9758`  
**Parent G05 preserve commit:** `c8acb8f`  
**Baseline before dirty work:** `ff23066`

## Decisions implemented

See Joe rulings encoded in [`docs/CANONICAL_GAME_ONTOLOGY.md`](../CANONICAL_GAME_ONTOLOGY.md) and updated [`JOE_DESIGN_DECISIONS.md`](JOE_DESIGN_DECISIONS.md).

| ID | Decision |
|---|---|
| D01 | Every human individual is a Person (incl. soldiers) |
| D02 | UnitState retains combat fields; requires `person_id` |
| D03 | Unit death ⇒ Person death; demobilisation allowed later |
| D04 | NPC = shorthand only |
| D05 | All living Persons Observe + Talk |
| D06–D07 | Roles/composition; occupation ≠ activity |
| — | No presentation-created Persons; carts ≠ people; layered building knowledge |

## CONCEPT | OLD | NEW | STATUS

| CONCEPT | OLD REPRESENTATION | NEW CANONICAL REPRESENTATION | STATUS |
|---|---|---|---|
| Person | `state.people` | same + may have Combatant | in progress |
| worker | Person + job | Person + Employment; activity separate | in progress |
| carrier | presentation_only Person via sync_carrier_jobs | activity on real employees; no invented Persons | pending |
| leader | profile flag | LeadershipRole on Person | done (affirm) |
| soldier | Unit only + `person_name` | Unit + `person_id` → Person | pending |
| formation | unit ID set | unchanged | keep |
| building | Building entity | Building + industry processes | clarify docs/UI |
| processor | industry binding | process on Building | docs |
| factory | building + meter | same | docs |
| cart | cart:* (+ person:cart journeys) | cart:* only | pending purge |
| quest participant | Person binding | Person + QuestBindings | keep |
| hazard | cube:* | unchanged | keep |
| local area | projection | lazy persist on first visit | keep/harden |
| fixture | specialised loaders | setup profiles of one runtime | audit |

## Schema changes

- Save schema: plan bump `1` → `2` with unit↔person migration (pending code).

## Remaining deliberate debt

- Full soft-contiguous art between nodes (presentation polish).
- Civilian consumption economy for processed goods (later).
- Champion / hero kinds deferred (Vehicle = Cart).

## Fixture-only semantics (to eliminate)

Tracked during consolidation; update as removed.
