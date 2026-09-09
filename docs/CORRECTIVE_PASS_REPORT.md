# Corrective Pass — Report

Branch `game-story-overhaul`. Source brief: "DUEL MASTER BATTLE — INTRO, COMBAT
PROGRESSION, NARRATION & DUNGEON CORRECTIVE PASS". Plan and approved decisions
D1–D6: `docs/CORRECTIVE_PASS_PLAN.md`. Every phase was done test-first (RED → GREEN);
`tools/run_all_checks.sh` is green at the final commit.

## 1. Architecture changes

| Layer | Change |
|---|---|
| `adventure.gd` (story state) | `story_phase` state machine (`halvard_prologue → john_intro → ashby_training → pre_trial → trial → post_trial_recovery`) with a transition table; `protagonist`; `SAVE_VERSION 3` — older saves are discarded, not migrated. `trial_ready()`. Encounter numbering (`begin_encounter`) with the every-third **optimal** tier; prologue never counts; retries keep their number. `story_defeats` / `left_for_dead_used`. `battle_policy_for(request)` → `PROLOGUE_FORCED_DEFEAT · TRAINING_CONTINUE · STORY_DEFEAT_TRANSITION · TRIAL_STORY_RESULT · QUICK_DUEL`. Run model reduced to a single attempt (`fail_run`, gate teleport, fight-reset removed — D6). Journal `notes` (`add_knowledge`). |
| `story_events.gd` (story logic) | Prologue (`prologue_open`, `red_intercept`, `_prologue_defeat`), Ashby three-duel arc (`ashby_training`, `_ashby_after`), defeat dispatch by policy (`_training_defeat`, `_story_defeat` → left-for-dead once, then `jane_wake`), `basket_ride`, `trapped_chest`, reworked `statue_riddle`, `throm_pit`, `false_eye`, `false_diamond`, `boulder_run`. `narrate()` centralised. |
| `overworld.gd` (render/interaction) | Player sprite keyed by `protagonist`; NPC `lines_phase` / `lines_run_flag`; readable `text_run_flag`; exits gated by `requires_run_flag` / `blocked_by_run_flag`, optional `travel_text`, `shortcut` tag; triggers `requires_phase`; `face_each_other()` + `ui_actor_facing()` reads the *texture actually assigned*; `start_battle_request()` for story-started battles; data-driven `WARD_BANS` (multiple bans per enemy); `_entity_text()`. |
| `sim/battle_sim.gd` | `forced_defeat_by_cast` — **prologue-only backstop** (D3): 0/off for every ordinary battle; set solely by the board under `PROLOGUE_FORCED_DEFEAT`. When on, enemy cast N breaks the player's Ward if the solver hasn't already, and the player's casts cannot break the enemy's. |
| `sim/weave_bot.gd`, `combatant.gd` | `bot_opening_attack` — an authored, legal first cast (Giant Fly's stupid lunge), then normal solving. |
| `game_board.gd` (UI) | Player combatant override from the request (Halvard); enemy overrides; optimal-tier bot profile; single **Continue** for all adventure policies (no "Try again"); optimal-tier intro line driven by data, not names. |
| `dialogue_box.gd` | Paginated: paragraph split + measured fit; tap = finish page → next page → close; choices wait for the last page; test API `ui_page_index/count/visible_text`. |
| `bestiary.gd` | `red_wizard_prologue` (3/3, capped_minimax 500, fast), `ashby_lesson1/2/3` (1/1, 2/2, 2/2), `giant_fly` (2/2, opening `[RED, RED]`), Burnt Wood roster all ≥2/2 with distinct pools/logics. |
| `world_data.gd` | Village prologue staging + phase-keyed villagers; corpse + staff spawn; Ashby NPC drives the arc; Burnt Wood pendant→Fire, shard→Stone+weave 3; D1 dungeon rewards (red book → weave 4, Dwarf → map/knowledge, elf charm stays an item); 4 gated dungeon loops; hazard clues; dead `forest_home` area removed; two pointless pockets sealed; dwarf-door landing fixed. |
| `tools/build_pixel_assets.py`, `tools/check_facing.py` | **Facing root cause**: the sprite pack's `Left.png`/`Right.png` are named for the sheet side, not the facing (both `Left.png` files face right). All right-facing sprites are now exact mirrors of a visually-verified left master; `check_facing.py` enforces it in `run_all_checks.sh`. |

Layer separation preserved: no enemy-name checks in UI; policy in data + story layer; sim knows nothing about the story except the isolated backstop value.

## 2. Gameplay / story changes

1. **Prologue as Halvard.** New game: "You are Halvard." Villagers recognise him. Walking onto the road brings the Red Wizard in from the east; they face each other (verified from textures). Halvard weaves three; Red solves in ≤3 casts (seeded: solver alone ≤3 in every legal Ward; backstop guarantees it), duel ≤90 s, no "Try again". Halvard dies; the narrator restarts ("Okay. That didn't work. Let's try again."). John begins where the body lies; body + staff present; prologue loss touches no defeat counter.
2. **Staff → Water / weave 1.** Then **Ashby ×3**: win 1v1 → lose 2v2 with one slot (mechanically impossible to win; Ashby grants Vine + weave 2 *on the defeat*; John stays put) → duel 3 is John's third battle = optimal tier; either result completes training → `pre_trial`.
3. **Giant Fly** is 2/2 with an authored zero-match opening. Declining ("Walk away") never counts as a defeat.
4. **Burnt Wood**: fires doused with Water; imp guards the pendant (Fire); golem guards the shard (Stone + weave 3). Normal Trial-entry state: Water+Vine+Fire+Stone, 3 knots. The Rollkeeper refuses anyone under that (tested with a debug save).
5. **Dungeon rewards (D1)**: red book → fourth weave slot; Dwarf test → map + knowledge; Mirror → Light; Bloodbeast → Shadow; elf charm remains an item (Manticore Vine ban).
6. **Defeats**: first real defeat → wake where you fell, enemy "watching", re-fight allowed; second → fade to Jane placeholder. Gem lock third strike scatters the gems (recoverable; never Jane — D5).
7. **Loops (brief §29)**: fork east shaft ↔ Service Tunnels (opens on the Fly's death), Basket lift Service ↔ inner vault (after paying Ivy or freeing the prisoner), reed tube river ↔ grotto, Dwarf's staff passage Trialmaster ↔ Manticore gate (after `trial_done`). Reciprocity + gating tested.
8. **Hazards with clues and trade-offs**: statue riddle is derivable (150; right → the Manticore hates Light → Light banned from its Ward; wrong → wounded); pit "climb alone" → wounded + torch lost; idol base says WEST EYE (wrong eye wakes the second guardian, not a random wound); elf's "the real one is cold" → false diamond bolts the inner vault (Basket lift becomes the way); chest and boulder answer to Stone magic, and the floor tells you where to stand.
9. **Dialogue** paginates; the Halvard note displays in full.
10. **Narration**: second person throughout; stale phrases purged; `docs/NARRATOR_VOICE.md`.

## 3. Modified files

See `git diff --name-only 35e5866~1 HEAD`. Core: `adventure.gd`, `game_board.gd`, `overworld.gd`, `story_events.gd`, `world_data.gd`, `dialogue_box.gd`, `battle_sim.gd`, `weave_bot.gd`, `combatant.gd`, `bestiary.gd`, `build_pixel_assets.py`, `check_facing.py`. New tests: `test_story_phase.gd`, `test_early_solver.gd`, `run_dialogue.gd`, `run_topology.gd`; rewritten: `run_adventure_flow.gd`, `test_trial_run.gd`, `test_asymmetric_battle.gd`; updated: all dungeon flow tests, `capture_adventure_qa.gd`, `run_all_checks.sh`.

## 4. Test results (final commit)

```
facing audit: 34 left/right pairs checked, 0 wrong
Passed: 14  Failed: 0            (sim: story phase, early solver, trial run, …)
UI SMOKE: ALL PASSED
DIALOGUE: ALL PASSED
TOPOLOGY: ALL PASSED
ADVENTURE FLOW: ALL PASSED       (prologue → staff → Ashby ×3 → Fly → Burnt Wood → gate refuses/admits)
DUNGEON FLOW: ALL PASSED         (+ left-for-dead, riddle, hazards, 4 loops)
DUNGEON P3/P4/P5/P6: ALL PASSED
FULL RUN: ALL PASSED             (single attempt, in-game-earned magic only)
REALTIME PLAYTEST: ALL PASSED
```

QA captures: `qa/screenshots/adventure/04_prologue_text.png`, `05a/05b/05c_red_intercept_*.png` (facing vision-verified: Halvard left faces right, Red right faces left), `06_john_over_the_body.png`, `07_pickup_dialogue.png`, `08b_ashby_workshop.png`, plus the existing dungeon zone shots.

## 5. Deferred (explicit)

- **Jane's chapter** — house, dialogue, town, wider-world quest. Placeholder room + one narration only.
- Post-Trial victory chapter beyond the Champion beat.
- Water-specific dungeon dressing (grotto/river tiles).
- Pit *staging* (rope tile geometry, Throm sprite moving first) — the choice, consequences and flags are in; the on-screen choreography is prose.
- p.149 stays `NEEDS_PAGE_IMAGE_CHECK`; the riddle's number is self-contained, not asserted as book canon.
- Fleeing mid-battle under `STORY_DEFEAT_TRANSITION` is not yet counted as a defeat (the intro "Walk away" is a decline, by design).
- A headed, human playthrough. All verification here is headless + vision review of captures.
