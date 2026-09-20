# Integrated runtime architecture

Authoritative short architecture for DuelMasterBattle after G01–G05.
Later gates **extend** this production runtime; they must not invent a second
implementation of a gameplay concept already accepted at an earlier gate.

## Hard rule

> Later gates extend the accepted production runtime. They must not create a
> second implementation of a gameplay concept already accepted at an earlier
> gate.

Fixtures may select or arrange deterministic initial state. They must not
implement parallel gameplay semantics, alternate clocks, alternate industry, or
shadow routes that IndustryService does not own.

## One world pipeline

```text
BoardBuilder / WorldSetupService  (topology, cores, buildings, carts, hazards)
        ↓
authoritative Python WorldState
        ↓
LocalProjectionService + IndustryProjection + domain views
        ↓
ONE Godot Overworld / presentation runtime
```

## Ownership

### Python owns

- board / topology (19 hexes, 54 nodes, 72 edges)
- factions and settlements
- buildings (centre, warehouse, primary, processor, factory, …)
- resources / stocks / ledgers
- industry (channels, processors, routes, factory meters, allocation)
- carts and logistics journeys
- people / jobs / dialogue profiles
- units / military identity
- hazards / catastrophe cubes
- quests / causes / knowledge
- inventory
- durable player pose
- clocks (`game_ms`, pause tokens, no catch-up)
- saves / loads

### Godot owns

- rendering and camera
- local grid movement and input routing
- local animation
- UI / semantic labels / dialogue presentation
- presentation of Python projections
- explicitly leased encounters (retained GameBoard duel, puzzle lease)

### Offline tools own

- content and dialogue generation only (never runtime authority)

## Identity invariants

| Concept | Rule |
|---|---|
| Person | ONE person ID = ONE person = ONE visible local actor |
| Building | ONE building ID = ONE real building |
| Factory | ONE factory = IndustryService factory / meter |
| Clock | ONE world clock |
| Player pose | ONE durable Python pose (Godot SyncPose coalesces local steps) |
| Quest | ONE quest state owner (Python QuestService) |

Static Overworld NPC export and `WorkerController` must never both present the
same `person_id`. Carriers / industry attendants are presented by
`WorkerController` using `ActorVisual` and existing character sprite families.
Quest stakeholders such as Mara remain Overworld dialogue actors when they are
not in the industry worker projection.

## FX-VILLAGE / G05

FX-VILLAGE is a deterministic seed (currently **507**) that:

1. generates a full two-faction board via `BoardBuilder.generate`;
2. applies `WorldSetupService` (real settlements, buildings, carts, roads);
3. selects a real core node whose touching hexes include woodland + ore
   (and clay when present);
4. binds primary channels to those real hexes;
5. runs a living working factory chain **and** a shortage factory chain;
6. places the demon cube on the real ore hex; sluice sabotage disables the
   legitimate alternate processor for the shortage factory.

The local 48×48 village is a projection of that strategic node — not a second
board and not invented terrain.

## Cumulative gates

G02 cargo, G03 industry, G04 hazards/duels, and G05 village/quest all share this
runtime. A later gate that needs workers, carts, factories, or demons must reuse
these systems rather than assemble a miniature special-purpose game.
