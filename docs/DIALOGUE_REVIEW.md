# Dialogue and line banks: owner review index

Every bank of authored text in Wizard World is placeholder prose until the owner has read it (plan M7, `docs/PLAN_OPENING_RPG_AND_DEATHTRAP.md`
section 4, M7: 'owner dialogue review of every placeholder line bank'). This index is generated from the data files (`scripts/dialogue_review_index.py`);
the count is of authored strings (lines, texts, alternates, introductions). Tick a bank here when it has been reviewed; the `note` field of
each file says the same until then.

| Bank (under `WizardRTSHybrid/wizard_rts/data/`) | Strings | What it is | Reviewed |
| --- | ---: | --- | --- |
| `narrative/dialogue/aftermath.json` | 79 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/campaign_scenes.json` | 73 | Placeholder authored scenes (owner review pending) | [ ] |
| `narrative/dialogue/forest_dispute.json` | 68 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/mother.json` | 30 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/occupations.json` | 128 | Reusable conversations by occupation (placeholder authored text, owner review pending) | [ ] |
| `narrative/dialogue/ranger_patrol.json` | 23 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/smith_dispute.json` | 29 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/trial_gate.json` | 38 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/tutorial.json` | 77 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/warehouse.json` | 37 | Placeholder authored text (owner review pending) | [ ] |
| `narrative/dialogue/progression.json` | 32 | The magic ladder's rung announcements (mentor, mentor by time, Mira, the inner voice), added 18 Oct 2026 | [ ] |
| `narrative/dialogue/inner_voice.json` | 15 | The apprentice's own Aspects at the absurd moments (narrative/voice.py), added 18 Oct 2026 | [ ] |
| `ai_wizards.json` | 49 | AI wizards: participants that stand in for a missing human wizard (idle, forfeit, arson lines added 18 Oct 2026) | [ ] |
| `narrative/opponents.json` | 0 | Opponents of Wizard Mode's Ward Duels: combatant fields plus a think band (seconds) | [ ] |
| `trial/zones_wizard.json` | 22 | Wizard World's overlay on the legacy Deathtrap zones (legacy_zones | [ ] |

Also authored, outside the banks: the Trial's event texts (`wizard_rts/trial/events.py`, the book's choices as the legacy wrote them, adapted),
the Trial's outcome lines (`wizard_rts/trial/run.py` `on_duel_resolved`), the AI apprentice's notices (`data/ai_wizards.json`), the client's
toasts (`godot_project/client/hybrid/trial_mode.gd`, `hybrid_world.gd`) and the legacy zone texts (`data/trial/legacy_zones.json`, exported from
the old adventure and overridden by `zones_wizard.json` where Wizard World differs).

## Variety and the fourth wall (M7)

* A hub variant with `lines_alt` says it another way each time it is seen again (`narrative/graph.py`, the sets rotate): the keeper's quiet
  store and his returning rats, the mother's thanks. Add `lines_alt` to any variant that a playtest shows repeating word for word.
* The fourth wall is noticed rarely and counted: `ledger` key `fourth_wall`; a villager's `who_counts` (after eight people accosted) and the
  Rollkeeper's `why_write` offer themselves only while fewer than two such lines have been said in the world.

## The world notices (18 Oct 2026)

* New variants in `tutorial.json` (never_came, second_generation, arsonist_first, arsonist, tree_burner, absent, empty_store), `mother.json` (arson, burned_village,
  idle, empty_store, second_generation), `trial_gate.json` (o_arsonist, o_still_here, o_second_generation, a second-visit line per contestant),
  `warehouse.json` (ruin, waves_over, burned_rats_only, burned_rats_some, eaten_empty, losses, the returned line by wave), `occupations.json` (the `often` hub pool
  after five visits, topics seen_burning, seen_trees, nothing_doing) and `campaign_scenes.json` (`confrontation_missed`). All placeholder prose.
* The facts they read are listed in `conversation.common_facts` and `narrative/deeds.py`; every new variant has a test in `tests/test_noticing.py` that reaches it.
* The fourth wall: `who_counts` now counts the apprentice's own talks (`my_talks`), not the mother's accostings.
