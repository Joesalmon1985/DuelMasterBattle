# G05 FIX_REQUIRED → AWAITING_HUMAN

**Status:** AWAITING_HUMAN after UX interaction repair

## Audit

| Item | Result |
|------|--------|
| Worker scale | `TILE_SCALE = 4` (matches Overworld) |
| Worker semantics | `register_dynamic_person` → shared `WorldInteractionLabel` |
| Occupational labels | `public_role` from job/sprite (not connection IDs) |
| Building Observe/Inspect | `IndustryProjection.player_building_observation` |
| Bridge bind | `_attach_semantic_label` uses `bind_bridge` in bridge mode |
| Topology Travel | `wire_topology_travel` + G01 `Travel` round-trip |
| Cumulative proofs | worker label/talk, building observations, travel turn+1 |
| Manual play_g05 | Launched; workers labelled; buildings readable |

Do not expose `person:` / `building:` / connection IDs in ordinary labels.
