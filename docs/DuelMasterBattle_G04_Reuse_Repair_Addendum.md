# DuelMasterBattle — G04 retained duel and shared interaction repair

Reviewed 19 September 2026. Branch: `BuildPackV03`.
Reviewed commit: `98ea7ffc658fdb42869fd8ebc212a42fa042483b`.
Suggested repository destination: `docs/DuelMasterBattle_G04_Reuse_Repair_Addendum.md`.

This is a source-grounded repair instruction, not a completed code change or human acceptance. It supplements the earlier G04 Interaction Repair Brief. On retained duel selection, shared NPC/unit presentation and observation-led identity, this addendum incorporates Joe's latest instruction and supersedes conflicting R06 decisions. Preserve valid later work; do not rewind to this reviewed commit.

### Integration branch correction — 19 September 2026

Implement on a new `fix/g04-retained-ui` branch created from the latest `origin/feature/spellbook-ui`, then merge the latest `origin/main` into that repair branch before implementation. This supersedes the earlier instruction to work directly on BuildPackV03. Fetch first, preserve local work, and record the actual source commits. Reuse an existing repair branch if it already exists rather than resetting it.

Verified GitHub state: `feature/spellbook-ui` at `454ccf11482b79559d40ffa8c95ed38f65242a15` contains the whole reviewed BuildPackV03 history and is one commit ahead. Its extra commit includes the missing spellbook helper/base integration, assets and UI. `main` at `441899bb8917e868d86a5628d0760b2e9de60663` has separate ensemble/dialogue-authoring work and merge history to preserve. [Branch ancestry comparison](https://github.com/Joesalmon1985/DuelMasterBattle/compare/98ea7ffc658fdb42869fd8ebc212a42fa042483b...454ccf11482b79559d40ffa8c95ed38f65242a15), [open spellbook PR #9](https://github.com/Joesalmon1985/DuelMasterBattle/pull/9).

Re-run baseline checks after integration: missing files found in the reviewed BuildPackV03 snapshot may already be supplied by this newer branch. Preserve the spellbook's valid presentation work while enforcing the shared target flow and original duel requirements below. Prepare the completed repair as a PR targeting `main`; merge after Joe's G04 playtest passes. That PR will also contain the spellbook work currently proposed in PR #9, so reconcile the overlapping PR when the repair is accepted.

## 1. Diagnosis

The existing duel and village presentation remain in the repository. The migrated fixtures bypass them, and the checks do not exercise enough of the player-facing path.

| Finding at reviewed HEAD | Evidence | Required correction |
|---|---|---|
| The correct duel had already been selected for reuse. | [T002 duel retention decision](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/Pack/DuelMasterBattle_Build_Pack/tracking/duel_rules.md) identifies `game_board.tscn`, `game_board.gd` and `DmbBattleSim`. | Retain that scene, presentation and engine; adapt its campaign boundary to the Python lease. |
| The later repair audited a different engine and chose a replacement. | [R06 audit](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/Pack/DuelMasterBattle_Build_Pack/tracking/handoffs/R06_duel_audit.json) considers `realtime_duel_sim.gd` and the Python prototype, but omits production `battle_sim.gd`. | Correct the audit and its governing amendments. Differences in default colour/cast counts are configuration work, not grounds for replacing the duel. |
| Hazard Challenge opens a newly built, simpler game. | [Hazard shell](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/godot_project/client/scenes/g04_hazard_shell.gd), `_build_duel_panel`, builds colour buttons and Guess/Resign. [New Python engine](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/sim/dmb/adventure/mastermind.py) implements the replacement. | Challenge must launch the retained production board. Reusing exact/colour scoring alone is insufficient. |
| The shared interaction is only partially shared. | [Battle shell](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/godot_project/client/scenes/g04_battle_shell.gd), `_input`, scans `_unit_nodes`; NPC Observe/Interact still runs through [G01 shell](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/godot_project/client/scenes/g01_shell.gd) and `_prompt.text`. | One target/action controller must serve NPCs, soldiers and hazards in migrated play. Keep the military menu appearance Joe approved. |
| Soldier observation does not learn identity. | Battle `_open_observation` copies a public label to HUD text. [World Observe](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/sim/dmb/core/world.py), `_handle_observe`, only reads filtered knowledge; NPC names are currently revealed by Interact. | A validated observation must update persistent knowledge for the selected individual, then refresh its label. |
| Walk-away dismissal misses important controls. | Battle `_process` checks only `ui_left/right/up/down`, despite its comment mentioning pad movement. | Use shared movement intent for keyboard, touch pad and ground movement. |
| The richer village UI was left on its old path. | [WorldInteractionLabel](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/godot_project/client/world/world_interaction_label.gd) already has observation, speech, responses, choice acknowledgement and dismissal. [Reuse inventory](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/Pack/DuelMasterBattle_Build_Pack/tracking/reuse_inventory.json) marks dialogue UI KEEP. | Adapt the existing presentation to filtered bridge data; retain its interaction behavior. |
| The playable test skips the interaction under review. | [G04 playable test](https://github.com/Joesalmon1985/DuelMasterBattle/blob/98ea7ffc658fdb42869fd8ebc212a42fa042483b/godot_project/client/tests/run_g04_playable.gd) sets the wizard position, calls `_apply_destroy`, `_on_duel_requested` and `_submit_guess`. | Keep service tests, but prove clicking, walking, discovery and actual duel UI separately through real input. |

The earlier repair wording allowed the agent to choose a fallback after an incompatibility assessment. That wording was too permissive: the existing T002 decision already identified the compatible production implementation. This repair removes that ambiguity.

### Verification performed during this review

All checks below used a clean worktree at the reviewed commit and native Godot 4.4.1 on Linux. They are not results from the experimental local repair work.

- Four focused Python files passed: `test_r02_view_merge.py`, `test_r03_fixture_ownership.py`, `test_r04_semantic_magic.py`, `test_r06_mastermind_duel.py` — **13 tests passed**. This confirms those assertions pass, not that the requested interactions work.
- The original `res://client/scenes/game_board.tscn` started headlessly and exited after five frames without reported errors. This is a boot check, not a full duel playthrough or visual acceptance.
- Existing `run_semantic_post_choice_reply.gd` passed, including both tested response branches, their displayed reply sequences and the inquiry returning to responses. It exercised the existing village path, not migrated G04.
- A clean editor import emitted parse errors despite exiting with code zero: G02 preloads missing `spellbook_non_g01_attach.gd`; G04 battle/hazard shells call `_configure_spellbook` and reference spellbook members absent from their G01 base. The pushed tree therefore needs dependency reconciliation before a new G04 acceptance run. This may reflect incomplete integration; the history causing it was not established.
- No Windows run, human playtest, complete G04 gate pass or finished repair is claimed by this review.

## 2. Required reuse map

Paths in this document are relative to the repository root.

| Component | Keep | Adapt |
|---|---|---|
| `godot_project/client/scenes/game_board.tscn` and `client/scripts/game_board.gd` | Original Ward setup, spell icons, menus, cast controls, rival presentation, feedback, histories and result display. | Accept a leased encounter request and return/checkpoint through the migrated bridge. |
| `godot_project/sim/battle_sim.gd` (`DmbBattleSim`) | Two-sided Ward duel, cast windows, rival planning, feedback, simultaneous outcomes and separate duel clock. | Complete versioned checkpoint/restore and lease integration. Its current read model is not a complete save serializer. |
| `godot_project/client/components/` duel components | Existing spell slots, feedback pips, cast button, portraits and spell VFX used by `game_board.gd`. | Only changes needed for encounter configuration, responsive layout or the lease boundary. |
| `godot_project/client/world/world_interaction_label.gd` | Anchored observation/speech/responses, input acknowledgement, focus, clipping and movement dismissal behavior. | Bind filtered Python semantic/dialogue views instead of requiring legacy Adventure knowledge. |
| `godot_project/client/world/dialogue_box.gd` | Existing dialogue presentation/semantic redirect, text progression and supported pagination. | Feed authored lines and response results from the migrated runtime. Avoid displaying two competing conversation panels. |
| `godot_project/client/ui/attached_choice_card.gd` | The appearance and action choices Joe likes. | Integrate as the shared action state of the retained interaction presentation. It must not own a second knowledge or dialogue system. |
| `godot_project/client/world/overworld.gd` conversation wiring | Reference for working speech, choice and reply sequences. | Extract/adapt the presentation connection; do not boot the legacy campaign inside a migrated fixture. |
| Python world/knowledge/dialogue/visit services | Durable state and validated consequences. | Supply the common interaction contract and apply a completed duel outcome once. |

There may be several reusable view components, but exactly one foreground target session and one owner for each live simulation state. Python owning the persistent world is compatible with Godot executing a leased duel; that split was the original design.

## 3. Player-visible contract

### Shared targeting and discovery

1. A visible unknown NPC or soldier can be selected by clicking/tapping its sprite or label. Public faction/type remains readable where already observable: for example, `Red Skirmisher`.
2. Clicking a distant target performs an observation and displays its description in the shared anchored presentation. It never casts remotely.
3. Clicking a nearby target opens the same action menu style for NPCs and soldiers. Actions differ by capability: NPC Observe/Talk and other already-valid actions; soldier Observe/Buff/Destroy; hazard Observe/Challenge when eligible. Do not add military buffs to ordinary NPCs solely to make the lists identical.
4. A deliberate, valid Observe learns that individual's permitted display name through the authoritative knowledge service, as Joe requests. Apply the same rule to NPCs and soldiers. Mere proximity must not silently substitute for observation. Keep hidden inventories, private statistics and off-node identities filtered.
5. After discovery, an NPC can display `Mira`; a soldier can display `Red Skirmisher — <name>`. The same knowledge supplies the overhead label, menu title and description. Refreshing projections, changing scene or saving/loading must not forget or reroll the name.
6. Reuse a soldier's existing persistent person/name record where one exists. If military records lack identity, add the minimum persistent identity field/link and a stable save-compatible backfill. Generate it once, not on every observation or sprite spawn. A full biography generator is outside this repair.
7. NPC Talk must show an actual authored line, response choice and resulting reply through the retained village presentation. A HUD message saying “Interacted: Mira” does not meet this requirement. Use a small existing authored exchange to prove integration; leave the wider G05 narrative expansion to its scheduled tasks.

Use the shared C09 two-tile interaction calculation and current validated world/lease poses. Unknown names must not be exposed through fixture label overrides or raw unit records used as UI labels.

### Dismissal and input

- Movement intent from keyboard, pad or ground gesture closes an open observation/action menu before walking proceeds. This must work while a formal choice has paused the world; do not wait for displacement that the pause itself prevents.
- Release only the interaction's own pause token. Focus/manual/duel pauses continue to apply. Closing without selecting performs no spell, response or World Turn.
- Consume target/choice presses so they cannot also move the wizard. Deduplicate native touch and emulated mouse. Stale direction held before opening must not immediately cancel a new menu.
- Preserve the village UI's brief acknowledgement of an already committed response. The selecting press must not skip its reply. Subsequent deliberate movement dismisses safely; it does not undo or repeat that committed consequence.
- Close or safely refresh on dead/despawned target, node change, load, bridge failure or invalidation. Actor recreation by ID must not leave the menu following a freed node.

### Hazard duel

Challenge must use the original `game_board.tscn` with `DmbBattleSim`, including both combatants' Wards, existing spell icons and controls, rival casting, feedback and cast histories. The new four-button Guess/Resign panel is removed from the production Challenge path.

Keep encounter differences as explicit data. If the G04 baseline requires four slots, six colours and ten casts, configure that through the existing combatant/encounter model. Do not flatten other working encounters or replace real-time mechanics to match a prototype's defaults. Fix stale UI help text where it disagrees with the actual configuration.

At entry, Python validates the target and visit allowance, acquires the world pause and grants one duel lease. Godot runs the retained duel and reports versioned checkpoints/results. Python validates lease identity/version and target eligibility, then applies one consequence. This must not call legacy `Adventure.report_battle_result` to save a second campaign or transition into the old overworld.

Checkpoint secrets, current inputs, both histories, cast windows, counts, duel time, RNG and rival planner state. Save/load restores the same encounter without rerolling or resetting the rival. Preserve 64-bit RNG values across JSON without float precision loss. Use the existing deterministic RNG scheme, not Python's process-randomized `hash()` as a cross-process seed.

Victory removes the chosen eligible cube once and records its allowance once. Defeat/draw/flee follows C10's nonterminal recovery without an extra World Turn, catch-up or renewed allowance. Stale/duplicate results cannot remove another cube. A client-supplied `success=true` without a valid completed lease is not a production outcome. Ordinary hazard challenges must not inherit the prologue's forced-defeat flag.

## 4. Ordered Cursor work

Use repair IDs below without renumbering the pack's T-tasks. One implementation worker proceeds through the list and records concise receipts.

| ID | Work | Completion evidence |
|---|---|---|
| U01 | Fetch; create/reuse `fix/g04-retained-ui` from `origin/feature/spellbook-ui`; merge `origin/main`, preserving local work and both branches' valid changes. Record source and integrated HEADs. Set G04 FIX_REQUIRED. Integrate this addendum into execution amendments, C09/C10/C13, G04 and the short Cursor rule. Correct/supersede the R06 selection decision. Amend T079/T085 and T091/T092 so they extend this retained implementation; do not mark their remaining work complete. | Integrated branch preserves BuildPack, spellbook and main's authoring work. Source-to-runtime reuse map names exact retained components and new callers. T077 remains NOT_STARTED. |
| U02 | Reconcile the missing spellbook helper/base integration if still present at live HEAD. Preserve unrelated valid spellbook work. Resolve the intended dependencies instead of deleting the feature or silencing parse errors. | Clean native Godot import plus launch checks for affected scenes. Record engine errors even when its exit code is zero. |
| U03 | Connect one shared target session and semantic action controller to people, units and hazards. Retain the approved menu appearance. Adapt the existing village observation/dialogue presentation to filtered bridge views. | A real NPC click and a real soldier click use the common controller; NPC conversation displays its authored response and reply. |
| U04 | Implement persistent observation-led identity and shared movement dismissal. Fix keyboard, pad, mouse and touch behavior together. | No name before observation; known name survives refresh/reload; walk-away closes without casting or clearing other pauses. |
| U05 | Implement the retained GameBoard/DmbBattleSim lease adapter. Disconnect the simplified Python Mastermind/panel from production Challenge. Keep useful scoring tests as reference evidence. | Challenge instantiates the actual retained scene/engine; original icons, Ward setup, rival activity and history work. |
| U06 | Complete duel checkpoint, save/resume, outcome, recovery and visit allowance integration. | Resume without reroll; one valid outcome; duplicate/stale result rejection; independent duel clock and correctly nested pauses. |
| U07 | Replace deficient G04 acceptance paths with real pointer/touch UI tests. Run relevant G01–G03 regressions and retained dialogue/duel regressions. Capture current portrait and landscape evidence. | Tests below pass on the candidate commit; record exact commands and actual platform. |
| U08 | Update packet, known defects, launch/reset instructions, evidence hashes and candidate commit. | G04 AWAITING_HUMAN, T077 NOT_STARTED; stop for Joe. Do not mark human PASS. |

Do not replace the original duel with another new implementation or reintroduce a legacy world owner to obtain its visuals. Keep successful one-owner battle setup, safe spawn, visible boundary hazards, cart/worker behavior and projection lifecycle repairs. No engine upgrade, Wine, new economy, runtime LLM or G05 content campaign is needed here. Apply the pack's bounded defect-repair rule; after three unsuccessful focused attempts on the same unexplained blocker, preserve diagnostics and stop that blocked work.

## 5. Acceptance evidence

Automated scenarios must use actual production input dispatch for UI claims. Deterministic fixture setup and clocks are allowed; moving the wizard directly, calling private cast/choice methods or forcing an outcome cannot prove the corresponding user interaction.

1. **NPC:** click sprite and label separately; distant description, nearby common menu, Observe reveals identity; Talk shows a line, explicit response and the correct reply. A held press does not choose twice or skip the reply.
2. **Soldier:** initially public type/faction, then Observe reveals a stable individual name. Buff and Destroy remain targeted and validated. A second unobserved soldier remains unknown by name.
3. **Dismissal:** repeat with keyboard, on-screen pad, mouse ground gesture and touch. Observation and choices close; no unchosen action; movement resumes when otherwise permitted. Test an additional manual/focus pause.
4. **Projection/save:** interleave partial views, recreate an actor, travel and reload. Labels retain knowledge, menus do not retain dead actors and untreated hazards stay visible.
5. **Exact duel reuse:** enter through the hazard's real Challenge button and assert the loaded GameBoard script and `DmbBattleSim` identity as well as visible controls. Click original spell icons, set/lock a Ward, cast, inspect both histories and exercise the original menu.
6. **Duel persistence/consequences:** legitimate victory and non-victory through the retained engine; save/resume during an unfinished duel; duplicate/stale completion, target already removed, nested pause and unchanged World Turn/Game Time. Confirm only one eligible cube/allowance changes.
7. **Regression:** affected G01–G03 gates; existing retained duel tests; existing `run_semantic_conversation_ux.gd`, `run_semantic_post_choice_reply.gd` and `run_semantic_ui_correctness.gd` where their scenarios remain applicable. Adapt old state bindings intentionally; never weaken their valid presentation assertions to obtain green output.

A success marker alone is insufficient if engine errors occurred. Use bounded waits and fail with useful diagnostics. Screenshots must come from the candidate build at actual 450×800 and 1280×720 viewports; log the measured size. Do not report Windows as tested from a Linux run. Run destructive legacy-save test helpers only with isolated test user data.

### Joe's manual pass, in order

1. Open G04 Battle. Click the NPC from a distance, approach, open its menu and Observe. Confirm its name is learned and Talk uses the familiar speech/response presentation.
2. Observe a soldier. Confirm its label gains an individual name while retaining faction/type. Test one buff, one cancellation and one destruction on separate appropriate targets.
3. Open an NPC menu and then a soldier menu; walk away using the pad each time. Repeat a ground click/drag. Each menu closes and the wizard moves without casting.
4. Save, quit and reload. The identities learned in steps 1–2 remain known; other individuals have not been named by proximity alone.
5. Open G04 Hazard and Challenge a manifestation. Expect the familiar full duel: spell icons, your Ward setup, rival display/casting, feedback and histories. Seeing only four colour-cycling buttons and Guess/Resign means the repair failed.
6. Resume a saved unfinished duel, finish one encounter, and confirm the correct cube/result and resumed world. Recheck the other manifestations and readable portrait controls.

Report `G04 PASS — <tested candidate commit>` only after these work. Otherwise report `G04 FIX_REQUIRED — <observed symptom>`. Do not start the next gate while this repair is pending.

## 6. Start prompt

Place this file at the suggested repository destination, then give Cursor:

```text
Fetch origin and preserve all local work. Create/reuse fix/g04-retained-ui from
origin/feature/spellbook-ui, then merge origin/main into the repair branch.
Resolve conflicts preserving valid work from both branches; do not reset or force-push.
Apply docs/DuelMasterBattle_G04_Reuse_Repair_Addendum.md on this integrated branch.
Record source and integrated HEADs. This is a G04 repair.
First read tracking/duel_rules.md and tracking/reuse_inventory.json under the build pack.
Follow U01–U08 in order and integrate the correction into the authoritative pack.
Reuse game_board.tscn + game_board.gd + DmbBattleSim for hazard duels, and adapt the
existing village interaction/dialogue presentation. The R06 replacement decision
is superseded. Preserve the military menu appearance Joe approved.
Prove shared NPC/unit interactions, observation-led names, walk-away dismissal
and the retained duel through actual player input. Keep durable state in Python
and the duel within a Godot lease. Run the stated checks and prepare the packet.
Stop at G04 AWAITING_HUMAN with T077 NOT_STARTED. Do not mark G04 PASS.
Prepare the repair for a PR targeting main; merge follows Joe's successful G04 playtest.
```
