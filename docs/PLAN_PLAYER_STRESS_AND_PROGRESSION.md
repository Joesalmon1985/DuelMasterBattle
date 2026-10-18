# Plan: branch clean-up, player stress testing, noticing dialogue, duel progression, the rats

Branch `feature/player-stress-and-progression`, cut from `main` at `1b9513dd` (18 Oct 2026). Written before any gameplay change, for the owner's
approval. Merging into `main` stays the owner's call. The content roster stays frozen (D33): everything below is narrative residents, dialogue,
duel rules and client interaction, nothing new from Widelands, OpenRA or Mindustry.

## 0. Where the game stands (18 Oct 2026)

* `main` carries 0.3.0: the free opening, mortal apprentices, the permanent world, the village (rats, the forest and granite disputes, the ranger's
  patrol), the stranger, the Trial of Champions, Mira, LAN play and the Android build. Four-colour PvP duels from each wizard's fourth duel were
  added on 16 Oct (`net/pvp.py` `FOURTH_COLOUR_AFTER`); story duels (mentor, stranger, rats, Trial creatures) still use the wizard's own three
  colours and weave of three (`narrative/wizard.py` `combatant`), and the Trial's Dwarf teaches Stone as a story reward.
* The dialogue audit branch (`analysis/dialogue-story-audit`, 16 Oct) built a runtime-probe harness (32 probes on the real code, seed 507) and
  recorded 20 defects, none fixed: DEF-01 the creed question is lost if the conversation is closed, DEF-02 duplicate "What should I do now?",
  DEF-03 the patrol quest can never be done, DEF-04 two identical log buttons at an empty store, DEF-06 Mira's `you_died_again` never spoken,
  DEF-10 worldview scores never read, DEF-11 seven skill checks cannot fail, DEF-07/08/09/17 shared-state faults in two-player games.
* Baseline on this PC: `test_village`, `test_free_opening`, `test_wizard_duel_lease`, `test_pvp_realtime` pass (43 tests, 9 s). Godot 4.5.1 is at
  `%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe` (console build beside it); `Run Tests.bat` still points at a 4.4.1 path that does not exist.
* Known limits that this plan does not touch: Mira neither fights nor picks things up in the Trial; the Trial's unverified passages; no phone has
  run 0.3.0.

## 1. Branch clean-up

Every branch below is fully contained in `origin/main` (`git branch --merged`, re-checked with `git cherry`). Deleting them loses nothing.

**Delete locally (23):** `BuildPackV03`, `BuildPackV03-ensemble-authoring`, `core-mvp-duel`, `feature/dialogue-e36b-vertical-slice-wip`,
`feature/dialogue-generation-factory`, `feature/mobile-mvp-two-device`, `feature/neuroevolution-plan`, `feature/opening-rpg-and-trial`,
`feature/tech-faster-progression`, `feature/wizard-rts-hybrid`, `feature/wizard-rts-hybrid-v02`, `first-adventure`, `fix/android-playtest-corrections`,
`fix/g04-retained-ui`, `fix/post-merge-followups`, `game-story-overhaul`, `game-world`, `integrate/neuro-lan-wizard`,
`overnight/g12-visual-training-finish`, `phase/g06-g12-autoqa`, `puzzle-system-pass`, `settlements-and-dungeons`, `work/current-main-polish`.

**Delete on `origin` (39):** the remote copies of the above plus `VillageQuestRunnerTry2`, `feature/alternating-duel-flow`,
`feature/duel-mastermind-build`, `feature/encounter-progression-rulesets`, `feature/g05-village-quest`, `feature/hybrid-playtest-fixes-v03`,
`feature/mobile-lan-multiplayer`, `feature/spellbook-ui`, `feature/wizard-duel-polish-web-demo`, `feature/wizard-duel-solver-art`,
`feature/wizard-mode-implementation`, `feature/wizard-settlement-stories`, `phase/g06-historic-mvp`, `refactor/canonical-ontology-g05`,
`work/gameplay-assets-v3`, `work/mechanics-completion-v4`, `work/ubuntu-autonomous-v2`.

**Two of the merged branches are checked out in extra worktrees** that must go first (`git worktree remove --force`): `..\DuelMasterBattle_followups`
(`fix/post-merge-followups`) and `..\DuelMasterBattle_techwt` (`feature/tech-faster-progression`). Both folders hold only the always-dirty files
(`RELEASE_NOTES.md`, `.import` remaps); nothing of value is lost by removing the folders.

**Keep, not merged (the owner's call, my recommendation in brackets):**

| Branch | Unmerged commits | Last commit | Recommendation |
| --- | ---: | --- | --- |
| `analysis/dialogue-story-audit` | 1 | 16 Oct 2026 | keep: the audit's probes and workbook (analysis only) |
| `origin/feature/character-sprites-animation` | 1 | 17 Oct 2026 | keep: fresh work, a layered character sprite system, not yet reviewed |
| `VillageQuestRunnerTry2` (local only) | 1 (WU-14 labels) | Sept 2026 | delete: the remote copy is merged; the extra commit is a Catan-era UI tweak |
| `BuildPackV03-ensemble-depth-pass` | 2 | 17 Sept 2026 | delete: an offline LLM authoring pilot, superseded by the wizard dialogue |
| `origin/test/full-board-dungeon-spatial` | 9 | 23 Sept 2026 | delete: a Catan-era dungeon test fixture |
| `origin/work/visual-sim-qa` | 2 | 1 Oct 2026 | delete: a QA pipeline experiment never used since |

Also two old stashes (`stash@{0}` a stray release-notes edit, `stash@{1}` a pre-G04 preserve) that I would drop with the branches.

## 2. Player stress testing: the misbehaving apprentice

The method is the audit's: small scripts that drive the real game code through the same messages the client sends (`story.dispatch`,
`MultiplayerSession.dispatch`), on seed 507, recording what the world actually says and does. They become a permanent pytest suite
(`WizardRTSHybrid/tests/test_player_stress.py`, one test per scenario, each asserting "the game said something and nothing broke"), plus a few
headed Godot runs for what only the client shows (cards, toasts, the duel board at four slots and six colours). Findings go in
`docs/PLAYER_STRESS_REPORT.md`: scenario, what happened, verdict (fine / silent / wrong / crash), and the fix or the new line it needs.

Scenarios, grouped by the kind of misbehaviour:

1. **Do nothing.** Stand still for 10, 30 and 60 game-minutes. Expect: the stranger comes by the fallback timer, the mentor dies alone, the
   aftermath still closes, the rats eat the store down to nothing, the lessons expire. Check what each villager says afterwards and whether the
   world ever goes silent (nothing to do, nobody with a new line).
2. **Leave at once.** Walk straight to the Trial gate (or off the map edge) before speaking to anyone; enter the Trial with no lessons; die to the
   first creature with nobody to bring you back (Mira does not fight inside). Expect: the ending card, "A new apprentice" into the same world, and the
   village remembering the first one.
3. **Spam.** Talk to the same villager twenty times; press ✦ in an empty field; challenge Mira ten times in a row (she accepts from the third, then the
   account resets); say goodbye mid-question to every speaker (DEF-01's pattern); open and close the pause menu during a cast.
4. **Burn the village.** Burn the warehouse with the rats in it (the keeper's rebuke exists), the mentor's house, every tree and rock around the
   village, the carriers on the road, the mason in the middle of the granite dispute, the ranger before the patrol forms, the woodcutter after
   taking his side. Expect quest substitution or interruption with a journal note each time; check nobody goes silent and the mentor still has
   something to say about a pupil who burns the village.
5. **Quests done stupidly.** Back both sides of the granite dispute; tell the keeper the rats are machines, then duel Mira in the road instead of
   fighting them (the "duelling instead" line fires at two duels); lose to every rat on purpose, repeatedly (the wound flag does not stack: check it
   should not); fight the same rat as Mira at the same time; clear all six waves and keep asking.
6. **Kill and die.** Kill Mira three times, protest to the mother each time, never resurrect; let Mira kill you; die in the Trial twice and
   loot your own previous body with the new apprentice.
7. **The Trial done wrong.** Wrong gem order at Igbut's door until the choices run out; leave by the door and re-enter; register with the Rollkeeper
   and never go in; go in, come out, then burn the gate's contestants (they are residents: are they targets?).
8. **Two wizards (host plus bot).** The shared-state defects DEF-07/08/09/17 reproduced with `scripts/lan_bot.py`: one wizard fails a check and the
   other inherits the memory; both back the mason and the warehouse loses two granite.

Fixes I will make as I go: anything that crashes, loses the player (a stuck scene, a conversation that cannot be left), or contradicts the world
(a dead person spoken to). Defects DEF-01, 02, 03, 04, 06 and the four shared-state ones are in scope; DEF-10 and DEF-11 are handled in section 3.

## 3. Dialogue that notices you (Stanley Parable, Disco Elysium)

What the game already has: a behaviour ledger (kills, deaths, protests, accosted, duels, burned warehouse, fourth-wall count), seven Aspects with
skill checks (Reason, Empathy, Authority, Guile, Resolve, Curiosity, Wonder), seven worldviews, per-speaker regard, hub variants with `lines_alt`,
and exactly two fourth-wall lines in the whole world (a villager's "who counts?" and the Rollkeeper's "why write?"). The principle for every new
line: the world has seen what you did and says so in character; nobody breaks the fiction to lecture, and the rare fourth-wall line stays rare.

1. **The inner voice (Disco Elysium).** A new bank `narrative/dialogue/inner_voice.json`: short interjections spoken by the apprentice's own
   strongest Aspect, shown as a card with the Aspect's name as the speaker, triggered by ledger facts at absurd moments and never more than one per
   two game-minutes, each once per world with `lines_alt` for the repeat. First set (about 25 lines): tenth tree burned (Curiosity: "You have learned
   that trees burn. The lesson is now complete."), warehouse burned with rats in it (Reason), Mira killed a second time (Empathy), ten game-minutes
   with nobody spoken to (Resolve), the stranger watched from 30 tiles away (Guile), the Trial entered with no lesson (Wonder), the same villager
   accosted eight times (Authority), losing to a rat twice (Resolve), the first four-slot duel (Wonder). Mechanism: `narrative/voice.py`, a tick that
   reads the ledger and the Aspects through the existing `checks.py`, and the client shows it through the existing narrative card.
2. **Failed checks that are worth failing (DEF-11).** Seven checks pass for every starting apprentice. I will lower or re-aim four of them so a
   normal apprentice can fail (the mentor's Wonder question already does this well), and give each failure a line that is funnier or more revealing
   than the success, Disco-style. Worldview scores (DEF-10) get read in at least three places: the mentor's judgement scene, the Rollkeeper's roll,
   and the mother after a killing.
3. **The world notices neglect (Stanley Parable).** New hub variants, all driven by facts that already exist or by one new ledger key each:
   * mentor: the pupil who never came (first talk after the lessons expired), the pupil who went straight to the gate; and, in the alone scene,
     a line that knows you were in earshot and stayed away (witness radius exists);
   * mother: the child who has done nothing all day; the child who burned the village (`burned_buildings` key); the third protest;
   * keeper: the store eaten empty ("there is nothing left to defend; you may stop now"), the sixth wave's end (there is no seventh: he says why),
     the rats burned (section 5);
   * the Rollkeeper: writes down everything the ledger holds and reads it back on the second visit, the one place the fourth wall is thin
     ("I keep the roll. Somebody has to.");
   * villagers (`occupations.json`): one "you again" variant per role after the fifth visit, and one line for an apprentice who has been seen
     burning things ("Put that down. I mean the staff.");
   * Mira: her `you_died_again` line wired in (DEF-06); a line when challenged for the tenth time; a line when you stand still for five minutes.
4. **Endings that acknowledge how you got there.** The ending card and the "A new apprentice" lobby text read the ledger: the apprentice who never
   spoke to anyone, the one who burned the village, the Champion who skipped the lessons.

All of it is placeholder prose awaiting the owner, like every bank (`docs/DIALOGUE_REVIEW.md` gets the new rows). Each new variant gets a probe
in the stress suite that proves it is reachable and that it is spoken at most as often as intended.

## 4. Duel progression: from three-by-three to four slots and six colours

Today: the first duels are three slots, three colours (Flame, Frost, Vine). PvP adds Light from each wizard's fourth PvP duel; story duels never
grow; the Trial's Dwarf teaches Stone. The board, the Python rules and Mira's solver all already support up to eight colours and slots
(`game_board.gd` lays out touch-sized slots up to four; `candidate_filter` handles 6^4 = 1296 candidates).

**One ladder for every duel**, in `config.json` under `progression`, counted per wizard on `duels_fought` (every resolved duel: lessons, the
stranger, rats, Trial creatures, PvP; a rat scrap is brief but it is a Ward duel on the real board and it counts):

| After duel | Gain | Colour id | Spoken by |
| ---: | --- | ---: | --- |
| 3 | fourth colour **Light** | 4 | the mentor if alive, else Mira, else the inner voice |
| 5 | **fourth slot** (weave of four) | | the same |
| 7 | fifth colour **Stone** | 3 | the same; skipped if the Dwarf already taught it, in which case Shadow moves up |
| 10 | sixth colour **Shadow** | 5 | the same |

Mechanism:

* `narrative/wizard.py`: `progress(world, seat)` called from every place a duel resolves (`duel_lease.resolve`, the PvP finish in `session.py`,
  `autoduel.play_lease`, the Trial's `on_duel_resolved`): bumps `duels_fought`, applies the next rung with `wizard.learn`, logs `rung_reached`, and
  queues the announcement. The ladder order is Flame, Frost, Vine, Light, Stone, Shadow, matching the Trial's colour names (`trial_mode.gd`
  `COLOUR_NAMES`); `pvp.py`'s `DEFAULT_POOL` (which puts Arcane fifth) is replaced by the ladder.
* `net/pvp.py` `make_format`: the adaptive format becomes "the smaller of the two wizards' colour counts and weave sizes", so neither player meets a
  colour or a slot they have not earned; `FOURTH_COLOUR_AFTER` goes. Named formats (`three`, `classic`) stay for the dev menu.
* `narrative/duel_lease.py` `_combatants` already builds the story opponent from the player's pool and size, so the mentor, the stranger and the Trial's
  creatures grow with the apprentice automatically; the rats keep their two- and three-colour `ward_pool` subsets (a rat is a rat). The mentor's
  told-Ward lesson keeps its fixed three-slot Ward.
* Mira: her challenge acceptance and solver need no change; her `lines` get one entry for a rung ("Four slots. You are showing off.").
* Client: a toast and the narrative card on each rung; the duel board's colour strip shows the new colour on its first duel; the challenge card
  already prints slots, colours and casts.
* Persistence: `duels_fought` and the rungs live in the wizard record that already crosses resets and saves (`narrative.carry_over`, the
  `persist.py` sidecar gets a migration that back-fills `duels_fought` from the ledger for 0.3.0 worlds). GAME_VERSION becomes 0.4.0 (the APK
  version check refuses mismatched presets, so client, host and presets move together); the protocol number does not change.
* Tests: the ladder in isolation; story and PvP formats at every rung; the Dwarf's Stone and the ladder not double-counting; a 0.3.0 save loading
  with the right rung; Mira winning and losing four-slot, six-colour duels on the Python core; a headed run of a four-slot duel on the board.

## 5. The rats: polish, and burning them

Today a rat is a narrative resident fought by standing within two tiles and pressing "Drive it off" (a brief Ward duel). Fire magic
(`magic.py`) burns buildings, units, workers, carriers, trees, rocks and animals, but not residents, so the Burn button never appears on a rat.

1. **Burn a rat.** `magic.fire` learns a `pest` class (the resident table, through `pests.is_pest`); range is fire's three tiles; the effect is the
   explosion the other targets get. Bookkeeping is the won-duel path (`pests.on_duel_resolved`'s win branch, factored out): the rat is gone, `killed_by`
   and the clear count move, waves continue, plus a new `burned` count per infestation. The client's pest card offers "Burn it with fire magic" beside
   "Drive it off" (`wizard_labels.gd`), gated on Flame like every other burn. The big rat takes two burns (the first scorches it and it bolts to a new
   tile, visibly) so the duel stays the cleaner way to deal with it. Burning a rat inside the warehouse's footprint also burns one food ware (the fire
   does not know the difference), which is what the keeper complains about.
2. **The keeper on fire.** New variants: the rats were burned ("I asked for them gone, not cooked, and not my grain with them"), all of them burned
   without one duel, and the mixed case; the `burned` fact and the existing `burned_warehouse` fact are told apart.
3. **The quest is visible.** The infestation joins the journal and objective list (`quests.snapshot` only covers the three templates): "Rats in the
   Central Warehouse: 3 of 5 left, 7 loads eaten" with the keeper's name, from the moment the apprentice walks within sight of the warehouse (an
   announcement when first within ten tiles), not only after talking to him.
4. **Behaviour.** The rats move: a short scurry between tiles around the warehouse every few seconds (`residents` beats), freezing when a wizard is
   adjacent, so they look alive and the "it scurries off" line matches the screen. The big rat is drawn a size larger and labelled. A lost scrap's
   wound shows on the HUD until the next duel heals it.
5. **Loose ends.** DEF-04's duplicate log button; a closing line when the sixth wave is cleared and no more come; Mira's help (she joins after the
   keeper has complained to you) verified in a probe, because the audit could not confirm she ever fights a rat; the keeper's "progress" line reads
   `escapes` so repeated losses are acknowledged.

## 6. Order of work and verification

1. Branch clean-up (section 1), on the owner's yes.
2. Stress suite and report, first pass (section 2, scenarios 1 to 7): one day of probes, the report, the crash and stuck fixes.
3. Duel ladder (section 4) with its tests, then a headed four-slot duel.
4. Rats (section 5), then the two-wizard scenarios (section 2, item 8) since burning and fighting rats together is one of them.
5. Noticing dialogue (section 3), written against the report's list of silent moments, each line with its probe.
6. Verification: `py -3 -m pytest WizardRTSHybrid/tests -q` (the narrative suites after every step, the full suite at the end, about 35 minutes);
   headed `run_headed_suite.sh warehouse` and `run_lan_headed.sh mortality` with `GODOT` pointed at the 4.5.1 console exe (and `Run Tests.bat`
   corrected to it); `check_versions.py` for 0.4.0; the Android APK rebuilt last, install and the two-phone run being the owner's.
7. Ledger `docs/ledger/PLAYER_STRESS_PROGRESS.md`, the handoff note's first section, `docs/DIALOGUE_REVIEW.md` rows for the new banks,
   `docs/OPENING_RPG_PLAYER_GUIDE.md` for the ladder and the burnable rats.

## 7. Decisions wanted from the owner

1. Delete the 23 local and 39 remote merged branches, the two worktree folders and the two stashes? And the four unmerged experiments in the table?
2. The ladder: rungs at duels 3, 5, 7 and 10, rats included in the count. (Alternative: rats count half, or only wizard-versus-wizard duels count.)
3. Burning a rat inside the warehouse costs one food ware and the big rat takes two burns. (Alternative: no cost, one burn for any rat.)
4. The inner voice as a new channel (cards spoken by an Aspect). (Alternative: only the villagers notice; no inner voice.)
