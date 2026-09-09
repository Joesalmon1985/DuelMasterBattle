# CORRECTIVE PASS PLAN — Intro, Combat Progression, Narration & Dungeon

Branch: `game-story-overhaul` (Joesalmon1985/DuelMasterBattle). Builds on the current
Trial-Day / Deathtrap implementation; does **not** revert it. Source brief: "DUEL MASTER
BATTLE — INTRO, COMBAT PROGRESSION, NARRATION & DUNGEON CORRECTIVE PASS" (35 sections).

Working rules for every phase below:

- RED → GREEN: write/extend the test first, run it, watch it fail for the right reason, then implement.
- Keep layers separate: `adventure.gd` (story state) · `overworld.gd` (render/interaction) ·
  `sim/*` (combat + AI) · `bestiary.gd`/`world_data.gd` (data) · `game_board.gd` (UI).
- No enemy-name checks in UI. Policy lives in data + story layer.
- Every phase ends with `tools/run_all_checks.sh` green and one commit.

Inspection notes (current state, verified from source before planning):

| Fact | Where |
|---|---|
| Player combatant always `adv.progression.to_combatant()` | `game_board.gd:156` |
| Result overlay offers "Try again" for any non-victory adventure result | `game_board.gd:1414-1421` |
| Bot logics: `random`, `candidate_filter`, `capped_minimax` (cap) | `sim/weave_bot.gd` |
| Spell ids: Red/Fire 0, Blue/Water 1, Stone 3, Light 4, Shadow 5, Vine 6, (9 in core pool) | `constants.gd`, `world_data.gd` |
| SAVE_VERSION 2; run-reset `fail_run()` sends John to gate | `adventure.gd` |
| Giant Fly = 1 weave / 1 ward / `random` | `bestiary.gd` |
| Two fly encounters: `fly_road1` (trial_road) and `fly_east` (dd_fork, east dead end) | `world_data.gd:336,457` |
| Dialogue: single page, `advance()` closes after typing finishes | `dialogue_box.gd` |
| Fire currently from red book (dd_lower), Stone from Dwarf, Vine from Elf charm | `world_data.gd` grants |

---

## PHASE 0 — Scaffolding: story phase, battle-result policy, player override

Goal: the authoritative state machine and policy hooks everything else hangs on.

### 0.1 Tests first (`sim/tests/test_story_phase.gd`, register in `run_tests.gd`)
1. `new_game()` → `story_phase == "halvard_prologue"`, `protagonist == "halvard"`.
2. `advance_phase("john_intro")` sets phase and `protagonist == "john"`.
3. Illegal transitions (e.g. `trial` → `halvard_prologue`) rejected.
4. SAVE_VERSION 3: a v2 save loads as **invalidated** (returns false, save deleted) — no impossible protagonist/progression state.
5. `trial_ready()` false with Water+weave1; true with 4 spells + weave 3; false with 3 spells + weave 3; false with 4 spells + weave 2.
6. `battle_policy_for(request)` returns category from request data: `PROLOGUE_FORCED_DEFEAT`, `TRAINING_CONTINUE`, `STORY_DEFEAT_TRANSITION`, `TRIAL_STORY_RESULT`, `QUICK_DUEL`.
7. `defeat_count` / `post_trial_recovery_pending` semantics: first story defeat → `left_for_dead` once; second → `post_trial_recovery_pending == true`, phase `post_trial_recovery`.
8. Encounter sequence: `begin_encounter(id)` increments `john_encounter_index` once per id; re-challenging same id does not increment; index 3, 6, 9… flagged `optimal`.

### 0.2 Implement (`adventure.gd`)
1. Add `story_phase` (enum-like strings: `halvard_prologue, john_intro, ashby_training, pre_trial, trial, post_trial_recovery`) + `protagonist`.
2. Add `advance_phase(to)` with allowed-transition table.
3. Bump `SAVE_VERSION` to 3; `load_game()` invalidates <3 explicitly (log + delete) — do not migrate dev saves.
4. Add `trial_ready()` = `flag(has_staff) and weave_size >= 3 and spells_known.size() >= 4`.
5. Add `encounter_sequence: {id: index}` + `john_encounter_index`; `begin_encounter(id)`; `is_optimal_encounter(id)`.
6. Add `story_defeats: int`, `left_for_dead_used: bool`, `post_trial_recovery_pending: bool`.
7. Add `battle_policy_for(request) -> String` (reads `request.policy` if given, else derives from `story_phase` and `request.training`).
8. Keep run/knowledge data model but `fail_run()` no longer teleports to the gate (see Phase 8).

### 0.3 Battle request → combatant override (`game_board.gd`, `battle_sim`)
1. Request may carry `player_combatant: Dictionary` (a `DmbCombatant.to_dict()`); if present, use it instead of `progression.to_combatant()`.
2. Request may carry `enemy_overrides` (weave/ward/bot fields) and `bot_opening_guess` (Phase 5).
3. Request may carry `policy` string. Result overlay:
   - `QUICK_DUEL` → Play again / Menu (unchanged).
   - all adventure policies → single **Continue**; **no Try again**.
4. `_return_to_world` passes `outcome`, `policy`, casts to `adv.report_battle_result`.
5. UI smoke test: assert no "Try again" button exists for any adventure policy; still exists for quick duel.

### 0.4 Narration helper
1. `story_events.gd`: `narrate(text)` → `_w.say("", text)`; all narrator lines route through it (grep for `say(""`, replace).
2. Later phases rewrite the content; this step only centralises.

Commit: `P0: story_phase + save v3, battle policy, player-combatant override, narrate()`.

---

## PHASE 1 — Halvard prologue (brief §1–§4)

### 1.1 Test first (`client/tests/run_adventure_flow.gd` — full rewrite begins here)
1. New game → `story_phase == halvard_prologue`; overworld renders **Halvard** sprite (`blue_mage`), not John.
2. Narration lines are second person (assert opening text contains "You are Halvard").
3. Halvard can walk ≥ 4 tiles in Ashwell.
4. Villager talk lines while `protagonist == halvard` contain no "Blue Wizard passed through" text (assert against a denylist of stale phrases).
5. Walk to trigger → Red intercept. Assert Red entity x < Halvard x ⇒ Red facing `right`, Halvard facing `left` (and vice versa) via `ui_entity_facing(id)` + `ui_john_facing()`.
6. Battle request: `player_combatant.display_name == "Halvard"`, `policy == PROLOGUE_FORCED_DEFEAT`.
7. Board: player weave/ward from Halvard combatant (3 slots), Red solves in ≤ 3 casts (seeded), outcome `defeat`, total sim time ≤ 90 s.
8. After Continue: narration pivot text present ("try again" beat), `protagonist == john`, `story_phase == john_intro`, Halvard corpse + staff pickup exist, John has 0 spells.
9. Take staff → Water, weave 1; `story_phase → ashby_training` on first Ashby talk.

### 1.2 Implement
1. `overworld.gd`: player sprite key from `adv.protagonist` (`blue_mage` vs `john`/`john_staff`).
2. `world_data.gd` village: NPC `lines_phase` variants — lines keyed by `story_phase`; villagers in `halvard_prologue` talk about the famous wizard in front of them, not about him having passed.
3. `story_events.gd`:
   - `prologue_open()` — second-person Halvard intro (original wording, keep the joke).
   - `red_intercept()` — stage Red walking in from the side; set facing by relative x (see Phase 2); request battle with `player_combatant = Halvard dict` (Water+Fire+Stone, weave 3, ward 3), `enemy_overrides` = Red prologue config, `policy = PROLOGUE_FORCED_DEFEAT`.
   - `on_battle_result` for `PROLOGUE_FORCED_DEFEAT`: Halvard death beat (no punchline), narrator pivot (user's line polished), swap protagonist, spawn `corpse` + `staff` pickup at duel site, `advance_phase("john_intro")`.
4. Prologue Red config (`bestiary.gd` entry `red_wizard_prologue`): `capped_minimax`, cap 500, `think_min 3 / max 6`, `min_cast_seconds` low; **prologue-only rule** in request: `enemy_max_casts_to_win: 3` — if solver has not broken by cast 3 the sim is allowed to reveal-and-break (isolated flag `forced_defeat`, only honoured when `policy == PROLOGUE_FORCED_DEFEAT`). Prefer solver strength; the flag is the guarantee.
5. `new_game()` starts at village with Halvard; John's start (`john_intro`) is the duel-site tile.
6. Ensure prologue defeat does not touch `story_defeats`.

Commit: `P1: playable Halvard prologue, forced Red defeat, protagonist swap`.

---

## PHASE 2 — Facing bug (brief §3)

1. Read `_update_john_sprite()` and actor sprite selection; confirm which PNG is `left`/`right` and how `facing` maps. Render a probe scene and **screenshot** both confrontation layouts (Red left / Red right); vision-check: left character faces right, right faces left.
2. Add `overworld.face_each_other(a_id, b_id)` helper used by every cutscene (prologue intercept, gate roster, Throm, Dwarf).
3. Regression test in adventure flow: after intercept, `ui_entity_facing("red") == "right" if red.x < player.x else "left"`, player opposite.
4. Fix sprite generation or mapping if the PNG orientation itself is mirrored (check `build_pixel_assets.py` `draw_human` for left/right).

Commit: `P2: confrontation facing helper + visual verification`.

---

## PHASE 3 — Ashby three-duel arc (brief §6–§8, §23)

### 3.1 Tests first (adventure flow + `test_ashby_training.gd` sim test)
1. Duel 1: John Water/1; Ashby `ashby_lesson1` (1/1); winnable (seeded win) → `ashby_duel1_done`.
2. Duel 2: Ashby `ashby_lesson2` **2 weave / 2 ward / candidate_filter**; John 1 weave ⇒ `player_can_break_enemy() == false`; assert outcome `defeat`; assert location unchanged, spells unchanged, no `story_defeats` increment, no Try again; then `progression.knows(VINE)` and `weave_size == 2` (granted **on defeat** via `grant_on_defeat`).
3. Duel 3: Ashby 2/2; John Water+Vine/2; `is_optimal_encounter("ashby_duel3") == true` (index 3) ⇒ bot uses hard solver; run seeded win AND seeded loss; both set `ashby_training_complete` and `story_phase == pre_trial`; loss leaves location/progression intact.
4. Sim test: with Water-only 1-slot John vs 2-slot Ward, no legal cast can produce 2 exact — mechanically guaranteed loss.

### 3.2 Implement
1. `bestiary.gd`: `ashby_lesson2` → weave 2, ward 2, attack pool [Blue, Vine], `candidate_filter`; add `ashby_lesson3` (2/2, pool [Blue, Vine]); optimal-tier override handled generically (Phase 4).
2. `world_data.gd` Ashby NPC: `choice_event: "ashby_training"` driving the sequence from flags `ashby_duel1_done/2/3`; requests carry `policy: TRAINING_CONTINUE`, `training: true`, `grant_on_defeat: {spell: VINE, weave: 2}` for duel 2.
3. `story_events.on_battle_result` for `TRAINING_CONTINUE`: apply `grant_on_defeat`/`grant_on_win`, mark duel done, return John beside Ashby, Ashby reacts to win/loss (different lines), no reset/day/narration of death.
4. After duel 3 either outcome: `set_flag("ashby_training_complete")`, `advance_phase("pre_trial")`; Ashby offers optional rematch (`policy TRAINING_CONTINUE`, no progression).
5. Remove old `duel_seen`/lesson flow that assumed one Ashby duel.

Commit: `P3: Ashby three-duel training arc with defeat-granted Vine`.

---

## PHASE 4 — Every-third-battle rule (brief §9)

1. Sim test (`test_encounter_sequence.gd`): sequence deterministic; retry of same id no increment; indices 3,6,9 optimal; prologue not counted.
2. `adventure.begin_encounter(id)` called in `overworld._start_battle` **before** request; request gets `encounter_index`, `optimal: bool`.
3. `game_board`: if `optimal`, override enemy bot to the "hard" profile: `capped_minimax`, cap ≥ 100 (use existing `MAX_MINIMAX_POOL_HARD`), `bot_mistake_rate 0`. Not the perfect solver — at least 2 casts behind optimal on average (assert in sim test over seeds vs an uncapped reference).
4. Intro overlay shows "This one is sharper than the last." style line when optimal (data-driven, not name check).

Commit: `P4: deterministic every-third-battle optimal-tier opponents`.

---

## PHASE 5 — Giant Fly redesign + purpose (brief §10–§11)

### 5.1 Tests
1. Sim: Fly = weave 2, ward 2, pool [Blue, Vine, Red]; enumerate **all legal John Wards** at Water+Vine/2; `opening_guess = [Red, Red]` ⇒ 0 exact, 0 colour for every ward.
2. Sim: after opening, candidate set is feedback-consistent and Fly can win a seeded duel against a fixed ward.
3. Flow: beat `fly_east` ⇒ a new exit / pickup appears (assert `ui_entity_exists` or area link).

### 5.2 Implement
1. `weave_bot.gd`: honour `combatant.bot_opening_attack: Array` (legal, used once, then normal logic). Reusable hook — set from bestiary or request.
2. `bestiary.gd` giant_fly: 2/2, pool [Blue, Vine, Red], `candidate_filter`, `bot_opening_attack: [RED, RED]`, description mentions a stupid first lunge.
3. `dd_fork` east branch: on `fly_east` win, `on_win_run_flag: "fork_east_open"` reveals an exit into **Service Tunnels** (`dd_service`) — becomes the dungeon's first shortcut loop (Phase 9). Add a scenic clue there (footprints + reed) so the branch reads as a route.
4. `fly_road1` (trial_road): guards the Burnt Wood entrance — keep, but ensure pool/AI strengthened per Phase 6.

Commit: `P5: Giant Fly is a real threat with a dumb opening; east fork leads somewhere`.

---

## PHASE 6 — Burnt Wood progression, pendant → Fire, shard → Stone, extra pre-Trial magic (brief §12–§14)

### 6.1 Tests
1. Bestiary data test: every Burnt Wood enemy (`flame_imp`, `steam_sprite`, `steam_brute`, `cinder_golem`, `moss_shade`) has weave ≥ 2, ward ≥ 2, non-random logic, and no two share identical (pool, logic).
2. Flow: pick pendant ⇒ knows Fire; beat golem, pick shard ⇒ knows Stone and weave 3.
3. Flow: at gate, `trial_ready()` true after normal route; debug state (Water only) ⇒ Rollkeeper refuses with diegetic line, `story_phase` stays `pre_trial`.
4. Optional-magic test: Light and Shadow obtainable pre-Trial from new optional sites; weave 4 reachable optionally (see decision D2) — **or** skip if D2 answered "no".

### 6.2 Implement
1. `bestiary.gd` Burnt Wood entries: varied pools (Red/Blue/Stone/Vine combos), all 2/2, mix `candidate_filter` + one `capped_minimax`.
2. `world_data.gd`: pendant grant `{spell: RED}`; stone_shard grant `{spell: STONE, weave: 3}`; requires-spell gates updated (steam sprites need Fire ⇒ pendant placed before them).
3. Two optional pre-Trial sites (small, off `trial_road`): e.g. **Healer's shrine** (Light, via a puzzle/duel) and **Hollow under the road** (Shadow) — each with one 2–3 slot guardian; optional 4th weave slot reward only if D2 = yes.
4. Gate: `gate_choice()` calls `adv.trial_ready()`; refusal dialogue from the Rollkeeper ("Four kinds, three knots — that is the floor, not the ceiling…").
5. Progression card text verified against actual state after each grant.

Commit: `P6: Burnt Wood is dangerous; Fire/Stone pre-Trial; trial_ready gate; optional Light/Shadow`.

---

## PHASE 7 — Map edges, dead ends, topology test (brief §15–§17, §31)

### 7.1 Topology test first (`sim/tests/test_topology.gd`, loads `world_data` areas)
1. Every exit `to_area` exists.
2. Destination tile walkable, not an exit, not an entity tile.
3. Direction continuity: exit on north edge ⇒ dest y within 2 of south edge and facing `up`; etc. (edge inferred from exit pos).
4. Reciprocity: for each A→B there is a B→A within 2 tiles of the dest (unless tagged `one_way`).
5. Graph connectivity: all `dd_*` reachable from `dd_entrance` given all flags; `dd_igbut` terminal (only exit back).
6. Dead-end audit: every walkable region ≥ 6 tiles deep that has no exit must contain a tagged entity (`purpose` key) — enforce via a `purpose` field on branch tiles or a per-area `branches` list.
7. Shortcut list (data): each shortcut's exit has `requires_run_flag`/`requires_flag` and both ends exist.

### 7.2 Implement
1. Fix every failing exit pair (expect the bottom-edge → bottom spawn bug and several dungeon pairs).
2. Remove or visibly block fake corridors (`X` rockfall tile / `~` water / `f` fence / `L` logs) — no more "dead end" signs.
3. Dungeon loops (target 3–4, no new rooms):
   - **Fork east ↔ Service Tunnels** (Phase 5).
   - **Basket Man** in Service ↔ Vaults/Inner Vault (vertical lift; needs Ivy paid or Basket man talked).
   - **Reed tube**: Troglodyte river ↔ Drowned Grotto (underwater passage, requires `reed_tube`).
   - **Concealed Trialmaster passage** (`dd_tunnel_tease`) ↔ Lower Route (opens after `trial_done`).
4. Each shortcut tagged in data (`shortcut: true`, `requires_*`) so the topology test can verify.

Commit: `P7: topology test, edge continuity, dead-end removal, 4 dungeon loops`.

---

## PHASE 8 — Defeat policy: left-for-dead once, then Jane (brief §22, §24–§27)

### 8.1 Tests
1. Post-training story defeat #1 (e.g. Cave Troll): no Try again; John wakes **in the same room**, enemy still present, narration "left for dead"; `left_for_dead_used == true`; run continues.
2. Story defeat #2: no Try again; `post_trial_recovery_pending == true`; `story_phase == post_trial_recovery`; automatic transition to `jane_placeholder` scene; placeholder text present; no gate reset.
3. Declining ("Not yet"/"Walk away") never changes defeat counters or phase.
4. Fleeing mid-battle in `STORY_DEFEAT_TRANSITION` counts as defeat; in `TRAINING_CONTINUE` does nothing.
5. Existing dungeon tests updated: `run_dungeon_flow` die-and-restart leg becomes "left for dead, then continue".

### 8.2 Implement
1. `story_events.on_battle_result` dispatch by policy (`PROLOGUE_FORCED_DEFEAT`, `TRAINING_CONTINUE`, `STORY_DEFEAT_TRANSITION`, `TRIAL_STORY_RESULT`).
2. `STORY_DEFEAT_TRANSITION` defeat: if `!left_for_dead_used` → set it, `narrate` wake beat, stay in area (position = pre-battle tile), clear conditions; else → `post_trial_recovery_pending`, fade, `load_area("jane_placeholder")`.
3. New tiny area `jane_placeholder` (one room, no exits, one narration on enter, one "Main menu"-style end). **Nothing more** — explicitly deferred.
4. `fail_run()` reduced to bookkeeping; no gate teleport. Gem-lock third strike routes through the same defeat policy.
5. Remove "Try again" branch from `game_board` for adventure mode (Phase 0.3 covers; verify no other retry path).

Commit: `P8: one left-for-dead wake, then Jane transition; no adventure retries`.

---

## PHASE 9 — Dialogue pagination (brief §19, §32)

### 9.1 Tests (`client/tests/run_dialogue.gd`, add to `run_all_checks.sh`)
short line · long line (> 1 page) · 3-paragraph note · rapid taps while typing · tap finishes page · tap shows next page · final tap closes · choice after long text · **the actual Halvard note text from `dd_entrance`** — assert total displayed characters == source length (nothing clipped/destroyed).

### 9.2 Implement (`dialogue_box.gd`)
1. `_pages: Array[String]` built by paragraph split + measured fit (use `RichTextLabel.get_content_height()` against panel height, or a fixed chars-per-page fallback with word boundary).
2. `advance()`: typing → complete page; else if more pages → next page (re-type); else close + `advanced`.
3. `choose_async` after multi-page prompt waits until last page shown.
4. Test API: `ui_page_index()`, `ui_page_count()`, `ui_visible_text()`.

Commit: `P9: paginated dialogue; Halvard note fully readable`.

---

## PHASE 10 — Puzzle & staging rework (brief §18, §20, §21)

### 10.1 Old-man riddle replacement
1. Design: "How many have walked this gallery today?" — evidence = footprint signs (`dd_prints_west` "several sets", `dd_prints_east` "one set, smaller") + gate roster (six others entered). Answer derivable in-world (e.g. count of distinct footprint sets described). Wrong answer: old man laughs, gives nothing; right: he names which contestant went east (clue feeding Phase 5 route) + torch hint. Never bricks.
2. Test: correct answer sets flag/grants clue; wrong answer leaves progress possible; no TODO text in any player-facing string (grep test: `TODO|verify` absent from `world_data.gd`/`story_events.gd` string literals).

### 10.2 Throm's pit
1. Geometry: pit row of `~`/`X` tiles spanning the room; only crossing is the rope tile.
2. Staging per choice: rope fade + John teleported to far side (lowered by Throm); Throm sprite moves first then John chooses (lower Throm); jump = shake + both moved, `wounded` if chosen "jump" with narration tying wound to landing.
3. Update Throm entity position/state after event; exits on far side `requires_run_flag: pit_crossed`.
4. Test: after each choice, `john_pos` on far side; Throm entity pos/state as narrated; blocked tiles verified via `ui_tile_walkable`.
5. Spelling audit: grep `Thromm|Trom|throm's` inconsistencies.

### 10.3 Hazard audit (rule: keep only hazards satisfying ≥ 2 quality criteria)
| Hazard | Action |
|---|---|
| False eye | Keep, add clue: idol sign describes which eye "watches the door"; wrong eye summons the second guardian instead of arbitrary wound |
| False diamond | Keep with clue from elf ("the real one is cold"); touching false one alerts the Vaults guardian (route change), not a flat wound |
| Trapped chest | Reacts to Stone magic (Stone-known ⇒ safe open, reward) else wound — resource trade-off + clue sign |
| Boulder | Keep "Run!" vs "Hold" but Hold with Stone known = brace safely; add rumble clue |
| Wrong-order gem lock | Keep (positional feedback is the puzzle) |
Tests: each hazard has ≥ 2 defensible responses with different outcomes.

Commit: `P10: coherent gallery riddle, staged Throm pit, hazards with clues and trade-offs`.

---

## PHASE 11 — Narration rewrite (brief §5)

1. Write voice guide `docs/NARRATOR_VOICE.md` (≤ 1 page: dry omniscient, second person, self-correcting, no gag on death/entry/injury beats, no copied prose).
2. Rewrite all `narrate()` strings in opening, Ashwell, Trial road, gate, and dungeon events. Grep audit: player-facing narrator strings containing "John " as subject (should be "you") — test asserts zero outside NPC speech.
3. Remove stale text: "run resets", "try again", "Blue Wizard passed through", third-person John.
4. Progression card copy matches actual grants (test compares card payload to progression diff).

Commit: `P11: second-person narrator pass`.

---

## PHASE 12 — AI tests (brief §33) — `sim/tests/test_early_solver.gd`
1. Enumerate legal Wards for pools {Water}, {Water,Vine}, sizes 1–2; every solver guess legal.
2. Candidate sets feedback-consistent after each register.
3. Every-third assignment deterministic; retry no increment (shares Phase 4 test).
4. Prologue Red solves every legal Halvard ward within 3 casts under the prologue config (seeded sweep) — or the isolated forced flag fires exactly at cast 3.
5. Fly opening = zero matches vs all legal John wards; then normal solver takes over.
6. Hard-tier bot is ≥ 2 casts behind uncapped minimax on average (seeded).

Commit: `P12: early-solver AI tests`.

---

## PHASE 13 — Rewrite end-to-end flows + manual playthrough (brief §30, §34)

1. `run_adventure_flow.gd` full rewrite to the 40-point sequence in brief §30 (prologue → staff → Ashby ×3 → Fly → Burnt Wood → gate rejects underpowered → gate accepts).
2. `run_dungeon_flow.gd`/`run_full_run.gd`: update for one-attempt model (left-for-dead once), new loops, riddle, pit staging, no gate resets.
3. Captures: extend `capture_adventure_qa.gd` (prologue, intercept facing, Halvard death, Ashby ×3 intros, fly intro, pendant/shard cards, gate refusal, pit before/after, Jane placeholder). Contact sheets → vision review with the §34 checklist.
4. Headed manual-style playthrough via realtime harness through Cave Troll defeat → Jane placeholder; fix every §34 defect found.
5. Docs: `docs/CORRECTIVE_PASS_REPORT.md` — architecture changes, gameplay/story changes, modified files, test output, deferred list (Jane wider-world chapter explicitly deferred).

Commit: `P13: rewritten flows, QA captures, corrective pass report`.

---

## Decisions (approved)

- **D1** Red book → weave 4. Dwarf → Trial clue/knowledge item (not Light). Elf charm stays an item with the Boa/Ward interaction. Mirror keeps Light, Bloodbeast keeps Shadow.
- **D2** Pre-Trial: exactly Water, Vine, Fire, Stone; weave max 3. No optional Light/Shadow areas pre-Trial; no weave 4 before entry. Weave 4 is a dungeon reward (red book).
- **D3** Strongest legitimate solver first, plus a strictly isolated `PROLOGUE_FORCED_DEFEAT` backstop (≤ 3 casts) that cannot activate in ordinary battles.
- **D4** After the one left-for-dead wake the enemy remains, marked "watching you"; re-fight allowed; second defeat → Jane.
- **D5** Gem-lock failure is NOT a battle defeat; repeated wrong placements get a comprehensible, recoverable local consequence (no Jane, no gate).
- **D6** Remove run-reset/retry semantics (`fail_run` no teleport, no repeat attempts). Keep `dungeon_knowledge` only as discovery state for the single attempt; delete unused retry plumbing (`start_run` restart path, run-scoped fight reset, gate restart text).

Phase 6.3 (optional Light/Shadow sites) is **dropped** per D2.

## Open decisions (answered above — kept for history)

- **D1 — Dungeon spell rewards now redundant.** Fire (red book), Stone (Dwarf), Vine (elf charm) are all learned pre-Trial in the new progression. Proposal: red book → weave 4; Dwarf test → Light *or* a Ward-reading clue item; elf charm stays a canonical item that bans Vine from the Boa's ward. Light/Shadow move pre-Trial only if D2 says optional sites grant them; otherwise Mirror/Bloodbeast keep them. Confirm.
- **D2 — "Up to 6 magic types and 4 ward slots before the Trial" (§14) vs "do not give John a fourth weave slot before the Trial" (§13, §35).** Proposal: optional pre-Trial sites can grant up to 6 spell *types* (Light, Shadow), but weave stays capped at 3 until inside the Trial. Confirm, or tell me the 4th slot should be optional-obtainable.
- **D3 — Prologue guarantee.** Accept a prologue-only `forced_defeat` flag (fires only under `PROLOGUE_FORCED_DEFEAT` if the solver hasn't broken by cast 3) as the backstop behind a very strong solver? Or require solver-only and accept rare >3-cast prologues?
- **D4 — Left-for-dead wake.** Enemy remains in the room and can be fought again (second loss → Jane), or enemy is gone/wandered (player must route around)? Proposal: remains, marked "watching you"; re-fight allowed.
- **D5 — Gem-lock third strike** routes to the same defeat policy (Jane) — confirm it should not be a separate "run ends" outcome.
- **D6 — Run/knowledge model.** Keep `run` + `dungeon_knowledge` in the save (dormant) as brief allows, or strip now to reduce surface? Proposal: keep, dormant.

## Deferred (explicit)
- Jane's house, dialogue, town, wider-world quest — placeholder room only.
- Full post-Trial victory chapter beyond the existing Champion beat.
- Water-specific dungeon dressing (grotto/river tiles).
