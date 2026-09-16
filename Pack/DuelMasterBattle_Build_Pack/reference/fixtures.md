# Reproducible fixture and test book

These are specifications for fixtures to implement in the normal runtime. No future game-test result is claimed. Each implemented fixture stores its version, definition/asset manifest hash, seed, full initial state or setup recipe, command/time trace and expected assertions. Persist actual fixture files under the mapped `content/fixtures/` tree.

Names A/B/N0/H0 below are symbolic references resolved to real stable IDs during fixture setup; never identify runtime objects by these display labels. Small graph fixtures test isolated services; full-world scenarios use a validated radius-2 19-hex board. No fixture-specific production/quest rules are allowed. Scenario setup may construct a rare initial condition; gameplay afterward follows production commands.

## FX-CLOCK — Frame independence, seats and pause

Seed 101, manifest `fixture_clock_v1`. Two factions A/B, current player N0 with an adjacent N1 and nonadjacent N9; no live industrial consumer until C06 is enabled. Record clock counters, RNG hashes and command receipt count.

1. Advance 60,000 ms as 600×100 ms; compare against a second identical world given chunks 17, 33, 50 ms repeated 600 times. Both total 60,000 ms with 600 industry boundaries; residual 0. Use equivalent 50 ms encounter segmentation where enabled.
2. Travel N0→N1 with command c1; retransmit c1; Wait once c2; invalid Travel N1→N9 c3. Final turn 2, one completed A/B round, one draft each when technology is enabled. Duplicate c1 returns original result; rejected c3 changes no RNG/IDs/state.
3. Acquire dialogue and inventory pause tokens, release dialogue only, advance 1,000 ms: no world time. Release inventory, advance 100: exactly one new quantum. Unknown pause-token release cannot clear other pauses.
4. Start a 60-second duel: world time, factories, other battles, puzzle timers and buff remaining duration unchanged; duel clock advances. Closing application for a day grants no catch-up.

Unit tests: clock accumulator, pause set, roster skip/reset, command receipts. Integration: actual sidecar/client clock driver and saved lease. Negative cases: ID reuse with different payload, old session command, missing expected version, held Wait, focus-loss return, interrupt after first local 50 ms step.

## FX-CARGO — Local goods and delayed construction

Seed 202. Road path N0–N1–N2, one cart capacity 4 at N0, source store 5 timber plus the specified other goods for the chosen build; N2 has a non-owning construction staging store. N0/N2 are distance-legal for a later settlement. Different ledgers carry industrial resources with similar names to prove namespace separation.

Ledger oracle: 5 timber → reserve 3 gives spendable 2/reserved 3 → load gives source 2/cargo 3 → after first turn cart N1/cargo 3 → after second turn destination timber 3/cargo 0. Retransmitting final delivery retains total 5. Destroying the loaded cart instead gives source 2/loss 3, no destination goods.

Construction case: deliver 1 timber, 1 brick, 1 wool, 1 grain to N2. Until all are present its order cannot commit, even if other warehouses have abundant stock. On valid completion those four quantities are consumed once and N2 becomes a 1-VP settlement with real baseline facilities. A replayed completion costs nothing further. A newly appeared adjacent centre before commit invalidates placement and leaves real goods available/returnable.

Blockage case: add one cube on a hex touching N1. Cart cannot enter or leave that blocked node; military/wizard can. Remove it legally and the next turn resumes the same cart/cargo. Change permissions to embargo while loaded; reroute/return/park without quantity loss. Destroy warehouse while cargo is aboard: only warehouse-resident goods are lost.

Trade case: A offers 2 timber for B's 2 ore using two real routes. First delivered leg stays escrowed; after second, both release to receiving spendable stores. Destroy one leg or expire deadline: surviving goods remain at their actual locations, enter return/dispute handling, and no compensating ore/timber appears. Check escrow/beneficial ownership during fission/collapse.

## FX-INDUSTRY — Independent numerical flow oracle

Seed 303. One normal node with an installed processor using one plentiful renewable channel and one 600-unit finite channel, processor cap 0.1 output/s. Three healthy factories consume 2/3/5 outputs per unit and each caps at 1/minute. Both source channels supply at least 0.1/s. No technologies, city multiplier, hazards or buffs.

Expected equal-weight rates: 0.01 units/s per factory. After 60 s: fractions [0.6,0.6,0.6], no units. At 100 s: three persistent units, one of each type, fractions [0,0,0]; processor used 10 units of each raw, finite remainder 590. Save at 59.9 s and resume for 40.1 s; compare exact receipts and remainder to uninterrupted 100 s.

Damage case: processor health 25% gives cap 0.025/s and each rate 0.0025/s. Destruction gives zero. A blocked decorative worker path changes neither case. An explicit strike modifier produces zero until removed. A source catastrophe blocks both channels and does not consume its finite balance.

Shared-deposit case: two identical nodes draw the same layer with 0.01 raw remaining over a 100 ms quantum. Aggregate finite consumption ≤0.01; individual meter progress matches allocated output, never two full 0.01 debits. Swap record insertion/visit order and compare results. Test finite balance zero, processor ceiling, city/source factor, technology scope and fixed-point carry separately.

Legacy case: convert an unrelated faction/core while this site survives non-core. Its old source layer and factories continue old-era production; newly added era layer does not refill its old balance. Load a legacy material stock only through explicit compatible stock route; a power service cannot be stored or carted.

## FX-BATTLE — Identity, tactics and handoff

Seed 404. Hostile A/B at one node: each has two line fighters and one skirmisher with persistent IDs. Include a 25%-cover tile, one blocking wall, a targetable processor/warehouse/cart and a worker. Initial positions, cooldowns and HP are explicit in fixture data. The wizard is a separate non-damageable actor.

Shared formula cases: Prehistoric base attack 15 at cover 0.25 → 11 damage; Historic → 113. Armour large enough to make the expression negative still gives minimum 1. Same-step lethal attackers both act; next-step dead units do not.

Local test: target selection follows distance/HP/ID, LOS/wall actually prevents attacks, and units move into range at declared speeds. Cast at a friendly, neutral and hostile ordinary unit/building in separate restored scenarios; each destruction takes one valid cast, with appropriate cargo/workplace/relationship effects. Group label cannot destroy three soldiers. Rival actor goes to duel entry. Faction military cannot harm the wizard.

Buff test: a Prehistoric line unit max HP 100 receives shields of 25 each, capped at total remaining 200. Frequency caps at 3×; range bonus at +4. Damage consumes earliest expiry shield first. Expiry never removes HP. Thirty seconds of world play expires effects; a 60-second paused duel does not.

Handoff test: play until one soldier dies and a second has partial damage; save their IDs/HP, leave, and resolve off-screen. No original army respawn. New factory completion at a locally leased battle enters once even after duplicate message delivery. Wait retains local lease. Off-screen steps add no global seconds, production or reinforcements; freeze handoff buff modifiers. Unreachable groups/120 simulated seconds produce stalemate. Withdrawal intent does not grant free node travel.

## FX-HAZARD — Cycles, typed overflow and visit persistence

Seed 505. Three mutually neighbouring hexes saturated at three cubes each, with other adjacent hexes explicitly included; total era outbreak count starts 0. Overflow one hex with type demon. Assert each saturated hex outbreaks at most once in that propagation event, no hex exceeds three cubes, neighbour order is stable and the incoming type propagates without replacing previous types.

Terminal variant: era outbreak count 7; overflow a saturated hex. Result is count 8, one terminal event, no later neighbour additions or remaining turn stages. Nonterminal variant reaches 10 VP in an earlier construction stage; old-era hazard draw is skipped and era conversion begins.

Visit variant: player node touches three affected hexes, one with two differently typed cubes. Win one eligible duel per distinct hex. Three removals succeed, second removal from the same hex fails. Wait/reload/interior/recovery keeps the ledger. A genuine later Travel away and back creates a new visit after strategic time advances. Failed duel does not spend a successful-treatment allowance. Another actor removing the target before result means no removal of a substitute cube.

Ordinary transition retains cube/type/cause and resets era outbreak count; full cycle records scars, retires active hazard causes and applies quest adaptations before fresh setup. Pollution refuses duel entry and accepts only eligible cleanup effects/responders. Faction treatment consumes its activation, separate from wizard visit allowance.

## FX-VILLAGE — One real engine for the village test

Seed 606, full valid board, local test node touching Woodland/Clay/Ore, best token 6, five primary sites and three factories. Install route A (Woodland renewable/Ore finite) and B (Woodland renewable/Clay renewable). Put one demon cube on Ore and an explicit sabotage modifier on route B. Positive-output shortage cause binds one existing factory worker (Mara in this fixture) and one quest. C10 defines the four-stage quest and sluice dungeon.

Required traces: inspect/talk/accept; demon duel victory restoring A; fresh start and clue→handle→box/plate→gate→sluice restoring B via next legal policy decision; ignore while faction clears hazard; target destruction and displaced speaker; explicit speaker death; lost/stranded handle recovery. Each trace uses normal commands and observes actual positive factory allocation before rewarding completion. Route B dialogue must not claim the demon died.

Save at each of: offered quest, failed Aspect check, carried handle, gate open, mid-duel and factory partly produced after completion. Leave/re-enter and compare person/quest/item/building IDs and dialogue facts. Retry with unchanged check fingerprint cannot farm effects. New evidence can permit retry. Unknown name/hidden fact cannot leak through a fallback or passive interpretation.

The village test panel may select a fixture/content manifest and inspect truth; it must use the same QuestService, DialogueResolver, puzzle/duel adapters and world core as normal gameplay. A separate test engine invalidates acceptance.

## FX-ERA — Immediate winner and inherited sites

Seed 707. Fully legal board or explicit validated saved state with scores 10,9,8,7,6,5 at the winning action; ensure those points are backed by actual current-era centres/cities. Expected collapse includes the 5 scorer even though viable. Separate below-5/tie fixture tests all weak factions plus one lowest by capacity/ID.

Give one survivor at least five sites with distinct installed theoretical capacities and temporary hazard/damage on the best two. Rank still selects those best two when temporary effects are ignored. Give a splitting survivor four core candidates whose known graph-distance table distinguishes the three possible pairings. Verify minimum summed pair distance and all asset ownership assignments exactly once.

Preserve loaded carts, partial factory meters, an active quest/person, dropped required key, old finite layers and puzzle state. Check in-place core IDs, 1-VP new cores, new meter zero, starter package once, no instant units, working legacy non-core old output, and paid upgrade after real Catan delivery. Collapsed assets become inert ruins; surviving centre-destroyed industry remains stranded real structures, not collapse ruins.

Place a winning completion before another queued build and due hazard stage. The later old-era actions must not run. Save/retransmit transition and presentation skip must not reapply grants or lose living identities.

## FX-SOLO — Survival and political recovery

Seed 808. Case A: several factions entered, one winner remains after dissolution; protect it and mark next solo era for mandatory fission. Case B: era starts with one faction; at its 10-VP transition it survives and produces two successors. With ≥4 sites use compact pairs; with 2/3 distribute existing cores; with 1 add one nearest legal empty core, with explicit one-time distance exception only when needed. Never clone four sites.

Case C: destroy all centres through legal effects; no Game Over. Next World Turn seeds two factions, retains displaced living people/active quests and uses normal setup. This is different from terminal catastrophe. Test six-faction cap for voluntary splits and stable winner/tie behaviour.

The one-/two-/three-site mandatory-split cases are isolated planner/recovery-unit fixtures. Do not falsely claim that one ordinary 2-VP city can reach 10 VP in normal play. The end-to-end solo-era fixture uses a score-backed reachable winning state; the smaller cases exercise the explicitly required defensive allocation helper independently.

## FX-CYCLE — Complete history loop

Seed 909, full manifest, six-faction start. Run at least three complete Prehistoric→Historic→Modern→Future→Prehistoric cycles using production turn/controller rules. Keep one living recurring person, active promise, dropped unique artifact and persistent bunker puzzle pinned throughout, including a hazard-linked quest adaptation at reseed.

Expected: board terrain/token/topology hash unchanged; cycle increments once each; new political/research competition starts; future military does not join the new army; person/quest/item/puzzle IDs persist; old active hazard retired through explicit outcome; Chronicle lifetime outbreaks/scars remain. Save during each era and compare continuation. Twenty-cycle headless stress additionally measures pinned history/state growth without deleting live entities.

## FX-RECOVERY and FX-RELEASE

Seeds 1001/1101 with manifests/versions frozen in report. Inject disconnect/process termination before acknowledgement, after accepted mutation, during save freeze, temporary-file write, atomic replacement and encounter transfer. Use duplicated delivery/duel/transition results after reconnect. Expect exact once-only mutations or an honest rollback to the last coordinated checkpoint; never a mismatched Python/Godot pair.

Release trace uses the actual packaged Windows executable and local sidecar/data/models. Test offline loopback, no developer dependencies, non-ASCII/path spaces, moved/read-only install, user-data save location, corrupt current slot/good backup and clean child shutdown. Run the full baseline scenario/three-cycle continuation with release manifests. A headless Python-only result cannot stand in for this platform acceptance.
