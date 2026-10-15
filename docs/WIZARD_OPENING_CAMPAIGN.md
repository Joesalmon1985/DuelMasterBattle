# Wizard Mode: the apprentice opening (introductory story milestone)

Status: implemented on `feature/wizard-mode-implementation` (15 October 2026). This is the reference for the opening campaign, how it uses the existing
Aspect, worldview, person and dialogue systems, how to run it, and where it deviates from the narrative architecture. It builds on
`WIZARD_CONVERSATIONS_AND_QUESTS.md` (conversations, the hold, quests played by ordinary people) and `WIZARD_UI_DESIGN_SYSTEM.md`. **It concludes the
introduction. The next chapter (somewhere to seek greater magic) is deliberately not started.**

## 1. What the player plays

1. **The Apprentice.** The player is already the pupil of an established wizard of the settlement. Three short arrival pages say so; the relationship is
   built through lessons (`data/narrative/dialogue/tutorial.json`), not exposition. The mentor is a named resident with an authored persona (Druidic with a
   Monarchist secondary view: power is a debt, a responsibility, not an entitlement) and a warm relationship with the player (40).
2. **Lessons.** Flame, Frost and Vine, the weave of three, the three-colour Ward, fracture/echo/fade, two practice duels on the real board (a Ward you are
   told, then a hidden one), and Flame in the world. Losing a practice duel never ends anything. The mentor reacts to how the apprentice did.
3. **Free exploration.** When the essential lessons are done the exploration begins (`campaign.explore_start_ms`). The Forest Dispute is still available
   from the mentor but is not required.
4. **The stranger.** A named hostile wizard of Arcane Supremacist conviction (`data/narrative/characters.json`) walks into the settlement over a real path,
   meets the mentor (his former pupil: a grievance, not a caricature), and kills them. He challenges the apprentice.
5. **The lethal duel.** A genuine Ward Duel lease, easy by configuration and never guaranteed.
6. **Victory** (the stranger retreats alive; the mentor stays dead) **or defeat** (terminal Game Over).
7. **Aftermath.** Ordinary people react as themselves. After a few conversations (or a fallback time) the journal records *Seek greater magical power.*

## 2. The campaign state machine (`narrative/campaign.py`)

```
training -> explore -> arrival -> confrontation -> duel -> victory -> aftermath -> complete        duel -> game_over
```

State is `world.narrative["campaign"]` (saved with the world, deterministic, no wall clock, no `world.rng`).

| Stage | Entered when | Ends when |
| --- | --- | --- |
| `training` | a campaign world starts | every essential lesson (`config.json` `tutorial.essential`) is done |
| `explore` | training ends | the attack is due (below) and nothing else owns the player |
| `arrival` | the stranger is created (exactly once: the stranger's existence is the latch) | he has walked up to the mentor (or 60 game seconds have passed) |
| `confrontation` | arrival ends | the last page is acknowledged: the lethal duel begins |
| `duel` | the lease opens | a verified victory (`victory`) or anything else (`game_over`) |
| `victory` | verified victory | the retreat scene is acknowledged |
| `aftermath` | the retreat scene ends | two conversations, or `aftermath_fallback_ms` of game time |
| `complete` | aftermath ends | never (the next chapter's job) |

### When the attack comes (all configurable, `config.json` `campaign`, overridable for tests by `HYBRID_EXPLORE_MIN_MS`, `HYBRID_EXPLORE_FALLBACK_MS`)

* `explore_min_ms` = 180 000 of **game** time, **and** `explore_min_contacts` = 3 (people spoken to plus things inspected); or
* `explore_fallback_ms` = 420 000 of game time whatever the player did (the bounded fallback: nobody waits for ever);
* and only when no conversation, no duel and no dungeon owns the player (`campaign._quiet`).

Game time stops under any pause token (an open duel, a paused client), so an application left open while paused never triggers it. Timing is
deterministic and saved with the world. The attack cannot occur during training, because the stage is not `explore` until the lessons are done.

### Scenes (`data/narrative/dialogue/campaign_scenes.json`)

A scene is a list of pages the player acknowledges. Each page has a speaker, lines (with placeholders `{mentor}`, `{attacker}`, `{settlement}`), a camera
`focus` (mentor, attacker or player), an optional `fx` (flash, shake) and **effects that apply exactly once when the page is first shown** (`kill_mentor`,
`retreat`, `note`, `fact`, `aspect`). A page may carry `responses` (the apprentice answers; see sections 5 and 6) and the page cannot be passed until one is
chosen (`answer_required`). The scene's `final` says what acknowledging the last page does: `arrival` (control returns; the stranger walks in live),
`duel` (the lease opens), `aftermath`. The client (`client/hybrid/campaign_ui.gd`) pauses the world during a scene, guides the camera with
`world.camera_focus`, and hands control back at the end. Ordinary conversations still never pause the world.

### The mentor's death is a real death

`campaign._kill_mentor` (one place in the data, one place in the code): `PeopleService.record_death` (alive false, status dead, tombstone with the cause),
the resident row becomes `dead` (a body in the world, drawn as one and inspectable), the death is logged once (`character_died`), a journal note is added
once, any open conversation with them ends. It is idempotent and guarded: if the mentor is already dead or unavailable the scene `confrontation_alone` is
played instead, nobody is killed twice, resurrected or duplicated. Nothing depends on the mentor afterwards: the lessons are over, the optional quest is
independent, and `talk` answers `dead`.

### The lethal duel and defeat

* The lease is an ordinary `story_ward_duel` (`duel_lease.begin`, purpose `stranger_duel`), hosted by the retained board through the same adapter as the
  lessons and **verified by Python** (`duel_lease.verify`: the enemy Ward reproduced from the seed, every cast re-scored). The same tier
  (`duel.tutorial_3x3`), the same rules and the same pool and weave as the lessons. Only configuration differs (`opponents.json` `opponent.stranger`):
  a `random` bot with long think times (45 to 75 s) and 8 casts, against an apprentice with 12. Nothing is rigged and nothing is forced.
* **Only a verified victory wins.** A defeat, a draw, a stalemate, leaving the board, a report that does not verify and a save loaded with the duel open
  all end in `campaign.game_over` (`duel_lease` calls `campaign.on_duel_void` from every path that voids the lease). There is no way to step out of it.
* `game_over`: recorded once (`wizard.fate`, a tombstone, the `player_died` event), the lease released, a pause token held so the world stops, the client
  shows **Game over** with **New game** and **Quit**. Every op except looking, loading and starting again is refused (`server.AFTER_DEATH`), saving is
  refused (`persist.SaveError("game_over")`; also by `server._handle`), the pause menu and autosave cannot run. A dead world that is somehow written and loaded
  is still dead (the state is in the world). An earlier valid save is untouched and loading it is an explicit act. `new_game` replaces the world with a
  fresh one configured by the same launcher switches.

### Aftermath (`data/narrative/dialogue/aftermath.json`)

Ordinary workers, carriers and soldiers react. Each person has (a) a trade, (b) a **persona** (section 7), (c) knowledge (`campaign.knowledge`:
*witnessed*, kept in `witnesses` as the bodies near the mentor when the confrontation began, or *rumour*) and (d) a relationship with the apprentice.
Their first words are chosen from `reactions` (most specific first); the topics (what happened, how they are taking it, who he was, where to learn more,
the soldier's report, comfort, a boast that can be caught out) are offered as `priority` topics. A rumour does not know the stranger's name. Nobody is
created for the story (a test asserts only the mentor's body and the stranger exist as residents).

### The final objective

After two conversations, or `aftermath_fallback_ms`, `campaign.complete`: stage `complete`, `wizard.campaign_finished`, and the journal note
*Objective: seek greater magical power.* (recorded once). The HUD and journal show **Seek greater magical power.** No destination, dungeon or quest chain
is created. The player is free to go on exploring the simulated world. After a cycle reset no second mentor is cast.

## 3. Aspects (capability): the existing `AspectService`, not a second system

`narrative/checks.py` is a thin wrapper around `sim/dmb/narrative/aspects.py`:

* The apprentice is the actor `player`. Starting scores come from `config.json` `campaign.start_aspects` (an apprentice is not a blank): Reason 2,
  Empathy 2, Authority 1, Guile 1, Resolve 2, Curiosity 3, Wonder 2. They live where `AspectService` keeps them (`world.dmb.definitions["aspects"]`), so
  they save, load and cross a cycle reset as before. `aspects.json` (frozen content) is untouched.
* A check is `{aspect, threshold: easy|demanding|exceptional, evidence: [{when, mod}]}`. The total is the real score + evidence (`when` is any dialogue
  condition, capped at 2 by the service) + the speaker's relationship band (`relationship_band`: -1, 0, +1 from `relationship_map["player"]`), against the
  service's thresholds (2, 4, 6). Nothing is random.
* **Repeat safety is the service's own**: a failed check records a retry fingerprint (aspect, score, evidence, relationship, context); asking again with
  nothing new is *blocked*: the choice is shown disabled (`available: false`) and refused by the server. A higher score, new evidence or a better
  relationship is a new attempt. A passed check stays passed and is never re-rolled. Results are kept in `world.narrative["checks"]` (per person and per
  choice), so a repeated conversation shows the same outcome and cannot be save-scummed.
* A failed check always gives an alternative path (`fail` branch) and never blocks the introduction. Effects of either branch are once-only (receipts).
* Examples in play: the mentor (Curiosity: the lore of Wards; Wonder: the light around their staff, harder until the lore is known; Reason: how to read
  feedback), the confrontation (Resolve: stand firm; evidence is what the mentor taught about responsibility), villagers (Curiosity: a clue about the
  stranger, evidence is having seen him; Empathy: comfort someone who loved the mentor; Authority: a soldier's report, evidence is having stood firm;
  Guile: bluffing a confirmation, which costs trust if it fails; Reason: catching a boaster who was not there).
* A duel victory gives +1 Resolve once (`aspect` effect and `checks.change_once`, receipt `campaign/duel_victory`).

## 4. Worldviews (belief): a small store beside `AspectService`, as planned (plan 11.4)

* `data/narrative/worldviews.json` is a copy of `tools/dialogue_generation/worldviews.json` (the Dialogue Factory's source of truth: codes M, A, R, G, S, D,
  C and their per-reply deltas). No runtime path imports `tools/`. `tests/test_wizard_aspects_worldviews.py` fails if the copy and the original diverge.
* `wizard.apply_worldview_delta(world, receipt_id, delta)` / `apply_worldview_choice(world, receipt_id, code)` add the established delta **once per
  receipt** (the pattern of `AspectService.apply_change_once`) to `world.narrative["wizard"]["worldview"]` (saved, crosses a cycle reset).
  `worldview_primary` is the code the apprentice leans towards. Worldviews and Aspects never mix: a Druidic apprentice may have high Reason.
* Authoring: a choice or response with `"worldview": "D"` pays its delta once (global receipt per answer). Meaningful ideological answers appear where
  they belong, not in every conversation: the mentor's creed (`why_not_rule`: Druidic, Monarchist, Anarchist, Guildist, Supremacist or Religious replies),
  the apprentice's answer to the stranger (all seven, the Illuminated one only after glimpsing the mentor's old craft), and the villagers' grief
  (`t_meaning`, all seven).
* Speakers take an answer according to **their own** persona: `personas.reaction` uses the established delta of the speaker's primary worldview towards
  the answer (the table's own numbers: agree at 2 or more, disagree below 0) and picks their authored reply (`agree`, `neutral`, `disagree`). Their opinion
  of the apprentice moves by +4 or -3, once per person and answer. One answer per person per topic.

## 5. People: persona, relationship, memory (`narrative/personas.py`)

* A persona is generated once per Person from `crc32(seed | body key | "persona")` (independent of who is met first), stored on the Person, and consists of
  seven worldview scores (the 88 profiles' `Score_*` columns), a primary and a secondary worldview, two traits, an attitude to the mentor (fond, respectful,
  wary) and to magic (devoted, reverent, practical, cautious, wary). Occupations only tilt the draw (foresters towards Druidic, soldiers Monarchist, ...);
  every persona has noise and one personal conviction, so no trade is of one mind (a test checks the spread).
* Dialogue conditions that read all of this (`graph.holds`): `persona` (primary, secondary, any, trait, mentor, magic), `relationship`, `knows`, `stage`,
  `aspect`, `player_worldview`, `fact`/`not_fact` (what the apprentice has learned), `check` (the state of an earlier check) and `role`.
* Memory: relationships (`relationship_map["player"]`), once-only effects, `world.narrative["responded"]`, `reacted`, `talks`, the apprentice's `facts`, and the
  forest dispute's decision, which now moves the cutter's and the planter's opinions. A woodcutter the apprentice backed offers to ask around later.
* Knowledge boundaries: a person who was not near the mentor has only heard a rumour and says so.

## 6. Capability inventory (what existed, what is now connected)

| Capability | State before | Now |
| --- | --- | --- |
| Person registry (`sim/dmb/people/registry.py`: identity, relationship map, known facts, tombstones, `record_death`) | implemented; used for workers and the quest NPC | **used** for the mentor's death, the stranger, relationships |
| `AspectService` (scores, thresholds, evidence and relationship modifiers, retry fingerprints, receipts) | implemented; connected only to the legacy `persuade` | **connected** to every Wizard Mode check (`checks.py`) |
| Dialogue graph conditions and effects | v0 runtime of the milestone before | **extended** (`persona`, `check`, `worldview`, `relationship`, `aspect`, `fact` effects, scopes) |
| Seven-worldview model (`worldviews.json`) | Dialogue Factory only | **connected**: a store, once-only deltas, persona reactions |
| 88-profile archetype library | designed (plan 4.2), not implemented | **partly**: generated personas use the same worldview scores; authored profiles can replace them; no profile CSV is read at runtime |
| Dialogue Factory worldview replies (7 variants per bank) | exported banks for E36B and E17A (Village Test Mode) | **not connected**; the wizard's replies are authored here as data |
| Ordinary conversations (occupations, facts) | implemented (polish milestone) | extended with persona, knowledge and aftermath |
| QuestService (`sim/dmb/quests`) | used by the legacy story fixture | not used by the campaign (it has its own stage machine); the forest dispute keeps its own narrative quest |
| Resident mortality, link watcher, residents leaving | designed (D.3 to D.5) | **minimal**: the mentor and the stranger can die or leave through `campaign`; general resident mortality is still D.3 |
| Director, templates v2, 112-story casting | designed (E, F) | not implemented; nothing here depends on them |
| Missing entirely | | persona-authored profiles for named canon (D19), a Game Over archive of past runs, the next chapter |

## 7. Running and testing

Launch (campaign profile, the default 450 x 800 window):

```
cd /home/joe/dmb_runs/wt_wizard_implementation && WizardRTSHybrid/scripts/launch_scenario.sh campaign
```

To see the whole opening in a few minutes, shorten the timings (game milliseconds; the defaults are 180 000 and 420 000):

```
HYBRID_EXPLORE_MIN_MS=30000 HYBRID_EXPLORE_FALLBACK_MS=90000 HYBRID_AFTERMATH_FALLBACK_MS=40000 WizardRTSHybrid/scripts/launch_scenario.sh campaign
```

* **Win:** learn the colours from the mentor, win or lose both practice duels, walk among the people (speak to three), wait for the stranger, read the
  confrontation, then fight the stranger on the board. Break his hidden Ward before your 12 casts are used (use fracture, echo and fade: never repeat what
  an answer ruled out). He retreats; talk to two villagers.
* **Lose:** in the lethal duel, cast carelessly (or leave the board). **Game over** appears; New game starts a fresh world, Quit leaves.
* Automated: `python3 -m pytest tests/test_wizard_campaign.py tests/test_wizard_aspects_worldviews.py` (about 70 s), the headed pair
  `scripts/run_headed_suite.sh apprentice_win apprentice_lose` (each plays the whole opening at 450 x 800 through the real UI and the real board), and
  `run_headed_suite.sh ui` (the scene and Game Over cards at five window sizes).

## 8. Limitations and deviations from the narrative architecture

* The stranger and the mentor are **residents** (narrative-owned bodies), not simulation workers: a wizard has no counterpart among the occupations. They
  are not in the economy and cannot be burned or hurt by anything but the story.
* The mentor and the stranger have `role` metadata but no `living.py` resilience policy yet (D.4): only the "already unavailable" case is handled.
* The apprentice has no Person record; `player` is an actor id for relationships and Aspects.
* Scenes are authored pages, not graph nodes (a scene is linear with answers); they use the graph's effects, checks and responses.
* `duel_lease` calls `campaign` (a dependency from the duel layer to the campaign, kept lazy) to make the lethal duel inescapable.
* The settlement's story name ("Skorlag Hold") is generated from the tribe's syllables; the simulation still calls it "Red home 1".
* The stranger's retreat is a walk away over a path for a few seconds, then he is "gone" (status), not a modelled journey; nothing returns him yet.
* All narrative text is placeholder prose written for this milestone and needs the owner's review.
* Zoom, scenes and the Game Over screen were checked at 450 x 800 and 1280 x 720 for real; 800 x 450, 720 x 1280 and 1920 x 1080 are laid out by the stretch
  maths (the laptop window manager keeps its window within the screen), see the UI design document.
* `new_game` replaces the world on the server; the previous run's saves are left alone.
