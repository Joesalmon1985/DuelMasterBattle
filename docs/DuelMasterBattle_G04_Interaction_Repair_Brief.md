# DuelMasterBattle — G04 controls, ownership and hazard repair

Source review: 18 September 2026. Branch: `BuildPackV03`.
Reviewed HEAD: `d265f6005c621dcd9b0d60348590e07083d9e312`.
Review method: GitHub source and build-contract inspection; no local gameplay run. Findings below distinguish observed code from suspected runtime causes.

## Instruction to the implementation agent

Implement this as a coordinated G04 corrective pass. First reconcile this brief with the current checkout and record its HEAD. Preserve later valid work if the branch has advanced. Do not rewind the branch to the reviewed commit.

Joe reports G04 is not acceptable: mixed-faction factories, awkward spawn movement, spell actions outside the target interaction, and missing hazards. Record G04 as FIX_REQUIRED. G01–G03 remain human accepted; run relevant regressions when touching their shared code. T077 must remain unstarted. Finish this repair, produce honest evidence, then stop at AWAITING_HUMAN for G04. Do not approve a human gate yourself.

Use the existing Python world, Godot client, command bridge and encounter leases. This is a repair to the normal game path, including fixtures, rather than another fixture-only interface. Complete the common interaction prerequisite now; leave the rest of G05's narrative content and systems in their existing tasks.

## 1. Findings that explain the drift

| Finding | Source evidence | Consequence |
|---|---|---|
| The desired interaction is already specified | C09 says distant targets are observable, nearby targets offer contextual actions, baseline range two tiles. C13 requires semantic labels and transient contextual controls. | Restore that flow; the request does not require a new overall control design. |
| Its implementation was scheduled too late | T079 implements full semantic action filtering; T085 implements attached choices, both after G04. Current `narrative/semantic.py` is only a knowledge-helper re-export; `semantic_labels.gd` is minimal. | Move the shared targeting/choice prerequisite into this repair and amend the later task dependencies. Do not mark their remaining narrative work complete. |
| Battle setup bypasses settlement ownership | `_load_fx_battle` puts Red and Blue factories and both armies' home references on `node:1`. | The fixture teaches the wrong ownership model and does not test a lawful defended settlement. |
| Battle input bypasses semantic interaction | `g04_battle_shell.gd` builds a permanent spell bar; `_input` selects units, `_cast_selected` sends the chosen toolbar spell. | There is no proper distant description / nearby choice flow. |
| Cast validation is weaker than the intended interface | `MagicService` accepts caller-provided observed IDs, can thereby bypass its same-node check, and does not validate two-tile interaction distance. | Fix command validation as well as the visible menu; hiding a button is insufficient. Respect Godot-owned local pose and leased battle positions when synchronising validation. |
| Spawn is unnecessarily constrained | The battle fixture spawns at tile `[7,8]`; the inherited scene blocks `[7,7]` with a tree and row 9 with its boundary. | North/south movement is obstructed immediately. This explains an awkward start, but a runtime test is still needed for input/focus or other movement faults. |
| Missing fields are interpreted as deleted hazards | The hazard shell queues a filtered async view and immediately consumes the shared cache. Other player views replace that cache without hazard fields. `_apply_hazard_view` defaults missing hazards to empty and frees actors absent from that empty set. | A concrete refresh/lifecycle defect plausibly explains disappearance. Confirm with an interleaved-response reproducer. |
| Target registration also has an ownership defect | G04 inserts external unit/hazard nodes into `_area._npc_nodes`; `_rebuild_people` frees everything in that dictionary. | A people refresh can destroy visuals owned by a different presenter. |
| Hazard presentation does not represent three boundaries | Current anchors are `[4,6]`, `[7,6]`, `[10,6]`, all on one row. | Use three distinct boundary approaches corresponding to the three adjacent hexes. |
| Hazard duel is a substitute mechanic | `_handle_hazard_duel_action` wins after three `channel` actions or loses on `falter`. C10 specifies the retained Mastermind duel or an explicit deduction-based fallback. | Restore the agreed duel, including its pause, lease, outcome and recovery rules. |
| Automated evidence can mask a broken player action | `run_g04_playable.gd` calls private selection/cast methods. If destruction has not happened, the test queues destruction itself. Its movement assertion also does not compare every unit against its actual initial position. | These tests do not prove that clicking and choosing work. Remove the result-forcing fallback and test actual input routes. |

The repository evidence is linked in section 7. Do not claim that this source review itself reproduced a frame-rate problem, verified Windows, or completed a playtest.

## 2. Control and interaction contract to integrate

### Target first, action second

| Player input / target | Required response |
|---|---|
| Move using the existing pad or ground gesture | Move normally through valid local space. Walking within an area does not advance World Turn. Preserve acknowledged automatic exit travel. |
| Click/tap a visible unit or its label from outside interaction range | Select that individual and show a short truthful observation. For publicly identifiable fixture units, label it `Red Skirmisher`, `Blue Heavy`, etc. No remote casting. |
| Click/tap that unit within interaction range | Open an attached contextual choice card in the style of the existing speech UI: `Observe`, `Buff…`, `Destroy`. Include an accessible close control. |
| Choose `Buff…` | Show `Shield`, `Attack speed`, `Range`, with Back/Cancel. Use C07's existing values, duration, stacking caps and eligibility; do not invent mana or a new progression rule. |
| Choose `Destroy` | Apply one ordinary-target destruction through the validated production command and current encounter owner. Show feedback on the chosen target; no army orders and no group destruction. |
| Click/tap an ordinary building, worker or cart | Use the same targeting, observation and choice presenter; show only the actions valid for that kind under C07/C09. Buffs apply to eligible military units. |
| Click/tap a distant hazard | Show its public description and affected-hex information without starting an encounter. |
| Click/tap a nearby eligible hazard | Offer `Challenge` plus observation/cancel. Challenge starts the normal hazard duel for that specific cube. Ordinary Destroy does not bypass the duel. Ineligible hazards explain why treatment is unavailable. |
| Close, cancel, or begin moving away | Close the card without performing an unchosen action. Release only its own pause token. |

The two-tile baseline comes from C09. Define one shared range calculation in tile units and use it consistently in the view and command validation; the inherited 72-pixel FX-CLOCK threshold must not silently define a competing spell range. Use the common local coordinate system and documented interaction anchors, not screen-pixel distances that change with viewport scaling.

Visible identity is knowledge filtered. A public faction colour/type may be named; hidden personal names, inventories, remote armies and private statistics must not leak. Unknown but visible targets remain selectable. Off-screen or other-node records are not selectable merely because they exist in a projection cache.

Choices are transient, world-anchored UI clamped inside the usable viewport. Use roughly three visible choices plus paging/back as necessary, readable text, and at least 48 logical pixels for touch targets. Essential actions work with a single pointer/touch; keyboard shortcuts are optional. There is no permanent spell toolbar in the playtest or normal gameplay. Debug inspectors remain separate and explicitly marked.

### Input ownership and time

- One shared input router decides UI choice, semantic target, or ground movement. A pointer gesture consumed by a target or button must not later be polled as held ground movement. Handle mouse-emulated touch without duplicate actions.
- Decorative labels/panels must not blanket-block the world. Interactive controls consume only their actual input regions. D-pad movement remains usable and dismisses a choice safely before movement resumes.
- A distant observation is nonmodal and does not pause Game Time. Formal choice cards acquire the existing pause token and freeze the local battle consistently with C02/C03 before presenting actionable choices. Buff expiry and industry also pause. No catch-up or World Turn is granted on close.
- Synchronise the player's local pose and leased unit positions through the existing ordered checkpoint/pause boundary. Re-evaluate range, node, target existence and allowed action when a choice commits. A late, dead, removed, other-node or stale target gets clear feedback and no effect.
- Do not grant authority to a caller-supplied `observed_ids` list. The current node, entity/lease membership, knowledge view and current local positions must support the action. Preserve exactly-once command receipts.
- A failed command must not be repaired by a client-only kill or buff. Projection feedback reflects the accepted authoritative/leased result. Menu closure cannot unpause focus loss, a duel, bridge failure or another active pause reason.

## 3. Ownership and local layout contract

A strategic node has zero or one controlling settlement faction. Several armies may fight there; army presence is not settlement ownership. All active industrial buildings at an owned node belong to that settlement faction. Destroying the centre removes ownership/VP and leaves surviving industrial structures inactive/unowned as C04 requires; attacker victory does not capture the node.

Make the main battle fixture a lawful defended settlement: for example, Red owns the node and its buildings; Blue attacks from a separate legal home settlement. The fixture may start after the attacker's arrival to make testing quick. Blue units retain valid original home/factory IDs while their current node is the battle node. Use normal setup/building definitions, including the three distinct military factories required for a core; do not make one arbitrary factory the producer of every unit type. Keep all three unit shapes and both faction colours.

Validate this invariant in fixture setup and normal construction/load validation. Do not fix it by recolouring the Blue building while leaving its ownership, production or home references unchanged. Preserved ruins/inactive structures are not a second active settlement.

Provide a stable saved local layout with shared building/terrain footprints for rendering, wizard movement and battle navigation. Reuse the projection/layout contracts rather than adding another independent map. Select a clear spawn with space to move in all cardinal directions and a route to required approach points and exits. Wizard spawn validation includes its collision footprint, not just the centre point. Re-entry and load preserve valid poses; any recovery from an invalid pose chooses and records a deterministic safe point once. Clock refreshes must not snap the player back.

For G04 hazard testing, place the three distinct hex manifestations near three different local boundaries, with walkable approaches. Labels, art and hit regions must follow the same stable anchors and remain visible above terrain, without sitting underneath the HUD or outside the playfield.

## 4. Ordered implementation work

Use IDs R01–R08 for this repair receipt only; do not renumber T001 onward. Read the indicated contracts and focused code excerpts per item instead of loading the entire pack into every agent turn. Keep the latest receipt and exact next item resumable.

### R01 — Integrate the correction into the authoritative pack

Read `AGENT_START_HERE.md`, `EXECUTION_AMENDMENTS.md`, the repository map, G04 status, and relevant sections of C02/C03/C04/C07/C08/C09/C10/C13. Record this user-directed correction in the execution amendments. Update the affected contracts, G04 gate/checklist and task dependencies. Add a concise link in `.cursor/rules/dmb-build-pack.mdc`; do not paste this whole brief into the rule.

Explicitly state that G04 now owns the minimum shared target/observation/choice integration. T079 and T085 extend it with their remaining narrative coverage rather than replacing it. Amend future entity/interaction tasks to declare public label, distant description, nearby actions, command owner and a real input-path test. Add a small traceability table linking each interaction requirement to its production owner and acceptance check. Do not record unsatisfied work as DONE.

Acceptance: one canonical control contract and one progress ledger; no later task instructs an agent to recreate a competing interface.

### R02 — Repair projection and visual lifecycle

Focus: `client/bridge/world_client.gd`, the G04 hazard view consumer, shared actor registration, and `fx_clock_area.gd` people rebuilding.

Correlate filtered views with their request/subscription and field coverage. A missing field means no update to that field; an explicitly empty authoritative collection means empty. Prefer separate versioned subscriptions or a carefully specified merge; do not blindly merge stale replies or silently retain explicitly deleted entities. Never process a previous generic cache as the reply to a newly enqueued hazard request.

Make target registration non-owning. Each presenter frees only its own sprites; registering a unit/hazard for selection does not make it a person owned by `_rebuild_people`. Unregister on removal/load/scene exit. Selection handles freed targets safely.

Acceptance: interleave normal clock/player/people and hazard replies, including delayed responses and explicit removals. Untreated hazards persist for at least 60 seconds; one real removal removes exactly its actor. A people refresh does not free any live military or hazard actor. Preserve asynchronous updates and existing responsiveness.

### R03 — Correct fixtures, ownership and spawn

Focus: `sim/dmb/testing/fixtures.py`, current settlement validation and local layout/footprint owners.

Implement section 3 through ordinary setup data and validators. Remove the accidental two-owner arrangement and invalid home/factory links. Make a fresh G04 seed immediately navigable. Audit saved-pose restoration and input blocking as well as the starting coordinate. Do not broadly delete user saves; document a deliberate isolated-fixture reset or versioned migration.

Acceptance: a two-active-owner fixture is rejected; a legal invading army is allowed. The wizard can leave the spawn in every cardinal direction, reach units and hazard approaches, and navigate the scene at both supported test sizes. Valid save/load pose remains unchanged. A destroyed centre leaves no active settlement owner and does not award the attacker ownership.

### R04 — Implement the shared semantic action path

Focus: C09's `SemanticResolver`, `client/ui/semantic_labels.gd`, `client/ui/context_actions.gd`, shared world input, `MagicService`, and existing pose/lease command boundaries.

Build one range/knowledge-aware target view and action catalogue. Route existing NPC, worker/cart, building, unit and hazard selection through the common interface while retaining each kind's real action service. Reuse/adapt `client/world/world_interaction_label.gd` presentation behaviour where compatible. Its old Godot world/knowledge dependencies must be replaced with the migrated projection/command interface, not reconnected to the old simulation.

Acceptance: distant versus nearby selection changes the available actions; commands reject distant/other-node/stale targets even when a forged observed-ID list contains them. Labels and description show permitted identity, never raw internal IDs as ordinary player text. The same click cannot both select and walk or cast twice.

### R05 — Replace the G04 toolbar with attached choices

Focus: battle shell, common choice presenter and existing pause/lease owners.

Implement section 2, remove the always-visible spell controls, and use actual pointer/touch hit routing. Show distinct unit shapes/faction colours, readable names, selection state, HP and a visible result for each buff/destruction. Keep battle autonomy and existing unit state; do not introduce player army commands. Menus must close correctly on movement, cancel, target loss, scene exit and bridge failure.

Acceptance: click far unit → observation; move near → click same unit → Buff/Destroy choices; choose one → exactly one validated effect. Cancel does nothing. Buff expiry/caps and destruction persistence obey C07. The pause round trip does not stall the world or reset local movement.

### R06 — Restore visible hazards and the normal duel

Focus: hazard shell/actor, shared semantic actions, `sim/dmb/adventure/duels.py`, command handlers and the retained duel core/adapter from C10/T074.

Use the repaired projection lifecycle and three boundary anchors. Obtain treatment eligibility from the real visit ledger; do not force `treatment_eligible=true` on the client. Connect contextual Challenge to the retained tested Mastermind runtime, or C10's specified fallback if the retained runtime is incompatible. Channel-three-times/Falter is not that fallback. Accept outcomes only through validated duel state/lease completion, not a free client-provided success flag.

Preserve four slots/six colours/repeats/ten casts for the baseline, exact/colour-only feedback, a separate duel clock, world freeze, save/resume without rerolling, and ordinary nonterminal recovery. A success removes only the chosen eligible cube and records that hex's visit allowance once. Failure, draw, cancellation before starting, stale target and duplicate result follow their existing distinct rules. Wait/save/load must not renew treatment allowances.

Acceptance: a player can see, inspect, approach and challenge each eligible manifestation. A legal guess sequence earns success; a failed/drawn encounter does not clear the cube. Pause and resolution remain correct, including another actor having already removed the cube.

### R07 — Replace misleading acceptance tests

Use production entrypoints and actual pointer/touch events for claims about clicking, menus and movement. Deterministic setup and clocks are fine; private `_select_unit`/`_cast_selected` calls cannot substitute for UI evidence. Remove the test-side `queue_destruction` fallback. Wait for a real receipt/checkpoint within a bounded timeout, then fail if the expected effect is absent.

Required regression cases:

1. Measured unit position changes from its captured initial coordinate, legitimate attacks, HP change and death; distinct shape/type and faction identity.
2. Far observation with no cast; near choices; every buff choice and Destroy affect the selected eligible individual only.
3. Pointer consumption across press/hold/release; touch emulation causes no duplicate; decorative UI does not block the world.
4. Pause token nesting, cancellation, stale/dead target and resumed movement/clock/battle.
5. Hazard persistence across interleaved partial views, people rebuilds, scene reload and save/load; real deletion removes only the right manifestation.
6. One-owner validation, valid invading-army home refs, safe spawn and reachable interaction approaches.
7. Real deduction feedback including repeated colours; outcome/visit allowance idempotency; no arbitrary success command accepted as gameplay.
8. G01 movement/travel/Wait/save/bridge behaviour; G02 delivery presentation and technology; G03 per-connection carriers and industry oracle remain intact.

Run mapped task/domain checks and `python3 tools/check.py --gate G04` (or the existing Windows interpreter launcher). Include relevant Godot import and scene checks. Test failures must stay failures: do not delete assertions, bypass production services or weaken wrappers. Capture actual rendered portrait 450×800 and landscape 1280×720 evidence. Record the platform actually exercised; do not claim Windows verification from Linux alone.

### R08 — Handoff and stop

Update the G04 packet with exact candidate and handoff commits, commands/results, the short manual checklist below, observed limitations, and reset/save instructions. Record any missing required check as blocked, not PASS. Use normal repository commit rules and preserve unrelated changes. Routine implementation may continue autonomously through R01–R08; follow the pack's existing bounded repair-attempt rule for concrete blockers. Stop at G04 AWAITING_HUMAN, with T077 unstarted.

## 5. Joe's manual acceptance checklist

Start with a fresh isolated G04 fixture after preserving any save you want to keep. Repeat save/load checks on the resulting played state.

1. **Ownership and spawn:** one faction owns the settlement and its active buildings; the opposing colour belongs to attackers. Move freely away from spawn without hunting for an unblocked direction.
2. **Distant unit:** click a visible unit from more than two tiles away. Read its faction/type and description. There is no remote spell option or permanent spell bar.
3. **Nearby unit:** approach, click again, choose a buff. See it on that unit. Reopen and choose Destroy on another unit; only that individual disappears/dies. Cancel another choice and confirm nothing happens.
4. **Time and input:** units fight while the world runs; formal choices pause it; closing resumes normally. Clicking labels/options does not walk the wizard. Movement away closes choices. An existing pause/focus loss is not accidentally cleared.
5. **Hazards:** all three manifestations remain visible while waiting and walking. Each occupies a different hex-boundary approach. Far click explains it; near click offers Challenge when eligible.
6. **Duel:** play the normal deduction duel. Winning removes that specific cube; other manifestations remain. Losing does not produce Game Over. Wait/save/load does not restore a spent treatment allowance.
7. **Persistence and layout:** save, quit, reload. Casualties, buffs according to their clock, remaining hazards, ownership and valid player position persist. Choices, pads and targets remain usable in portrait and landscape.

Return `G04 PASS — <candidate commit>` only after these work. Otherwise return `G04 FIX_REQUIRED — <specific symptom>`. Screenshots and headless PASS results cannot replace these interactions.

## 6. Scope limits

Preserve accepted G01–G03 behaviour and the Python/Godot ownership split. No engine upgrades, Wine setup, unrelated framework replacement, full G05 narrative implementation, neural-network training, runtime LLM, new resource economy or optional G03 visual-polish campaign in this repair. Placeholder shapes are sufficient if readable and truthful. The deliverable is a playable, design-faithful G04 plus shared contracts that future tasks actually reuse.

## 7. Pinned repository evidence

- [C09 — people, semantic observation and range](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/contracts/C09_people_dialogue.md)
- [C04 — ownership and centre destruction](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/contracts/C04_board_building.md)
- [C07 — wizard destruction and support](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/contracts/C07_combat.md)
- [C10 — retained duel and explicit fallback](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/contracts/C10_adventure.md)
- [Battle/hazard fixtures](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/sim/dmb/testing/fixtures.py)
- [Battle shell and permanent spell bar](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/godot_project/client/scenes/g04_battle_shell.gd)
- [Hazard shell and cache consumption](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/godot_project/client/scenes/g04_hazard_shell.gd)
- [Shared player-view cache](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/godot_project/client/bridge/world_client.gd)
- [Inherited local area: spawn obstacles, input and people rebuilding](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/godot_project/client/world/fx_clock_area.gd)
- [Magic command validation](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/sim/dmb/player/magic.py)
- [Playable test with result-forcing fallback](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/godot_project/client/tests/run_g04_playable.gd)
- [T079: later semantic implementation](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/tasks/T079.md)
- [T085: later speech/choice presentation](https://github.com/Joesalmon1985/DuelMasterBattle/blob/d265f6005c621dcd9b0d60348590e07083d9e312/Pack/DuelMasterBattle_Build_Pack/tasks/T085.md)
