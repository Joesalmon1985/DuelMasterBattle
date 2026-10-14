# Plan: Wizard Mode in the real RTS world, the magic tutorial, living characters and three dynamic storylines per settlement

Status: **REVISED after owner review (14 October 2026), awaiting approval. No gameplay code is changed by this document.** Branch `feature/wizard-settlement-stories` (worktree `/home/joe/dmb_runs/wt_wizard_stories`), cut from `origin/feature/neuroevolution-plan` at `4b67f55c`. Audit of what exists: `WIZARD_NARRATIVE_AUDIT.md` (sections 9 to 13 were added for this revision). Tasks: `EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`. Interface assumptions and foreseeable merge conflicts: `WIZARD_STORY_INTEGRATION_CONTRACT.md`. Ledger: `ledger/WIZARD_STORIES_PROGRESS.md`.

The owner's criterion: **launch the current RTS game, inhabit it as a wizard, learn magic from someone who lives there, and undertake meaningful quests inside the same continuously simulated world.** One integrated game, not an RPG bolted onto an RTS.

Decisions in force that this plan obeys: D02 (the wizard commands no faction), D03/D07 (square grid, settlement = command centre plus territory), D10 (real world effects), D11 (cycle reset keeps only the wizard), D14 (Python owns the world, Godot presents), D19 (named canon deferred; preserve existing stories), D22 (inexhaustible mines; collapse is the shortage cause), D33 (content freeze), D34 (neuroevolution is the other workstream; this plan neither touches it nor designs for it beyond documenting interfaces). Owner decisions from the 14 October review are recorded in section 15 and applied throughout.

Terms: a **story** is a template bound to a settlement; a **quest** is a story the wizard has accepted (one `QuestService` instance); a **slot** is one of the three story positions a settlement holds; a **character** is a Person record (`world.dmb.people`) with a persistent identity; a **resident** is a character the narrative layer created (spouse, child, elder, apprentice, teacher) and moves; a **linked character** is a Person bound to a simulation entity (worker, carrier, unit) that the simulation moves.

---

## 1. One world, and how the wizard enters it

### 1.1 What exists today (verified)

`scripts/launch_scenario.sh campaign` runs `launch_hybrid.sh wizard`: it starts `python3 -m wizard_rts.server` with `HYBRID_PROFILE=campaign` (gated tech, no God Mode, primitive start) and opens Godot on `client/scenes/hybrid_world.tscn`. The scene polls `advance` every 200 ms, so the six faction AIs play while the wizard walks; the wizard's pose goes back with `pose`; a click on an entity opens a semantic label (`wizard_labels.gd`); E at the route hazard opens the retained Ward Duel board inside the scene through `DmbDuelLeaseAdapter` under a Python lease; `story_ui.gd` draws story persons, dialogue, dungeon rooms and the Mastermind board from `story.dispatch` replies. The wizard starts "just east of the Red settlement" (`world._stand_near(red["road"])`). G switches to God Mode only when the profile allows it.

So the integrated launch already exists. What is missing for the owner's criterion: a person to learn from, a known-spell record, a tutorial duel in the Ward Duel format, a way to talk to the simulation's own workers (today only the story's separate `npc` rows are talk targets), building interaction, a journal, save and load, and the narrative systems of sections 5 to 11.

### 1.2 Architecture of the integrated game

```text
HybridWorld (wizard_rts/world.py)                         <- the only simulation; untouched by this plan
  advance(): economy, logistics, construction, industry, story.story_quantum, vp, regions, ..., ai, military
                                              |
                 story.story_quantum (wizard-owned story.py)
                   |-- legacy families (today)            : collapsed mine, outbreak
                   `-- narrative.tick(world)              : runs only when world.narrative exists (created by server.py, never by HybridEnv)
                         director (slots, casting, living checks)    residents (routines, lifecycle)    tutorial    interrupts (worker summons)
  snapshot(): ... entities.extend(story.entity_rows(world)) ...  story.snapshot(world)   <- residents, persons, journal, lessons ride on these hooks
  server.py: story.WIZARD_OPS (talk, choose, observe, ask_out, accept, journal, duel_*, save, load, ...)

Godot hybrid_world.gd + story_ui.gd + wizard_labels.gd + DmbDuelLeaseAdapter + game_board.tscn : presentation only, no rules
```

Three consequences. First, **no change to `world.py`** is needed: the narrative tick hangs off the existing `story.story_quantum` call, narrative rows ride on the existing `story.entity_rows` and `story.snapshot` hooks, and the wizard's ops already dispatch through `story.WIZARD_OPS`. Second, **training worlds never see the narrative layer**, not by a gate but by construction: `world.narrative` is created by `server.py` (and by the wizard-facing environments when they ask for it), never by `HybridWorld.__init__` or `HybridEnv`. Third, the **only shared-simulation change** this plan needs is the worker summon in `workers.py` (section 8), additive and inert unless a wizard asks a worker outside.

### 1.3 Module map (new package `WizardRTSHybrid/wizard_rts/narrative/`)

| Module | Responsibility | Writes |
| --- | --- | --- |
| `__init__.py` | `state(world)` (the `world.narrative` dict, pickled with the world), `tick(world)` called by `story.story_quantum`, config loading, version stamp | `world.narrative` |
| `config.py` | `data/narrative/config.json`: unlock time (20 game minutes), tutorial expiry (30), slots (3), journal cap (4), cadences, caps, archetype library paths | |
| `wizard.py` | wizard progression: `spells`, `weave_size`, `lessons`, `duels`, `worldview`, journal notes, visited settlements; Aspects stay in `AspectService` | `world.narrative["wizard"]` |
| `duel_lease.py` | Ward Duel leases for the wizard (tutorial, quests, dungeon wardens): encounter from the wizard's progression and the opponent's tier, `bot_seed`, fixed wards, pause token, Python-side verification of the reported casts, checkpoints | `world.dmb.leases`, `world.dmb.clock["pause_tokens"]` |
| `characters.py` | persistent identities (`identity_for`), the archetype library (`data/narrative/archetypes/*.json`), name generation, relationships, history; the **link** between a Person and a simulation entity (section 6) | `world.dmb.people[pid]` (`identity`, `archetype`, `link`) |
| `residents.py` | residents the narrative layer created: creation, routines, bounded movement, lifecycle (absent, inside, moving, displaced, departed, dead), expiry of temporary characters | `world.narrative["residents"]` |
| `interrupt.py` | the wizard's building interaction: asks `workers.summon`, holds the conversation, releases the worker; fallbacks | calls `workers.summon/release`; `world.narrative["conversations"]` |
| `tutorial.py` | the lessons, the teacher and the two helpers, the notes landmark, the replacement teacher, the unlock rule | `world.narrative["wizard"]["lessons"]`, residents |
| `context.py` | `settlement_context(world, sid)` cached by a version stamp (section 10.2) | cache |
| `templates.py`, `graph.py`, `facts.py`, `dialogue.py`, `effects.py` | template v2 loader and validator; the story-graph runtime (Village Test node semantics in Python); truthful facts; dialogue packs; the two effect registries with receipts | per-quest graph state in `world.narrative["quests"]`, `world.dmb.command_receipts` |
| `casting.py` | bind roles to real entities and residents; dry-run casting; **contingency rebinding** (section 7) | links, quest bindings |
| `director.py` | per-settlement slots, eligibility, scoring, selection, refill, living-story checks (section 10) | `world.narrative["settlements"]`, `QuestService`, `CauseTracker` |
| `ops.py` | the wizard ops added to `story.WIZARD_OPS`: `observe`, `ask_out`, `end_talk`, `accept`, `decline`, `journal`, `lessons`, `travel_hint`, `duel_resolve`, `duel_checkpoint`; `save`/`load` live in `server.py` | |
| `persist.py` | save and load: atomic pickle with format, hash and narrative version; recovery policy (section 12) | files under `$DMB_RUNS/saves/` |
| `events.py` | the narrative log and the presentation events in `story.snapshot()["narrative"]["events"]`; nothing new is appended to `world.events` | `world.narrative["log"]` |
| `perf.py` | counters for the performance tests | |

Data: `WizardRTSHybrid/wizard_rts/data/narrative/{config.json, archetypes/*.json, names/*.json, opponents.json, role_map.json, schema/*.json, templates/*.json, casts/*.json, dialogue/*.json}` and one new tier in `godot_project/content/source/duel_rules/progression.json`. Tests: `WizardRTSHybrid/tests/test_narrative_*.py`, `test_wizard_*.py`. Godot: `client/hybrid/story_ui.gd`, `wizard_labels.gd`, `client/scenes/hybrid_world.gd`, `client/scripts/game_board.gd` (one optional lease flag), `client/tests/run_hybrid_{launch,tutorial,quest,stories,acceptance}.gd`.

---

## 2. The magic tutorial: three colours, three weave slots

### 2.1 Which duel implementation (audit result, `WIZARD_NARRATIVE_AUDIT.md` section 9)

Two duel mechanics exist. `sim/dmb/adventure/mastermind.py` is a one-sided code-breaking game (the player guesses the warden's four-slot, six-colour code; the warden never casts back). The retained **Ward Duel** (`godot_project/sim/battle_sim.gd` with `combatant.gd`, `feedback.gd`, `weave_bot.gd`; Python port `wizard_rts/duel/ward.py`, parity-tested) is two-sided: each side hides a Ward of `ward_size` loci from its `ward_pool` and casts weaves of `weave_size` spells from its `attack_pool`; feedback is fracture (right spell, right locus), echo (right spell, wrong locus) and fade; the first to break the other's Ward wins; casts are timed windows in Godot and turns in the Python core. Every parameter is per combatant and already data-driven: the bestiary and the Ashby lessons use sizes 1, 2 and 3 and pools of two or three spells; `encounter_for_tier` in `sim/dmb/adventure/duels.py` builds an encounter from `progression.json` tiers (4/6, 5/7, 6/8 today) and the hazard lease hands it to `game_board.tscn` through `DmbDuelLeaseAdapter`, which `hybrid_world.gd` already hosts.

**Decision: the Ward Duel is the one duel of Wizard Mode.** The tutorial teaches it with three colours and three slots; later duels use the same engine with more colours, bigger weaves and harder opponents. The warden's Mastermind duel in the collapsed-mine story becomes a Ward Duel against the warden (Milestone C), so the tutorial teaches what the player then uses. `mastermind.py` and `MastermindEnv` stay for the headless environments and tests; nothing is deleted.

Required adaptations, all small:

| Change | Where | Size | Why |
| --- | --- | --- | --- |
| A tier `duel.tutorial_3x3` (`slot_count 3, colour_count 3, max_casts 8, allow_repeats true`) and a tier `duel.wizard_3x3` for early quest duels; `era_binding` unchanged | `godot_project/content/source/duel_rules/progression.json` (data) | 12 lines | tiers are the only legal way to change duel mechanics (the file's own note) |
| `narrative/duel_lease.py`: build a lease record of kind `story_ward_duel` with the same fields the hazard lease has (`encounter`, `bot_seed`, `checkpoint`, `pause_token`), the player combatant from the wizard's progression (`spells`, `weave_size`), the enemy combatant from the opponent (archetype tier, `fixed_ward` for the told lesson, `bot_logic`, think band), stored in `world.dmb.leases`; `acquire_pause("story_duel")` | new, wizard-owned | ~150 lines | the hazard code (`HazardDuelService.begin`) is written for cubes; copying its lease shape rather than editing the legacy file keeps the "frozen by convention" rule |
| `story.duel_begin/duel_abandon` create and release the lease; new ops `duel_resolve` (Godot reports outcome, cast counts, history and the checkpoint) and `duel_checkpoint` (every cast) | `story.py`, `narrative/ops.py` | ~80 lines | one Python owner of duel state |
| Python verifies the report: the enemy ward is reproduced in Python (`WeaveBot.generate_ward` with the lease's seed is bit-for-bit with Godot's RNG, or the `fixed_ward`), every reported player attack is re-scored with `ward.score_attack`, and "broken" must hold for a claimed win; a report that fails verification is rejected and the lease voided | `narrative/duel_lease.py` | ~40 lines | Godot never owns an outcome |
| `hybrid_world.gd`: open the adapter from a `duel` reply of any story op (today only from `interact`); route `ResolveHazardDuel` to `duel_resolve` when the lease kind is `story_ward_duel`; forward the adapter's checkpoints | `client/scenes/hybrid_world.gd` | ~40 lines | reuse the hosted board |
| Optional: `lease_config["reveal_rival_ward"]` sets the rival slots' `hidden_mode = false` during the told-ward lesson | `client/scripts/game_board.gd` | ~10 lines | the Ashby lessons *tell* the ward in dialogue; showing it on the board too is a presentation nicety, not required |
| `story_ui.gd`: delete the Mastermind board once the warden uses the lease (Milestone C) | `client/hybrid/story_ui.gd` | removal | one duel UI |

Headless: `WardDuel` (`ward.py`) plays the same lease turn by turn; `story_agent.py` gains a candidate-filter solver from the player side (`WeaveBot(me=player, target=enemy)` already implements it) so the scripted playthrough can win duels.

### 2.2 The three starting colours

The hybrid's dungeon puzzles already know three spells: Flame, Frost and Vine (`puzzle/logic.py` checks `ctx["spells"]`). Those are the starting palette: spell ids **0 Flame, 1 Frost, 6 Vine** from the retained ten-colour palette (`DmbConstants`; the core six are 0, 1, 3, 4, 6, 9). Fire magic in the world (`magic.fire`) is the Flame spell's overworld use. Later colours (Stone 3, Light 4, Arcane 9, then 2, 5) are learned from stories, dungeons and teachers; the weave grows to 4 at the first era tier and up to the supported cap of 6 slots and 8 colours.

### 2.3 The introductory progression (exact)

The teacher and two helpers are **temporary residents** (section 7.5) cast near the starting settlement at minute 0. Nothing below protects them from the simulation.

| Step | Lesson id | What happens (through real systems) | Completion record |
| --- | --- | --- | --- |
| 1 Meeting the teacher | `meet` | The teacher stands near the settlement centre (routine `near_centre`). Talk (click, or E in range). Opening lines come from the `tutorial.teacher` pack. The journal gains a "Lessons" panel. | `lessons.meet = game_ms` |
| 2 The three colours | `colours` | The teacher gives the wizard **Flame, Frost and Vine** in one lesson (narrative effect `learn_spell` ×3 and `grow_weave 3`). The lesson text explains the palette and that a Ward hides three of these. The wizard's Ward is three loci from the same three spells. A one-line check: the fire label on a tree now says "burn it" and works (Flame known). | `lessons.colours`, `wizard.spells = [0,1,6]`, `wizard.weave_size = 3` |
| 3 The three weave slots | `weave` | A dry run on the board itself: the teacher opens the board in **ward-setup only** (the lease is created with `practice: "setup"`; the board's Ward setup phase is played and then the lease is voided without a duel). The player places three spells, locks the Ward, reads the hint line. | `lessons.weave` |
| 4 Practising against a revealed ward | `told_ward` | The teacher says their Ward aloud ("Frost, then Vine, then Frost") and the lease uses `fixed_ward` for exactly that; `bot_logic: "random"` with `bot_mistake_rate 0.4`, generous casts (8); optional `reveal_rival_ward`. Breaking it in one or two casts is the point: fracture means right spell in the right slot. Loss is impossible unless the player dawdles; either way the lesson completes. | `lessons.told_ward`, `wizard.duels.won` |
| 5 A genuine duel against a hidden ward | `hidden_ward` | The teacher's Ward is hidden (seeded by the lease, `candidate_filter`, easy profile think band 26 to 48 s, 8 casts each). The result is real: a loss is recorded, the teacher comments, and the player may retry (a new attempt, new seed). Completion is **having fought it**, not having won it. The lesson lines explain echo versus fracture using the player's own last cast (facts from the history). | `lessons.hidden_ward` |
| 6 Magic and the world | `world` | The teacher points at the settlement: observe a workplace (`observe` op on a building within 3 tiles returns what it makes and why it is idle), then the helper, an apprentice, has a tiny simple-tier story ("find my dropped tally stick by the warehouse": an `investigate` node on a real building) that ends with a history fact and the journal's explanation of rumours versus quests. If the settlement holds a live collapse or outbreak, the teacher names it instead. | `lessons.world` |

Essential set `{meet, colours, told_ward, hidden_ward}`, configurable. Lessons 3 and 6 are recommended but optional. Lessons never close; the teacher, the notes or the replacement teacher (section 7.5) offer the next undone lesson on every talk.

### 2.4 Unlock rule (approved)

Dynamic settlement stories unlock when **all essential lessons are done OR `game_ms >= unlock_after_ms`**, whichever comes first; default **20 game minutes**, `config.narrative.unlock_after_ms`, overridable by `HYBRID_NARRATIVE_UNLOCK_MS` for tests. Before the unlock the director still fills slots (so a settlement is never empty) but offers only simple-tier stories; after the unlock, everything.

### 2.5 Where the wizard's magic lives and how it is restored

`world.narrative["wizard"] = {"spells": [ids], "weave_size": n, "lessons": {id: game_ms}, "duels": {"won": n, "lost": n, "attempts": [...]}, "worldview": {M,A,R,G,S,D,C}, "journal_notes": [...], "visited": [sids], "version": 1}`. It is pickled with the world (save and load, section 12) and copied by `server.py` into the fresh world on a cycle reset (D11: the wizard carries over; `history.cycle_reset` already carries Aspect scores the same way). The player's combatant is built from it exactly as the retired `DmbProgression.to_combatant` did (ward size equals weave size, repeats allowed, 10 casts). Expansion is data: `learn_spell`, `grow_weave` and `set_cast_budget` are narrative-only effects any template may grant; opponents are archetype tiers in `data/narrative/opponents.json` (combatant fields plus a think band), validated against the supported caps.

---

## 3. The first playable vertical slice (Milestone C, after A and B)

The slice the owner asked for, end to end, on the real `campaign` world:

1. `launch_scenario.sh campaign`: six AIs, the wizard beside the Red home settlement.
2. Talk to the teacher; take lessons 1, 2, 4, 5 (about six minutes of play).
3. Walk to the Red coal mine. The mine's own worker is a linked character (section 6): clicking the worker or the mine shows the person's name and "Ask the miner to come out"; the miner stops digging, walks to the door, the conversation opens (section 8). If the mine's gallery has collapsed (the developer fixture `story` forces it; in a plain campaign the director's simple stories fill the time until a collapse or outbreak happens), the miner offers the collapsed-gallery story.
4. Accept; the journal shows the objective; the miner goes back to work.
5. Evidence, the Aspect check, the sigil, the old gallery (four puzzle rooms), the warden: a **Ward Duel** against the warden's three-colour Ward (the lease, the hosted board).
6. `reopen_gallery`: the gallery clears through `disruption.clear`; the mine's programme runs again; coal reaches the warehouse; the smelter restarts. The AIs never learn why.
7. Save from the pause menu, quit, relaunch, load: the journal, the miner's identity, the gallery and the clock are as left.

Everything in the slice already exists in some form except: the person link, building interaction and work interruption, the Ward lease, the journal and save/load. Those are Milestones A to C.

---

## 4. Characters: persistent identities from modular archetypes (Q2, hybrid approach approved)

### 4.1 Identity

Every character the wizard can meet is a Person record (`PeopleService.create_person`, `world.dmb.people`). The narrative layer adds `person["identity"] = {"name": ..., "given": ..., "family": ..., "epithet": ..., "born_ms": ..., "origin_sid": ..., "seed": int}` and `person["archetype"] = {"id": ..., "version": n, "tags": [...], "voice": [...], "scores": {...}}`. The identity is created once and never regenerated; the name comes from `data/narrative/names/<tribe>.json` seeded by `crc32(world.seed, entity id or resident id)`, so the same world always names the same miner the same way, and two miners differ. The 88 profiles are not named individuals in the world (D19); their names stay in the library as example material.

### 4.2 The archetype library

`data/narrative/archetypes/*.json`, one file per archetype, validated by `data/narrative/schema/archetype.json`:

```jsonc
{"id": "arch.suspicious_climber", "schema_version": 1, "version": 1, "source": "88 profiles: row 23 (name, district and base stripped)",
 "fits": {"roles": ["worker", "processor", "miner", "apprentice", "carrier"], "tiers": ["primary", "supporting"], "eras": "all", "exclude_roles": ["child"]},
 "personality": {"virtue": "Diligent", "shadow": "Envious", "mood": "watchful", "humour": "dry"},
 "motivation": {"desire": "to be the one they cannot do without", "fear": "being passed over", "secret": "has been counting the keeper's stock"},
 "voice": {"register": "clipped", "tics": ["answers a question with a question"], "tone_tags": ["wary", "ambitious"]},
 "worldview": {"primary": "G", "secondary": "M", "scores": {"M": 1, "A": 0, "R": 0, "G": 3, "S": 1, "D": 0, "C": 1}},
 "relationships": {"wants": ["rival_same_role"], "avoids": ["authority_figure"]},
 "hooks": {"story_tags": ["disputed_ownership", "withheld_resource", "absent_worker"], "complication": "...", "alternate_solution": "..."},
 "lines": {"intro": ["..."], "vulnerable": ["..."], "angry": ["..."], "lie": ["..."], "truth": ["..."]},
 "absence": "the keeper's count is short the week after"}
```

The loader (`characters.load_archetypes`) reads every file in the directory, validates, and indexes by `fits`. Adding an archetype is adding a file; the generation code does not change. `scripts/build_archetypes.py --from-profiles docs/characters/DMB_Character_Profiles_88_Disco_Elysium_Depth.csv` converts the 88 profiles into archetypes once (names, districts and home bases stripped; `Village_Role` becomes `fits.roles`; the voice, temperament, desire, fear, secret, worldview scores, attitudes, conflict style, quest hook, complication, alternate solution, puzzle type and the five lines map one to one), so the library starts at 88 and is `approved: false` until read.

### 4.3 Assignment

When a character is created or first linked, `characters.assign_archetype(world, pid)` picks from the archetypes whose `fits` match the character's occupation, tier and era, excluding archetypes already used in the same settlement (so a settlement is not three suspicious climbers), by a seeded pick `crc32(world.seed, pid, "archetype")`. The choice is permanent for that Person. A miner's archetype goes with the miner when the same person changes job (section 6.3); it never transfers to a replacement.

### 4.4 Occupation, faction and world conditioning

Dialogue selection (section 11.3) keys lines by `(pack, node, role, variant)` and then by archetype `tone_tags` and `worldview.primary`; facts fill `{placeholders}` from the live world; the occupation and faction add the `{occupation}`, `{workplace}`, `{faction}`, `{tribe}` placeholders and the role baseline pack (`settlement_normal.json` kept). A character's `relationship_map` (existing field, -100 to 100), `known_facts` and `history_refs` (existing) hold relationships and history; stories write them with the narrative-only effects.

### 4.5 Compatibility with the 112-story workbook

Workbook casts list twelve personalities per cast by occupational role. The converter (section 11.2) maps each personality word to archetype `personality.virtue`/`shadow` tags and emits them as **preferences** on the role (`prefer_archetype_tags`), not as fixed assignments, so the director casts a real person whose archetype fits best and the lines still read true. Where no character with a fitting archetype exists, the lines fall back to their neutral variant.

---

## 5. Supporting characters: all characters are mortal (Q3 revised)

### 5.1 Residents

The simulation has workers (one per workplace role), carriers (per road) and units; it has no spouses, children, elders or apprentices. The narrative layer may create **residents**: Person records with `link = {"kind": "resident", "home": building id, "settlement": sid}`, a `routine`, a position and a lifecycle state, kept in `world.narrative["residents"][pid]` and drawn by Godot from `story.entity_rows` as `npc` rows (the figure chosen by role and tribe as today). No fixed cap of four: the caps are per household and per settlement in `config.json` (`residents.per_workplace` default 2, `residents.per_centre` default 4, `residents.per_settlement` default 12) and the director creates a resident only when a story needs one or a household archetype asks for one at casting time; residents are never created for decoration.

### 5.2 One lifecycle for workers, soldiers and residents

`characters.lifecycle(world, pid)` returns one of the states below for any character, computed from the authoritative source for that kind of character; stories, dialogue and casting read only this.

| State | Worker (`world.workers` row) | Unit (`world.units` row) | Resident (narrative) | Quest reading |
| --- | --- | --- | --- | --- |
| `present` | row exists, on a walkable tile outside | alive, deployed | routine `about` or `near` | talk in range |
| `inside` | row at the building tile, idle, no path (`snapshot row["inside"]`) | garrisoned or inside a transport | routine `inside` (home) | talk through the building (`ask_out`) |
| `working_away` | path or programme running elsewhere (cutting, carrying) | on an order | n/a | talk when within range; `ask_out` from the workplace calls the worker back |
| `absent` | summoned elsewhere, or in a dungeon with the wizard | away on a long order | temporary absence (`visiting` another building for a routine beat) | wait; dialogue says where they went |
| `moved` | the link now points at a worker of another building (same person, new job; section 6.3) | redeployed | routine rebound to a new home (displaced, then rehoused) | rebind location, keep identity |
| `changed_job` | same person, `worker["role"]` differs from the link's recorded role | n/a | became a worker (a resident takes a vacant job: `assign_job`) | identity kept; occupational lines change |
| `displaced` | `PeopleService.displace` (home destroyed; the worker row is gone, the person is alive and unhoused) | n/a | home destroyed while outside; routine rebound to the settlement centre; if no standing settlement of the faction within 60 tiles, `departed` after 5 game minutes | `displaced_route` (the person is found at the centre) |
| `dead` | `record_death` (fire magic; inside a building when it was destroyed; "caught in the fighting": within 1 tile of a building destroyed by combat) | `kill_unit` | fire magic; inside a destroyed home; within 1 tile of a building destroyed by combat; outbreak illness (section 5.3) | `dead_route` (section 7) |
| `departed` | n/a (workers do not leave) | n/a | voluntary departure: temporary characters at expiry, displaced residents with nowhere to go, a story ending that sends someone away | `departed_route`; a history fact says where to |
| `removed` | n/a | n/a | a temporary character whose purpose ended and who is not referenced by any open quest, after `departed` | never referenced again; the Person record remains (`status: "departed"`) |

Dead stays dead: `PeopleService.record_death` writes the tombstone and the narrative layer never reuses the id; a replacement worker spawned by the hut is a **new** Person with a new identity and archetype, who may inherit the *story role* (section 7) but never the name or history. The same holds for a resident re-cast for a vacated household role.

### 5.3 What kills or moves a resident (the simulation decides, the narrative reads)

Residents live in narrative state, so the simulation cannot push them; the narrative layer therefore watches the simulation every game second, in this order, deterministically:

1. **Home destroyed** (`building_removed` for `link.home`, read from the bounded event scan or by the id vanishing): residents in routine state `inside` die (`cause_id = "building_destroyed:<bid>"`); residents `about`/`near` are displaced.
2. **Combat beside them**: a building destroyed with `by` a unit or a building (not `wizard`, not `dismantle`) kills any resident within Chebyshev distance 1 of its footprint ("caught in the fighting"). This is the only way soldiers kill residents; it mirrors what happens to the building's worker today (`purge_building` drops the worker). No simulation change.
3. **Fire magic**: `magic.find` gains residents as a target class (wizard-owned file): burning a resident kills them through `record_death` and the same explosion effect.
4. **Outbreak illness**: while the settlement's region holds `cubes >= config.residents.illness_cubes` (default 3), every 5 game minutes each resident of that settlement rolls `crc32(world.seed, pid, minute)` against `config.residents.illness_death_per_check` (default 0.05) and may die of the outbreak; the healer's cure removes the risk. Narrative RNG only; nothing in the simulation changes.
5. **Settlement destroyed**: residents displaced; those with no settlement of their faction within 60 tiles depart after 5 minutes.
6. **Faction split** (`history.split` rewrites `settlement["faction"]`): residents keep their home and follow its new faction label; the `faction_changed` fact becomes available to dialogue.
7. **Cycle reset**: every resident is gone with the world (D11); the wizard's journal keeps the closed quests as history.

Workers and units die by the simulation's existing paths (`worker_abort` from fire magic, `purge_building`, `no_path_home`; `kill_unit`). The link watcher (section 6.4) turns those into Person deaths or displacements.

### 5.4 Movement of residents

Residents move on a **bounded routine**, never across the map: `routine = {"anchor": building id, "radius": r, "beats": [...]}` where a beat is `(state, duration band)` such as `inside 2-4 min`, `about radius 3 for 1-2 min`, `near_centre 1-3 min`, `visit <building of the household> 1 min`. `residents.quantum(world)` runs once a game second over at most `budget` residents (round-robin, the wizard's settlement first); a resident walks one tile per 600 ms along `workers.find_path` (the same A* the workers use, avoiding the blocked and solid sets) to the next beat's target, chosen by `crc32(world.seed, pid, beat index)`. Routines by role: a child stays within radius 3 of home; a spouse walks between home, the centre and the nearest road; an elder stays near the centre; an apprentice stays within 2 of the workplace; a merchant (a resident attached to a trade post) stays at the post; the tutorial teacher stays near the centre. Interruptions: a dialogue freezes the beat; a destroyed home ends it (displacement moves the anchor to the centre); the wizard standing on the target tile makes the resident stop one tile short. Residents do not block tiles and are not drawn inside buildings. Cost target: under 0.1 ms per resident per game second.

---

## 6. Linked characters: the simulation's own people as quest characters (no duplicate Persons)

### 6.1 The link

```text
world.dmb.people[pid]["link"] = {"kind": "worker"|"carrier"|"unit"|"resident", "id": entity id, "building": workplace id, "role": occupation}
world.narrative["links"]["worker:17"] = pid          # reverse index kept by the narrative layer (no field on the simulation row)
```

`characters.person_for(world, kind, entity_id)` finds the Person by the reverse index or creates one (`create_person` with the occupation as role, the workplace, the faction, `area_id="hybrid.world"`, the entity's tile) plus identity and archetype. One entity, one Person. The Person's position is read from the entity every time it is needed; `story.snapshot()["persons"]` publishes `{entity id: {person_id, name, has_quest, quest_status}}` so Godot can label a worker, carrier or unit row with its person without any change to `world.snapshot` rows (the join is done in `story_ui.gd`). `story.entity_rows` stops emitting a second actor for a linked person. The collapsed-mine story binds the mine's real worker (`building["worker_ids"]`), which removes the audit's two-actor problem.

### 6.2 Who may be a character

Workers (every role of every operational workplace), carriers (per road; talk in place, no interruption), units (a faction's soldiers, founders, caravans; talk in place when not on an attack order), residents. Buildings and settlements are bound as places, not characters.

### 6.3 Employment changes with the same person alive

The simulation never moves a worker between buildings (a worker belongs to one hut and is removed when it is destroyed). So "the same person changes job" happens in exactly two ways: a **resident takes a vacancy** (narrative: when a hut's worker is gone and the hut is in `respawn_ms`, the director may, by archetype preference, decide that a resident of the household walks to the hut; when the simulation spawns the replacement row, the link moves to the new row and the resident record closes with `became_worker`), and a **story effect** that says a worker now works somewhere else, which binds the person to that building's next spawned worker. In both cases the Person id, name, archetype and history stay; `person["link"]` is rewritten; `assign_job` records the new workplace. A replacement spawned without such a decision is a new person.

### 6.4 The link watcher

Every game second `characters.watch(world)` scans the bounded new `world.events` (kinds `worker_aborted`, `worker_spawned`, `carrier_killed`, `building_removed`; unit deaths are seen as `alive` flips on linked units) and applies: `killed_by_fire_magic`, `workplace_destroyed` with the worker inside, and unit deaths → `record_death`; `workplace_destroyed` with the worker outside → `displace`; `worker_spawned` at a building whose previous linked person is alive and `displaced` → nothing (the displaced person stays displaced; the new row is a new person unless a story effect rehouses the old one); a vanished row with no event (should not happen) → `displaced` with reason `lost`.

---

## 7. Quest resilience: every stage, every character

### 7.1 Per-role contingency policies

Every template role carries a `living` block and every graph node may override it:

```jsonc
"roles": {"miner": {"bind": "worker", "of_role": "A_mine", "required": true,
                    "living": {"dead": ["evidence", "rebind:same_building_worker", "rebind:household_of_building", "suspend", "fail:lost_contact"],
                               "displaced": ["find_at_centre"], "departed": ["acknowledge", "rebind:same_role_in_settlement"],
                               "absent": ["wait"], "changed_job": ["keep"], "rebind_deadline_ms": 600000}}}
```

Policies (the response list from the owner's brief, made executable):

| Policy | Behaviour |
| --- | --- |
| `rebind:<pool>` | reassign the role to another suitable person from the pool (`same_building_worker`, `same_role_in_settlement`, `household_of_building`, `any_resident`), in order; the new person's lines use the `inherited` variant ("I took over from ...") |
| `alt_character:<role>` | continue the quest through another bound character (a `talk` node with `npc: alt` in the graph) |
| `evidence` | the dead person's last known position gets a `landmark` entity ("<name>'s pack") that an `investigate` node accepts in place of the talk; the facts include `cause_of_death` |
| `acknowledge` | the next talk with any bound character of the settlement opens with the `acknowledge_death`/`acknowledge_departure` variant and the graph advances past the dead person's node if it was a `talk` |
| `find_at_centre` | the displaced person is found near the settlement centre (their routine anchor moved); the quest continues |
| `wait` | the node waits for the character to be `present` or `inside` again |
| `suspend` | `QuestService.suspend`, deadline `rebind_deadline_ms`; the journal shows "waiting"; on the deadline, the next policy |
| `fail:<branch>` | `failed_with_consequence` through the named `conclude` node (a consequence always: a relationship, a history fact, a bounded unrest change, or a world effect not applied) |
| `resolve:<branch>` | an alternative route to a conclusion (for example the gallery reopened by the crew after the miner's death: `resolved_by_world` with its own text) |

Lists are tried in order. Not every quest must survive every disaster: a list may end in `fail`, and the validator only requires that the outcome is defined and recorded.

### 7.2 Per-stage check

The graph runtime evaluates the policies at three moments: every game minute for every open quest (director), on every wizard op touching the quest (so dialogue never lies), and on load. For each **node the quest can currently reach** (the current node and its direct successors), the runtime lists the roles that node needs; for each role whose lifecycle state is not `present`/`inside`/`working_away`, it applies the role's policy. The validator proves at build time that **every node of every template has a defined outcome for every lifecycle state of every role it uses** (either a policy list or `optional: true` on the role), so no quest can hang on a dead character.

### 7.3 Buildings and settlements

Place roles have `living: {"destroyed": "fail:destroyed_target" | "rebind:same_kind_in_settlement", "faction_changed": "keep", "cause_cleared": "resolve:world_fixed"}`; a settlement role has `destroyed: "fail:site_destroyed"`, `faction_changed: "keep"`. The existing `story.py` routes (`invalid_target`, `world_fix`, `destroyed_settlement`) are these policies written by hand today; they migrate unchanged.

### 7.4 Supplementing the 112 structures

The twenty situation structures have four roles and three decisions. The converter emits, per structure, the default `living` block for each role by role class: the **requester** (A) `["evidence", "alt_character:C", "fail:requester_lost"]`; the **holder** (B) `["acknowledge", "rebind:same_role_in_settlement", "resolve:holder_gone"]` (what B withheld is moot); the **persuader** (C) `["rebind:household_of_building"]` with `optional: true`; the **unlocker** (D) `["rebind:same_role_in_settlement", "suspend", "fail:no_unlocker"]`. Each structure file then lists the extra conclusions these policies need (`requester_lost`, `holder_gone`, `no_unlocker`) with one neutral line each, marked `generated: true` until authored; the tragic ending the workbook already defines maps to `fail:tragic` where the structure's "tragic rule" fires. The pilot (three casts) reviews these before any wider conversion.

### 7.5 Temporary tutorial characters: expiry, departure and backup learning (Q5 revised, approved)

Three temporary residents are created at minute 0 near the starting settlement's centre: the **teacher** (archetype pool `arch.hedge_wizard*`), an **apprentice** (who carries the simple story of lesson 6 and can repeat lessons 2 and 3 if the teacher is gone) and a **traveller** (who can repeat lessons 4 and 5 as a sparring partner). Each has `temporary = {"purpose": "tutorial", "expires_ms": 1_800_000}` (30 game minutes, configurable).

Expiry rule: at `expires_ms`, if the character is in a dialogue or a duel with the wizard, or bound to a quest node the wizard is inside (the apprentice's story), the expiry is deferred until that interaction ends (`grace` state; the journal says "about to leave"); then `residents.depart(pid, "tutorial_over")`: the routine ends, the figure walks to the settlement's edge tile nearest its last beat over at most one game minute and is removed from `entity_rows`; the Person record gets `status: "departed"`, a `history_ref` ("left <settlement> at minute 30 for the road east"), and any open quest role bound to them takes its `departed` policy. Not a death: no tombstone, no `alive = False`.

Backup routes, so essential learning is never lost:

1. **Any surviving temporary character teaches.** The apprentice teaches lessons 1 to 3; the traveller runs 4 and 5; the lesson texts have `inherited` variants.
2. **The notes.** When the teacher dies, departs, or the wizard reaches minute 30 with essential lessons undone, a `landmark` entity "the teacher's notes" appears at the starting settlement's centre (or, if that settlement is gone, at the nearest standing settlement's centre of any faction, moving again if that one falls). Reading it (talk) gives lessons 2 and 3 as text and offers lessons 4 and 5 as duels against a **bound manifestation** (a lease whose enemy is the notes' warden: the same mechanism the hazard uses; no character is needed). The notes exist until the essential set is complete, then remain as a journal entry.
3. **A replacement teacher.** From minute 30, if the essential set is incomplete, the director casts a permanent resident with a teaching archetype in the settlement the wizard stands in (or the nearest standing one), who offers every lesson; if that person dies, another is cast after 5 minutes elsewhere. Permanent residents are mortal like everyone.

Tests cover: teacher killed before any lesson (notes appear; lessons completable), teacher departs at 30 minutes during a duel (grace; departs after), all three killed (notes plus replacement), starting settlement destroyed (notes move), the player ignoring everything until minute 90 (replacement teacher found; stories had unlocked at 20).

---

## 8. Real-time interaction with workers and buildings (Q8 revised, approved)

### 8.1 What the simulation does today (audit section 10)

A building runs a Widelands programme stack (`building["stack"]`); `callworker` hands a programme to the worker (`worker["program"]`, `pc`, `status`), sets `building["waiting_worker"]` and holds the stack frame until the worker reports back (`building["worker_done"]`); the worker walks (`path`), works (`wait_ms`), carries (`carrying`), returns home (`returning`) and stores the ware on arrival (`_arrive_home` → `economy.produce`). A failed programme (`_fail_program`: no tree, no path) releases reservations (`_release`: the reserved tree, the reserved tile), returns the worker, marks `prog_failed` so the building stalls (`_fail`, `FAIL_SLEEP_MS`). `worker_abort` removes the worker outright (fire, destroyed workplace) and the building respawns one after 30 s. Idle workers stand at the building tile (`snapshot row["inside"]`); a destroyed building drops its worker and the ware it carried.

### 8.2 The summon (the one shared-simulation change)

Add to `workers.py`, additive and inert unless called:

```python
def summon(world, worker, tile, by="wizard") -> bool:
    """A worker is asked outside (a wizard at the door). Whatever it was doing stops legitimately: reservations are released,
    the ware in its hands stays in its hands, the building keeps waiting for it (no production meanwhile) and will re-issue the same
    step when it reports back. Returns False when the worker cannot come (already summoned, no path, or the building is gone)."""
    # _release(world, worker); worker.update(program="", pc=0, wait_ms=0, status="summoned", summoned=True, returning=False)
    # path = find_path(world, (tx,ty), tile) -> worker["path"]; anim walk/walkload
    # building["waiting_worker"] = True; building["prog_interrupted"] = True  (the frame is not advanced on report)
def release(world, worker) -> None:
    """The conversation is over: the worker goes home by the ordinary return path and stores what it carries (_arrive_home)."""
    # worker["summoned"] = False; _begin_return(world, worker)
```

and two guards: in `worker_quantum`, a summoned worker walks its path, then stands (`anim idle`, `status conversing`) and does nothing else; in `production_quantum`'s `waiting_worker` branch, `if building.pop("prog_interrupted", False): pass` (the `callworker` step re-runs because the frame was never advanced) instead of advancing the frame. About 25 lines; `_fail_program`, `_arrive_home`, `worker_abort` and the stack semantics are untouched. Hash baselines are unaffected because nothing calls `summon` in a world without a wizard op (`test_hash_baseline` and `test_determinism` prove it).

### 8.3 The interaction, step by step

| Case | Behaviour |
| --- | --- |
| Worker visible outside, within talk range (3 tiles) | `talk` as for any character; the worker **pauses in place** (`summon` to its own tile: no walk, same economic effect) for the conversation and resumes on `end_talk` |
| Worker inside (idle at the building) or working away; the wizard clicks the building | the label offers "Ask the <role> to come out" → `ask_out {building, role}`: `summon` to the free walkable tile nearest the wizard adjacent to the building's footprint (`story._free_tile_near` logic); the reply says "coming" and the client shows the worker walking; when the worker's status is `conversing` the dialogue opens (the client polls `story_view`); if the worker is working away, it walks from where it is (a lumberjack mid-forest comes back carrying its log) |
| No free adjacent tile | the conversation happens at the door: `summon` to the building tile itself (the worker stays `inside`, status `conversing`); the dialogue opens with the "through the doorway" variant |
| The worker is already summoned or conversing | `rejected: busy` |
| Dialogue ends (`end_talk`, a `conclude`, closing the panel, walking out of range for 10 s) | `release`: the worker returns, stores its ware, the building re-issues the interrupted step |
| The wizard enters a dungeon or a duel while conversing | the conversation ends first (`release`) |
| Workplace destroyed while conversing | `worker_quantum` aborts the worker as today (`workplace_destroyed`); the link watcher records displacement (outside) or death (at the door); the dialogue closes with the `interrupted_by_destruction` line; the quest applies the role's policy |
| Worker killed while conversing (fire magic by the wizard, combat at the door) | as above with death |
| Save during a conversation | the worker row (status, `summoned`, path, `carrying`) and the building flags pickle as they are; `world.narrative["conversations"]` records `{worker, building, opened_ms}`; on load the conversation is **closed** and the worker released (policy: a loaded game never resumes an open dialogue); nothing is duplicated or lost because the ware is still in hand and `_arrive_home` stores it |
| Carriers and units | talk in place without summoning (they have no programme stack); the conversation follows them within range; a pause on the road tile is added in Milestone G only if play shows it is needed |

Economic truth of the interruption: during the conversation the building is `waiting_worker` and produces nothing; the worker's reserved tree is released (another lumberjack may take it); the ware in hand is neither lost nor duplicated; the building's `stall` is not set (a summons is not a failure), so the AI's shortage statistics do not count it; the lost time is real. Pathfinding uses `find_path` with the worker's locomotor; a summons that cannot find a path returns `False` and the client says "cannot come out now".

### 8.4 Residents' interaction

Residents are talked to in place; a dialogue freezes their beat (section 5.4). Residents inside their home answer through the building's label ("Call for <name>"), which moves them to the door tile by the same summon logic implemented in `residents.py` (no simulation change: residents are narrative-owned).

---

## 9. Quest consequences and the autonomous factions (Q6 approved; separation rule)

### 9.1 Effects

| Kind | Class | Implementation (existing API) | Introduced in |
| --- | --- | --- | --- |
| `history_fact`, `known_fact`, `relationship_change`, `aspect_change`, `worldview_delta`, `learn_spell`, `grow_weave`, `give_item` (story and dungeon items only), `set_flag`, `journal_note`, `settlement_mood` (a chronicle label), `rehouse_person`, `depart_person` | narrative-only | `PeopleService`, `AspectService`, `world.narrative` | B, C |
| `reopen_gallery` (exists), `clear_disruption` | world | `disruption.clear(world, b, "wizard")` for any cause | C, E |
| `cure_region` | world | `regions.cure(world, building, cubes)` only while the wizard stands in the region (the `treat` rule) | E |
| `caravan` | world | `trade.send_caravan(world, faction, wh, partner_wh, give, want)` only if `trade.can_supply`: wares move, none appear | E |
| `diplomacy_offer` | world | `diplomacy.propose(world, a, b, state, duration)`; the receiving AI answers in `diplomacy_quantum` by its own policy; the story reads the answer later | E |
| `unrest_delta` | world (bounded) | `rec["unrest"] = clamp(rec["unrest"] + d, 0, 1)`, `abs(d) <= 0.1`, at most once per story per settlement | E |
| `destroy_target` | world | never directly: the story asks and the wizard burns it with `magic.fire` under its range rule | C |

Each world effect arrives in its own task with its own test: the API was called, nothing was created (`ledger.check` balanced), the receipt prevents a second application, and a load after the effect does not re-apply it. Forbidden by the validator: creating wares, buildings, units or roads; commanding units; stock changes other than by caravan; VP, era, card or roster changes.

### 9.2 The separation rule (enforced, tested)

The faction AIs (`ai.py`, `ai_plus.py`, `ai_industry.py`, `diplomacy_quantum`, `trade_quantum`) read the world. They do not read `world.narrative`, `world.story`, `world.dmb.people`, `world.dmb.quests` or the narrative log, and the narrative layer writes no faction-visible field except through the APIs above. Tests: (a) `grep` the AI modules for those names (a test asserts the result is empty); (b) a quest completed in a copy of a world and the same world where the gallery was cleared by the faction's own repair at the same game second produce identical AI decisions for the next 10 minutes (the AI cannot tell a wizard's clearing from its own); (c) no new `world.events` kind is written by the narrative layer, so the AI's event scans see nothing new.

---

## 10. Three dynamic storylines per settlement

### 10.1 Slots, journal and rumours

`world.narrative["settlements"][sid] = {"epoch": n, "slots": [slot×3], "history": [...], "cooldown_until_ms": t}`; a slot is `{"template": id, "status": "assigned"|"offered"|"accepted"|"closed"|"empty", "quest": qid|None, "cast": {...}, "assigned_ms": t, "seed": int, "empty_reason": ""}`. Assigned stories are **rumours**: the entry character has a marker and the settlement panel lists up to three; a story becomes a quest only when the wizard accepts (`QuestService` offered → active). The journal lists accepted quests (cap `max_accepted` = 4) with objective text, separately from the rumours of the settlement the wizard stands in and from the lessons. If three legitimate stories cannot be cast, the slot is `empty` with `empty_reason` (for example `no_second_workplace_kind`) and is retried at the next pass; nothing is invented to fill it.

### 10.2 Settlement context

`context.settlement_context(world, sid)` is a plain dict built only from reads and cached until the settlement's version stamp changes (counts of standing buildings, disrupted, stalled, region cubes, unrest band, foreign units within 40 tiles band, era index, residents, events bucket). Fields: identity and chronicle tail; era; centre and radius; buildings with kind, class, operational, constructing, disrupted (cause, progress), stall, workers, inputs, outputs, deposit; kind counts; workers, carriers, units own and foreign; neighbours with diplomacy state and trade partners; warehouse stock by group; shortages; buildings with no road to the centre; region state; recent losses; residents and linked characters with their archetypes; current slots and recent closures. Cost under 2 ms for 80 buildings; rebuilt only on version change.

### 10.3 Eligibility, scoring and selection (deterministic, varied)

Eligibility: every predicate in the template's `requires` passes (allowlisted ops: `has_building_kind`, `has_building_class`, `has_role`, `count_gte`, `disrupted_cause`, `stall_reason`, `region_cubes_gte`, `unrest_gte`, `neighbour_hostile_within`, `foreign_units_within`, `no_road_link`, `trade_partner`, `era_in`, `age_gte_ms`, `recent_loss`, `has_resident_role`, `lessons_done`, `all`, `any`, `not`) **and** every required role casts in a dry run.

```text
score(t, sid) = relevance(t, ctx)                       # 0..1 from select.relevance rules (a live disruption 1.0, a stale one 0.5, a social story 0.4)
              + 0.25 * cast_quality                      # fraction of roles bound to real workers/units rather than residents
              - 1.0  * same_family_in_settlement
              - 0.5  * same_template_nearby              # assigned in one of the 2 nearest settlements
              - 0.5  * recently_closed_here              # within repeat_cooldown_ms
              - 0.3  * same_archetype_hook_in_settlement # the entry character's archetype hook already in use
              + 0.10 * jitter(crc32(world.seed, sid, epoch, t))
```

Greedy fill of empty slots in `(-score, template id)` order, one family per settlement, ties on the id. The epoch increments on every rebuild and is saved, so load reproduces the choice.

Selection strategy per settlement type (what the predicates yield in practice):

| Settlement | Likely slots |
| --- | --- |
| Peaceful, developed | one shortage or transport story if any stall exists, one social story from the workbook structures (disputed ownership, debt triangle, succession), one personal or mystery story (missing flock, tainted well, broken promise) |
| Newly founded (under 3 minutes, one or two buildings) | one simple-tier story ("the founder's first worry": an investigate node on the warehouse), then empty slots with `empty_reason: too_young`; filled as workplaces appear |
| Industrial centre | shortage (collapse, spill, starved workshop), labour strike when unrest is high, a road or caravan story |
| Militarised border town | raid warning, deserter hunt, road toll, border truce; shortage only if a disruption exists |

Low-dependency social stories (the workbook's twenty structures need only "two people with different occupations and a third voice") are what guarantee three legitimate stories without extraordinary events.

### 10.4 Cadence and living checks

`director.quantum` runs once a game minute over at most `budget_per_minute` settlements (default 8) in a round-robin over `sorted(settlements.standing)`, always including the wizard's settlement and any settlement whose version changed. New settlements get slots after `min_age_ms` (3 minutes). Closed slots refill after `refill_cooldown_ms` (5 minutes) with a different family. Living checks (section 7) run every minute for every open quest, on every wizard op touching it, and on load. World changes:

| Event | Behaviour |
| --- | --- |
| Bound character dead, displaced, departed, absent, changed job | the role's policy (section 7) |
| Bound building destroyed | the place policy (`fail:destroyed_target` or `rebind:same_kind_in_settlement`) |
| Cause gone (repaired, cured, road rebuilt) by the faction | `resolved_by_world`; the lines acknowledge it; no reward |
| Settlement destroyed | slots closed; accepted quests `fail:site_destroyed`; residents displaced or departed |
| Settlement founded | slots after `min_age_ms` |
| Faction split (ownership change) | templates kept; `faction: same` roles re-cast against the new faction; entity-bound roles keep their bindings (the entities moved with the settlement); `faction_changed` fact |
| Faction collapse | its settlements are destroyed by `history.collapse`; handled as above |
| Era change | nothing breaks; templates whose `era_in` excludes the new era are not offered again; active ones continue; the duel tier for new leases follows `era_binding` |
| Cycle reset | all settlement state gone; wizard state copied by `server.py` |
| Save and load mid-quest | identical state; dungeon runs resume; duels resume from the lease checkpoint or are voided (section 12) |
| Duplicates | `CauseTracker` occurrence key, binder dedupe, slot key: never two quests for one cause, never one template twice in a settlement, never two rewards (receipts) |

Suspension is bounded (`rebind_deadline_ms`, default 10 minutes).

---

## 11. Templates, authored content and dialogue

### 11.1 Template v2

Unchanged from the first revision in shape: legacy quest schema (causes, routes, persistent return) plus `roles` (with `living`), `graph` (Village Test node types `talk`, `choice`, `branch`, `investigate`, `travel`, `deliver`, `dungeon`, `duel`, `wait`, `conclude`; `requires`/`sets` flags; `accept: true` on a choice), `dialogue` (pack reference), `select` (tier, relevance, exclusive group, era), `tunables`. New in this revision: the `living` blocks, `duel` nodes reference an opponent tier and may name a bound character as the rival, `conclude` nodes may carry `learn_spell`/`grow_weave`, and `investigate` nodes may accept an `evidence` landmark. Validation: schema, reachability, every path ends in a `conclude`, roles exist, facts exist, effects registered, world effects name a bound target, every `talk` node has a fallback line, **every node has an outcome for every lifecycle state of every role it uses**, no two conclusions apply the same world effect twice.

Example (`shortage.gallery_collapse`, abridged; the full file is written in Milestone E):

```jsonc
{"id": "shortage.gallery_collapse", "schema_version": 2, "family": "shortage", "archetype": "industrial_accident",
 "select": {"tier": "standard", "relevance": [{"when": {"disrupted_cause": ["mine", "collapse"]}, "score": 1.0}], "exclusive_group": "mine"},
 "requires": [{"has_building_class": "mine"}, {"disrupted_cause": ["mine", "collapse"]}],
 "roles": {"miner": {"bind": "worker", "of_role": "A_mine", "required": true, "talk_at": "anywhere", "living": {"dead": ["evidence", "rebind:same_building_worker", "suspend", "resolve:crew_digs_out"]}},
           "A_mine": {"bind": "building", "class": "mine", "disrupted": "collapse", "required": true, "living": {"destroyed": "fail:destroyed_mine", "cause_cleared": "resolve:world_fixed"}},
           "starved": {"bind": "building", "stall_reason": "inputs", "needs_ware_of": "A_mine", "required": false}},
 "graph": {"start": "talk_miner", "nodes": {
   "talk_miner": {"type": "talk", "npc": "miner", "sets": ["heard"], "choices": [{"id": "ask_cause", "next": "cause"}, {"id": "give_up", "next": "abandon"}]},
   "cause":      {"type": "talk", "npc": "miner", "facts": ["collapsed_by", "minutes_since", "props_have", "props_need"], "choices": [{"id": "ask_gallery", "next": "gallery"}]},
   "gallery":    {"type": "talk", "npc": "miner", "choices": [{"id": "accept_help", "next": "sigil", "accept": true}]},
   "sigil":      {"type": "talk", "npc": "miner", "effects": [{"kind": "give_item", "item": "@dungeon.needs"}], "next": "persuade"},
   "persuade":   {"type": "choice", "npc": "miner", "check": {"aspect": "empathy", "threshold": "easy", "evidence_from": "learned"}, "pass": {"sets": ["persuaded"]}, "next": "descend"},
   "descend":    {"type": "dungeon", "dungeon": "cave", "at": "A_mine", "guardian": {"duel": "opponent.warden_3x3"}, "on_solved": "resolve_full", "on_exhausted": "resolve_thin"},
   "resolve_full": {"type": "conclude", "branch": "warden_solved", "effects": [{"kind": "reopen_gallery", "mode": "full", "target": "A_mine"}, {"kind": "history_fact", "person": "miner", "fact": "gallery_reopened:full"}]},
   "resolve_thin": {"type": "conclude", "branch": "warden_unsolved", "effects": [{"kind": "reopen_gallery", "mode": "thin", "target": "A_mine"}]},
   "crew_digs_out": {"type": "conclude", "branch": "miner_dead_crew_finishes", "status": "resolved_by_world"},
   "abandon":    {"type": "conclude", "branch": "abandoned", "status": "failed_with_consequence", "effects": [{"kind": "relationship_change", "person": "miner", "delta": -20}]}}},
 "dialogue": {"pack": "shortage.gallery_collapse", "fallback_role": "worker"},
 "persistent_return": {"dedupe_by": ["template_id", "cause_id", "stakeholder_id"], "no_duplicate_reward": true}}
```

### 11.2 Converting the 112-story workbook and the 88 profiles

`scripts/build_story_templates.py` reads the Cast Matrix and Dialogue Matrix through `tools/dialogue_generation/workbook_reader.py` (read-only) and writes one template per situation structure (20) and one cast file per workbook cast (112) with role lists, archetype preferences, the twelve rows as pack lines keyed by node and character letter, gossip as ambient lines, and the default `living` blocks of section 7.4. `data/narrative/role_map.json` translates workbook roles into hybrid filters; Wastes roles map to quarry, charcoal and (Modern) scrap by era. `scripts/build_archetypes.py` converts the 88 profiles into the archetype library (section 4.2). The pilot is three casts (E36B, E53A, E56A) with the two exported Factory banks; nothing more is generated until the owner has played them.

### 11.3 Dialogue packs and selection

Packs are `data/narrative/dialogue/<pack>.json` with lines keyed by node, role, variant, tone tags and worldview; selection is exact key, then archetype tone, then default variant, then the role baseline, then the neutral fallback plus a generated report sentence from the facts (`generated: true`), stably picked by `(qid, node, role)`. Placeholders come from `facts.py`; an unknown placeholder fails validation. Wizard replies show the plain text unless worldview variants exist and are enabled, in which case the seven variants are offered and their `scores` go to the wizard's worldview. The Dialogue Factory keeps its own SQLite and approval flow and gains an exporter target `--format narrative-pack`; no runtime path imports `tools/`; the game never needs Ollama, Claude, Mistral or the network.

### 11.4 Aspects and worldviews (Q4: keep both, least complexity)

Audit: `AspectService` (`sim/dmb/narrative/aspects.py`) stores seven Aspect scores per actor under `world.dmb.definitions`, with thresholds, evidence modifiers, retry fingerprints and `apply_change_once` receipts; it is called by `story.choose("persuade")` and its scores already survive a cycle reset. Worldviews exist only in the Dialogue Factory (`tools/dialogue_generation/worldviews.json`: seven codes M, A, R, G, S, D, C with per-reply deltas); nothing in the runtime holds them.

Recommendation: **keep both, add nothing structural.** Aspects stay where they are (checks and `aspect_change` effects call `AspectService`). Worldview is a seven-key integer dict on `world.narrative["wizard"]["worldview"]` written by one function `wizard.apply_worldview_delta(world, receipt_id, delta)` that copies the receipt pattern of `apply_change_once` (about 30 lines). Dialogue conditions may read either (`aspect_gte`, `worldview_primary`). Merging them would save nothing (the Aspect store is keyed by Aspect ids with thresholds that mean something to checks; worldview scores are a leaning, not a capability) and would cost a migration of `aspects.json` content. No redesign before the core game is playable.

---

## 12. Save and load (Q7: reuse the existing format, make it an acceptance requirement)

Audit: `HybridEnv.save/load` pickles `{"format": 2, "hash", "world", ...}` and refuses another format; the server has no save; the Godot client persists only settings (`DmbSaveData`, a `ConfigFile`). The world pickle already carries `world.story`, `world.dmb` (people, quests, leases, clock with pause tokens, receipts) and will carry `world.narrative`; `test_story_slice::test_save_reload_and_reenter_never_reapply_or_respawn` proves a mid-quest round trip today.

Design (`narrative/persist.py`, ops in `server.py`):

* `save {"slot": name}` writes `{"format": 2, "hash": world.state_hash(), "narrative_version": N, "world": world, "profile", "seed", "game_ms"}` with `pickle` protocol 5 to `$DMB_RUNS/saves/<profile>/<slot>.pkl.tmp`, `fsync`, then `os.replace` to `<slot>.pkl` (atomic); keeps `<slot>.prev.pkl`. Autosave slot `auto` every 5 game minutes outside dialogues, dungeons and duels, and on quit.
* `load {"slot"}` refuses a different `format` or a `narrative_version` newer than the code, verifies the hash of the loaded world against the stored one (a mismatch loads but reports `hash_mismatch` and marks the save `recovered`), swaps the world in the server, and replies with terrain and a full snapshot; the client rebuilds its static rows.
* Retained by construction (all inside the pickled world): the RTS world and factions; the wizard's pose, spells, lessons, duels, worldview; identities, archetypes, living and dead characters, tombstones; links; residents and routines; quest assignments, flags, choices, graph state, receipts; conversations; tutorial expiry timers.
* Restoration policy: **dungeon** runs resume exactly (the run is in `world.story["dungeons"][did]["run"]`; the wizard re-enters at the mouth as today). **Duels**: a lease with a checkpoint (the adapter submits one after every cast, `duel_checkpoint`) resumes through the board's existing `restore_checkpoint` with the same secret and RNG state (`save_checkpoint` already refuses a secret reroll); a lease without a checkpoint is voided on load (pause token released, attempt not counted, the story offers the duel again). **Conversations** are closed on load and the worker released (section 8.3). **Temporary characters** keep their expiry (game time, so a load never shortens it).
* Version checking: `narrative_version` in `config.json`; a save older than the code is migrated by `persist.migrate` steps (none at first; the mechanism exists from the start) or refused with a message naming the version.
* Tests: identical `state_hash` after save and load at every stage of the acceptance scenario; load with a duel checkpoint resumes with the same enemy ward; a corrupted `.pkl` (truncated) is refused and `.prev.pkl` offered; two saves in a row differ only by `game_ms`.

Godot: a pause menu (Escape) with Save, Load, Quit; the launcher gains `scripts/launch_scenario.sh campaign --load <slot>` (sets `HYBRID_LOAD_SLOT`, the server loads before `HYBRID_SIM_READY`).

---

## 13. Example stories in contrasting settlements (illustrative)

Composed from building kinds, disruptions, outbreaks and diplomatic states that the measured `campaign` worlds contain (seed 507 reaches 41 settlements and 402 buildings by minute 60). People keep generated names until canon is decided (D19); residents are marked.

### 13.1 Red home 1, Historic, a mining town (coal mine, iron mine, smelter, smithy, lumberjacks, quarry; Blue at war to the east)

| Slot | Template | Cast | Entry and arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `shortage.gallery_collapse` | miner = the coal mine's own worker (linked); mine; starved = the smelter | Ask the miner out of the mine; the roof came down 12 minutes ago; props 1 of 4. Evidence, Aspect check, the old gallery (four puzzles), the warden's three-colour Ward. | `reopen_gallery`: coal flows, the smelter restarts |
| 2 | `shortage.starved_workshop` (*The withheld resource*) | smith = the smithy's worker; supplier = the smelter's worker; keeper = a resident elder at the warehouse | Three choices: side with the smith, with the smelter, or carry the keeper's ledger to both. | relationships, a history fact; `caravan` from an allied warehouse if `can_supply`; `unrest_delta -0.05` on the fair ending |
| 3 | `military.raid_warning` | watchkeeper = a Red spearman unit (linked); carter = a carrier on the east road; envoy = a resident at Blue's nearest warehouse | Blue riders within 30 tiles; the carter refuses the east road. Investigate the frontier, then warn the keeper or carry a truce offer (`diplomacy_offer`; Blue's AI answers by its policy). | a real truce if Blue accepts; otherwise narrative |

### 13.2 Green outpost 9, Historic, agricultural (farm, well, bakery, sheep farm, hunter; two outbreak cubes; unrest 0.45)

| Slot | Template | Cast | Arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `catastrophe.outbreak_treatment` | healer = the clinic's worker if drafted, else a resident healer; affected = the bakery's worker | Treat the region (stand in it). If the healer dies of the outbreak first (section 5.3), the baker's spouse (resident) takes the role with the `inherited` lines. | cubes removed, production factor back to 1.0 |
| 2 | `mystery.tainted_well` | healer (same person), digger = the well's worker, mother = a resident of the farm household | Go down (a two-room dungeon at the well), seal it, or cure the water (`cure_region` 1 cube). | one cube cured on the magic ending |
| 3 | `conflict.labour_strike` (*The absent worker*) | shepherd = the sheep farm's worker (programme failing `no_space`), reeve = resident elder, healer | Who yields. | `clear_disruption` on the farm's blight on one branch; `unrest_delta` |

### 13.3 Yellow outpost 12, Modern, a militarised border town (war lodge, barracks, trade post, drills and belts, a toxic spill; Orange hostile 25 tiles away)

| Slot | Template | Cast | Arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `conflict.road_toll` | carter = the caravan's unit (linked), tollman = an Orange soldier standing on the road (linked, other faction), smith = the drill's operator | Fight (a Ward Duel at the era's tier against the soldier), report (`diplomacy_offer` truce with Orange), or make him road-warden. | world only through the truce offer |
| 2 | `shortage.workplace_closed` (toxic spill) | operator = the crafter's worker, keeper = resident, healer | Clear it (`clear_disruption`) at the cost of a relationship, or carry words only. | `clear_disruption` on one branch |
| 3 | `military.deserter_hunt` | soldier = a Yellow unit killed near the town in the last 10 minutes (tombstone fact), kin = a worker of the same faction, reeve = resident | Reluctant-witness structure; history facts and a settlement mood. | narrative |

---

## 14. Performance, determinism and the frozen catalogue

* Lazy and budgeted: contexts cached by version; director 8 settlements per minute; residents round-robin with a budget; the disabled path (no `world.narrative`) costs one dict lookup in `story.story_quantum`.
* Targets, asserted by `test_narrative_perf.py` and recorded in the ledger: director pass under 2 ms per processed settlement on the 20-minute campaign fixture; under 20 ms per game minute at 30 settlements; residents under 0.1 ms each per game second with 60 residents; `settlement_context` under 2 ms for 80 buildings; a 60-minute AI world with Wizard Mode state present versus absent differs by under 1% wall time.
* Determinism: sorted iteration everywhere; narrative randomness is `random.Random(zlib.crc32(...))` seeded from `(world.seed, ids, epoch)`; `world.rng` is never touched; no wall clock; `tests/test_determinism.py` and a two-process `PYTHONHASHSEED` test on the director and residents.
* Frozen catalogue (D33): no new buildings, units, wares, liquids, resources or cards; residents are Person records and snapshot rows with existing figures; templates reference kinds by id and the validator checks them against `freeze.manifest()`; no importer is run; `test_content_freeze` stays green on every commit.

---

## 15. Owner decisions recorded, and what remains open

| Id | Decision (14 October 2026) | Applied in |
| --- | --- | --- |
| Q1 (training gate) | Out of scope for this programme: no gate design, no baseline scheduling, no coordination work. The narrative layer exists only when `server.py` (or a wizard environment) creates `world.narrative`; `world.py` is not changed. | sections 1.2, contract |
| Q2 (identities) | Hybrid: persistent generated identities drawing personality and material from a modular, expandable archetype library seeded by the 88 profiles. | section 4 |
| Q3 (residents) | Residents may be created beyond four, under household and settlement caps; all characters are mortal under one lifecycle; dead stays dead; new characters inherit roles, never identities. | sections 5, 7 |
| Q4 (Aspects and worldviews) | Keep both; the least complex reuse (a 30-line worldview store beside `AspectService`). | section 11.4 |
| Q5 (unlock, tutorial cast) | Unlock on essential lessons OR 20 game minutes; temporary tutorial characters expire at 30 game minutes with a clean departure; backup learning routes; no invulnerability. | sections 2.4, 7.5 |
| Q6 (world effects) | The five effects approved in principle, introduced one task at a time with tests; factions learn only through the world. | section 9 |
| Q7 (save) | Reuse the pickle format; save compatibility and reliable restoration are acceptance requirements. | section 12 |
| Q8 (movement) | Characters move by their simulation role; building interaction summons the worker with a real economic cost; residents follow bounded routines. | sections 5.4, 8 |
| Milestones | Reordered around playable vertical slices A to G. | execution plan |

Remaining decisions the owner may still want to make (defaults in force otherwise):

| Id | Question | Default |
| --- | --- | --- |
| R1 | Starting palette: Flame, Frost, Vine (the dungeon's three) or Flame, Frost, Stone (the first three core colours)? | Flame, Frost, Vine |
| R2 | Should the warden of the collapsed gallery become a Ward Duel in Milestone C (one duel system from the first slice) or stay Mastermind until Milestone F? | Milestone C |
| R3 | Resident illness deaths during outbreaks (section 5.3 item 4): on with the defaults, or off until Milestone G? | on, defaults |
| R4 | Residents in every settlement the director processes (created on demand by stories) or only in settlements the wizard has visited? | every settlement, on demand |
| R5 | Autosave every 5 game minutes (default) or only on quit? | 5 minutes |
