# Player stress, noticing dialogue, the magic ladder and the rats: progress ledger

Plan: `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md` (approved by the owner 18 October 2026, with the ladder revised the same day: world state, duels or
play time, interrupts). Branch `feature/player-stress-and-progression` from `main` at `1b9513dd`. Report: `docs/PLAYER_STRESS_REPORT.md`. Merging into
`main` is the owner's call.

Legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## 1. Branch clean-up
- [x] 25 local and 42 remote branches that were fully merged into `main` deleted (list in the plan, section 1); the two extra worktrees
  (`DuelMasterBattle_followups`, `DuelMasterBattle_techwt`) removed; two stale stashes dropped; the four old unmerged experiments deleted on the owner's word.
  Kept: `main`, `analysis/dialogue-story-audit`, `origin/feature/character-sprites-animation`, this branch.

## 2. Stress suite
- [x] `WizardRTSHybrid/tests/_stress.py`, `tests/test_player_stress.py`: fifteen scenarios through the real `MultiplayerSession` (seed 507, one human and
  Mira), observations in `WizardRTSHybrid/docs/evidence/stress/observations.json`, verdicts in the report.
- [x] Crash fixed: the second barbarian at the gate had no speaker (`trial/run.py`).

## 3. The magic ladder (`narrative/progression.py`, `data/narrative/dialogue/progression.json`, `config.json` `progression`)
- [x] World state `narrative["progression"]`: duels (every resolved duel by anyone), `played_ms` (game time while a human is present, not the catch-up), rung,
  history, pending announcements. Rungs: Light at 3 duels or 12 min, a fourth slot at 5 or 25, Stone at 7 or 40, Shadow at 10 or 60, whichever first.
- [x] Floors: `wizard.combatant` (story duels) and `pvp.make_format` (adaptive PvP) read the ladder; `DEFAULT_POOL` is the ladder's order (Flame, Frost, Vine,
  Light, Stone, Shadow); an authored Ward (the told lesson, a creature) keeps its own size; the Dwarf's Stone is a personal extra, not counted twice.
- [x] Persistence: carried across a cycle reset, saved with the world, back-filled for 0.3.0 worlds on first use, narrative version 3 (identity migration).
- [x] Delivery: the session tells the rung the moment the wizard is not on a duel board (`_deliver_rungs`), closing any conversation; speaker is the mentor if
  alive, else Mira, else the apprentice's strongest Aspect; `state_view["progression"]`, the journal's `magic` section.
- [x] `tests/test_progression.py` 9 passed; `test_mortality`, `test_pvp_realtime`, `test_lan_multiplayer`, `test_ai_wizard` and the Godot test scripts moved from the
  old Stone-based three-colour pool to Flame, Frost, Vine.

## 4. The rats (`narrative/pests.py`, `magic.py`, `warehouse.json`, `residents.py`)
- [x] `magic.fire` burns a rat (class `pest`); a small rat burns outright, the big one is scorched and bolts first; a rat burned beside the store takes one
  food ware (`narrative:burned` bin); counts `pests_burned`, `burned` per infestation, `food_burned`.
- [x] A destroyed warehouse scatters the rats and ends the infestation; no wave comes to a ruin; the keeper's `ruin` line.
- [x] The keeper thanks per wave (`said_cleared` reset at each new wave), says when the waves are over, minds the burned rats, the empty store, a run of losses.
- [x] Journal entry (`pests.journal`, in `tutorial.snapshot` `quests`) from the moment the apprentice is within ten tiles of the store or has been told, with
  a `pests_noticed` notice; the rats scurry every four seconds and freeze beside a wizard.
- [x] `tests/test_village.py` 21 passed (six new).
- [x] Godot: the rat's card offers "Burn it with fire magic" beside "Drive it off", names the big one and its scorch; toasts for a burned rat, the scorched big one,
  the scattered rats, the journal entry.

## 5. Noticing dialogue (plan section 3)
- [x] Mechanics: the ending waits up to 150 s while a living AI apprentice can walk to the body (`session._rescuer_coming`, `you_dead.rescuer`); a scene nobody
  answered becomes `confrontation_missed` and a page that asks nothing gives way when the player talks to somebody (`campaign.dismiss_if_idle`); a lone
  apprentice's stranger walks in after the grace whether or not the notice was read; the arson ledger (`narrative/deeds.py`); `talks`, `visits`,
  `idle_minutes` (the gap before the act in flight), `generation`, `previous`, `played_minutes`, `food_left` as facts for everyone (`conversation.common_facts`);
  absent ledger keys read as 0 (`my_trial_entries` etc. were `None` before, so the Rollkeeper's unprepared line never fired).
- [x] The inner voice (`narrative/voice.py`, `dialogue/inner_voice.json`): 14 triggers spoken by the apprentice's Aspects, one per world per wizard (two for idleness),
  two game-minutes apart, never over a duel or a scene; delivered as an `inner_voice` notice to that wizard alone; the client shows it as a card.
- [x] New lines (placeholder prose): the mentor (never came, second generation, arsonist on a first meeting and later, tree burner, absent, empty store), the
  mother (arson, burned village, idle, empty store, second generation), the Rollkeeper (arsonist, still here, second generation), a second-visit line per
  contestant, the villagers ("you again" after five visits, seen burning, the smell of trees, a quiet day), the keeper (section 4), Mira (idle, forfeit,
  burned someone, burned the store), the rung announcements (`progression.json`).
- [x] `tests/test_noticing.py` 12 passed.

## 6. Client (`godot_project/client`)
- [x] `campaign_ui.gd` notice card (queued, Continue); `hybrid_world.gd` handles `rung`, `inner_voice`, `pests_noticed`, `pest_scorched`, `pests_scattered`,
  burned `pest_killed`; the death card names the rescuer and the forfeit; `story_ui.gd` journal "MAGIC IN THIS WORLD"; `wizard_labels.gd` Burn on a rat.
- [x] `run_lan_parse.gd` HYBRID_LAN_PARSE_OK on Godot 4.5.1 (Windows) after the changes.
- [x] Headed `run_headed_suite.sh warehouse` (Godot 4.5.1, Windows, a fresh simulator): PASS with the Burn button on the rat's card and the keeper's new lines; the two leaked `wizard_rts.server` processes were stopped by PID afterwards (the known Windows pitfall).

## 7. Versions and build
- [x] GAME_VERSION 0.4.0, Android version code 4, protocol 3 unchanged; `check_versions.py` VERSIONS_OK.
- [ ] APK rebuilt (see the session log).

## Session log (newest first)

### 18 Oct 2026, evening (Windows 11, Python 3.14, Godot 4.5.1 console build at `%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe\`)
* Regression over the narrative, duel, Trial, party, LAN and save suites plus the stress suite: 208 passed, 2 failed, both explained and gone: the placeholder
  validator did not know the new common facts (`previous` and friends, now listed), and the two-process LAN test collided with the headed run's simulator
  (passes alone). `test_noticing` 12, `test_progression` 9, `test_village` 21, `test_player_stress` 15, `test_narrative_quests` 16 all pass.
* Godot headless `run_lan_parse.gd`: HYBRID_LAN_PARSE_OK (every client script parses; the net duel mirror at three and four colours in the ladder's order).
* Headed `warehouse`: PASS (see section 6).
* Commits on the branch: the plan (two), the stress suite and report, the ladder and the rats, and this session's noticing dialogue, mechanics, client and docs.
* APK: see the next entry.
