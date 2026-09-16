# C03 — Clocks and the turn transaction

Source: GDD §§28, 31–33, 189–190. No scene may call faction/economy systems in an ad hoc order.

## Classes

`ClockService` (`sim/dmb/time/clock.py`) owns game_ms, residual_ms and pause tokens. Methods: `request_advance(ms, sequence) -> quanta`, `acquire_pause(reason, owner) -> token`, `release_pause(token)`, `clock_view()`. It does not roll dice or run industry.

`TurnScheduler` (`time/turns.py`) owns world_turn, world_round, round roster, completed seats and active seat. Methods: `begin_turn(trigger)`, `active_seat()`, `finish_seat() -> round_result`, `reset_for_era(faction_ids)`. It reads active faction status but never deletes factions itself.

`TurnRunner` (`time/runner.py`) executes the stages below. Methods: `execute_travel`, `execute_wait`, `run_stage`, `interrupt(reason)`. Stage IDs and cursor are part of transaction/recovery diagnostics. Transitions finish atomically; no normal save is taken halfway through a strategic stage.

`ImmediateOutcomeService` (`core/outcomes.py`) checks terminal/10-VP results after every relevant committed mutation and requests the interrupt. No subsystem queues an unchecked VP gain until turn end.

## Clock semantics

Game Time progresses at every occupied node in 100 ms industry quanta. Accumulate fractions smaller than a quantum. Godot local movement may render at any rate; leased combat/mechanisms use 50 ms fixed steps. No extra seconds are assigned to Travel or Wait. A held Wait button sends one press ID until release. Rejected movement has zero time, RNG or seat effect.

Paused reasons: formal dialogue choice, inventory, grimoire, journal/map/Chronicle, settings, pause menu, focus loss, save/load, bridge failure, transition presentation and wizard/hazard duel. Ambient chatter does not pause. Pauses are a set of tokens, not one boolean: ending a duel cannot unpause an open menu. Duel time runs separately; a focus-loss pause also stops accepting duel input until focus returns. Closing a pause resumes from saved clocks without catch-up.

Military buffs and timed puzzle mechanisms use Game Time. Strategic carts/movement, Catan rolls, catastrophe cadence and ordinary quest deadlines use World Turns. Technology and selected policies use World Rounds. Every serialized duration carries its clock name. A local dialogue effect or destruction is immediate and uses the same outcome interrupt check.

## One Travel/Wait transaction

| Stage | Committed behaviour | Early interruption |
|---|---|---|
| 0 boundary | Validate; freeze/settle outgoing battle only on Travel; no partly applied accounting quantum | Failure rejects action without a turn |
| 1 arrival | Commit destination/unchanged node; increment turn; establish active seat; update visit ledger | Arrival event is now canonical |
| 2 production | Draw 2d6 once; credit Catan goods at eligible warehouses | Never industrial raw resources |
| 3 logistics | All carts take at most one legal road edge; complete eligible delivery receipts | Exactly one destination credit |
| 4 completions | Previously delivered legal construction, cyclic seat order from active seat, then stable faction/order IDs | Check 10 VP after EACH completion |
| 5 active decisions | One construction order and one trade/diplomatic proposal; one objective per disengaged formation; instant local completion uses stage-4 rules | First winner ends old-era work |
| 6 forces | Only active faction moves, at most two edges; stop on hostility; local or off-screen ownership | Apply battle/centre loss and dissolve if required |
| 7 hazards | Planned faction treatment, then due placement/cascades | Eighth outbreak stops immediately |
| 8 consequences | Evaluate cause changes, NPC/quest deadlines and policy expiry | Same immediate VP/terminal check |
| 9 seat end | Mark seat; skip dissolved factions; if roster complete draft once simultaneously, increment round, capture new roster | No old-era draft after interruption |

A responder assigned treatment in stage 5 is marked `activation_spent=treatment` and cannot also move/attack in stage 6. World Turn increments only once even if the active seat dissolves later. A round roster is captured at round start; newly created factions join a new-era/reset roster, never receive retroactive seats. Empty-world recovery in C11 happens before selecting stage-1's active seat. A sole faction completes one round each World Turn.

## Interrupt ordering

A construction at 10 VP wins before a catastrophe draw scheduled later in that turn; skip that draw. An outbreak already committed at the limit ends the run; do not execute a later quest that could award VP. Ordering is event order, not a global preference for winning. Recalculate VP from centres, not a second independent points ledger. A later building destruction cannot reverse an already triggered era transition.

An era transaction starts a fresh round roster and resets the era's round-based catastrophe escalation counter, preserving absolute world_turn/round chronology. Store `era_completed_rounds` separately from global round. A partial old-era round gives no draft. Ordinary era conversion does not increment World Turn again.

## Required oracles

With A/B: Travel, Wait, rejected nonadjacent Travel produces turn=2, one completed round and one draft each. With A/B/C and B dissolved before its seat, A then C completes one round; B gets no draft. Sixty unpaused seconds in arbitrary render chunks yields the same 600 industrial quanta. A 60-second duel yields zero world quanta, strategic turns or buff expiry. Wait at node N retains its battle and treatment ledger. Two affordable faction builds that would each win commit in the explicit seat order; exactly one transition occurs and the other order/cargo receives the transition disposition.
