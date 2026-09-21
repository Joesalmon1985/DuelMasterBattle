# G01–G04 → Full-world G05 visual audit

**Branch:** `refactor/canonical-ontology-g05`  
**Foundation commit:** `85fca3c` (full Prehistoric 19/54/72 — preserved)  
**Pass:** Visual integration of accepted G01–G04 presentation into one Overworld

Do **not** rebuild topology. Do **not** restore the shortage quest. Do **not** start T097.

---

## Mechanic table

| mechanic | Python authority | old Godot presentation | current G05 (85fca3c) | reuse plan |
|---|---|---|---|---|
| World Turn / clock | `AdvanceGame` / `Pause` / `Resume` / `Wait`; `state.clock` | `ClockDriver` → shell `_pump_clock` | Same ClockDriver on G05; no player Turn HUD | Keep clock; add unobtrusive Turn / Game Time label; pause token already freezes driver |
| Travel | `Travel` + topology; turn +1 | G01 exits via `fx_clock_area` | Overworld exit entities → `travel_to_node` | Keep; brief destination toast with human name (no raw `node:29`) |
| Carts / cargo | `state.carts`, logistics journeys (`presentation.journeys`) | G02 `LocalMovementPresenter` + EconomyView | Static `deco` box labelled Cart | CartPresenter: faction colour, cargo pips, journey pose from journeys view |
| Construction orders | `state.orders` / construction status | G02 EconomyView status lines | Not shown | Project scaffold footprints / road outlines from real orders on current node/edge |
| Warehouse stocks | `state.stocks` | G02 Interact + EconomyView | Building observe text only | Inspect warehouse → Timber/Brick/Wool/Grain/Ore (distinct from industry) |
| Industry workers | `IndustryProjection.workers()` | G03 `WorkerController` | Mounted; no carry pip | Keep WorkerController; add carried-resource marker from projected connection |
| Processor / factory meters | `industry.processors` / `factories[].meter` | G03 Polygon2D sites + progress bars | Doors/signs only | IndustryOverlay: bar from Python meter; recipe Inspect from catalogue names |
| Produced units | `state.units` + `person_id` | G03 spawn markers; G04 UnitController | Static NPC-like entities | Geometric UnitPresenter (△■●) by archetype + faction; battle lease uses UnitController |
| Local battle | Battle lease commands | `LocalBattle` + `UnitController` + `EncounterHost` | Not mounted | Host under Overworld when live battle on player node; Travel closes lease |
| Soldier targeting | Observe / CastBuff / CastDestroy | `TargetSession` + AttachedChoiceCard | NPC talk only | Reuse TargetSession for combatants (Person social / Unit combat) |
| Buffs | `CastBuff` lease poses | LocalBattle optimistic markers | Absent | Ring/chevron/range markers while buffs exist in authority |
| Catastrophe cubes | `hazards.catastrophe.cubes` (WorldSetup already creates them) | G04 `HazardActor` diamonds | Not exported to Overworld | Export one `cube_id` entity; HazardActor / geometric diamond; map marker same ID |
| Hazard Challenge / duel | `StartHazardDuel` / `ResolveHazardDuel` | `DuelLeaseAdapter` + `game_board` | Adapter mounted; no cube to Challenge | Keep adapter; wire Challenge from hazard entity; quest demon helpers quarantine |

---

## Reusable files

| Path | Role |
|---|---|
| `client/core/clock_driver.gd` | Game Time pending AdvanceGame |
| `client/world/local_movement_presenter.gd` | Cart journey interpolation |
| `client/world/worker_controller.gd` | Industry worker actors (already on G05) |
| `client/world/hazard_actor.gd` | Diamond hazard manifestation |
| `client/combat/local_battle.gd` | Leased battle sim |
| `client/combat/unit_controller.gd` | Polygon unit + HP bar |
| `client/encounters/encounter_host.gd` | Lease versioning |
| `client/encounters/duel_lease_adapter.gd` | Retained duel board (already on G05) |
| `client/ui/target_session.gd` | Soldier/hazard targeting |
| `client/debug/economy_view.gd` / `industry_view.gd` | Dev-layer stock/meter text |
| `client/scenes/g03_shell.gd` | Polygon site + factory progress patterns to lift |
| `sim/dmb/presentation/journeys.py` | Authoritative journey dicts |
| `sim/dmb/industry/projection.py` | Workers / connections / factory readout |

---

## Known gaps verified at 85fca3c

1. No Turn / Game Time player chrome on G05.
2. Carts are static boxes; no cargo pips / journey.
3. Construction orders not projected.
4. Factory meters / recipe Inspect absent from LocalArea.
5. Catastrophe cubes exist in Python but not in `overworld_export`.
6. Local battle stack not hosted by G05 Overworld.
7. Military units look like generic NPCs.
8. `g05_shell.gd` still carries quest-named helpers (`resolve_demon_success`, sluice).

---

## Non-goals

- New topology / LocalArea size contract
- Active quest / Route A–B
- Separate G01–G04 production scenes
- Era transition (T097)
