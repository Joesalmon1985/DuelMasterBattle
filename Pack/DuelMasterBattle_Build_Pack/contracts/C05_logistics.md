# C05 — Stock, carts and bilateral trade

Source: GDD §§79–81, 87–92, 101, 120. Only Catan goods require inter-node shipping in the baseline. Industrial animations are not cargo records.

## Objects and interfaces

| Class / logical file under `sim/dmb/logistics/` | Owns and public API |
|---|---|
| `StockLedger` / `stock.py` | Node quantities and reservations; `available(store,good)`, `reserve(order,goods)`, `load(reservation,cart)`, `credit_delivery`, `consume`, `record_loss` |
| `RoutePlanner` / `routes.py` | Pure road/access/blocked-node graph; `route(owner,source,target) -> path or reason`, `validate_next_edge` |
| `CartService` / `carts.py` | Persistent carts, cargo lots and route progress; `assign`, `advance_turn`, `deliver`, `reroute`, `destroy` |
| `TradeService` / `trade.py` | Bilateral contracts and escrow; `propose`, `accept`, `dispatch_legs`, `settle`, `cancel_or_default` |
| `LogisticsService` / `director.py` | Deterministic assignment of idle carts to unmet construction/trade demand; no teleporting stock |

`CartState`: id, owner_faction, home_store, current_node, next_edge, status, capacity (4+tech), cargo_lots, route node IDs/index, source/destination_store, shipment_id, delivery_id, assigned_turn. Optional edge/progress is presentation only between turns; authoritative crossing happens at the turn stage.

## Local cart journeys (Game Time presentation)

Godot may animate a cart between portal anchors using Game Time only. Rules:

1. Python remains the sole writer of `current_node`, cargo lots and stock. Animation callbacks never load, deliver, credit or advance World Turns.
2. `board.presentation.journeys[actor_id]` holds stable `journey_id`, `cart_id`, source/destination nodes, exit/arrival grids, local from/to/pos, phase, `presenting_node`, `progress_ms`/`duration_ms`, `authorized_cross`, `onward_phase`, `last_consumed_sequence` and optional `committed_edge`.
3. Start delivery / resume begins a `to_exit` leg toward the hold for the next route node. Without an authorised crossing the cart waits at the exit (`waiting_exit`).
4. Each logistics edge advance enqueues one pending transition (capped). Presenters play departure → `hidden` → entrance → onward (next exit or delivery pad) exactly once, in sequence order. Rapid Wait presses must not create duplicate sprites, loops, or an unbounded animation backlog.
5. Paths use local walkability (avoid walls/trees). Local obstacles do not change strategic transport legality.
6. `SyncPresentation` is a sequence acknowledgement: it must atomically persist phase, presenting_node, from/to, local_from/to/pos, onward_phase, progress/duration and `consumed_sequence`/`last_consumed_sequence` without bumping World Turn. Pending is removed only after Python accepts the matching sequence. Duplicate ACKs are idempotent; stale/out-of-order ACKs are ignored. Save/load and room re-entry resume the acknowledged leg rather than replaying a finished entrance.
7. Pause, focus loss and bridge failure freeze presentation with Game Time. Viewing another area does not change logistics outcomes.
8. Clock/HUD refreshes must preserve in-flight motion and selection; never adopt an older authority phase over a newer acknowledged phase, and never show the cart in two rooms at once.

`CargoLot`: id, good_id, quantity, beneficial_owner, contract_id/reservation_id, status and physical_container. One lot has exactly one physical location: warehouse reservation, cart, destination escrow, spendable destination or recorded loss. Positive integer quantities only.

`TradeContract`: id, parties A/B, offered goods/quantities, source/destination stores for each leg, route permissions, reservation/escrow IDs, shipment IDs, accepted_turn, deadline_turn, status, settlement receipt. Delivery promises never count as spendable goods.

## Ledger invariants

For each Catan good: initial grants + dice grants + explicit authored grants = spendable stock + reserved stock + loaded cargo + escrow + construction consumption + recorded losses/retirements. Classifications are disjoint. A reservation is a slice of stock, not an extra copy. Loading moves reserved warehouse goods into the cart atomically. Destination delivery moves cargo out before crediting the receiver.

Example: source has 5 timber. Reserve 3: spendable 2/reserved 3. Load: spendable 2/reserved 0/cargo 3. Deliver: source 2/destination 3/cargo 0. A replayed delivery still totals 5. Destroying the loaded cart gives source 2/loss 3, no destination credit. Deleting a building never destroys goods carried elsewhere.

## Scheduling

All factions' carts move at most one constructed road edge per World Turn, including Wait. No road congestion model. Route must allow the owner: own, allied or explicitly trade-permitted roads; hostile/embargoed edges/nodes fail. Any catastrophe cube touching the destination node prohibits civilian/cart entry; also prohibit departure through a blocked current node until cleared. Wizard/military remain exempt.

Arriving carts deliver in the same logistics stage when the destination accepts the contract. A cart newly assigned or loaded in active decisions cannot receive a retroactive move in the already-completed logistics stage. A cart returning home empty is still the same entity. Visually obstructing a cart cannot delay a legal strategic edge crossing.

Route invalidation leaves cargo aboard. Deterministic fallback: reroute to original destination; otherwise return to its surviving accessible source; otherwise nearest accessible own warehouse by road distance/ID; otherwise park blocked at the current node. Do not discard cargo because a route search failed. Destruction/explicit political retirement records actual loss. Changing a cart's successor faction does not move its cargo or complete its trade.

## Trade settlement default (I11)

One active faction may propose a trade or diplomacy action. Propose only mutually legal quantities with identified stores and routes. A proposal expires after one full round if unaccepted; an accepted contract reserves both sides immediately using the same transaction, then issues physical shipments. Default acceptance: both sides improve a currently identified construction shortage and retain committed goods; score candidate trades deterministically by fulfilment and route length. No hidden bank supply.

Delivered goods enter escrow at each receiving node, preserving beneficial owner until both complete. When both legs are complete, transfer beneficial ownership and release both escrows to spendable stock once. Deadline is acceptance turn + 2×longest planned leg distance + 2×active faction count, fixed when accepted. Split loads are allowed; capacity is not waived to fit a contract.

If a leg is destroyed/retired or deadline expires, default/cancel the contract. Release undelivered source reservations. Return surviving escrow/cargo to its beneficial owner's nearest legal store using carts. If stranded, keep a claim at the actual node and mark dispute; never conjure repayment for destroyed goods. A quest may settle the dispute only through typed, conserved transfers. Prior settled contracts are not unwound by later war. Hostility invalidates future movement permissions and can block an unsettled trade.

## Required tests

Check quantity conservation after every transition, partial deliveries across multiple carts, duplicate acknowledgements, cancellation after one leg arrives, warehouse destruction with reservations, embargo en route, both parties collapsing, fission with cargo, and loading during an activation. Small exhaustive action sequences over 0–4 goods and 0–2 carts should never create negative/disappearing balances except a recorded loss. Use a three-node road fixture with catastrophe touching the middle node to prove blockage and recovery.
