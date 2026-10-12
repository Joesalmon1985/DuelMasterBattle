# Autonomous civilisation run: status

Owner request of 12 October 2026 (playtest fixes, an improved heuristic AI against the existing one, long headless tournaments,
balance iteration, 16x God Mode spectator). Branch `feature/hybrid-playtest-fixes-v03`; nothing is merged into `main`.
The restart point is `docs/NEXT_AGENT_HANDOFF.md`. Words used below: **done** = implemented and exercised by the named test or
measurement; **partial** = works for the cases named; **not done**.

## P0 baseline (before any change)

- Commit `6ab0a4c`, Ubuntu, 4 cores, Python 3.12.3, Godot 4.5.1.
- `python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py` (run in an isolated git worktree of
  HEAD): **312 passed in 26 min 42 s**.
- A 40-minute primitive (`developer` profile) six-AI game, seed 507, measured with the old rules: every faction stayed in
  **Prehistoric at 1 VP**, held 3 cards, had **no army and no second settlement**; logs piled up (100+) while planks sat at ~21 and
  rations at 0-2. 82 s wall (29x realtime). Cause: one card per 15 game minutes, the MCV behind a four-card Historic chain, and an
  era rule (one faction must gain 6 VP) that could only be met by conquest, so every era change would have come from the stall guard.

## Plan and ledger

| # | Item | State |
| --- | --- | --- |
| 1 | D22 inexhaustible mineral sites (Widelands mines, Mindustry drills), source ledger | done (see below) |
| 2 | Miner quest re-caused by a real gallery collapse; repair by the faction or the wizard | done |
| 3 | Workplace disruptions from collapses and outbreaks; outbreak overflow burns a workplace | done |
| 4 | Settlement unrest from hunger, closures, war, isolation; garrisons and food calm it; splits read it | done |
| 5 | Tech catalogue v2: 32 cards over four eras, offers of up to 7, 4-minute rounds, 3-minute window, lapses logged | done |
| 6 | Era rule: world VP gained since the era began (6/8/10), stall guard 75 min, reasons in the HUD | done |
| 7 | Prehistoric expansion (Settlers card: a wagon from the warehouse) and warriors (war lodge: clubmen, spearmen, slingers) | done |
| 8 | Era unit roster: OpenRA infantry and vehicles by card, Mindustry crawler and nova rules | partial (art pending) |
| 9 | Improved AI `ai_plus.py` and per-faction policy (`world.ai_policy`, `HYBRID_AI_POLICY`) | done, iterating |
| 10 | Tournament runner `scripts/run_civilisation_tournament.py` | done, iterating |
| 11 | Wizard collision with trees and rocks (Python `set_pose` and Godot `is_walkable`) | done, headed check pending |
| 12 | Label overlap (response buttons over the description), passive label clutter | done, headed check pending |
| 13 | Quest/healer discoverability (worker sprites, names, "!" marker, objective line, outbreak status, labelled region) | done, headed check pending |
| 14 | God Mode spectator HUD (era reasons, faction table, 7-card draft panel, event feed, pause/speeds, explicit Take control) | done, headed check pending |
| 15 | Licensed art for new units/buildings (OpenRA SHP from conquer.mix, Mindustry sprites) | not done |
| 16 | `launch_scenario.sh autoplay` and a headed 16x autoplay test | not done |

## Changes that were bugs, found by simulation

- **Red was crippled in every game**: the road planner let a new road run along any road at its endpoint, so the tavern road shared
  the tile of the retained Ward Duel hazard and its carrier stood blocked forever. A new road may still join an endpoint's roads
  (the hybrid has no flags) but never through a tile a carrier cannot pass. Test: `tests/test_road_path.py`.
- Performance: the road A* rebuilt a 20k-tile set union per search; the tribe planner retried every failing placement every 5 s.
  The A* now uses flat arrays (paths identical to the old code, compared in `tests/test_road_path.py`) and failed tribe placements cool
  down for 60 s. A 30-minute mixed game went from 12x to 24x realtime.

## Stop point (session usage limit, 12 Oct 2026)

Committed as an UNVERIFIED checkpoint: the full suite was not re-run green on the final tree (the last full run hit a sync fault).
Verified individually: test_story_slice, test_civilisation_rules, test_road_path, test_ai_behaviour, test_quest_env, test_dungeon_env,
test_training_smoke, test_fullgame_env, test_outbreaks, test_outbreak_env, short test_campaign_tech; headed run_hybrid_playtest2 passed.
Smoke tournaments (2 seeds x mirrored x 40 min, ~/dmb_runs/civ_smoke{1,2,3}): improved AI won 3.5-0.5, 3-1, 4-0 by VP; every game
reached Historic by VP (no stall guard); natural splits occurred; too many early collapses (fixed after: capital militia now actually
fires, Concrete capitals, 2000 HP), ledger leaks fixed (destroyed wares, founder cargo).

Next, in order: 1) sync + full pytest (expect fixes for test_campaign_tech 40-min and anything touched by militia/HP);
2) headed `run_headed_suite.sh autoplay outbreak playtest2` (autoplay now opens God Mode with G; measure 16x pace);
3) 10-seed x 120-min mirrored tournament + crisis mode with --wizard-pilot, write BALANCE_REPORT.md;
4) check Modern/Dystopian reachability (~/dmb_runs/civ_hist1 was interrupted); 5) update NEXT_AGENT_HANDOFF.md.
Rule learned: never `pkill -f`/grep-kill a pattern that appears in your own command line; kill exact PIDs.
