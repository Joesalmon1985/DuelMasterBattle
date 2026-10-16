# Plan: the free-form opening, mortal apprentices, a permanent world, and the Trial of Champions

Status: **assessed and amended plan, awaiting the owner's sign-off** (16 October 2026). Nothing in this document is implemented.
Source brief: the owner's "Mobile-First Multiplayer RPG Opening and Deathtrap Dungeon" brief with its revised requirement on death,
resurrection and permanent world persistence. Baseline: `main` at `e6e6399b` (Android 0.2.0).

This plan keeps the brief's goals and scenarios. It changes the brief only where the repository already does something the brief
asks for (reuse, not rebuild), where two parts of the brief conflict with each other, or where a requirement cannot be met as
written on a phone and needs a bounded version. Every such change is listed in section 2 with the reason, and the ones that need
the owner's word are collected in section 7.

---

## 1. What already exists (verified against the code on `main`, not the documents)

| Area | State on `main` | Where |
| --- | --- | --- |
| One Wizard World | Player menu is Play Single Player / Host / Join / Settings. Single player is a private hosted session with the AI apprentice Mira; two phones share the host's world. The old adventure, Quick Duel and G01 are developer tools behind `DMB_DEV_MENU=1`. | `godot_project/client/scripts/main_menu.gd`, `dev_menu.tscn`, `docs/ANDROID_PLAYTEST_CORRECTIONS.md` |
| Host-authoritative LAN | One `HybridWorld`, one clock, validated one-tile moves, per-player views, reconnect tokens, UDP discovery; no faction or clock op reachable by a client. | `WizardRTSHybrid/wizard_rts/net/{host,session,protocol}.py` |
| PvP Ward duels | Real-time, independent casts, three-colour three-slot format available **from the first second** (the format's pool is independent of the wizard's lessons). Loss has no consequence beyond Mira's relationship score. The duel **pauses the whole world** (pause token `pvp_duel`). | `net/pvp.py`, `net/session.py:654` |
| The party | Seats for one or two humans plus AI guests; private per-seat story (spells, lessons, journal, relationships, fate); shared settlement, mentor, stranger and campaign stage. | `narrative/party.py` |
| The AI apprentice | Mira: follows, treats outbreaks, accepts or declines a challenge by relationship, duels with the retained `WeaveBot`, speaks notices. No narrative reach, single player only, never initiates a duel. | `net/ai_wizard.py`, `data/ai_wizards.json` |
| The opening campaign | Mentor (authored persona), lessons on the real board, event-based exploration, the stranger walks in over a real path, kills the mentor (a real Person death with a body), a **forced lethal duel** (any outcome but a verified win is Game Over), aftermath, objective "seek greater magical power". Training gates the arrival. | `narrative/campaign.py`, `data/narrative/dialogue/*.json`, `docs/WIZARD_OPENING_CAMPAIGN.md` |
| Character systems | Personas (seven worldviews, traits), relationships, knowledge (witness or rumour), Aspect checks with retry fingerprints, once-only receipts, dialogue graph conditions. | `narrative/{personas,checks,graph,conversation}.py`, `sim/dmb/narrative/aspects.py`, `sim/dmb/people/registry.py` |
| Residents | Narrative-owned people with a tile, routine and graph; the mentor and stranger are residents. No mortality policy beyond the mentor's scripted death. | `narrative/residents.py` |
| Death today | Alone: `game_over` holds a pause token, refuses every op but new game or load, **refuses saving**; `new_game` builds a **fresh world**. In company: death is personal (`fate`), the others go on; the campaign ends when no human is alive. | `campaign.game_over`, `server.AFTER_DEATH`, `session._solo_op` |
| Save and load | Whole-world pickle with a narrative version and migrations table (empty), atomic write, `.prev` fallback; autosave every five minutes and on Android pause; Continue in the menu. Saves refused when the apprentice is dead. | `narrative/persist.py`, `net/host.py:load_saved_world`, `hybrid_world.gd` |
| Settlement economy | Warehouses are real buildings (a faction's first warehouse is its command centre); workplace disruptions, outbreak regions with a production factor and the wizard's `treat` action; blight nests as hostile actors. | `settlements.py`, `disruption.py`, `regions.py`, `nests.py`, `data/outbreaks.json` |
| Mindustry art | Crawler, atrax, dagger and the rest are imported and in the catalogue, loading through `asset_loader.gd` with an export audit. | `godot_project/client/hybrid/art/mindustry/unit_crawler*.png`, `scripts/android/asset_audit.py` |
| Deathtrap Dungeon (legacy) | **Sixteen authored zones** (`dd_entrance` to `dd_igbut`) with tile rows, entities, traps, items, Throm's state machine, the run model, nine bestiary opponents, pixel art and shell tests. It runs in the **old Godot adventure**, not in Wizard World. | `godot_project/client/world/world_data.gd`, `godot_project/sim/bestiary.gd`, `godot_project/assets/pixel/{creatures,chars,props,tiles}`, `docs/DD_FULL_DUNGEON.md`, `docs/DD_FIRST_SLICE.md`, `tools/run_dungeon_*.sh` |
| Deathtrap Dungeon (canon) | Verified macrograph of 28 passages, required items, contestants, the encounter translation table, the physical-dungeon design, and the explicit gaps. | `DD/*.json`, `DD/*.csv`, `DD/Deathtrap_Dungeon_Canonical_Adaptation_Report.md`, `docs/DEATHTRAP_OVERHAUL_PLAN.md` |
| Dungeons in Wizard World | Generated four-room puzzle dungeons (`DungeonRun`), per player, drawn as a placeholder overlay. | `wizard_rts/puzzle/dungeon.py`, `client/hybrid/story_ui.gd` |
| Android | Signed APK build on Windows with Chaquopy CPython; asset audit; exported-pack art probe; two-phone checklist. **No phone has run 0.2.0.** | `Build Android APK.bat`, `docs/ANDROID_EXPORT.md`, `docs/MOBILE_LAN_MULTIPLAYER.md` section 10 |
| Tests | 1,395 Python tests (32 min), `tests/_party.py` drives real sessions with an advanceable clock; headed Godot scripts play the opening through the real board; `run_lan_two_clients.gd` plays a human-versus-human duel. | `WizardRTSHybrid/tests/`, `godot_project/client/tests/` |
| UI the brief wants gone | A journal panel (J), a HUD objective line and "new in your journal" flashes exist in the player build. | `hybrid_world.gd:825-870`, `story_ui.gd` |

Conclusion of the assessment: **about two thirds of the brief's opening is built**, the LAN and party machinery is the right base,
and the dungeon exists as authored content in the wrong engine layer. The brief's genuinely new work is (1) mortal apprentices
with bodies, resurrection, the mother, and the new single-player death rule; (2) the permanent world with new characters,
offline catch-up and host ownership; (3) making the opening free (no gates, no forced lethal duel, no journal); (4) the warehouse
rats and village situations; (5) porting the Trial into the authoritative simulation as a shared two-player space; (6) the
reactive-humour layer; (7) Mira as a narrative participant.

---

## 2. Amendments to the brief

Each entry: what the brief says, what was found, what this plan does instead, and whether the owner must decide (marked **DECISION**).

1. **The forced lethal duel goes; the stranger's challenge becomes optional.** The brief's section 5 says the stranger defeats the
   mentor and tells the apprentices to grow stronger, and that players must not be forced into revenge or any particular duel. The
   built campaign forces a lethal duel whose loss is Game Over. Amendment: the stranger kills the mentor, says his piece, and leaves
   over a road to a place the world records. An apprentice may challenge him there and then; losing means death under the new rules
   (a body, resurrection by the other), not a special game over. The existing scenes and `opponent.stranger` are reused for that
   optional duel. He persists as a character for the next chapter. **DECISION D1.**
2. **Lessons stop gating the story.** `campaign` enters `explore` only after training. Amendment: the stage machine keeps its
   shape but `training` is an activity, not a gate; the arrival trigger counts what the apprentices actually did (lessons, duels,
   deaths, contacts, the warehouse, a visit to the Trial gate) with the existing game-time fallback. The mentor's lines condition on
   the party's duel record ("you have already killed each other twice, so we can skip the part where I explain what a Ward is").
3. **Death becomes the brief's revised rule, replacing the built Game Over.** Today saving is refused when dead and `new_game`
   builds a fresh world. Amendment: a dead wizard is a **body** (a resident row and a tombstone), the world is saved with the body in
   it, `new_game` enrolls a new seat in the same world, and the pause token on death goes. Single player: human death ends the
   session and returns to the menu at once (the AI cannot resurrect a human in single player; that part of the original brief is
   superseded by the revision, as the revision itself says). Multiplayer: the dead player spectates until the survivor reaches the body.
   Both dead: both to the menu, world saved. **DECISION D2** (confirms the revision over the original brief's "the AI attempts to
   resurrect the human").
4. **Duels no longer freeze the world.** A PvP duel pauses the whole world today; the brief's section 8 wants the world to continue
   and section 6 wants players in different places. Amendment: in Wizard World no duel pauses the clock (the pause menu in a
   private session still does). Story and rat duels run beside the live world like the two-human story duel already does.
   **DECISION D3.**
5. **The mother is one resident per apprentice.** The brief says "the surviving apprentice's mother". Amendment: every apprentice
   seat is cast a mother when it enters the world (lazily, like other residents); the survivor's mother grounds the survivor; a mother
   whose child dies permanently grieves and remembers. Two humans have two mothers. Mira has one too. **DECISION D4.**
6. **The grounding is enforced by the host, in the world.** "Not allowed to leave the starting area" is a `move` refusal at the
   home settlement's territory edge and a refusal to enter the Trial, with the mother's line as the reason, and the mother walking
   after the survivor. Escalating lines come from the behaviour ledger (amendment 9). Softlock rules: the body is always on a
   reachable free tile (relocated by the host if it is not), resurrection is always possible while the survivor lives, and the grounding
   lifts the moment the other apprentice is alive again or when the survivor dies too.
7. **The rats are narrative pests, not new units.** The content roster is frozen (D33). A rat is a narrative-owned hazard actor
   (like a blight nest or a resident) drawn with the imported Mindustry crawler sprite at half size, living inside a real
   warehouse's footprint and applying the existing disruption production factor to that building while any are alive. It is fought
   through a story Ward duel lease (host-verified, brief one- and two-slot formats). Nothing is added to the entity roster; the
   freeze check stays green. **DECISION D5** (freeze interpretation).
8. **The Trial is an interior area of the one world, entered through a gate on the map.** The brief wants a physically
   explorable 2D adventure. The hybrid scene already extends the legacy `Overworld` whose `load_area` builds the sixteen `dd_*`
   zones as tiles. Amendment: the gate stands on the world map on a road a short walk from the starting settlement; stepping
   through loads the zone as an interior area in the same scene with the same touch controls; the **host owns the Trial state**
   (one shared run per world, per-player positions, shared items and encounter state), the client only draws. Players inside are
   "away" on the world map. The zone data moves from GDScript into JSON data the Python host reads. **DECISION D6.**
9. **Humour is driven by a behaviour ledger, with variety by design.** A per-world and per-seat ledger of counted behaviours
   (duels between apprentices, kills, resurrections, time spent duelling while a task waits, lessons skipped, questions repeated,
   Trial entered before any lesson, attacks during a scene, an upset win) feeds authored line banks with escalating variants and
   a cooldown so the same reaction never repeats twice running. Speakers are the people the brief names; personas and worldviews
   tilt the pick. This is data in the existing graph format, not a new system.
10. **Offline progression is bounded real simulation, not a fixed real-time ratio.** The brief asks the world to catch up on what
    should have happened while closed, efficiently, with meaningful outcomes. Measured: a six-faction game costs about 4.4 s of one
    PC core per simulated minute mid-game (`docs/NEXT_AGENT_HANDOFF.md`, bench of 14 Oct); a phone is roughly three times slower.
    Hours of absence cannot be replayed at full fidelity, and a coarse summary model would be a second economy, which the architecture
    contract forbids and which would break ware conservation. Amendment: while closed the world is owed `min(elapsed_real × R, CAP)`
    of simulated time (recommended R = 10 simulated minutes per real hour, CAP = 30 simulated minutes per reopening); the real
    simulation pays that debt in a background thread while the menu shows "the world turned while you were away", with an
    "Enter now" button that forfeits the rest; the debt is written off in the save immediately so it can never be applied twice.
    Final numbers come from the phone measurement in M0. **DECISION D7.**
11. **The journal and objective line leave the player build.** The brief forbids journals, checklists and markers. Today the
    journal also carries "what you missed while away" for latecomers. Amendment: the journal stays as data (tests and the
    developer menu); the HUD objective and journal button are removed from Wizard World; what a returning or new wizard missed is
    said by people (the mother, the mentor if alive, a neighbour). The dungeon's items are shown as a small pocket strip on the
    dungeon view only, the one management surface the Trial cannot do without. **DECISION D8.**
12. **The Trial's canon status is tracked in three columns from the start.** Implemented in the legacy zones; verified in the
    backbone but not implemented (Pit Fiend, Medusa, the Ninja and the diamond route 269/330, Sukumvit's final trap passages
    31/376); unverified (p.149 betrayed-Throm route, the statue riddle's correct answer, 449). The dungeon milestones (M5, M6)
    only claim what a test plays. Nothing invented is labelled canon.
13. **Permanent world and save durability.** A whole-world pickle is fragile across code versions; a world that must outlive
    updates needs a stated policy: every save carries the game version, the migrations table is used, and a save the code cannot
    read is reported with the choice to keep the file or start a new world **explicitly**. Silent regeneration is forbidden.
14. **Scope and order.** The brief wants everything; the plan orders it so that the mortal-apprentice rules and the permanent world
    (M1, M2) are proven before any content is built on them, the free opening and the village (M3, M4) make a complete playable
    game, and the Trial (M5, M6) is built in two halves with an owner checkpoint between. Each milestone is tested against the
    brief's scenarios and is a commit the owner can merge.

---

## 3. The amended design

### 3.1 Premise and freedom

Unchanged from the brief. Both apprentices spawn beside the home settlement (the host where the single-player wizard spawns, the
second on the nearest free tile). Both know the three colours and can challenge each other at once. The mentor, the mother(s), the
warehouse keeper and the Trial official are residents; everyone else is the simulation's own workers with generated personas. No
objective is shown. The road to the Trial gate is a real road; the gate is a landmark on it; people mention it.

### 3.2 Mortal apprentices (Python: `narrative/mortality.py`, new; `net/session.py`; Godot: `hybrid_world.gd`, `campaign_ui.gd`)

* **Dying.** Losing a PvP duel, a story duel marked lethal (the stranger, the Trial's monsters, Throm's forced fight) or a lethal
  trap sets the seat's `fate` to dead, creates a body resident on the tile (`status: dead`, drawn as a body, inspectable, holding
  the wizard's Trial pockets), writes a tombstone and a `wizard_died` event, closes conversations, and tells the behaviour ledger.
  Practice duels with the mentor and the warehouse rats are not lethal to the apprentice (a lost rat duel wounds: one fewer cast next
  duel, the legacy condition rule).
* **Resurrection.** A `resurrect` op: the caster stands on a tile adjacent to the body, channels for six game seconds (the `treat`
  pattern: interruptible, one at a time), the client plays a visible weave (the duel board's spell icons orbit the body, a flash,
  a sound), the body resident is removed, the seat's `fate` cleared, the wizard placed on the body's tile with their spells, weave,
  relationships and pockets intact, and an event is logged. There is no remote resurrection and no menu option. In the Trial the
  same op applies and the body stays where it fell.
* **Spectating.** A dead seat's client keeps polling `state`; the host refuses `move`, `talk`, `interact` and the duel ops with
  `dead`; the client shows a quiet banner ("You are dead. <Name> can bring you back.") and a camera that follows the survivor or
  the body (two taps to switch). Mira's lines to a dead human are notices.
* **Session end.** Private session, human dead: the host saves the world (with the body), ends the session, and the client returns to
  the main menu with one card ("<Name> died. The world goes on."). Shared session, both humans dead: the same for both; the host
  saves and stops. Both branches are tested with `tests/_party.py`.
* **The mother.** Cast per seat on enrolment: a resident of the home settlement with a persona and the `mother` role, routine
  near the apprentice's spawn, a dialogue graph. When her child kills the other apprentice inside the home territory she walks to the
  survivor, confronts them (a short scene, pages in `campaign_scenes.json` style, no pause), and the seat is `grounded` until the
  other is alive. Grounded: `move` across the territory boundary and `enter` at the Trial gate are refused with her line; the client
  shows the line as speech from her, not a system message. Lines escalate with the kill count ("Again?"), with the time the survivor
  has spent wandering, and with a protest response the player may choose. If the kill happened outside the territory (on the road,
  in the Trial), she reacts when the survivor next comes home, without grounding. In single player she grounds the human when the
  human kills Mira. If a mother dies (the world is mortal), the grounding is simply not cast; nothing waits on her.
* **Mira and death.** Mira accepts a challenge only after the human has provoked her (two refused challenges, or a fire spell near
  her, or an insulting dialogue choice; the ledger counts). After killing the human in a shared world she would resurrect them;
  in a private session that line is spoken and the session ends per the rule. After being killed and resurrected she remembers it
  (relationship and a line bank). A human dead in the Trial while Mira lives is not a case: the private session has already ended.

### 3.3 The permanent world (Python: `net/host.py`, `narrative/persist.py`, `narrative/party.py`, `narrative/clockdebt.py` new; Godot: `main_menu.gd`, `lan_menu.gd`)

* **One world per installation.** The host loads the newest valid Wizard World save if one exists and builds a world only when
  none exists or the player explicitly chooses "Start a new world" from Settings (two confirmations; the old file is renamed, not
  deleted). "Play Single Player" becomes: Continue (your wizard is alive) or New wizard (your wizard is dead or none exists). "Host
  Multiplayer" always hosts the installation's world. A guest never sends a world; its own installation's world is untouched.
* **New wizard, same world.** `new_game` becomes `new_wizard`: enrol a new seat (name, avatar), cast its mother, spawn beside the
  home settlement, and let the campaign's `on_join` and `catch_up` tell it where the world stands. Dead wizards remain as bodies and
  tombstones; Mira remembers the previous apprentice; the mentor, if dead, is dead; the stranger, if he came, has gone where he went.
* **The opening in an old world.** The campaign stage is world state. A new wizard in a world past `confrontation` gets the
  "arrived after" variant: the mentor's absence explained by people, the stranger's visit known, lessons from a surviving senior
  apprentice or nobody (Mira can teach the colours if the mentor is dead: a small line bank, no new mechanic). A new wizard in a
  world still in `explore` joins the story in progress exactly as a late joiner does today.
* **Elapsed time.** Every save records `closed_at` (wall clock) and the game version. On load the host computes the debt
  (amendment 10), clamps clock jumps (negative or more than 30 days become zero), pays it with `world.advance` in 100 ms quanta in
  the host thread before opening the lobby, reports progress, and rewrites the save with the debt consumed before any client enters.
  A crash mid-catch-up loses only the unpaid remainder. Guests never compute a debt. Determinism holds: the debt is a number of
  milliseconds, not a wall-clock decision inside the world.
* **Durability.** `persist.py` gains: the game version in the payload, a migration per narrative version bump made in this
  programme, a `.prev` kept per day for seven days (small files on a phone, measured in M0), and a load report. Repeated save,
  load and catch-up are tested for no duplicated events, no resurrected dead, no reset dungeon (acceptance test 8).

### 3.4 The free opening and the mentor (Python: `narrative/campaign.py`, `tutorial.py`, dialogue JSON)

* Stages keep their names; `training` ends when the apprentices do anything that proves they can duel (a lesson, a PvP duel, a rat
  duel) or when the fallback time passes. The mentor's `meet` line reads the ledger. Lessons remain available until the mentor dies.
* The arrival is due when the explore conditions hold (contacts now include deaths, duels, the warehouse and the gate) and no scene
  owns anyone present. If nobody present is in the settlement, the confrontation still happens (the mentor dies, the witnesses are
  whoever is there); apprentices away learn it from people when they return (`welcome_back`, already built, now spoken by a person
  rather than written in a journal).
* The confrontation scene ends with the stranger's judgement of the apprentices (authored variants for: never duelled, duelled
  each other, already killed each other, came from the Trial, unusually skilled) and his departure. No lease opens by itself. Challenging
  him is a choice on his last page and a `pvp_challenge`-like op while he is still walking out; it is a story lease with
  `opponent.stranger`, lethal.
* Aftermath as built, with the journal note replaced by people's lines; the "seek greater power" objective is said by the people
  the player talks to, never displayed.

### 3.5 The village (Python: `narrative/situations.py` new, dialogue JSON; art reuse)

* **The Central Warehouse.** At world start (and again after a cooldown in any settlement, so the village stays alive), an
  infestation is cast on the home settlement's warehouse: 4 to 6 pests with crawler sprites inside the building's footprint, one
  or two at a time outside it, moving on a seeded routine; while any live the warehouse carries a disruption factor (existing
  mechanism) and the keeper (a resident cast from the warehouse's own worker if it has one) complains, with lines that read the
  ledger (cooperating, duelling instead, burning the building, leaving). A pest is approached and fought through a story lease
  (one-slot for the small ones, two-slot for the "big rat"); defeat removes it with a visible break and a sound; a loss wounds the
  apprentice (no death). Both apprentices can clear pests at once; Mira joins when the keeper has complained to the human. The last
  pest clears the factor and the keeper reacts (differently by who did the work).
* **Three small situations**, authored in the existing graph with the Forest Dispute as the model: the smith's missing materials
  (a dispute between two real workers whose resolution moves relationships and, if the player backs the wrong one, costs a ware from
  a real stock); the ranger's patrol (walk with the ranger to the territory edge, a conversation that reveals the Trial and the wider
  world); the mentor's materials (bring a ware from the warehouse: an `interact` on the building, a real stock change). A fourth,
  "something unusual", is the arrival of the stranger's advance signs (a scorched tree, a traveller's rumour) so that the event is
  foreshadowed in the world. None of these appear as objectives; each is restartable by talking again.
* All of this survives the mentor's death and the Trial; situations recast if a cast member dies (the existing resilience idea from
  the stories plan, in its smallest form: the keeper's replacement is the next worker).

### 3.6 The Trial of Champions (Python: `wizard_rts/trial/` new package; data `wizard_rts/data/trial/*.json`; Godot: `hybrid_world.gd`, the legacy `Overworld.load_area`)

* **Placement.** The gate is a landmark entity on a road 20 to 30 tiles from the home settlement, generated at world build (deterministic
  from the seed, placed on ground that is not a settlement site). An official and the contestants stand there until the Trial begins for
  a party; the contestants' entry order is the book's. A sign and the villagers' lines make it discoverable without a marker.
* **Shared state.** One `TrialRun` per world: zone states, items taken, doors, traps sprung, Throm's state, the contestants' fates,
  gems held per wizard, and a per-wizard position (zone, tile). Both wizards may be in different zones. Entering creates the party's
  run if none is live; a second wizard entering joins the live run. Unique items are taken once. Encounters that the book writes for one
  adventurer are adapted per the report's rules (Cave Trolls: one duels while the other's fight is authored unless both apprentices
  are present, in which case each duels one; the pit: one lowers the other; Throm's forced fight is with whoever he is locked in
  with). The adapted rule for each encounter is written in the zone data with its source passages.
* **Zones.** The sixteen legacy zones are exported from `world_data.gd` to JSON once (a script, kept), with the bestiary and the
  conditions; the host validates movement, triggers, pickups, choices and leases; the client draws the zone with the legacy tile
  builder and the existing pixel art (through `asset_loader.gd`), with the touch pad and the action button. Dialogue is rewritten for
  this game in the existing graph format. Combat is the story lease on the retained 3x3 board with the Trial's opponents (one to four
  slots as the legacy bestiary says, within the `duel.wizard_3x3` tier plus the tiers this programme adds for four slots and the two
  further colours). Spell finds in the Trial grow the wizard record (Fire, Stone, Vine, Light, Shadow map onto the hybrid palette and
  weave growth), so the Trial is the first "greater magic".
* **Death in the Trial.** The rules of 3.2 apply: the body stays where it fell with its pockets; the survivor may walk back to it and
  resurrect; monsters near a body are the danger that makes it a decision. When every wizard in the run is dead the run ends: a shared
  session ends for both, a private one for the human; the bodies remain in the dungeon for the next contestants to find; Sukumvit's
  staff reset traps, monsters and the unique items that no body holds for the next Trial (the dungeon's own fiction), while bodies and
  the gems they hold stay. **DECISION D9.**
* **Canon status table** (`docs/TRIAL_CANON_STATUS.md`, kept current by the milestones): every zone and encounter in one of the three
  columns of amendment 12, with the source passages and the test that plays it.

### 3.7 Mobile simplicity (Godot)

No journal, objective, markers or checklists in the player build (amendment 11). The dungeon view adds a pocket strip of at most eight
icons. All reactions are speech from a person on screen. Conversations keep the existing card with large buttons. Nothing new on the
HUD beyond the dead banner and the catch-up line.

### 3.8 One persistent simulated world

Unchanged architecture: one `HybridWorld`, host authority, no second economy, the faction AIs untouched, no new roster entities,
the neuroevolution package and its tests untouched, the hash baselines and determinism tests green at every milestone. Narrative
code keeps the stories contract: sorted iteration, seeded `random.Random`, typed effects with receipts, nothing appended to
`world.events`.

---

## 4. Milestones

Branch: `feature/opening-rpg-and-trial`, cut from `main` at `e6e6399b`. One commit per task when practical, pushed after each;
never `git add -A`; `docs/release_notes.md` is never committed. Merging into `main` is the owner's call at each checkpoint.
Each milestone names the brief's scenario it proves. **OC** marks an owner checkpoint: the next milestone starts only on the owner's word.

### M0 Baseline and measurements (1 session)

* Full Python suite and the headed set on the branch; pre-existing failures recorded in the ledger.
* Export the sixteen `dd_*` zones and the bestiary to JSON with a script; a parity test that the export equals the GDScript tables.
* Build the APK and, **on the owner's phone**, measure: narrative world speed (simulated seconds per real second with Mira present),
  the cost of one simulated minute of catch-up on a `small` map early and mid-game, save file size and write time.
* The Trial canon status table, first version (implemented / verified / unverified), from `DD/` and the legacy zones.
* Done when: the measurements are in `docs/evidence/opening_rpg/m0/` and the numbers in amendment 10 are confirmed or replaced.

### M1 Mortal apprentices (2 to 3 sessions) — scenarios A, B, G (village part)

* `narrative/mortality.py`: death from a PvP loss and from lethal leases, the body resident, tombstone, events, the `resurrect` op,
  spectating refusals, session end rules; the behaviour ledger (`narrative/ledger.py`).
* The mother: casting per seat, the confrontation, the grounding and its refusals, line banks with escalation, softlock rules.
* Mira: provocation counter, acceptance, her reactions to death and resurrection, her resurrection of a human in a shared world
  (used only by tests until a second AI exists).
* No world pause for duels in Wizard World (amendment 4).
* Godot: the resurrection channel and effect, the dead banner and camera, the "died" card and return to the menu, speech from the
  mother. Headed: `run_hybrid_mortality.gd` (two wizards, one kills the other on the real board, the mother, the resurrection).
* Python: `tests/test_mortality.py` (through `tests/_party.py`: scenarios A and B, both-dead, body relocation, grounding lifts,
  refusal reasons, idempotent resurrect, determinism and hash baselines unchanged).
* **OC1.**

### M2 The permanent world (2 sessions) — persistence tests 1 to 8

* Save with the dead; `new_wizard`; menu wording; the explicit "Start a new world"; host-only world; guest protection.
* `closed_at`, the debt, the catch-up thread, the progress line, "Enter now", write-off before clients enter.
* Durability: version in the payload, migrations, daily `.prev`, load report, no silent regeneration.
* The campaign in an old world (3.3), spoken by people, journal removed from the player build (amendment 11).
* Tests: `tests/test_permanent_world.py` covering the brief's eight acceptance tests, plus "repeated catch-up never double-applies",
  "a 30-day clock jump is clamped", "a newer save is refused with the report". Headed: `run_hybrid_new_wizard.gd` (die, menu, new
  wizard, the mentor still dead).
* **OC2** (the rules are proven; content starts).

### M3 The free opening (2 sessions) — scenarios D, E (opening part), F

* Training as an activity; arrival conditions; confrontation variants; the optional challenge; the stranger's departure to a recorded
  place; the mentor's ledger-aware lines; what-you-missed by people; the first humour pass (mother, mentor, warehouse keeper
  placeholders).
* Tests: `test_wizard_campaign.py` updated (no forced lease; the away-in-the-Trial case; two humans in different places; a wizard
  who never spoke to the mentor); headed `apprentice_win` / `apprentice_lose` rewritten as `run_hybrid_opening.gd`.
* Scenario F is proven here with a stub Trial area (the gate exists and can be entered; the interior is M5).

### M4 The village (2 sessions) — scenario C

* The warehouse infestation: pests, the disruption factor, the keeper, the leases, the effect and sound, Mira joining, the recast.
* The three situations and the foreshadowing; the second humour pass (keeper, official, twenty-minutes-of-duelling, doing nothing).
* Tests: `test_village_situations.py` (the factor applies and clears, wares conserved, both apprentices clear pests at once, the
  keeper's four reactions, situations survive the mentor's death); headed `run_hybrid_warehouse.gd`.
* **OC3: a complete playable opening.** Owner playtest on the PC and, if the M0 phone build held up, on two phones.

### M5 The Trial, first half (3 sessions) — scenarios E, F, G

* `wizard_rts/trial/`: `TrialRun`, zone loading from the exported JSON, per-wizard positions, shared items, triggers, choices,
  conditions, leases, death and bodies in the dungeon, the run end and Sukumvit's reset.
* The gate on the map with the official and the contestants; zones A to D (entrance, fork, galleries, pit, lower route) with the
  two-player adaptations and rewritten dialogue; the pocket strip; the dungeon drawn by the legacy tile builder inside the hybrid
  scene; LAN `state` carries the zone.
* The canon status table updated; a Godot headed `run_hybrid_trial_a_d.gd` (two clients: separate, meet at the pit, one dies to the
  Cave Troll, the other walks back and resurrects); Python `tests/test_trial.py` (every branch of A to D, shared items, the unprepared
  entry before any lesson, the stranger arriving while both are inside).
* **OC4.**

### M6 The Trial, second half (3 to 4 sessions)

* Zones E to K: Trialmaster (Throm's forced fight, the dice and cobra tests as choices), idol and emerald, grotto and the elf, vaults and
  the sapphire, the diamond (true and false), service tunnels and the prisoner, mirror gallery, Bloodbeast with the learned weakness,
  grub tunnels, troglodytes, manticore, Igbut's gem lock and the final trap; the spell and weave growth; the champion's exit.
* The verified-but-unimplemented encounters are either built with their passages cited or left in the table as not built; the
  unverified ones stay unverified. No invented content is called canon.
* `run_hybrid_trial_full.gd` (a complete run with two clients, including a both-die ending and the next contestants finding the
  bodies); `test_trial.py` extended to every branch.
* **OC5.**

### M7 Mira in the story and the Trial, humour pass three, polish (1 to 2 sessions)

* Mira's goals: follow, help with pests, go to the Trial with the human, pick up what she is told to, answer the mentor, speak at scenes;
  the Trial adaptations for a human plus Mira. Repeated-behaviour variety across all speakers, the fourth-wall lines (rare, counted).
* Owner dialogue review of every placeholder line bank.

### M8 Android and the two-phone acceptance (1 session plus the owner's time) — scenario H

* APK build, asset audit (the pixel art and the Mindustry crawler must pass the exported-pack probe), performance on the phone with
  the Trial loaded, the two-phone checklist extended with scenarios A to G, the build-and-test instructions.
* **OC6 (final)**: the owner's two-phone playtest. The final report lists what was played on phones and what only on the PC.

Order of priority if time runs short: M1 and M2 are not negotiable; M3 and M4 make the game; M5 before M6; M7 and M8 close.

---

## 5. Testing

* Every rule in Python is tested through `tests/_party.py` real sessions (host, two links, an AI link, an advanceable clock), never by
  calling internals directly, so that what is tested is what a phone would send.
* Every gameplay claim is also played through the real Godot scene with genuine casts on the board (the stories execution plan's rule 9).
  Headed scripts run against a fresh host on a free port; evidence shots under `WizardRTSHybrid/docs/evidence/opening_rpg/<milestone>/`.
* The adverse scenarios are tests, not notes: immediate murder, kill-resurrect loops, both die in the Trial, one in the Trial during the
  confrontation, a wizard who never talks to anyone, a guest who disconnects mid-resurrection, a host killed mid-catch-up, two
  consecutive new wizards in a world where the first two died.
* Gates at every commit: `test_hash_baseline`, `test_determinism`, `test_content_freeze`, the neuro tests, `test_lan_multiplayer`,
  `test_android_assets`.
* Phones: the owner's checklist; nothing is reported as phone-verified without the owner's run.

---

## 6. Risks and limits (stated now, not discovered later)

| Risk | Handling |
| --- | --- |
| Phone CPU: the narrative world plus Mira plus the Trial on the host phone | M0 measures before any rule is fixed; the catch-up cap and the view radius are tuned from it; the Trial zones are small tile areas |
| A whole-world pickle must outlive updates | Version in the payload, migrations written with every narrative bump, explicit refusal with options; still, a save from before this programme (0.2.0) will not be migrated: 0.3.0 starts the permanent world |
| The legacy zones were written for one adventurer and a four-colour game | Each encounter's two-player rule and palette mapping is written in the zone data with its passages; the canon table says what changed |
| Scope | Milestone order and owner checkpoints; the Trial's second half is the part most likely to slip, and the game is complete without it at OC3 |
| Humour that lands flat or repeats | Placeholder prose is marked for the owner's review at M7; cooldowns and escalation are in data, not code |
| No pause for duels changes a retained test (`hazard_duel` pause) | The retained Ward Duel test keeps its pause in the developer profiles; only Wizard World sessions skip the token |
| Freeze (D33) | No roster entity is added; pests, bodies and contestants are narrative actors like the mentor; `freeze_content.py --check` runs at every commit |
| Neuroevolution programme | Untouched files per the stories contract; its tests in the gate |

---

## 7. Decisions for the owner's sign-off

Each has the recommended default. Signing off the plan with no comment accepts the defaults.

| # | Decision | Recommended default |
| --- | --- | --- |
| D1 | The stranger's lethal duel becomes optional (he leaves; a challenge is the player's choice; losing is death under the new rules) | Yes |
| D2 | The revised death rule replaces the built Game Over: single-player human death ends the session at once; Mira never resurrects a human in single player | Yes |
| D3 | No duel pauses the world in Wizard World | Yes |
| D4 | One mother per apprentice seat, cast on enrolment | Yes |
| D5 | Rats are narrative pests with the crawler sprite, not roster units | Yes |
| D6 | The Trial is an interior area entered through a gate on the map, host-owned, drawn by the legacy tile builder | Yes |
| D7 | Offline progression: 10 simulated minutes per real hour away, capped at 30 simulated minutes per reopening, paid by the real simulation at the menu with "Enter now"; final numbers from the M0 phone measurement | Yes |
| D8 | Journal, objective line and flashes removed from the player build; a pocket strip is the only management surface, in the Trial only | Yes |
| D9 | When every wizard of a run dies, the Trial resets traps, monsters and unheld unique items; bodies and what they hold remain | Yes |
| D10 | 0.3.0 starts the permanent world; 0.2.0 saves are not migrated | Yes |
| D11 | Work on `feature/opening-rpg-and-trial`; the owner merges at checkpoints | Yes |

---

## 8. Deliverables at the end of the programme

1. The gameplay experience in one page (`docs/OPENING_RPG_PLAYER_GUIDE.md`).
2. What is implemented and how it was tested, per milestone, with evidence paths (`docs/ledger/OPENING_RPG_PROGRESS.md`).
3. The Trial canon status table (`docs/TRIAL_CANON_STATUS.md`) and every other gap.
4. Build and two-phone test instructions (an update to `README_ANDROID_TWO_PHONES.md` and the checklist).
5. Branch and commit references in the ledger's session log.
