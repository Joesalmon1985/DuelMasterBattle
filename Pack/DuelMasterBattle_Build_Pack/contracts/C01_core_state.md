# C01 — Core objects and state contracts

Source: GDD §§9, 41–44, 187–196. Logical Python package: `sim/dmb/`. Use ordinary typed records and services; do not introduce an ECS framework or one subclass per content definition.

## Common value types

`EntityId`, `DefinitionId`, `CommandId`, `EffectId`, `CauseId`, `LeaseId`, `TransitionId` and `EventId` are distinct validated string types. Definition IDs are stable lower-case dotted identifiers. Instance IDs are `kind:creation_sequence` scoped by a saved `world_id`; creation sequence is monotonic and persisted. Include world_id whenever an ID leaves its save/session. Never derive identity from array position, display name or current era. Deleted IDs are not reused.

Wire integers must fit the exact JSON integer range ±(2^53−1); larger sequence/counter values use canonical decimal strings. Internal Python integers remain unbounded. Economic fixed-point values use a scale of 1,000,000, with exact rational carry where a division produces a fraction. Wire rational carry is `{numerator: decimal_string, denominator: decimal_string}` in reduced form. Times are integer milliseconds. Local positions use integer 1/256 tile units for snapshots. Display calculations may use floats; canonical ledgers may not.

Every record has `id`, `record_version`, `created_cycle`, `created_era`, `status`; relevant records add ownership, location and definition IDs. Optional references use null, never an empty ID. Enums have one canonical spelling. Tombstones retain kind, last location/owner, retirement cause/time and display identity needed by live references.

## Core classes

| Class / logical file | Owns | Public contract | Forbidden responsibility |
|---|---|---|---|
| `WorldState` / `core/state.py` | Registries below, clock, manifest and receipts | `read_view(scope) -> immutable view`; `validate() -> violations` | Running strategy or rendering |
| `WorldSim` / `core/world.py` | Service composition and ordered dispatch | `dispatch(CommandEnvelope) -> CommandResult`; `advance(GameAdvance) -> Result`; `snapshot() -> SaveEnvelope` | Implementing economic/combat formulas itself |
| `IdAllocator` / `core/ids.py` | Next instance/event sequences | `new(kind) -> EntityId` | Random names or save I/O |
| `RngBank` / `core/rng.py` | Named versioned stream states | `draw_int(stream, low, high)`; `shuffle(stream, ids)` | Ambient sprite variation |
| `TransactionCoordinator` / `core/transaction.py` | Mutation barrier and provisional write set | `begin(cause)`, `apply(validated_change)`, `commit()`, `abort()` | Business legality |
| `CommandRouter` / `core/commands.py` | Handler map and receipts | `validate_envelope`, `route`, `prior_receipt` | Trusting client state patches |
| `EventJournal` / `core/events.py` | Ordered immutable event records | `append_batch`, `since(sequence)` | Applying its own events twice |
| `EffectDispatcher` / `core/effects.py` | Typed effect routing and receipts | `prepare(effects, context) -> plan`; `commit(plan)` | eval/exec or arbitrary setters |
| `DefinitionCatalog` / `content/catalog.py` | Immutable versioned definitions | `load(manifest)`, `get(kind,id)`, `validate_all()` | Mutable inventory or identity |

Use a single simulation writer. Read views never expose mutable references. Workers calculate plans from immutable views; only the coordinator commits. An event is a fact after commit, not an invitation for an event subscriber to repeat the same mutation. Cross-system consequences are queued in deterministic order by the orchestrator and drained before the next external command.

## WorldState registry contract

| Registry | Required state beyond the common fields | Sole service writer |
|---|---|---|
| `clock` | game_ms, residual_ms, turn, round, scheduled_faction_ids, completed_seats, active_faction_id, pause_tokens | ClockService |
| `era` | era_id, cycle, started_turn, started_faction_ids, mandatory_split_ids, transition_id, next_future_path | EraService |
| `board` | axial hexes, shared nodes, edges, adjacency, immutable terrain/token, layout seed | BoardBuilder at setup; never regenerated on visits |
| `factions` | name, culture_id, lineage, status, policy_id/version, research, commitments, entry_strength, public diplomacy | FactionService / named subservices |
| `settlements` | node_id, faction_id, centre_id, warehouse_id, era_id, city flag, primary/factory slots, active/scoring status | ConstructionService |
| `buildings` | definition_id, settlement_id, position/footprint, health, max_health, source/route bindings, job_ids | BuildingService |
| `stores` | node_id, spendable/reserved/escrow quantities by Catan good, reservation IDs | StockLedger |
| `layers` | hex_id, cycle, era, finite_resource_id, balance and carry | IndustryService |
| `factory_meters` | building_id, unit_def_id, route_id, fraction/carry, allocated_rate, reason codes | IndustryService |
| `carts` / `trades` | See C05; one physical location per cargo lot | LogisticsService |
| `people` / `jobs` | name, role, affiliation, workplace, location, relationship map, knowledge, dialogue profile, alive/displaced, job status | PeopleService |
| `units` / `formations` | definition, home, faction, node, health, shields, buffs, position, cooldown; unit-ID membership and order | MilitaryService except leased live fields |
| `hazards` | typed cube IDs per hex, cause IDs, deck/discard, era/total outbreaks, placement ordinal | CatastropheService |
| `player` | node/area/position, inventory refs, focus/artifact, colours/slots, seven Aspects, friendly fallback, visit ledgers | PlayerService and typed effects |
| `knowledge` | observer, entity/fact IDs, evidence/version/time, confidence/testimony status | KnowledgeService |
| `quests` | template/version, bindings, cause, state, stage, branch, deadlines, applied effects | QuestService |
| `items` | definition, unique/fungible quantity, owner/container or ground area/position, quest bindings | InventoryService |
| `areas` / `puzzles` | projection seed, persistent anchors/overrides, mechanism state and protected object placement | ProjectionService / encounter checkpoint |
| `leases` | owner, kind, entities, version, checkpoint, command barrier and time | EncounterRegistry |
| `history` | event summaries, referenced tombstones, lineage, scars and cycles | HistoryService |

Subservice writers are exclusive by field, not a licence for two systems to overwrite entire records. `FactionService` owns membership; `DiplomacyService` relations; `TechnologyService` research; `PolicyService` commitments. Construction requests BuildingService operations inside the same transaction. Active encounter fields are defined in C02.

## Definition common schema

Every definition has `id`, `schema_version`, `kind`, `era_id` or `all`, `name_key`, `description_key`, `asset_family_id`, and typed `tags`. Store costs/effects/rates in explicit fields rather than prose. Catalog version is a hash of canonical definition payloads plus referenced asset/content hashes. A save requires compatible manifests, not just matching game executable versions.

Concrete resource and recipe reference rows are included in `reference/resources.json` and `reference/recipes.json`. Building definitions add kind, footprint, max health, costs, primary/factory slot type, upgrade mapping, input/output IDs and rate caps. Unit definitions add the C07 stats. Quest/dialogue and technology fields are defined in C10/C12. Type records with no applicable field omit it rather than inventing values.

## Mutation and error contract

Handlers validate all references, permissions, clocks and costs before writing. An invalid command returns `REJECTED` with a stable code and public explanation; no RNG, identity, time or stock mutation. A duplicate valid command returns its recorded result, including original events. A command with the same ID and different payload is `ID_REUSE`. Unexpected internal error aborts the transaction, pauses play, writes a diagnostic and retains the last checkpoint.

Terminal loss and era transition are successful interrupts, not exceptions that roll back the winning/loss-causing action. The orchestrator drains their required consequences and cancels remaining old-era work. `Result` includes `status`, `code`, `world_version`, `events`, `interrupt` and `public_feedback`.

## Behavioural verification

Independent tests assert IDs never repeat after save/load; insertion-order changes cannot change a seeded result; failed commands preserve hash/RNG/next ID; committed mutations occur once; unknown IDs are rejected; save snapshots contain all mutable registries; read views cannot mutate state; ambient animations consume no world RNG. Domain tests live with their owning service and verify outcomes, not private method calls.

The typed event/payload registry and concrete revalidation examples are in [interface_events.md](../reference/interface_events.md). Read it when implementing an event producer or cross-system consumer.
