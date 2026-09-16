# Commands, effects and event payloads

Use with C01/C02. These are proposed schema contracts, not implemented endpoints. Commands express intent, effects express validated cross-system mutations, and events record committed facts. A scene consumes events to refresh its projection; it must not reapply the mutation named by an event.

## Common envelopes

Command envelope fields: protocol_version, session_id, world_id, command_id, expected_world_version, kind, payload. Encounter messages additionally include lease_id/version, sequence and base_checkpoint_hash. C02 defines framing/authentication and full player command kinds.

Event envelope fields: event_id, world_id, world_version, event_sequence, caused_by_command_id or caused_by_event_id, game_ms, world_turn, world_round, era, cycle, kind, payload, visibility_policy. Store canonical full payload internally; derive observer-filtered payloads before sending to player UI. Visibility policy is a typed rule ID, not an LLM judgement.

Effect envelope fields: effect_id, owning_service, kind, target refs, typed arguments, preconditions, duration_clock/expiry where applicable, origin quest/choice/encounter, expected target versions and exception_definition_id when the source explicitly permits an exceptional outcome. Effect batches validate together and commit atomically. Unknown effect kinds cannot fall back to arbitrary writes.

## Event contract registry

| Kind | Minimum payload | Emitter → principal consumers |
|---|---|---|
| `ClockAdvanced` | before/after game_ms, residual, quantum count | Clock → industry/encounter coordination/replay |
| `TurnStarted` | trigger, player from/to, turn, active faction, visit_id | TurnRunner → projections/history |
| `RoundCompleted` | roster, completed seats, era-round count | Scheduler → draft/policy expiry |
| `StockGranted` | store, good, quantity, grant source/receipt | Catan/setup → ledger/history |
| `CargoLoaded` | lot/cart/source/reservation, goods | Logistics → views/quest causes |
| `CargoDelivered` | delivery/lot/cart/destination, goods, escrow status | Logistics → construction/trade/causes |
| `CargoLost` | lot/container, goods, loss cause/receipt | Ledger → trade/default/quests/history |
| `ConstructionCommitted` | order, action, site/buildings, consumed goods receipt | Construction → VP/industry/jobs/projection |
| `BuildingDamaged` | building, old/new health, lease checkpoint or direct effect | Battle/building owner → capacity/projection |
| `BuildingDestroyed` | building, role, node, disposition/cause | Building owner → centre/storage/jobs/quest consequences |
| `UnitCreated` | unit, definition, factory, faction, node, completion receipt | Industry via MilitaryService → formations/local reinforcement |
| `UnitDestroyed` | unit, combat/destruction cause, checkpoint | Combat/magic owner → formation/history/quests |
| `PersonChanged` | person, role/job/location/status changes | People → dialogue/quest bindings/projection |
| `CauseOpened/Changed/Resolved` | cause, kind, affected refs, verified fact changes | CauseTracker → quest binding/status/dialogue |
| `QuestChanged` | quest, old/new status/stage, bindings changed, outcome/effect receipts | QuestService → dialogue/history/knowledge |
| `KnowledgeLearned` | observer, fact, evidence, attribution | Knowledge → semantic labels/dialogue/journal |
| `DiplomacyChanged` | parties, old/new relation, agreement/commitment ID | Diplomacy → routing/AI/quests |
| `TechnologyAcquired/Activated` | faction, card instance/definition, stack count, effect scope | Research → capacity/combat/AI/history |
| `CubeAdded/Removed` | cube, type, hex, cause, authority/visit receipt | Hazard → source/transit/quests/projection |
| `Outbreak` | propagation event, hex, incoming type, era/total count | Hazard → terminal/alerts/history |
| `LeaseGranted/Checkpointed/Closed` | lease/version/kind/participant IDs/hash/time | EncounterRegistry → owning client/save/transfer |
| `EraTransitionCommitted` | transition, source/next era/cycle, winner, plan hash, dispositions | EraService → history/roster/projection |
| `RunTerminated` | reason=catastrophe, outbreak event, final state hash | Terminal → stop all scheduling/menu |

Special quest-authored endings, if later supplied, use an explicitly defined outcome and a separate terminal reason. They do not introduce a generic retirement or military-death path.

## Revalidation examples

`CastWorld(destroy, cart:17)` with a current local view token is accepted even if the cart is friendly. If it is leased, the encounter confirms destruction first; Python then records its cargo loss and relationship consequence under the same causal command. A retransmission returns the same receipt. It does not emit a second CargoLost event.

`ChooseDialogue(quest:8, restore_supply)` includes a binding/context version. If military has already removed its demon target, do not use a stale list of effects to pay the demon-slaying reward. QuestService switches to its world-resolved path, renders its correct line, and applies only effects whose predicates still hold.

`EncounterResult(lease:3, sequence=19)` after that lease was closed at sequence 20 is stale. It cannot restore prior health, replace a current-era building definition or complete the same hazard again. A byte-identical already accepted sequence returns its prior acknowledgement rather than a new mutation.

The exact event/effect schema versions enter save/content manifests. Adding a new gameplay effect requires owner validation, rejection/duplicate tests, serialization and the relevant source rule; adding a decorative line does not.
