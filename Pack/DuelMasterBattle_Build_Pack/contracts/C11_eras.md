# C11 — Era transitions, political survival and history

Source: GDD §§38–40, 103–116, 166, 189–191. Era conversion is a planned atomic transaction, not a sequence of scene reloads.

## Classes and outputs

`EraTransitionPlanner` (`sim/dmb/eras/planner.py`) exposes `plan(snapshot,trigger) -> EraTransitionPlan`. Pure: no ID allocation, stock writes or mutable RNG. Candidate successor IDs derive from a reserved ID block recorded when the plan is committed.

`EraService` (`eras/service.py`) exposes `request_transition(winner,event_id)`, `commit(plan)`, `upgrade_legacy(order)`, `reseed_cycle(plan)`. It coordinates owners and records one transition receipt. `HistoryService` (`history/chronicle.py`) exposes `record`, `summarise_retired`, `pin_live_reference`, `query_known_history`; it never erases a live referent. `TransitionPresenter` (`client/world/era_transition.gd`) displays four-second staged changes from committed before/after projections, preserving IDs and positions.

`EraTransitionPlan` fields: id, source world/hash/era/cycle, winning event/faction, next era/path/cycle, scores, theoretical site ranking, collapse IDs/reasons, survivors, split decisions, successor lineage/core pairs, asset/person/research ownership assignments, core upgrade operations, legacy sites, explicit retirements/losses, source layers, starter grants, hazard rollover, quest adaptations, layout relocations, new roster and validation results. Every input ref must still match when committed.

## Ordinary era algorithm

1. At the first committed action scoring 10 VP, finish that atomic action, freeze clocks/leases and snapshot. Do not run later turn stages/drafts. Calculate each site's theoretical military output using C06 with finite supply available and temporary disruption removed. Keep installed facilities, permanent tech and city multipliers. Ties use settlement ID.
2. If several factions entered this era, collapse all currently below 5 VP plus exactly one lowest scorer; tiebreak lower total theoretical capacity then faction ID. Protect an only remaining winning faction under source §40. If the era began alone, protect it and require fission now.
3. If one survivor remains from a multi-faction contest, it normally enters the next era alone and must split at that next transition. Voluntary fission is a separate legal policy decision requiring four sites and respecting the six-faction ceiling; it cannot avoid a collapse already decided in step 2.
4. Non-splitting survivor selects its two best sites (or all available if fewer). For a split use the top four sites; evaluate all three pairings, minimise summed within-pair graph distances and break ties by sorted site IDs. Each pair is a successor's core set.
5. Assign other settlements to nearest successor core by graph distance/ID. Residents/buildings/stocks follow their settlement; roads use minimum endpoint distance to cores. Units follow their home settlement, else nearest core. Cart cargo stays physically aboard; update ownership and revalidate delivery. Successors inherit research/history and external relations; they begin neutral/trade-permitted toward each other.
6. Add next-era resource layers. Upgrade centre/warehouse, existing primaries and three factory slots in place at each selected core, preserving building IDs/positions/workers. Rebind primaries and factories to new era, retain extra legacy processors, install minimal feasible new processor route(s), reset new factory meters only. Catan stock/cargo stays compatible. Upgrade cores become 1-VP settlements even if previously cities. Grant each 2 timber, 2 brick, 1 wool, 1 grain exactly once by transition+core receipt. No instant army.
7. Surviving non-core sites keep old industry/units/stocks and score zero until delivered legacy upgrade. Legacy factories still use their original layer. No extra primary slots from retaining old-era structures. Upgrade in place must account for all existing slots; never leave both old and new versions occupying a duplicated slot.
8. Collapsed organisations remove operational settlements/buildings/road ownership and disband military. Retire economic stock/cargo with loss receipts. Living civilian people become displaced and keep quests/relationships. Visual collapse ruins are inert: zero collision, loot, cost, road capacity, VP or site reservation. Separately authored dungeon/relic entities have their own explicit persistence.
9. Reconcile active quests, required items, jobs and lost targets through their defined branches. Preserve living identities, knowledge, ordinary inventory and dungeon mechanisms. Reset era catastrophe counter/escalation while preserving cube types/causes. Start fresh seats/hands and recompute current-era scores. Commit everything once, then show transformation.

The visual sequence cannot alter mechanical conversion. Skip/reduced-motion changes presentation only; reload uses the committed transition receipt. Save during presentation resumes the new state, not a partial old/new economy.

## Undersized and empty-world safeguards

Mandatory sole-faction split with two/three sites gives each successor at least one existing core, assigning extras by rank/distance. With one site, seed a second at nearest legal empty node; if none distance-legal, nearest empty node may use the explicit one-time exception. Do not manufacture four duplicate settlements. There is no repeat exception for normal expansion. If no empty node exists, report an invariant violation and preserve the old checkpoint rather than overlapping centres; the 54-node board/placement validation should make this unreachable.

A faction with no centres dissolves during ordinary play. On the next World Turn with zero active factions, seed two new factions through the validated setup/recovery contract before selecting a seat; this is not catastrophe/Game Over. Preserve living displaced NPCs and revalidate cargo/quests. Do not force a player to wait for an impossible 10-VP event.

## Future → Prehistoric

This is political reseeding, not ordinary legacy-industrial continuation. Preserve board coordinates/numbers, wizard memory/progression/inventory, living person IDs/relationships, active quest records and persistent dungeon/puzzle state. Retire old faction memberships, research competition and military organisations. Old strategic units/structures become inert history unless an explicit non-faction relic rule keeps an entity active. No future army or permanent technology hand is granted to new Prehistoric factions.

Create six new factions where normal board validation permits; use explicit bounded setup fallback. Assign living people/jobs by location without replacing their identities. Create current-cycle industrial layers under a new cycle key, leaving prior balances in historical records. Record scars/bunkers/artifacts/myths under typed legacy rules. Retire active catastrophe causes, adapt dependent quests, and place new-cycle starting cubes. Full-cycle adaptations cannot mark an unsolved promise as completed merely because its target was retired.

`next_future_path` defaults dystopian. An installed Utopia pack may expose a typed quest outcome setting the flag before Modern→Future; missing pack means the option is unavailable. Preserve the extension schema; Utopia content is outside this baseline finish line.

## History and tests

Chronicle records who/where/what/why/time with original IDs and causal parent IDs. Player view uses known history; developer inspection may see all. Retired events may be summarised after pinning references from every live person, quest, item, scar and relationship. Stress many cycles without deleting live identities to meet a memory budget.

Fixtures assert 10/9/8/7/6/5 collapses the 5 scorer; ties use capacity then ID; top-two/four ranking ignores temporary catastrophe; paired distances choose the true minimum; core grants occur once; old non-core factory still produces; collapse ruins do not block new placement; only winner protection works after mid-era dissolution; solo enters→splits next era; active quest and dropped key survive both conversion types. Full-cycle replay runs at least three complete cycles with the same commands and compares canonical continuation hashes.
