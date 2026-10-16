# Opening RPG and the Trial: progress ledger

Plan: `docs/PLAN_OPENING_RPG_AND_DEATHTRAP.md` (signed off 16 October 2026, defaults D1 to D11 accepted). Branch `feature/opening-rpg-and-trial` from
`main` at `e6e6399b`. Tick a task only when its tests pass; evidence on the same line. Session log at the bottom, newest first.

Legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## M0 Baseline and measurements
- [x] Full Python suite on the branch before any change: see the session log (counts and pre-existing failures).
- [x] Legacy zones and bestiary exported to JSON: `godot_project/client/tools/export_legacy_zones.gd` -> `WizardRTSHybrid/wizard_rts/data/trial/legacy_zones.json` (17 zones), `legacy_bestiary.json` (25 opponents). Parity: the export is produced by the GDScript tables themselves.
- [x] Catch-up cost measured on the PC (`WizardRTSHybrid/scripts/bench_catchup.py`, small map, seed 507, AI on, narrative on, Python 3.14): 0.3-0.7 s per simulated minute in the first 10 minutes, 1.6-1.9 s per simulated minute at 30-60 minutes (241 buildings); 60 simulated minutes in 75 s. Evidence `WizardRTSHybrid/docs/evidence/opening_rpg/m0/catchup_small_pc_60.json`.
- [ ] Catch-up cost measured on a phone (no phone attached in this session; the owner runs `bench_catchup.py` through the APK's self-test or the PC numbers x3 stand in).
- [x] Trial canon status table, first version: `docs/TRIAL_CANON_STATUS.md`.

## M1 Mortal apprentices
- [x] `narrative/ledger.py` (behaviour counts) and `narrative/mortality.py` (death, bodies, resurrection channel, spectating refusals, endings); `campaign.game_over` routes through `mortality.die` (no game_over stage, no pause token; the classic server marks a death terminal); `persist` saves the dead; `resurrect` op in `story.WIZARD_OPS`, `protocol.PLAYER_OPS`
- [x] The mother: `narrative/mother.py`, `data/narrative/dialogue/mother.json` (facts from the ledger: grounded, kills, protests, resurrections, deaths), grounding refusals on `move` (`reason: grounded`, her line), she walks over and opens the conversation herself (a `conversation` notice), escalation on the second killing
- [x] Mira: declines `accept_after_challenges` (2) challenges then fights seriously; dies and is resurrected like anyone; walks to a dead human's body and resurrects when the game goes on; lines in `data/ai_wizards.json`
- [x] No pause token for duels in Wizard World (`session._respond`); `test_lan_multiplayer` updated
- [x] Godot: `hybrid_world.gd` dead mode (hidden avatar, banner, Watch button, controls off), resurrection ring and orbit with sounds, the ending card (Leave), the mother's speech as a conversation card and as the move refusal toast; `wizard_labels.gd` "Bring them back" on a body; `campaign_ui.gd` leaves the ending to the session in a hosted world
- [x] `tests/test_mortality.py` 14 passed; `test_ai_wizard`, `test_wizard_party`, `test_wizard_campaign`, `test_wizard_save`, `test_lan_multiplayer`, `test_pvp_realtime` and the narrative suites green after the rule change (the old Game Over assertions rewritten). Headed `run_hybrid_mortality.gd` (`scripts/run_lan_headed.sh mortality`): PASS on Windows, Godot 4.5.1, 720x1280; shots `WizardRTSHybrid/docs/evidence/opening_rpg/m1/mortality_{body,mother,inspect_body,channel,alive}.png`

## M2 The permanent world
- [ ] Save with the dead; `new_wizard`; menu wording; explicit "Start a new world"; guest protection
- [ ] `closed_at`, the debt, catch-up at the menu, write-off before clients enter
- [ ] Durability: version in the payload, migrations, daily `.prev`, load report
- [ ] The campaign in an old world, spoken by people; journal out of the player build
- [ ] `tests/test_permanent_world.py` (the eight acceptance tests); headed `run_hybrid_new_wizard.gd`

## M3 The free opening
- [ ] Training as an activity; arrival conditions; confrontation variants; optional challenge; stranger's departure to a recorded place
- [ ] Mentor's ledger-aware lines; what-you-missed by people; humour pass one
- [ ] Tests updated; headed `run_hybrid_opening.gd`

## M4 The village
- [ ] Warehouse infestation: pests, disruption factor, keeper, leases, Mira joining, recast
- [ ] Three situations and the foreshadowing; humour pass two
- [ ] `tests/test_village_situations.py`; headed `run_hybrid_warehouse.gd`

## M5 The Trial, first half
- [ ] `wizard_rts/trial/`: run, zones, positions, shared items, triggers, choices, conditions, leases, death, run end and reset
- [ ] The gate with official and contestants; zones A to D; pocket strip; drawn by the legacy tile builder in the hybrid scene
- [ ] `tests/test_trial.py`; headed `run_hybrid_trial_a_d.gd`; canon table updated

## M6 The Trial, second half
- [ ] Zones E to K; spell and weave growth; the champion's exit
- [ ] `run_hybrid_trial_full.gd`; `test_trial.py` extended; canon table updated

## M7 Mira in the story and the Trial, humour pass three, polish
- [ ] Mira's goals; Trial adaptations for a human plus Mira; variety and the fourth wall; placeholder line banks marked for review

## M8 Android and the two-phone acceptance
- [ ] APK build, asset audit, exported-pack probe, two-phone checklist extended, build and test instructions

## Session log (newest first)
- 16 Oct 2026 (session 1): M0 done (baseline suite, zone export, PC catch-up measurement, canon table), M1 done (Python and Godot, headed PASS). Next: M2.
