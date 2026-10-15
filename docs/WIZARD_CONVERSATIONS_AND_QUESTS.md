# Wizard Mode: conversations, interruption and quests played by ordinary people

Status: implemented on `feature/wizard-mode-implementation` (polish milestone, 15 October 2026). This is the reference for how the wizard talks to anybody,
what happens to the person while he does, and how a quest is played by the settlement's own workers. The design it serves is
`PLAN_WIZARD_SETTLEMENT_STORIES.md` sections 5 to 8; the one simulation change is row W3 of `WIZARD_STORY_INTEGRATION_CONTRACT.md` section 4.

## 1. One owner for talking: `narrative/conversation.py`

Everybody the wizard can talk to goes through `conversation.talk / choose / end`: the tutorial teacher (a resident), a worker, a carrier, a soldier, and the
people of a quest (who are ordinary workers or soldiers). `story.talk` and `story.choose` route there for anyone who is not one of the legacy story fixture's
people. A reply is:

```json
{"status": "ok", "npc": "worker:1", "person": "person:12", "name": "Ragtor Blackshield", "subtitle": "Lumberjack of the Red settlement",
 "lines": ["..."], "choices": [{"id": "what_happened", "text": "...", "available": true}], "ends": false, "text": "(the answer to the last choice)"}
```

### The lifecycle (explicit, never guessed from a label)

1. **Begun** (`talk`): the person is within three tiles, no duel is open, nobody is fighting (a soldier who is fighting says he is busy and is not held).
   A conversation record is created and the person is **held** (section 2). The world keeps running.
2. **Speaking**: `lines` and the `choices` that are open (the person's own graph first, then up to three things their occupation lets you ask, then Goodbye).
3. **Responding** (`choose`): the person answers (`text`), and the reply says whether the conversation `ends`.
   * A choice whose data says `"ends": true` (every Leave, Farewell and Goodbye) ends it. A choice that starts a Ward Duel ends it too (the lease exists, the
     clock is paused).
   * Any other choice goes on to the next node and the conversation stays open.
4. **Closing**: when a reply `ends`, `choices` is empty and the card shows the final response with **one** acknowledge button (Continue, or Begin the duel).
   The player can read it; nothing closes until they acknowledge. Quest state changed by the choice is already applied.
5. **Ended** (`end_talk`): the person is released and goes back to what they were doing. This happens on **acknowledge**, **Escape**, the **Leave** button,
   **walking away** (more than six tiles), **another conversation** starting, **a duel starting**, the person **dying or being removed**, a conversation left
   **idle** for two game minutes, and a **loaded save** (every hold is cleared). The client also closes its card if the server ended the conversation.

A choice the person cannot give right now (a quest decision before both sides are heard) is refused with `choice_unavailable` and changes nothing.

## 2. Stopping one person without stopping the world: `hold.py`

A worker, carrier or soldier being talked to carries `held_until_ms` (game time). The three movement loops (`workers.worker_quantum`, `logistics.logistics_quantum`,
`military._unit_step`) skip a held body entirely: its position, its work programme or order, its timers and the ware in its hands stay exactly as they were, so
nothing is completed, teleported or duplicated, and every other body keeps simulating. While held the figure stands (`anim`/`status` are shown as idle and
restored on release). A held worker's building waits for him (only that building) and carries on when he is released. The hold check comes after the
"workplace destroyed" abort, so a held worker whose hut is destroyed is still removed. `held_until_ms` is a 30 second failsafe, refreshed every game second by
`conversation.tick` while the conversation lives, so a client that vanishes cannot strand anyone. A soldier's move order is kept and resumes.

### Asking someone out of a building

A worker inside his building is not drawn. The inspect card of the building lists who works there and who is inside; **Ask <name> to come out** (`call_out`) holds
the worker and steps him, one tile a game second, to the free tile near the building closest to the wizard (the wizard has to be within six tiles). Nothing
is teleported further than the door. When the conversation ends the building's own programme takes him back to work. Refused when he is not inside, the wizard
is too far, or there is no free tile.

## 3. Ordinary people talk like what they are: `occupations.py`

`data/narrative/dialogue/occupations.json` holds a compact set per occupation (lumberjack, forester, stonemason, hunter, carrier, soldier, any other worker):
an introduction (said once), a greeting (afterwards) and four to eight topics. A topic carries `when` conditions on **facts read from the simulation at that
moment**: trees and saplings near the person, timber in the settlement's warehouses, rocks and game near them, whether a hostile soldier is within 25 tiles,
whether a barracks exists, what they carry, their workplace and settlement. A line whose facts do not hold is not offered, so a soldier in a settlement with no
barracks says "No barracks yet", and no one mentions a castle. Variation comes from the number of times the wizard has spoken to the person (a rotating selection;
a question already asked in a conversation is not offered again) and from the facts themselves. Every line's placeholders are checked by `test_narrative_quests.py`.

## 4. Quests are played by existing people: `quests.py`

A quest template (`data/narrative/dialogue/forest_dispute.json`) names its cast by **role selectors**, not ids: "a worker whose role is lumberjack", "a soldier,
else a stonemason or hunter, else a carrier". When the stories unlock (all essential lessons, or 20 game minutes) the selectors are matched against the
simulation's workers, carriers and soldiers of the wizard's settlement (within 40 tiles of its centre, nearest first, ids as the tie-break) and each match is bound
to **its existing Person** (`characters.person_for`: one Person per body). Casting is all or nothing: if a required role has no match the quest is `unavailable`
(retried every 30 game seconds), the teacher says nothing needs a wizard, and nothing is forced. **Nobody is created for a quest**; there are no quest NPCs.
Bound people look and move like everybody else, carry no marker, and also keep all their ordinary conversation.

State is `world.narrative["quests"][id]`: `status`, `settlement`, `bindings` (`role -> {kind, id, pid}`), `history`. Everything is deterministic and saved with the world.

### When the world changes

* A bound person dies, is displaced or is otherwise gone: for up to 60 game seconds the role waits (a hut sends a new worker after 30 s); if a body with the same
  selector appears (another lumberjack of the settlement) it **takes the role as a different person** with its own name, and the journal records "X is gone. Y has
  taken their side". Nobody is resurrected and nobody is teleported.
* If nobody fits within the grace period the quest is `interrupted`: the journal says so honestly, the others are ordinary people again, and the teacher does not offer it.
* A quest changes nothing in the simulation: its consequences are flags, lines and a journal note. `test_narrative_quests.py` runs it to the end with the hold
  disabled and shows the world bit-for-bit equal to a world nobody talked in.

### The Forest Dispute (the first quest)

A woodcutter and a forester of the settlement have fallen out over how fast the forest becomes timber; a soldier saw part of it. The wizard hears both
(each person also answers everyday questions), may ask the witness, and decides: **compromise** (the cutter fells only old trees, the forester stakes the young
ones), **back the woodcutter**, **back the forester**, or **stay out**. Each ending has its own reactions from all three, and a journal note with the real names.
Lines are conditional on facts (for example the number of logs in the stores, or saplings around the forester) so they are true of the world being played.

## 5. Where it lives

`wizard_rts/hold.py`; `wizard_rts/narrative/{conversation,occupations,quests,graph,characters,residents,tutorial,ops}.py`; data in
`wizard_rts/data/narrative/dialogue/{occupations,forest_dispute,tutorial}.json`; presentation in `client/hybrid/{story_ui,wizard_labels}.gd`.
Tests: `tests/test_narrative_conversation.py`, `test_narrative_quests.py`, `test_wizard_tutorial.py`, `test_narrative_characters.py`; headed `conversation`, `tutorial`.

## 6. Known limits and decisions for the owner

* Only one quest exists, and only for the starting settlement; the director that gives every settlement three stories is Milestone E.
* A person inside a building cannot be talked to until they are asked out (or come out on their own). The simulation's workers walk out regularly.
* Zoom (pinch, wheel, keys) is about the wizard; the point under a pinch is not held fixed.
* The teacher is a dedicated resident and cannot yet be killed (residents are mortal from D.3), so there is no notes or replacement-teacher fallback yet (D.5).
* Narrative text, including every occupation line, is placeholder prose written for this milestone and needs the owner's review.
