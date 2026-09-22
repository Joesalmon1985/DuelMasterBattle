# ENTITY → PRESENTATION CONTRACT

Proposed contract for visible canonical entities.  
**Not implemented by this review.** Aligns with `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md` and extends it.

Pipeline for every interactive visible thing:

```text
Python identity  →  projection / view  →  Godot actor  →  semantic label  →  allowed verbs
```

---

## 1. Hard invariants

1. **One durable ID → at most one local actor** in a loaded LocalArea.  
2. **Animated workers remain the same semantic people** (`person_id` stable across job cues).  
3. **Changing job changes behaviour, not identity.**  
4. **Presentation-only motion cannot alter simulation truth** (throughput, cargo, combat).  
5. **A visible interactive entity must have a useful semantic view** (knowledge-filtered).  
6. **No fixture invents an alternate type** of worker / building / soldier.  
7. **Local unload / reload / Travel never silently changes durable identity.**  
8. **Raw registry IDs are not ordinary player text.**  
9. **Static Overworld export and WorkerController must not both present the same `person_id`.**  
10. **If Model B is adopted:** every visible soldier actor binds `unit_id` *and* resolves `person_id` for social verbs as decided in D03.

---

## 2. Per-entity contract

### Person (`person:*`)

| Stage | Owner / artefact |
|---|---|
| Python | `state.people` / PeopleService |
| Projection | LocalProjection anchors; IndustryProjection.workers when employed; knowledge filter |
| Godot actor | Either static Overworld human **or** WorkerController ActorVisual — never both |
| Semantic label | Name / occupation progression via SemanticResolver |
| Verbs | Observe, Talk (baseline); Destroy if ordinary target; quest choices when bound |

### Unit / Soldier (`unit:*`)

| Stage | Owner / artefact |
|---|---|
| Python | `state.units` / MilitaryService |
| Projection | LocalProjection unit anchors; battle lease poses |
| Godot actor | Battle/overworld soldier sprite keyed by `unit_id` |
| Semantic label | Knowledge-filtered archetype/faction/name (`person_name` interim) |
| Verbs today | Observe, Buff…, Destroy (not Talk) |
| Verbs if D03 expands | Talk / limited banter via linked Person |

### Building (`building:*`)

| Stage | Owner / artefact |
|---|---|
| Python | BuildingService + optional industry bindings |
| Projection | LocalProjection building footprints; IndustryProjection sites |
| Godot actor | Structure node / tiles |
| Semantic label | Public building name + player-safe observation (D05) |
| Verbs | Observe / Inspect; Destroy when allowed |

### Cart (`cart:*`)

| Stage | Owner / artefact |
|---|---|
| Python | CartService / stocks lots |
| Projection | Journey presenter / local anchors |
| Godot actor | Cart sprite (cargo cues) |
| Semantic label | Cart / goods (knowledge-filtered) |
| Verbs | Observe; Destroy (cargo loss rules) |

### Hazard (`cube:*`)

| Stage | Owner / artefact |
|---|---|
| Python | CatastropheService |
| Projection | Hex/local markers |
| Godot actor | Hazard FX / demon actor |
| Semantic label | Typed danger name |
| Verbs | Observe; Challenge / treat per catastrophe rules |

### Item (`item:*`)

| Stage | Owner / artefact |
|---|---|
| Python | InventoryService |
| Projection | Ground entity or inventory UI |
| Godot actor | Pickup / pockets |
| Semantic label | Item name |
| Verbs | Take / Examine / Use as defined |

### Entrance / Exit

| Stage | Owner / artefact |
|---|---|
| Python | `board.nodes[*].exits` + Travel command |
| Projection | Local exit markers with arrival poses |
| Godot actor | Door / path trigger |
| Semantic label | Destination place name |
| Verbs | Travel (after acknowledged exit) |

### Formation

| Stage | Owner / artefact |
|---|---|
| Python | `formations` |
| Projection | Group label over member units |
| Godot actor | No separate human; optional group chrome |
| Semantic label | Group inspect |
| Verbs | Inspect members; **not** mass Destroy |

### Player / Wizard

| Stage | Owner / artefact |
|---|---|
| Python | `state.player` + SyncPose |
| Projection | — |
| Godot actor | John / wizard ActorVisual |
| Semantic | N/A (actor is subject) |
| Verbs | Move, Wait, Travel, cast, talk, inventory |

---

## 3. Projection responsibilities (justified set)

| Projector | Responsibility | Not responsible for |
|---|---|---|
| `LocalProjectionService` | Durable anchors / layout for a node | Inventing people; industry rates |
| `IndustryProjection` | Worker cues, connections, player-safe building observations | Authoritative throughput writes |
| `WorldState.read_view` | Immutable scoped snapshots | Mutating state |
| `SemanticResolver` | Labels, inspect, available actions | Spawning actors |
| `overworld_export` | Bridge/Overworld area dict for FX-VILLAGE / playable export | Second simulation |
| `presentation/journeys` | Cart/person journey presentation helpers | Logistics authority |
| Godot `WorkerController` | Animate projected carrier rows | Production commands |
| Godot Overworld | Spawn actors, input, camera | Durable identity |

**Smell to eliminate:** any path that creates a human actor without a durable Python ID, or a semantic target without an actor when the entity is claimed visible/interactive.

### Observed wiring failures (implementation / presentation — not new ontology)

These were confirmed in the presentation audit of the current checkout. They do **not** invent new entity kinds, but they violate the contract above and can look like “ontology bugs” in play:

1. **`register_dynamic_person` may keep `pos: [0,0]`** while the WorkerController actor moves — semantic range/Action-facing disconnect from the visible person (`overworld.gd`).
2. **`bridge_talk` / `bridge_challenge` flags can fail to reach** `_interact_bridge_npc` / Challenge when `_perform_entity_action` short-circuits on `bridge_entity`.
3. **`_finish_village_build` may `queue_free` WorkerController** if it lives under `_actors_root`, dropping carriers after Travel/reproject (`overworld.gd` + `g05_shell.gd`).
4. **Building inspect is often a door prop**, not a building-sized actor — acceptable if semantic ID remains `building:*`, dangerous if prompts say only “Door”.
5. **Cart journeys must not require a fake `person:cart` identity** in production village; logistics identity is `cart:*`.

Classify (1)–(3) as ordinary presentation/implementation bugs for G05 repair; (4)–(5) as contract clarity (D05 / D09 / D19).

---

## 4. Fixture rule

Fixtures may:

- choose seed, faction count, which node is focal;  
- place authored hazards/quests using normal services;  
- pause or schedule for demos.

Fixtures must not:

- introduce `kind` values that do not exist in production;  
- create workers that are not Persons;  
- create soldiers that are not Units (and, if Model B, unbound to Persons);  
- run a second quest engine or clock.

---

## 5. G05 acceptance relevance

Before treating G05 as ontology-complete, verify:

- Mara / factory worker: one actor, Talk works, same ID after Travel/save;  
- Buildings: readable observations without connection IDs;  
- Exits: real topology Travel;  
- No duplicate industry + static NPC for same person;  
- Demon / sluice solutions mutate industry/hazard truth, not only quest text.

Classification of current G05 issues belongs in [ROADMAP_RECONCILIATION.md](ROADMAP_RECONCILIATION.md) §G05.
