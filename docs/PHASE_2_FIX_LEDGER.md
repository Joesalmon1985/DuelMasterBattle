# Phase 2 fix ledger

Live recovery record. Update this file at the end of each task. Do not treat chat history as the source of truth.

| Field | Value |
| --- | --- |
| Current task | P2R-15 |
| Status | complete — stopped for manual inspection |
| Last good commit | `f85420ed7bddcbab89d13d5c4953cf83fa0a5bb3` (working tree not committed) |
| Files changed | see log |
| Tests run | sim suite 28/28; actor fallback; village test mode including E17A |
| Known blocker | none. Game was not launched. |
| Next task | manual visual pass of the three cases below |

## Log

### P2R-00 — Recovery ledger

- Status: complete
- Last good commit: `f85420ed7bddcbab89d13d5c4953cf83fa0a5bb3`
- Files: `docs/PHASE_2_FIX_TASKS.md`, `docs/PHASE_2_FIX_LEDGER.md`
- Tests: none
- Blocker: none
- Next: P2R-01

### P2R-01 — E17A always uses John

- Status: complete
- Diagnosis: `new_game()` starts the Halvard prologue. Village test boot used that identity, so the controllable sprite was the blue mage.
- Fix: test-session seeding sets `story.protagonist` to `john` after the campaign snapshot is taken. Exit still restores the snapshot.
- Files: `godot_project/client/scripts/village_test_runner.gd`, `godot_project/client/tests/run_village_test_mode.gd`
- Tests: headless E17A boot — protagonist `john`, sprite key `john`, campaign restored to Halvard on exit
- Blocker: none
- Next: P2R-02

### P2R-02 — Missing NPC graphics

- Status: complete
- Fix: one path, `DmbActorVisual`. A missing character resource is not loaded. The stand-in is a generated rectangle-and-circle texture plus a name label.
- Files: `godot_project/client/world/actor_visual.gd`, `godot_project/client/world/overworld.gd`, `godot_project/client/tests/run_actor_fallback.gd`
- Tests: `ACTOR FALLBACK: ALL PASSED` for sprite `no_such_npc_zzz`
- Blocker: none
- Next: P2R-03

### P2R-03 — E17A visible names

- Status: complete
- Diagnosis: `cast.json` stored visible names `"A"`, `"B"`, and so on. Projection copied that field. Internal ids were already `a`–`l`.
- Fix: fixture names are the roles. Projection still prefers `role` if a future name is a single letter. Ids unchanged.
- Files: `godot_project/content/village_tests/E17A/cast.json`, `godot_project/sim/world/village_composite_projection.gd`, `godot_project/sim/tests/test_e17a_fixture.gd`
- Tests: id `a` remains `a`; visible name `Miner`. Same for Distiller, Reeve, Storekeeper.
- Blocker: none
- Next: P2R-04

### P2R-04 — E17A dialogue silence

- Status: complete
- Diagnosis: opening node `scene_01_a` is a choice bound to npc `a`. `interact_npc` returned a menu and zero turns. Overworld only speaks `turns`, so the talk was silent. `dialogue.json` does have speech, but those turns are the branch responses and were only returned by `make_choice` (verified: choice 0 returns 4 turns).
- Fix: a choice talk now includes spoken turns. A default/opening entry is used when one exists. This opening node has none, so it speaks the node's existing prompt, then the choice. Writing was not changed. Branch turns still play after the choice.
- Files: `godot_project/sim/world/village_quest_runner.gd`, `godot_project/sim/tests/test_e17a_fixture.gd`
- Tests: opening interact with `a` at `scene_01_a` returns non-empty turns; `make_choice(0)` still returns the authored turns
- Blocker: none
- Next: P2R-05

### P2R-05 — Larger canvas

- Status: complete
- Fix: steadings 49×37–73×55, towns 81×61–113×85. Crossings stay 17×13. Size follows how much is built, so the band is used rather than everything clamping to the floor.
- Files: `godot_project/sim/world/settlement_layout.gd`, `godot_project/sim/tests/test_settlement_layout.gd`
- Tests: deterministic reproduction and reachability still pass on the larger maps
- Blocker: none
- Next: P2R-06

### P2R-06 — Built core and outer work

- Status: complete
- Fix: layout now reports `core` and `outer`. Civic, processing and housing stay in the core (a slightly grown core if the strict one is full, still clear of the map edge). Production goes to the outer hex sectors.
- Tests: most houses are inside the core and not on the map edge; most production is in the outer work area
- Blocker: none
- Next: P2R-07

### P2R-07 — Open navigation

- Status: complete
- Fix: every settlement exit is painted through to the plaza, then widened to three tiles inside the border. Building links prefer a straight spur. A short detour remains only when the straight line is blocked. Flood-fill still requires every important interaction point to be reachable, and each exit road must reach the centre.
- Tests: exit roads open onto path tiles and reach the plaza
- Blocker: none
- Next: P2R-08

### P2R-08 — Wood dressing

- Status: complete
- Fix: forest outer sectors place tree/copse placeholders. Count is `4 + strength * 7` (a modest copse on a crossing).
- Tests: wood strength 3 places more trees than strength 1
- Blocker: none
- Next: P2R-09

### P2R-09 — Grain dressing

- Status: complete
- Fix: grain strength adds field strips and lengthens them. Crops are dark-grass rows inside fence placeholders.
- Tests: grain strength 3 has more field representation than strength 1
- Blocker: none
- Next: P2R-10

### P2R-10 — Pasture dressing

- Status: complete
- Fix: wool strength adds fenced open paddocks. Distinct from grain: open floor inside the fence, not crop rows.
- Tests: pasture strength 3 has more fencing than strength 1
- Blocker: none
- Next: P2R-11

### P2R-11 — Ore dressing

- Status: complete
- Fix: mining strength adds rock and mine mouths (a dark tile under a rock arch). A strength-1 sector gets one mouth; a stronger one gets more mouths and more rock.
- Tests: mining strength 3 has more mouths than strength 1
- Blocker: none
- Next: P2R-12

### P2R-12 — Clay dressing

- Status: complete
- Fix: clay strength adds dug pits (dark rectangles with rock heaps). Not the mine arch.
- Tests: clay strength 3 has more pit representation than strength 1
- Blocker: none
- Next: P2R-13

### P2R-13 — Worker housing and camps

- Status: complete
- Fix: canonical houses are spread inside the built core. A roofed worker-camp placeholder is added near a production sector only when that sector's strength is at least 2. Camps are kind `camp` and are not counted as housing.
- Tests: a strong sector gets a camp; house count does not change with production strength
- Blocker: none
- Next: P2R-14

### P2R-14 — Crossing flavour

- Status: complete
- Fix: crossings stay 17×13. Roads are not widened. Each terrain gets a modest placeholder: trees, a field strip, a paddock, a mine mouth, or a clay pit. The plaza stays open.
- Tests: five terrain crossings keep their size and each has its own dressing
- Blocker: none
- Next: P2R-15

### P2R-15 — Structural regression

- Status: complete. Stopped before launching the game.
- Tests:
  - `godot --headless --path godot_project --script res://sim/tools/run_tests.gd` — Passed: 28, Failed: 0. That run does the three canonical cases first, then the seed sweep (seeds 5, 7, 11, 23 at turn 30, 12 settlements in seed 5 alone).
  - `res://client/tests/run_actor_fallback.gd` — `ACTOR FALLBACK: ALL PASSED`
  - `res://client/tests/run_village_test_mode.gd` — `VILLAGE TEST MODE: ALL PASSED` (generated cases, E36B, E17A as John, state restored)
- Blocker: none
- Next: manual visual pass. Do not treat this as visual acceptance.

## Manual cases

Do not treat the automated pass as a look at the maps. These three are the cases to walk.

Village Test Mode, generated, seed 5, turn 30. Reproduce a report with:

`godot --headless --path godot_project --script res://sim/tools/settlement_report.gd -- 5 30 <node>`

### 1. Node 22 — The Fang Wardens steading

John's home steading. 73×55. Forest family: pasture, forest, mountains. One sheepfold, two woodcutter huts, one mine. Sawmill, weaver, smithy, charcoal burner. Housing 5. Core `[21, 16, 31, 23]`. Dressing: 18 trees, 18 pasture, 1 mine mouth, 1 worker camp. Quest: missing flock. Not infected.

Look for: a built centre, woods and a paddock outside it, one modest mine, roads from the exits into the plaza, houses not stuck on the border. One woodcutter hut can still sit well out in the work band.

### 2. Node 8 — The Drover Compact town

113×85. Fields, forest, mountains. Three grain fields, two woodcutter huts, two mines. Mill, sawmill, smithy, charcoal burner. Housing 10, walled, hall and market. Core `[31, 24, 50, 37]`. Dressing: 57 field, 18 trees, 2 mine mouths, 3 camps. Quest: road toll.

Look for: a clearly larger town than the steading, a walled core, field strips that read as stronger than the steading's pasture, two mine mouths, broad exits into the centre.

### 3. Node 16 — The Sukumvit Levy town

113×85. Pasture and hills, infection 3. Two sheepfolds (idle), three clay pits (one idle). Weaver. Housing 10. Core `[31, 24, 50, 37]`. Dressing: 39 pasture, 44 clay, 2 camps, no mines. Three creatures. Quest: tainted well. Overrun.

Look for: clay pits rather than mine arches, scorched ground, creatures still reachable, idle works still standing.

### E17A (authored fixture, not a generated settlement)

Village Test Mode, fixture E17A. Expect John (not Halvard). Miner, Distiller, Reeve and Storekeeper as labels, ids still `a`–`d`. Talking to the Miner should speak before the choice, then play the existing branch lines after a choice. Writing was not revised.
