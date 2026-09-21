# G05 known defects / notes — ontology consolidation return

**Status:** AWAITING_HUMAN after canonical ontology consolidation

## Audit

| Item | Result |
|------|--------|
| Person identity | Workers + Mara are persistent Persons; no `job:carrier` mint |
| Occupation ≠ activity | e.g. Woodcutter + carrying; projection `role=carrier` is activity tag only |
| One actor | `register_dynamic_person` + WorkerController preserve |
| Building Observe/Inspect | `player_building_observation` — Clay pits / Clay works style labels |
| Topology Travel | real adjacent nodes; turn +1 |
| Unit↔Person | schema 2; G04 battle units linked |
| Gate check | `tools/check.py --gate G05` PASS |
| Manual capture | `play_inspect.png` refreshed |

## Deliberate limitations (not blockers for this return)

- Soft-contiguous countryside art between nodes is still discrete LocalArea loads.
- FX-VILLAGE seed 507 may have zero locally visible soldiers (linkage still enforced in G04 / spawn).
- Battle combat sprites remain specialised; identity bridge via `person_id`.
- G01/G02 cart journey demos may still mention legacy `person:cart` paths (debt).
- Civilian consumption of typed processed goods remains MVP-abstracted into military supply.

Do not expose `person:` / `building:` / connection IDs in ordinary labels.
