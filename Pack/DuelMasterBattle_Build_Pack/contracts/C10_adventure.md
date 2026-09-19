# C10 — Quests, items, dungeon mechanisms and duels

Source: GDD §§48–77, 128–145, 188–191. All production fixtures and authored scenarios enter these same services.

## Classes and contracts

| Class / file | API / ownership |
|---|---|
| `CauseTracker` / `sim/dmb/quests/causes.py` | `observe_changes(events)`, `active_causes`; stable occurrence IDs, not one ID per visit |
| `QuestBinder` / `quests/binding.py` | `eligible_templates`, `bind(template,cause) -> QuestInstance`; no prose generation |
| `QuestService` / `quests/runtime.py` | `offer`, `accept`, `choose_branch`, `evaluate`, `apply_outcome`; state graph and receipts |
| `InventoryService` / `player/inventory.py` | `pickup`, `drop`, `give`, `use`, `combine`, `equip`; atomic containers and item IDs |
| `PuzzleRegistry` / `adventure/puzzles.py` | Prepare/checkpoint puzzle lease and persistent object bindings |
| `PuzzleController` / `client/adventure/puzzle.gd` | Execute whitelisted mechanism graph, local fixed time, submit effects |
| `DuelAdapter` / `adventure/duels.py` | Validate rival/hazard entry, acquire global pause, grant lease, apply result/recovery once |
| `DuelController` / `client/encounters/duel_lease_adapter.gd` + `game_board.gd` | Preserve/adapt retained `game_board.tscn` + `DmbBattleSim`; own only leased duel state |
| `RecoveryService` / `player/recovery.py` | Pick safe return location without extra World Turn or treatment renewal |

## Quest graph and effects

`QuestTemplate`: id/version, family, required cause predicate, binding queries and cardinality, stages, allowed status transitions, solutions, deadlines with clock, world-resolved route, invalid-target/death/collapse route, mandatory-item recovery, era/full-cycle continuation, dialogue keys and typed effect definitions. `QuestInstance` stores template/version, cause, bindings, state, current stage, branch, deadline, effect receipts and historical references.

Statuses: offered, active, suspended, completed, resolved_by_world, failed_with_consequence. Templates normally have 2–5 meaningful stages; status handling is common engine infrastructure. Dedupe by template/cause/affected entity. A new occurrence after actual recovery receives a new cause ID. Never dedupe by display name or only by current village.

Typed effects initially support relationship/knowledge/Aspect change, quest transition, policy commitment, diplomatic agreement, item transfer, production modifier, conserved construction-stock transfer, eligible hazard treatment, entity relocation and history fact. Each has a unique effect ID, conditions, target refs and owner service. Validate an entire choice's effects before applying any; commit atomically. Revalidate concurrent external changes. No arbitrary script, free industrial import or direct player army order.

## The required village fixture: `FX-VILLAGE`

Use a normal generated-layout node touching Woodland, Clay Mountains and Ore Mountains with best token 6. It has five primary slots, three factories and two installed routes. Route A consumes Woodland renewable + Ore finite and is initially selected. Route B consumes Woodland renewable + Clay renewable and has an explicit `sluice_sabotage` production modifier. The ore hex has exactly one demon cube. Both routes are therefore unavailable, so the real factory-output shortage creates cause C and one quest bound to the existing factory worker, Mara (fixture display name only).

Stages: offered problem → investigate cause → intervention → acknowledged outcome (four). Two legitimate solutions:

1. Challenge the adjacent demon, win the normal duel, remove that cube within visit allowance, and restore route A.
2. Enter the existing sluice dungeon, solve its mechanism, remove the explicit sabotage modifier. On the next eligible faction decision the policy selects the now-working installed route B. This is a consequence of a repaired world mechanism and autonomous policy, not a player route-management menu.

The quest resolves only when a real positive factory allocation confirms output. It remembers which intervention occurred and does not falsely say the demon was removed on route B. If military removes the cube first, use resolved_by_world and acknowledge it. If the factory centre is destroyed, suspend/redirect to displaced Mara and finish with the declared loss consequence. If Mara is explicitly killed, a named surviving witness or the Chronicle records the failure; never resurrect her. Era change preserves her ID, quest and promises; current line selection updates the era/route references via the migration rules.

Illustrative lines to expand into the MVP bank: offer, "The yard has gone quiet. I can show you where the work stopped." Evidence-specific demon line, "Nothing comes from the ridge while that thing is there." Sluice route line, "The water channel could keep us working, if someone opened it." World-resolved line, "The patrol cleared the ridge before you returned." Route-B completion, "The channel is open. We can work again, though the ridge is still unsafe." These examples must be gated by verified speaker knowledge and current cause predicates.

## Dungeon and inventory fixture

Sluice area: entrance room, side workshop with recoverable handle, switch corridor, chamber with pressure plate/box and final gate, exit loop. Clue inscription states that the pressure plate must hold the gate while the handle opens the sluice. Interactions: inspect, pick up, put handle in receptor, push box onto plate, open gate, activate sluice. Solve sets `sluice_open=true` and requests removal of the specific sabotage effect once. It never directly credits units or stock.

Every required item has stable identity and accessible recovery. Dropping the handle persists; leaving/re-entering does not clone it. If stranded after a layout upgrade, move it to the nearest accessible recorded point. If a location is destroyed, open an alternate recovery interaction at its entrance/witness. Puzzle state graph is finite and must have a machine-checked solution trace from all permitted reset states. Timed variants use Game Time and pause during duel/modal screens.

Inventory has no encumbrance; unique quest/artifact IDs, stackable fungibles, one focus and one artifact slot. One item has one container or ground position. Combining is an explicit definition with input IDs/quantities and one resulting transaction; no arbitrary item synthesis. Personal inventory does not pay faction construction costs.

## Duel contract and fallback

T002 audits and preserves tested existing rules where compatible. Required baseline: four slots, six colours, repeats allowed, ten casts per side, configurable windows, separate duel clock and global world pause. Feedback uses exact positional matches plus colour matches after removing exact matches. Example secret A A B C, guess A B A D gives 1 exact, 2 colour-only; repeated colours cannot count twice.

If no valid duel implementation exists, use this explicit fallback (I07): each side has a hidden legal secret selected once at start; player may choose theirs or request seeded selection. Both submit one guess per 20-second duel window; early submission locks the guess but resolves with the rival at the window boundary. Missed submission spends that cast. A solution wins at that boundary; simultaneous solutions draw, and ten windows without a sole winner draw. Draw is an ordinary non-victory for hazard/reward purposes and uses recovery. Optional assistance can show logically eliminated colours; it cannot reveal the secret.

Rival baseline maintains candidates consistent with its observed feedback, selects a legal candidate by deterministic strategy and never reads the opponent's secret. At larger supported rulesets use a bounded candidate representation/sampler plus constraints; a chosen guess must satisfy its own feedback history. Store secrets, guesses, feedback, windows, current input, rival candidates/strategy state and duel RNG in checkpoints. Do not reroll a resumed secret. Progression supports up to 8 colours/6 slots initially; authored overflow rewards follow C00.

Starting any duel acquires a global pause; industry, battles, puzzles and buffs freeze while the duel clock runs. End outcome is applied once after target/quest revalidation. Victory removes one eligible hazard cube or applies rival quest effects. Non-victory returns to last surviving friendly settlement (wizard relation neutral-or-better); otherwise nearest non-hostile settlement, then nearest catastrophe-free wilderness, then least-affected node, ID ties. No turn, catch-up or fresh same-turn treatment allowance. A rival/hazard duel actor cannot be bypassed by ordinary destruction.

## G04 amendment — duel adoption rule

T002 and the G04 Reuse Repair Addendum select the retained production duel:
`game_board.tscn` / `game_board.gd` / `DmbBattleSim`. Hazard Challenge must
lease that implementation. Configure the board from the lease before startup;
preserve quick-duel and Adventure `pending_battle` paths. Duplicate outcome
submission is idempotent. Python `mastermind.py` remains reference scoring
only. Channel×3/Falter and the Guess/Resign panel are forbidden as production
Challenge. Do not invent a second owner of duel state.

Tests cover branch reachability, world repair before player action, target destruction mid-choice, mandatory item recovery, duplicate outcome, mid-puzzle/mid-duel save, feedback multiplicities, simultaneous solutions and same-engine fixture loading. G05 is a required manual break before scaling content.
