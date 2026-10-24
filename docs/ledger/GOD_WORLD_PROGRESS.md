# Ledger: God World (0.6.0, branch `feature/god-world`)

The owner's PRD is `docs/GOD_WORLD_PRD.md` (24 Oct 2026, v1.0). Decisions: `docs/DECISION_REGISTER.md` section 7 (D35 to D41). Restart notes:
`docs/NEXT_AGENT_HANDOFF.md`, first section. Base: `feature/polish-watching-feel` at `1e37aef2` (which carries the minigames, the opening RPG and the
polish on top of `main` at `1b9513dd`), so every earlier piece of work rides along; nothing older was deleted. Merging into `main` is the owner's call.

Note on the working tree: the checkout carried uncommitted changes that are not this branch's (the rival's name in the AI wizard, a name prompt in the main
menu, test and data edits, `observations.json`). They were left as they were; `main_menu.gd` was staged as HEAD plus this branch's own hunks. The seven
baseline failures listed below are in those narrative files, not in God World.

## Milestones (PRD section 14)

| Milestone | State | Where |
| --- | --- | --- |
| M0 Reconcile and baseline | done | this ledger (baseline below), `docs/DECISION_REGISTER.md` section 7, `CLAUDE.md`, `WizardRTSHybrid/AGENTS.md`, `wizard_rts/data/god_world/asset_manifest.json` + `tests/test_god_world_assets.py` |
| M1 Executable Catan world | done | `wizard_rts/god_world/` (board, rules, ledger, world, ai, ages), `tests/test_god_world_rules.py`, `tests/test_god_world_ages.py` |
| M2 Mobile observer and villages | done (headed, PC); phone pending | `godot_project/client/god_world/` (camera, view, labels, hud, scene), `client/tests/run_god_world.gd` |
| M3 Physical economic journeys | done | `world.py` (expeditions, caravans with escrow, bank caravans, road crews), `tests/test_god_world_journeys.py` |
| M4 Four-age continuity | done | `ages.py`, `tests/test_god_world_ages.py`, the corpus |
| M5 Autonomous soak and Android | corpus done; APK built (0.6.0); phone unverified | `scripts/god_world_run.py`, `docs/evidence/god_world/corpus.json` |

## What is built (one paragraph each)

**Authority.** `WizardRTSHybrid/wizard_rts/god_world/` is the whole `god_catan_v1` profile: `board.py` (the explicit 30-cell 5-6 layout, 80 nodes, 109
edges, integer corner keys, seeded roles and tokens with 6/8 kept apart, saved as an explicit cell list), `rules.py` + `data/god_world/god_catan_v1.json`
(five roles, costs, odds, timings, the four ages' names, buildings, workers and military art), `ledger.py` (one five-slot hand per faction; reservations,
escrow, cargo; the conservation identity of PRD 8.4 checked by `check()`), `world.py` (`GodWorld`: one clock in 100 ms quanta, snake setup replayed from
real AI decisions, the global 2d6 pulse every 15 s, road crews, founding expeditions over own completed roads, caravans with escrow and a single exchange,
bank caravans 4:1 to an exterior point, the military quota, the AI pass each game second, stall diagnostics), `ai.py` (placement by pips, diversity and
room to grow; a readable decision pass: city, settle, road toward a target, trade for the plan's missing role, bank; wait reasons; `POLICY` is the seam for
a learned controller), `ages.py` (the 10-VP trigger, two villages per faction by theoretical output, one transaction: cancel and refund commitments, archive
hands with receipts, retire the rest, new-age construction, the lower site's starting grant; the fourth age ends with a result), `composition.py` (one
warehouse, `pips * level` stations per touching hex, pairs in age two, the military wedge, parade slots; positions in board units), `snapshot.py`,
`inspect.py` (plain-language labels and details), `session.py` (`GodSession`: the same wire as the Wizard World session plus board, label, inspect, pause,
speed, save, new_world), `persist.py` (JSON saves under `DMB_RUNS/god_world/saves/`, never the wizard's folder). `net/host.py` builds a God World host when
`--profile god_catan_v1`; `net/android_entry.py` does the same for the phone. `HybridWorld` is never constructed in this profile.

**Viewer.** `godot_project/client/god_world/`: `god_camera.gd` (one finger pans past 8 dp, two fingers pinch around the midpoint, wheel and keys, clamped to
the island, zoom from the whole-board fit to a close view; a drag or a pinch never taps), `god_view.gd` (hexes, tokens, roads, villages with their stations
drawn through `hybrid_art.gd` and `AssetLoader`, Mindustry machines on industrial pads, workers, parties, caravans, garrisons; three levels of detail by
zoom with the same ids; picking by draw order and an enlarged touch area), `god_labels.gd` (HIDDEN, LABEL, DETAILS; the label is a 48 dp button anchored
with the world's transform; the sheet is the existing `DmbNarrativeCard`), `god_hud.gd` (age, next roll, the six VP chips, pause, 1x/2x/4x, fit, overlay,
menu, toasts, the age and final cards), `god_world.gd` (hosts the world through `LanSession` with `profile = "god_catan_v1"`, polls `state` every 200 ms
asynchronously, saves on backgrounding and on leaving). The main menu's first entry is **Watch the World**; the Wizard World entries stay below it as
legacy. `Watch the World.bat` opens the scene directly.

## Acceptance (PRD section 15): what is verified, and how

| AC | State | Evidence |
| --- | --- | --- |
| AC01 | verified | `test_android_assets.py::test_the_player_menu_is_god_world_first_then_wizard_world`; `run_menu_routes.gd` (MENU_ROUTES_OK, Watch the World first); `run_god_world.gd` boots the scene with no avatar, lobby or flag |
| AC02 | verified | `test_god_world_rules.py::test_ac02_*` (30/80/109, rows 3,4,5,6,5,4,3, inventory, reciprocity, 6/8 apart) |
| AC03 | verified | `test_ac03_*` (explicit cells round trip; a radius payload is refused) |
| AC04 | verified | `test_god_world_ages.py::test_ac04_*` (snake order, two legal sites each, second-site grant once, reasons logged) |
| AC05 | verified | `test_ac05_*` (controlled rolls: once, twice, nothing on 7 or a desert) |
| AC06 | verified | `test_ac06_*` (36 pairs: five tokens as a settlement, ten as a city, whatever the station count) |
| AC07 | verified | `test_ac07_*` (five roles only; nothing cosmetic has an entry point) |
| AC08 | verified | `test_ac08_*` (charged once, duplicates and unconnected edges rejected without mutation, refunds) |
| AC09 | verified | `test_ac09_*` (2 settlements + 3 cities = 8, then 9, then 10 and one trigger; five cities reach ten) |
| AC10, AC11, AC12 | verified | `test_ac10_ac11_ac12_*`, `test_worst_case_city_layout_*` |
| AC13, AC14 | verified | `test_god_world_journeys.py::test_ac13_ac14_*` |
| AC15, AC16 | verified | `test_ac15_ac16_*`, `test_ledger_vector_*` (escrow, one exchange, replays change nothing, save/load mid-journey) |
| AC17 | verified | `test_ac17_*` (trails for caravans, roads for settlers, bank without port or consent) |
| AC18 | verified | `test_ac18_*` (six factions summing past ten do not trigger; waiting never advances; diagnostics emitted) |
| AC19 | verified | `test_ac19_*` (theoretical output ranks; lucky rolls do not) |
| AC20, AC21, AC22 | verified | `test_ac20_ac21_ac22_*` (ids and warehouses kept, two level-one sites, stock reset, remains hold nothing, reload at the boundary neither repeats nor forks: equal state hashes) |
| AC23, AC24 | verified | `test_ac23_ac24_*` (seed 1 through four ages in one run; garrisons bounded and idle; no second final award) |
| AC25, AC26, AC27 | verified (headed, PC) | `client/tests/run_god_world.gd`: 25 checks, GOD_WORLD_OK (section below); not yet on a phone |
| AC28 | verified | `test_ac28_*` (snapshots, inspections and board views between two identical runs: equal hashes) |
| AC29 | **unverified on a phone** | `build/android/DuelMasterBattle-debug.apk` built from this branch (0.6.0, code 7, 145.9 MB, `ANDROID_APK_OK`, art probe 2565/2565 from the exported pack, packed Python sources); no phone has run it |
| AC30 | verified | the corpus below: 21 seeds, every age within the 600-pulse budget, accounts checked every 60 s of game time |

## Corpus (seeds 0 to 19 and 507, `scripts/god_world_run.py`, 24 Oct 2026)

`docs/evidence/god_world/corpus.json`. Every seed completed all four ages with legal actions and a balanced ledger; no age reached the 600-pulse budget.
Pulses per age: 39 to 90 (10 to 23 game-minutes at 1x; the PRD's first target is 10 to 25). Trades per run: 221 to 394 caravans and 64 to 184 bank
trades. Villages at an age's end: 19 to 34 active, 6 to 22 of them cities. Seeds 3 and 7 re-run with a save/load round trip every 300 game seconds
(`corpus_saveload.json`) gave the same winners, pulses and counters as the plain run. Wall time: 15 to 28 s per seed on the owner's PC.

## Baseline (before this branch's code, `feature/polish-watching-feel` at `1e37aef2`, 24 Oct 2026)

`python -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py`: 1612 passed, 7 failed, 20 skipped in 34m50s. The seven
failures are in the narrative suite and existed before this branch (they match the other session's uncommitted edits to the dialogue data and tests):
`test_mira_trial::test_the_mentor_mentions_mira_when_she_is_near_and_the_scene_gives_her_a_line`,
`test_narrative_conversation::test_a_conversation_has_a_beginning_responses_and_a_declared_end`,
`test_wizard_aspects_worldviews::test_people_are_not_all_the_same_before_the_attack_either`,
`test_wizard_aspects_worldviews::test_helping_someone_earlier_makes_them_more_willing_afterwards`,
`test_wizard_campaign::test_the_aftermath_uses_ordinary_people_who_react_as_themselves`,
`test_wizard_campaign::test_the_final_objective_is_recorded_once_after_conversation_or_the_fallback`,
`test_wizard_campaign::test_every_scene_and_aftermath_line_formats_and_names_exist`. New failures introduced by this branch: none (the God World suites, 29
tests, pass; `test_android_assets.py`, `test_android_packaging.py`, `test_lan_multiplayer.py`, which touch the shared host and menu code, pass).

## Headed evidence (`client/tests/run_god_world.gd`, shots in `docs/evidence/god_world/headed/`, 24 Oct 2026, 450x800 window)

`GOD_WORLD_OK`, 25 checks: the scene hosts the real Python world on this PC and reaches `playing`; state polls arrive; the AIs complete the snake setup
with no input; the clock runs while the camera is still; a village is on screen at start; no missing art at village zoom; a drag that starts on the
warehouse pans the camera and selects nothing on release; a pinch zooms from 0.8 to 1.3 with the world point under the midpoint staying put (0.0 px) and
selects nothing; the first tap on the warehouse shows the anchored label "Ashford / Ashwell · Settlement" (304 x 100 viewport px, over 48 dp); a second
tap on the label opens the details sheet; Back returns to the label; a tap on the ground clears it; a tap at region zoom labels a station; the fit button
shows the whole island (zoom 0.071); 4x speed and pause act on the one clock (game time frozen while paused, resumed after); a journey is on the road;
no missing art after the tour. Shots: `01_setup` (the placements), `02_village_close` (warehouse, yard, flag, districts, a worker, a caravan notice),
`03_pan_before`/`04_pan_after`, `05_pinch_after`, `06_label`, `07_details`, `08_region`, `09_whole_board`, `10_journey`. A phone has not run this.

## Not done, and honest limits

- No phone has run this build (AC29); the Android route is the existing plugin with `profile` passed through, exercised only by the Python host test.
- Frame-time measurement on a device (PRD 13.4) was not possible here.
- The worker routines are a presentation of each district's first row (one walker per district), not Widelands programs; cargo icons are a crate.
- Historical remains keep the old warehouse picture, faded; old roads are drawn as paths.
- Sounds: none yet in God World (the simulation is understandable without them, PRD 7.3).
- The pyratite naming (P09), the carry-over contract (P07) and the reduced Catan subset (P05) are implemented as the PRD's defaults; they remain the three
  owner-facing choices to review.

## Session log (real clock, 24 Oct 2026)

- 12:40 Read the PRD, `CLAUDE.md`, `AGENTS.md`, `world.py`, `host.py`, `session.py`, `android_entry.py`, `board.py`, `hybrid_world.gd`, `hybrid_art.gd`,
  `wizard_labels.gd`, `lan_session.gd`, the catalogue (every id in PRD 5.2 verified present). Baseline suite started in the background. Branch
  `feature/god-world` cut from `1e37aef2`.
- 12:55 to 13:25 The authority: `god_world/` package, data file, headless runner. First run: seed 0 won age one in 39 pulses with 48 trades.
- 13:30 First corpus stalled in every age two: the AI's frontier search treated a faction's own historical roads as still usable. Fixed (only an own
  completed road carries expansion); seeds 0 and 1 then ran through all four ages. Tests written for AC02 to AC28; three test assumptions corrected.
- 13:50 Corpus of 21 seeds clean (above). Host route: `host.py` and `android_entry.py` select the God World by profile; `test_god_world_host.py`.
- 14:05 to 14:40 The viewer: camera, view, labels, HUD, scene, `LanSession.profile`, the menu's first entry, `run_god_world.gd`; the checker is clean except
  the known `LanSession` autoload identifier (as in `main_menu.gd` and `hybrid_world.gd` before this branch).
- 14:45 to 15:05 Headed runs: injected positions are window pixels (the scene reasons in viewport units) and a tap within 250 ms of a pinch is swallowed
  by design; the test now converts and waits. The details sheet got a dark backing (buildings showed through the card's translucent style).
  `GOD_WORLD_OK` (25 checks), `MENU_ROUTES_OK`, `ANDROID_APK_OK` (0.6.0). Committed.

## Living world (the owner's second brief of 24 Oct 2026: natural terrain and living village networks)

Plan and the improvements over the brief: `docs/PLAN_GOD_WORLD_LIVING.md`. Decisions D42 to D47. The brief's screenshot was not attached; the headed
captures of `45ff228f` are the regression reference. Commit `0c16e875` carries stages A to C; the docs and evidence follow in the next commit.

| Stage | State | Where |
| --- | --- | --- |
| A Terrain embedding and rendering | done | `god_world/embedding.py`, `scripts/god_world_embed.py`, `data/god_world/embedding_Egyptian_Mandala_v1.2.json`, `terrain_view.gd` fallbacks, `god_view.gd` |
| B Living villages (ages 1 and 2) | done | `planner.py`, `local_ops.py`, `data/god_world/chains.json`, `god_view.gd` (sites, agents, trees, streets, hubs) |
| C Industry (ages 3 and 4) | done | `planner._plan_industry`, `local_ops` segments, pump, generator, factory; `god_view._draw_segment` |
| D Generalisation, saves, invariance | done | every village is planned by the same planner in normal play; `test_v17_*`, `test_v12_v18_*`, the corpus |
| E Polish and performance | partial | depth sorting by anchor, state effects (smoke while working, a red lamp when short or unpowered, crates at the door); no calibration fixture scene; no device measurements |

### Acceptance (the brief's V01 to V20)

| V | State | Evidence |
| --- | --- | --- |
| V01 | verified (headed) | `docs/evidence/god_world/headed/02_village_close.png`, `09_whole_board.png`: the Egyptian Mandala island with summer-set terrain, water, woodland; no role-coloured hexagons |
| V02 | verified | `test_god_world_embedding.py::test_the_checked_in_embedding_matches_the_map_and_validates` (80 plots, 109 corridors, every corridor joins its logical endpoints) |
| V03 | verified | the same test (plots on buildable ground, at least 0.55 units apart; corridors avoid other plots) and `test_sites_stand_on_buildable_ground_*` |
| V04 | verified | corridors are A* paths over passable tiles with crossing repair (`embedding.validate`); journeys follow them with per-edge times exact (`test_journeys_follow_corridors_and_the_rules_do_not_move`) |
| V05 | verified | `test_v05_capacity_is_a_budget_not_a_copy_count` |
| V06 | verified | `test_v06_workers_perform_routed_tasks_and_face_the_way_they_walk`; headed `02_village_close.png` |
| V07 | verified | `test_v07_a_log_goes_from_a_tree_through_the_sawmill_to_the_hub_and_the_woodland_regrows` (conservation of logs in operating units) |
| V08 | verified (headed) | trucks are the modern age's carriers (`openra.truk`, 32 facings from the simulation's heading); `run_god_world_ages.gd` age 3: goods delivered to the command centre by truck (`headed_ages/age3_village_close.png`) |
| V09 | verified (test and headed) | `test_v09_silicon_and_lead_build_a_unit_within_the_quota`, `test_v11_a_broken_belt_delivers_nothing_and_recovers`; headed age 4 in normal play: "the ground factory mustered a unit from silicon and lead" (`headed_ages/age4_factory_unit.png`) |
| V10 | verified (test and headed) | `test_v10_water_is_pumped_through_the_pipe_and_tank_into_the_cultivator`; headed age 4: a pipe carrying water to the cultivator (`AGES_WATER pipes=1 carrying=1`, `age4_village_close.png`) |
| V11 | verified | `test_v11_belts_carry_spaced_packets_and_back_up_when_the_end_is_full`, the broken-belt test |
| V12 | verified | `test_v12_v18_operating_goods_never_touch_the_hand_*` (no ledger entry point for an operating good; on/off identical) |
| V13 | verified (test and headed) | `test_the_hub_changes_with_the_age_and_stays_one` (store, warehouse, command centre, core / core foundation for a city, one id); `headed/02_village_close.png` (store), `headed_ages/age2_village_close.png` (warehouse), `age3_village_close.png` (command centre), `age4_village_close.png` (core) |
| V14 | partial | anchors and y-sorting per site and agent; industrial pads only under the command centre and the core; no calibration fixture scene |
| V15 | verified | heading from motion in `local_ops._move`; `test_v06_*` checks heading against the position derivative; the old oscillator is gone |
| V16 | verified | `planner.py` scored placement; provenance per symbol in `WizardRTSHybrid/docs/SOURCE_REUSE.md` with the named comparison tests |
| V17 | verified | `test_v17_save_and_load_mid_haul_keeps_jobs_cargo_and_buffers` |
| V18 | verified | `test_v12_v18_*`, `test_the_industrial_layer_does_not_move_the_strategic_game_either`; the bare and the mapped world play the same hour |
| V19 | verified | the 21-seed corpus with the living layer on: every seed through four ages, no stall, 10 to 24 game-minutes an age, 28 to 49 s wall a seed (`docs/evidence/god_world/corpus_living.json`). Bare board, mapped board and mapped board with the living layer play the identical game (seeds 0 and 1 through four ages, same winners and pulse counts). The outcomes differ from the `45ff228f` corpus only because units now have their own id counter (the brief's invariance test needed it): village and journey ids no longer shift when a unit is recruited, which changes deterministic tie-break order, not a rule |
| V20 | partial | normal play builds every network autonomously (the planner is the only path); phone input/export checks: the asset and packaging tests pass, no device run |

### Headed evidence of the ages (`client/tests/run_god_world_ages.gd`, `docs/evidence/god_world/headed_ages/`, 24 Oct 2026)

`GOD_AGES_OK`. For each of the historic, modern and future ages the ordinary scene opened a fresh island in that age (developer start age), the planner
built every village's network in normal play, and the capture waited for goods to move: age 2 carriers carrying loads, age 3 trucks delivering to the
command centre, age 4 belts carrying packets, the water pipe carrying, the ground factory mustering a unit from silicon and lead. No missing art in any
age. Shots: `age{2,3,4}_village_close`, `age{2,3,4}_village`, `age{2,3,4}_overlay`, `age4_factory_unit`.

### Session log (continued)

- 15:10 to 16:40 The second brief. Stage A: the embedding on Egyptian Mandala (The Big Lake rejected: half water); two routing fixes (corridors steer clear of each
  other, crossings repaired; the board's scale and offset searched so nodes are not pushed across lakes); terrain fallbacks for the desert palette; the
  start zoom clamped (a remembered fit zoom had leaked into the headed run); taps converted from window to viewport units in the test.
- 16:40 to 17:30 Stage B: planner, local_ops, chains; every district guaranteed a first producer; woodland planted on mountain sides and beside every plot;
  foresters plant anew. Stage C: belts, pipes, generator, support drills, factory; belts leaving one outlet take turns (the generator had starved);
  units got their own id counter (the strategic invariance test had seen village ids drift). Commit `0c16e875`.
- 17:30 to 18:10 Evidence: corridor leg times made exact per edge (the first living corpus had drifted from the bare one by rounding); agents refreshed on
  re-plan (age-3 carriers had stayed carriers instead of trucks); Mindustry machines scaled to their cells. `GOD_AGES_OK`, `GOD_WORLD_OK`, the corpus.

## Renewal, growth and Pandemic (the owner's third brief of 24 Oct 2026: organic growth, age renewal and the shared campaign)

Plan with the improvements made to the brief: `docs/PLAN_GOD_WORLD_PANDEMIC.md`; decisions D48 to D56 (`docs/DECISION_REGISTER.md` section 9). Built on
the living-villages build (`0b627f43`). Version 0.6.1. The brief's screenshot was not attached; the captures of `0b627f43` were the before reference.

**What is built, one paragraph each.**

*Renewal (D48).* `board.reshuffle_tokens(rng)` shuffles the 28 productive tokens under the keep-apart rule from `world.rng_layout`, a saved stream of its
own; `ages._transition` calls it once, after the ranking that used the old tokens, and bumps `world.production_revision`, which keys every layout cache,
every village's development record and the planner's re-plan; the transition record carries `tokens_before`, `tokens_after` and the revision. Saves carry
the layout stream and the revision, so a save before the boundary replays to the same tokens and a save after keeps them.

*History (D49).* A retired village is frozen by `local_ops.freeze`: the sites it had actually completed, its finished belts and its streets, with its
age; it holds no ops, claims, hand, reservations or VP. The snapshot sends `frozen` for historical villages in the window (the hub alone outside it);
the viewer draws the frozen buildings faded with no smoke, crates, accent or flag, frozen streets and belts faint, and `inspect` answers "Old <name>" for
them. A new village on the node supersedes the frozen hub always and any frozen building its own buildings cover (`_supersede_history`); never two hubs.

*Growth (D50).* `planner.plan` lays the whole eventual network out once as a blueprint: every district's sites carry a `slot` in the mixed sequence
(producer, support, processor, second producer, second processor, the rest) and a `district`. `local_ops.ensure` commissions at founding only the hub, the
military facility, the age's infrastructure (support drills, generator, pump, tank, factory), one seed producer per district and a village allowance for a
first processor (settlement 1, city 3). `village["dev"][region] = {cap, unlocked, receipts}` with `cap = pips x level`; `world._roll` hands every matching
grant to `local_ops.growth_ticket(world, village, region, "epoch:pulse:village:region")`, which unlocks one further place once per receipt, never past the
cap, never for a retired or pending village, and commissions the district's next latent slot. A city raises the cap without filling it. Cities and
carried villages re-seed the same way in the new age (the record is reset at the boundary).

*Construction (D51).* Every commissioned site goes PLANNED, RESERVED, FOUNDATION, BUILDING, then operates: `BUILD_MS` by kind (8 to 20 s), one crew per
settlement and two per city (`builder` agents, the carrier family with a hard hat in the early ages and the OpenRA engineer later), who walk to the
site, work it (the hammer swings) and go home; workers appear only on completion; belts move nothing until both ends stand; `work_done_ms`, `build_ms`
and the state are saved, so a save mid-build resumes the same build. The viewer draws pegs (planned), the cleared footprint (reserved), a low stone
course (foundation), the native Widelands `.build` sheet at the frame of the progress where the roster has one, else the finished sprite revealed from
the ground behind scaffolding, and a progress arc; `inspect` names the stage and the percentage.

*Processing in every age (D52).* `chains.json` adds age 1 charcoal kiln, lime kiln, smokehouse (the tavern), weaving hut and coal-fired smithy (the metal
workshop); age 2 the tavern and the mill; age 3 the graphite press, kiln, separator and pulverizer with support drills for lead and sand. Every age
and every role has a processor (`test_p07_*`). The roster is unchanged: the names in play are adaptations of imported buildings, as the register says.

*Space and sight (D53, brief items 4 to 6).* The command centre's grey rectangle and the core's dark slab are gone: `_draw_apron` lays packed earth and
tyre tracks that fade into the terrain. `_plan_industry` runs from age 3: belts from every drill to its district's processor and from the support
drills, trucks still carry to the command centre; age 4 belts everything to the core as before. The island is `Egyptian_Mandala_v1.2@2x`:
`wl_map.upsample` resamples the map two to one with weighted-majority terrain (coast and class boundaries round instead of stepping), interpolated
heights and resources re-checked against their class; `embedding.build_scaled` places every node at twice its base position (a few tiles of slack for
the smoothed coast), re-routes every corridor on the fine grid and validates (unit 26.74 tiles, no crossings, no poor plots). `DEFAULT_MAP` is the 2x
map; a save made on the base map reloads on the base map with its own embedding.

*Pandemic (D54, D55).* `god_world/pandemic/`: `rules.py` (the published core rules, pure, one JSON-able state with its own generator), `scenario.py`
(the 80 nodes as locations, 109 links, four families by quarter of the island, six field posts at the factions' bases, six responders with the six
published roles), `coordinator.py` (the cooperative mind playing from `public_view`, which hides the decks: cure when a hand allows, concentrate a
family's cards in one collector by sharing and rendezvous, treat the heaviest formations, dispatcher and researcher roles, events when they are worth
more than keeping), `campaign.py` (the bridge: begun when an age runs, one responder turn every 20 game seconds on the shared clock, responders
manufactured at the base facilities under recorded supply contracts in `history["pandemic_contracts"]`, results in `history["pandemic"]`, retry from
the age's checkpoint with a new crisis seed), `presentation.py` (formations in the age's hostile art with enemy livery, responders in the age's art
with a role crest walking their last turn's path along the corridors, posts, the panel, short effects). The viewer draws all of it at the three zoom
levels (`_draw_campaign`), the HUD's campaign panel shows the four countermeasures, outbreaks and rate, deck and posts, whose turn and the gate, and a
lost campaign raises the card with "Retry from the checkpoint" or "A new world" (`retry` op, host only).

*The gate (D56).* `world.gate_open()` is the campaign off or won this age; a ten-point completion with the gate shut records `economic_qualified` (the
first qualifying completion is the cause) and the age waits; the campaign's win then triggers the age with that cause; the other order triggers at
once. A loss pauses the run (`paused`, `pandemic_lost`). `scripts/god_world_run.py --economy-only` keeps the strategic regression; the default run is
the combined one with retries from the checkpoint up to `--max-retries` and honest per-age campaign records.

### Acceptance (the brief's P01 to P24)

| Check | Status | Evidence |
| --- | --- | --- |
| P01 | verified | `test_god_world_renewal.py::test_p01_*`, `test_p02_*`: the multiset, roles, graph and keep-apart hold; the shuffle happens once per boundary from its own stream |
| P02 | verified | `test_p02_*` (ranking on the old tokens, capacities and `dev` on the new), `test_p03_*` (a save before the boundary replays to the same tokens; a save after keeps them) |
| P03 | verified (test and headed) | `test_p04_*`: frozen sites are exactly the built ones, no claims, the picture never changes, build-over supersedes the hub; headed boundary not captured this session (the ages run opens fresh ages) |
| P04 | verified | `test_god_world_growth.py::test_p05_*`: one seed producer per district, repeated `ensure` never fills the blueprint |
| P05 | verified | `test_p05_*`, `test_p06_*`: one place per matching grant, once per receipt, never past `pips x level`; the roll itself is the receipt |
| P06 | verified | `test_p05_*`: an unmatched region, a duplicate receipt and a retired village add nothing; a city raises the cap without filling it (`test_p08_*`) |
| P07 | verified (test and headed) | `test_p08_*` (the lifecycle, one job per builder, nothing works before completion, workers on completion, two crews for a city), `test_p09_*` (a save mid-build resumes); headed age 2 capture shows pegs, footprint and a foundation |
| P08 | verified | `test_p07_*`: a processor in every age for every role; the allowance commissions a first one at founding |
| P09 | verified (headed) | `headed_ages/age3_village_close.png`: the command centre on its earthen apron, no rectangle; the core likewise |
| P10 | verified (test and headed) | age 3 belts from drills to processors (`test_god_world_industry.py` fixtures at age 3 and 4), headed age 3 and 4 captures with packets on the belts and consumption at processors and the factory |
| P11 | verified | `test_v11_a_broken_belt_*`; an unbuilt end moves nothing (`_step_segments` requires both ends built); the viewer draws an inactive belt faded |
| P12 | verified (test) | `test_the_resampled_island_*`: 384 x 384, every node at twice its base separation, every adjacency and corridor validated without crossings; device measurements not taken |
| P13 | verified (test) | `test_p24_*`: six contracts, one per faction, each manufactured after the last; the campaign never reads the garrison (`units` are untouched by `pandemic/`) |
| P14 | verified (headed) | formations drawn per node and family with stable ids `formation:<node>:<family>`, `n` = the canonical count, era art with enemy livery and the family glyph (`headed/11_campaign_formation.png`) |
| P15 | verified | `test_god_world_pandemic.py::test_p15_*`: 80 location cards, four reserves of 24, six roles at six posts, two cards each, four escalations, five events, 3/3/3 with 3/2/1 |
| P16 | verified | `test_p16_*`: four actions, links, flights need cards, treat counts; `IllegalAction` leaves the state untouched |
| P17 | verified | `test_p16_*`: the fourth unit outbreaks to every neighbour, once per location per chain |
| P18 | verified | `test_p18_*`: the bottom card, three units, the shuffled discard on top; the rate track `[2,2,2,3,3,4,4]`; `test_p19_*` the three losses |
| P19 | verified | treat removes the canonical count once (`rules.treat`); the viewer shows the formation's `n`, nothing else can change it |
| P20 | verified (honest) | `test_p21_*`: `public_view` hides the decks. Benchmark (120 crises on seeds 0 and 1's islands, `coordinator.TUNING`): the first coordinator won 35%; with the play habits added afterwards (the dispatcher brokers the researcher to the collector, the medic never collects, a collector near a countermeasure keeps to a post, shorter flights to trouble, the cards seen going back on top at an escalation weighted as coming soon, families near the end of their reserve treated first, the quarantine specialist standing where she shields most) it wins 59% (71 of 120: outbreaks 33, reserve 11, deck 5). Ablations: the broker and the medic rule carry most of the gain |
| P21 | verified | `test_p17_*` (four cures win once; a cured family needs its cards at a post), `test_p19_*` (every defeat condition) |
| P22 | verified | `test_god_world_gate.py::test_p22_*`: ten points first then the campaign, and the campaign first then ten points, each transitions exactly once with the recorded cause |
| P23 | verified | `test_p20_*` (the campaign's state is identical after a JSON round trip and six more turns), `test_p24_*` (a world save mid-campaign replays turn for turn), `test_p09_*` (mid-build), `test_p03_*` (the boundary) |
| P24 | partial | the ordinary viewer runs the 384-tile island on the PC (`GOD_WORLD_OK` with the campaign, `GOD_AGES_OK`); no phone run, no device frame-time or memory figures |

### Corpora (`scripts/god_world_run.py`, 24 Oct 2026, the 2x island, growth on)

- Economy-only (`--economy-only`, `docs/evidence/god_world/corpus_economy.json`): 21 seeds through four ages, no stall; ages run longer than before
  the brief because production places unlock one roll at a time and the island is larger (10.2 to 22.8 game-minutes an age over 84 age results, 33.1 to 55.2 s wall a seed).
- Combined (`docs/evidence/god_world/corpus_combined.json`, retries from the checkpoint up to 6, the tuned coordinator): 21 seeds; 18 complete all four ages, 3 (seeds 11, 15, 18) stop in an age whose campaign was lost seven times running (no seed hit the pulse budget); 81 campaigns won and 76 lost (outbreaks 56, a reserve 14, the player deck 6), 73 retries; a won campaign takes 7.3 to 12.7 game-minutes (median 10.0, 21 to 37 turns); a won age runs 11.8 to 66.8 game-minutes (the long ones waited through lost campaigns); 45 to 157 s wall a seed. Before the coordinator's play habits the same corpus completed 9 seeds with 62 campaigns won and 124 lost (112 retries). Reported as it is.

### Headed evidence (24 Oct 2026, 450x800 window)

`client/tests/run_god_world.gd` (`GOD_WORLD_OK`, shots in `docs/evidence/god_world/headed/`): the age-1 tour as before, then the campaign: six responders
manufactured, formations and six posts on the island, the campaign panel, a tap on a formation labels it (`11_campaign_formation`, `12_campaign_label`,
`13_campaign_board`). `client/tests/run_god_world_ages.gd` (`GOD_AGES_OK`, `docs/evidence/god_world/headed_ages/`): ages 2, 3 and 4 opened fresh on the
2x island, villages growing one place at a time with builders at work, age 3 belts and trucks, age 4 belts, water and the factory, the campaign in
each age.

### Not done, and honest limits

- The coordinator wins about six crises in ten (it won a third before the play habits of 24 Oct evening); the corpus retries from the checkpoint
  and records every loss. Further gains would need real planning over several turns (card routing, outbreak forecasting).
- No phone run and no device figures for the 384-tile island (P24); the PC viewer holds the frame at village zoom.
- A real age boundary with frozen villages is covered by tests, not by a headed capture (the ages runner opens fresh ages).
- The builder's own sprite does not exist in the frozen roster: the carrier with a hard hat and the OpenRA engineer stand in (D51).
- The grey rectangle's screenshot was not attached to the brief; the before reference was the previous commit's capture.

### Session log (continued)

- 18:30 to 19:20 The plan, decisions D48 to D56, the audit of construction and troop art and of the legacy hazards deck (not reused: it recycles the
  discard on exhaustion). Stages 1 and 2 in Python: the reshuffle, frozen histories, development records, blueprint slots, the construction lifecycle
  and builders; the chain tests complete the blueprint through `local_ops.complete_all`.
- 19:20 to 20:00 The viewer: construction stages, frozen villages, the hard hat and hammer, the apron; the 2x island (`wl_map.upsample`,
  `embedding.build_scaled`, 4 s to build); the dressing's search window scaled with the map.
- 20:00 to 21:10 The campaign: rules, scenario, coordinator, bridge, presentation, gate, retry op, inspect, the HUD panel and the loss card; the
  coordinator measured over 60 crises; the headed test's campaign section (a camera focus settles a frame later than the call: position asked after).
- 21:10 to 22:30 Corpora, the ages capture, the documentation, commit `19968f2a`.
- 22:30 onward The owner asked for a stronger coordinator: `coordinator.TUNING` habits benchmarked one by one (`scratchpad coord_bench`), 35% to 59%
  over 120 crises; the combined corpus rerun.
