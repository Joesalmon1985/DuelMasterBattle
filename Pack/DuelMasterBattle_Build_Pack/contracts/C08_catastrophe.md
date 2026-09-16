# C08 — Catastrophe, visits and terminal ordering

Source: GDD §§31, 158, 166. Pure rule layer supports typed hazards; Godot shows manifestations and runs eligible duels.

## Contracts

`CatastropheService` (`sim/dmb/hazards/service.py`): `add_cube(hex,type,cause)`, `resolve_placement(step)`, `remove_cube(cube_id,authority)`, `is_source_blocked(hex)`, `is_civilian_blocked(node)`, `rollover(era)`.

`HazardDeck` (`hazards/deck.py`): saved shuffled 19-hex deck/discard, cursor and RNG stream; `draw(count)`, reshuffle discard when exhausted.

`VisitService` (`player/visits.py`): `arrive(node,arrival_kind,turn)`, `can_treat(hex)`, `record_success(hex,effect_id)`; owns treatment ledgers separate from duel state.

`HazardResponder` (`hazards/responders.py`): eligibility by type/unit/facility, adjacency and unused active formation; chooses one treatment instead of travel/attack. `TerminalService` (`core/terminal.py`): transition running→terminal once and end further scheduling.

`CubeState`: unique id, hex, type, cause_id, added_turn, source_event. Hex contains at most three cubes total across types. `CatastropheState`: cubes, deck/discard, draws, era_outbreaks, lifetime_outbreaks, current propagation event/visited set, placement ordinal. Hazard/cause identity never changes type on an ordinary era transition.

## Placement and spread

Setup places one demon cube on each of three distinct validated hexes. Standard placement every third World Turn, Gentle every fifth, Severe every second. Use elapsed turns since era start for cadence, avoiding a skipped/double draw after era changes. Draw count 1 until four era-completed rounds, then 2 until eight, then 3. Threshold is eight outbreaks per era in every difficulty.

If target hex has 0–2 cubes, append one of the incoming type. At 3 cubes, keep them unchanged, mark the hex as outbreaked for this propagation event and increment counters. If this reaches 8, emit terminal once and stop before any further neighbour additions. Otherwise process its adjacent hexes in stable ID order with the incoming type. A hex already outbreaked in this event cannot outbreak again or receive a fourth cube. A new independent placement event has a fresh visited set. Persist progression only through a coordinated transaction/checkpoint.

Any cube blocks both Catan grants and industrial sources on its hex. Civilian/cart transit through any touching node is blocked. Military and wizard transit is allowed. No local worker-collision rule implements this strategic ban. Source suppression does not deplete finite stock.

## Treatment

A successful duel against a specific eligible cube removes that one cube and records that hex as treated for this visit. A failed duel consumes no successful-treatment allowance, but its authored consequence still commits. At most one success for each distinct adjacent hex, at most three overall. Selecting a different type on an already treated hex is still prohibited. If another actor removes the target before completion, result revalidation must not remove a different cube or pay a false reward; return a world-resolved outcome without spending a successful-treatment allowance.

Visit key uses stable visit ID, node, arrival turn and treated hex set. New strategic arrival creates a new visit after time advances. Wait, interiors, menu, save/load and duel recovery do not reset it. Keep node+turn ledgers so a same-turn recovery to a prior node reuses its allowances. Prune historical ledgers only once no recovery/save context can refer to them, retaining the current visit indefinitely until actual travel.

Faction response is independent: one eligible formation treats one adjacent cube instead of moving/attacking on its faction activation. Baseline demons/aliens/machines/nuclear manifestations use matching responder capabilities; pollution needs a cleanup-capable facility/unit and has no wizard-duel command. Full-era definitions add a cleanup capability to a baseline Modern unit/facility, without inventing a fourth mandatory military archetype. Typed quest cleanup can remove pollution through an explicit validated effect; magical visit limits apply only to magical treatment.

Modern additions alternate pollution/alien; dystopian Future alternates nuclear escalation/hostile machine. Alternation uses a saved ordinal for each scheduled placement attempt, whether it adds a cube or overflows; propagated neighbour attempts do not advance that ordinal. Prehistoric/Historic add demons. Old cubes retain type; a surviving demon can be treated in Modern. Each type must have a reachable response path in every era where it can persist, either a compatible responder, quest cleanup or eligible duel.

## Rollover

Ordinary transition resets era outbreak counter/cadence/round escalation, retains typed cubes/causes and lifetime Chronicle count. Reuse the saved deck order; no secret favourable reshuffle. Full cycle records scars/contamination, retires active hazards with quest continuation events, and runs new-cycle seeded setup. Never silently mutate pollution into a demon to keep a quest alive.

Terminal catastrophe is the only ordinary game-over route. Faction extinction recovers under C11; military attacks do not hurt the wizard. On the threshold, stop input/industry/encounters, record one terminal event and return to menu. Retain manual saves; loading a doomed save is allowed.

Test a three-hex cycle at saturation: each outbreaks at most once in one propagation. With outbreak count 7, another saturated target emits exactly one terminal event and no subsequent neighbouring mutations. Test same-turn recovery, three adjacent treatments, two types on one hex, fifth treatment attempt after Wait/reload, pollution duel rejection, retired cause adaptation and ordinary-era retention.
