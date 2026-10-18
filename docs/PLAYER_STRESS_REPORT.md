# Player stress report: the misbehaving apprentice

Branch `feature/player-stress-and-progression`. The suite is `WizardRTSHybrid/tests/test_player_stress.py` (helpers `tests/_stress.py`); it plays
the game badly on purpose through the real `MultiplayerSession`, seed 507, one human and Mira, and writes what the world said and did to
`WizardRTSHybrid/docs/evidence/stress/observations.json`. Run it with:

```bash
py -3 -m pytest WizardRTSHybrid/tests/test_player_stress.py -q
```

Every quoted line below is placeholder prose (owner review pending, `docs/DIALOGUE_REVIEW.md`). "Fixed" names the commit or the section of the
plan (`docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md`) that answers the finding; the table is updated as the work lands.

## Verdicts

| Id | Scenario | What the game did | Verdict | Fixed |
| --- | --- | --- | --- | --- |
| STR-01 | Stand still for an hour | The story ran on its timers: explore at 5 min, the stranger at 12, the mentor killed alone at 14.5, aftermath 17.5, complete at 20. Nothing crashed. The rats ate the warehouse to nothing (65 loads, 0 food left) and nobody said a word about it; the ledger recorded nothing in an hour; Mira said her greeting and nothing else for sixty minutes. | silent | fixed: the keeper's `eaten_empty`, the mother's and the mentor's `empty_store`, the inner voice (`store_empty`, `idle_ten`), Mira's idle lines; the hour of nothing now reaches four rungs of the ladder |
| STR-02 | Never press a button on the stranger's scene | The world moved on without the answer (good), but the confrontation page stays open afterwards with stale text ("has stopped what they were doing... staff in their hand") while the mentor is dead and the stranger gone, and while it is open every `talk` is refused with `scene`. Forty-five minutes later the Rollkeeper still cannot be spoken to. | wrong | fixed: `confrontation_missed` replaces the stale page; a page that asks nothing gives way to a conversation (`campaign.dismiss_if_idle`) |
| STR-03 | Walk straight to the Trial, enter with no lesson, die to the first creature | Rollkeeper notices the unprepared apprentice; the Guard Dog kills; the ending card comes; the body stays inside; a new apprentice arrives a generation later. But the next generation hears exactly the first-day lines: the mother "Have you eaten?", the mentor "There you are. Late again", the Rollkeeper the same roll. Nobody remembers the apprentice who died in the Trial 40 seconds earlier. | silent | fixed: `second_generation` variants for the mentor, the mother, the Rollkeeper; the inner voice (`generation`) |
| STR-04 | Talk to the same person twenty times | Mentor: three openings, then "What would you like to learn?" for ever. Keeper, mother, Rollkeeper: the same opening twenty times out of twenty. Villagers: four openings. The "who counts?" fourth-wall line never came because its condition reads `my_accosted`, which only the mother's accostings bump. | silent | fixed: the villagers' `often` pool after five visits, the Rollkeeper's `o_still_here`, a second-visit line per contestant; `who_counts` reads `my_talks` |
| STR-05 | Press every button in an empty field, on a rat, on yourself | Every op refused with a reason (`no_such_person`, `pest`, `too_far`, `no_target`, `no_body`). Fine. | fine | - |
| STR-06 | Challenge Mira ten times and walk out of every duel | She declines twice, accepts the third, and the forfeit kills the apprentice (a duel between apprentices is to the death; walking out counts as losing). She says "Hold on" and does nothing: the ending fires the instant the only human is dead, and her rescue code stands down whenever an ending exists. In single player Mira can never bring you back. | wrong | fixed: the ending waits 150 s while Mira can reach the body; she says `you_forfeited` and brings you back; the death card says she is coming |
| STR-07 | Burn the warehouse with the rats in it, then ten trees, ten rocks, ten carriers, ten workers, five soldiers | The keeper's rebuke fires once ("think about the order of those two things"), then he goes back to complaining about rats in a warehouse that no longer exists; the five rats stay for ever around the ruin, no further wave can come. Forty-five other things burned: no line from anyone, nothing in the ledger, Mira silent. | silent | fixed: the arson ledger (`deeds.py`); the mentor (`arsonist_first`, `arsonist`, `tree_burner`), the mother (`arson`, `burned_village`), the Rollkeeper, the villagers (`seen_burning`, `seen_trees`), Mira, the inner voice; a ruin scatters the rats (`ruin` line) |
| STR-08 | Burn one person from each quest | Each quest found a replacement and wrote a journal note (good). The patrol's replacement was the forester who already plays in the forest dispute, so talking to "the ranger" gives the forester's lines and the patrol cannot be reached (the cast-time rule "one part per person" is not applied to replacements). The patrol's guard shows as "?" (no soldier in the settlement; the optional part is unfilled but still printed). | wrong | fixed: replacements exclude other quests' casts; an unfilled optional part is not printed |
| STR-09 | Back both sides of the granite and the forest disputes | The graphs refuse the second side (`choice_unavailable`), as designed. | fine | - |
| STR-10 | Lose to the rats five times on purpose | The wound does not stack (one cast fewer, never two); five `pest_escaped` notices; then the keeper, who had been complained to, says his first complaint again word for word. His "progress" line needs a kill before it will acknowledge a run of losses. | silent | fixed: the keeper's `losses` line; the inner voice (`lost_to_rats`) |
| STR-11 | Clear all six waves of rats | Waves two to six come with three rats each and are cleared; the keeper thanks you once (wave one) and then says "Store is quiet" after every later clearing because his `said_cleared` flag is never reset; after the sixth wave nothing more comes and he says "Nothing to report" with no acknowledgement that it is over. | silent | fixed: `said_cleared` reset per wave, `returned` reads the wave, `waves_over` closes the waves, the journal entry says so |
| STR-12 | Kill Mira three times, protest each time, try to leave | Works as written: the mother's three escalating speeches, protest and "and if I just walk off?" answered, grounded each time, Mira's lines ("I remember exactly who put me there"), relationship down to 1, thanks after the last resurrection. Each button press repeats the whole opening speech above the answer (the client shows the answer, then the hub's lines again). | fine / repetitive | fixed: the hub's lines are not repeated under an answer (`graph.choose`) |
| STR-13 | Igbut's door: three wrong orders, then face it again | Each wrong order wounds; the third scatters the gems; facing the door without them gets the counting line; placing is refused. Fine. | fine | - |
| STR-14 | Register with the Rollkeeper, never enter, come back at 15 and 45 minutes | Blocked by STR-02: the stale scene refused both talks. | wrong (STR-02) | fixed with STR-02 |
| STR-15 | Every conversation in the village, every button | 19 speakers, 130 buttons: everything opens, nothing offered is refused, every crawl runs out of new choices. The five contestants have one button ("Thank you") and no variety; the mother has two when not grounded. Talking to the second barbarian crashed the server with `KeyError: 'barbarian2'` (no such speaker in the gate's bank). | crash | fixed (speaker falls back to the barbarian's lines) |

## Gaps the dialogue work answers (plan section 3)

* Neglect: an empty store (STR-01), a mentor killed while the apprentice stood thirty tiles away (STR-01/02), a generation that remembers nothing (STR-03).
* Spam: "you again" variants after repeated visits (STR-04); a fourth-wall counter that counts the right thing (talks, not the mother's accostings).
* Arson: a ledger of what was burned and lines for it from the mentor, the mother, the keeper, the villagers and Mira (STR-07).
* Rats: the keeper on losses, on later waves, on the end of the waves, on the burned rats (STR-10, STR-11, plan section 5).
* Mira: idle lines, a line on a forfeit, and the rescue in single player (STR-01, STR-06).

## Mechanics fixed (all landed on the branch; `tests/test_noticing.py` and `tests/test_village.py` prove each)

* STR-02: when the stage moves past the confrontation, a scene nobody answered is replaced by a short "you were not there" page instead of staying open with the old text.
* STR-06: the ending waits while a living AI companion can reach the body; the apprentice is told she is coming.
* STR-07: a destroyed warehouse ends its infestation (the rats leave the ruin) and the keeper says so.
* STR-08: a replacement is never a person already cast in another quest; an unfilled optional part is not printed as "?".
* STR-11: the keeper's cleared-flag is reset per wave; a closing variant after the last wave.
* STR-12: after a choice the hub's opening lines are not repeated under the answer.
* STR-15: fixed in this branch.

## After the fixes (same suite, same seed)

* An hour of nothing: the ladder reaches all four rungs by time, the inner voice speaks twice, Mira four times, and the keeper, the mother and the mentor
  all have the empty store to say when finally spoken to.
* Walking out of a duel: Mira names it and brings the apprentice back; no ending card.
* The next generation: the mother, the mentor and the Rollkeeper remember the dead apprentice by name.
* Forty-six things burned: Mira, Empathy, Reason, the mentor, the mother, the Rollkeeper and the villagers all react; the keeper keeps a ruin.
