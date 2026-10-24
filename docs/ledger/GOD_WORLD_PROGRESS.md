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
