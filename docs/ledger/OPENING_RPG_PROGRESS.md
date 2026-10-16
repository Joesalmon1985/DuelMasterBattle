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
- [x] The installation's world: `host.prepare_world` loads the newest save whenever the app passes `--runs-dir` (a world is built only when none exists; a save the code cannot read is an error, never a silent restart); `party.retire` (generations: `gone:<seat>:<n>`, the host's actor id moves to `player:N`, bodies, mothers and counts re-pointed); human seats of the last session retired at load; a dead host seat retired; `--new-wizard`; `--new-world` archives (never deletes); the session's `new_game` seats a new wizard in place; the sidecar `<slot>.json` the menu reads; Mira keeps her seat and memory across sessions
- [x] `closed_at` and the game version in every save; `narrative/clockdebt.py` (10 simulated minutes per real hour, cap 20, nothing under a minute or over 30 days); the host pays the debt in slices in `step()` while the lobby is open, `start` ("Enter now") forfeits the rest, the write-off save happens before the world opens; `HYBRID_FAKE_ABSENCE_S` for tests
- [x] Durability: migrations (1 -> 2), one copy a day for seven days, `.prev`, the load report (`hash_mismatch`, `recovered_from_prev`)
- [x] The campaign in an old world: a newcomer's mother says what happened (`newcomer` variant: the mentor's death, the previous apprentice by name); the journal button, the objective line and the journal flashes are out of Wizard World (kept for the classic developer server)
- [x] Godot: Continue as <name> / A new apprentice / Start a new world (Settings, two confirmations); the catch-up page with Enter now; the lobby line while hosting
- [x] `tests/test_permanent_world.py` 8 passed (the brief's tests 1, 3-8; 2 is in `test_mortality.py`); headed `run_hybrid_new_wizard.gd` PASS (new wizard in place, the menu's Continue as, a six-hour pretended absence: the catch-up page, the world further along, the same mentor); shots `WizardRTSHybrid/docs/evidence/opening_rpg/m2/`. Not verified: a phone

## M3 The free opening
- [x] The colours and the weave from the first moment (`campaign.grant_basics`; the lessons teach the method); training ends by lessons, by play (a duel or a death) or by time (`training_fallback_ms`); duels, deaths and resurrections count as contact for the arrival; the stranger's judgement reads the ledger (killed your friend / brawling / died already / never finished the lessons / more craft than they let on); the lethal duel is a challenge on the last page (`$challenge_or_not`), fought by whoever made it, declined by everybody else; the stranger leaves once every present wizard has had their say or after a grace (`_depart_check`, `_begin_aftermath`), and the world records where he went (`stranger_gone_to`); the confrontation's world effects happen whether or not anybody present read the page (`world_effects`)
- [x] The mentor reads the ledger (killer, brawler, died, and a rare fourth-wall line at two deaths); "I know the colours. Test me." skips the theory; the mother tells a returning child what they missed (`told_news`)
- [x] `tests/test_free_opening.py` 9 passed; `test_wizard_campaign`, `test_wizard_party`, `test_wizard_tutorial`, `test_ai_wizard`, `test_permanent_world` updated to the new rules (150 passed together); headed `run_hybrid_apprentice.gd` win and lose PASS through the real board with the challenge as the player's choice; shots `WizardRTSHybrid/docs/evidence/opening_rpg/m3/`

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
- 16 Oct 2026 (session 1): M0, M1, M2, M3 done (Python and Godot, headed PASS for each). Next: M4 the village.
