# Wizard narrative audit: existing story, quest, dialogue and settlement systems

Branch `feature/wizard-settlement-stories`, created 14 October 2026 from `origin/feature/neuroevolution-plan` at `4b67f55c00892decf43c8ce6736167a919abf235`. Read against the code and tests of that tree, not against documentation alone. Companion documents: `PLAN_WIZARD_SETTLEMENT_STORIES.md` (architecture), `EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md` (tasks), `WIZARD_STORY_INTEGRATION_CONTRACT.md` (boundaries with the neuroevolution programme), `ledger/WIZARD_STORIES_PROGRESS.md` (checklist). Nothing in this document changes code; it is the inventory the plan is built on.

Status words: **WORKS** (a passing test exercises it on the hybrid world), **LEGACY-WORKS** (passes its own tests in the Catan-era runtime, not connected to the hybrid), **DATA** (content present, no runtime reads it in the hybrid), **TEST-ONLY**, **SUPERSEDED**, **ABSENT**. Reuse words: **REUSE** (call it as it is), **ADAPT** (keep the module, change its binding), **MIGRATE** (keep the content, move it into the new template format), **ARCHIVE** (keep the file, do not build on it), **EXCLUDE**.

---

## 1. Summary of findings

1. **The hybrid already has a working, tested, one-world story core**: `WizardRTSHybrid/wizard_rts/story.py` (816 lines) opens quests from real state (a collapsed mine gallery, an outbreak with two or more cubes), binds them through the legacy quest services, runs a four-room dungeon and a Mastermind duel, and applies typed effects exactly once with receipts. `tests/test_story_slice.py` (12 tests) proves the chain, `test_quest_env.py`, `test_dungeon_env.py`, `test_duel_env.py`, `test_outbreak_env.py` (32 tests) drive it headlessly, and `godot_project/client/tests/run_hybrid_story.gd` drives it through the real Godot UI. This is the canonical runtime to grow, not replace.
2. **Its people are not the simulation's workers.** `story._ensure_npc` creates a *new* `PeopleService` person ("Miner of Red home 1") standing on a free tile beside the mine; the mine's actual worker is a separate row in `world.workers` that Godot draws as a second actor. The hybrid has no link between `world.workers` rows and `world.dmb.people` records at all (`grep -n person wizard_rts/workers.py` finds nothing). This is the single most important gap for the owner's requirement that "a working miner should remain the same person".
3. **The quest state machine, binder, cause tracker, people registry, aspects, condition evaluator and offline dialogue resolver already exist in `sim/dmb`** and are already imported by the hybrid. They are reusable as they stand. The line catalogue and the person-talk helper are tied to Catan-era projections and need an adapter.
4. **Two settlement-story engines exist outside the hybrid**: the Catan-era `DmbQuests` (three authored binary-tree stories with world effects) and the Village Test `VillageQuestRunner` (a generic graph runner for the E36B/E17A fixtures with talk/investigate/branch/choice/conclude nodes, flags and multiple endings). Both are GDScript. The graph *format* of the second is the right story-template format; the engine must be re-implemented in Python (the ontology makes Python the only quest state owner). The three Catan stories are reusable as templates.
5. **The 112-story workbook is a structured, machine-readable story library, not prose fragments**: 112 casts over 56 economic profiles, 20 four-role situation structures, three binary decisions each (eight coded outcomes), a combat branch, a tragic ending, gossip lines, and 1,344 dialogue rows (12 per cast) with opening lines, choice prompts, both options, both responses, both state changes and an end line. The roles are occupational ("Woodcutter 1", "Sawmiller 2", "Reeve", "Healer"), which is exactly what dynamic casting needs. Realistically **all 20 structures and about two thirds of the casts** can be bound to hybrid settlements (section 6.3); the rest need a role substitution rule or a later era.
6. **The Dialogue Factory is a complete offline pipeline** (`tools/dialogue_generation`, 15 model-free tests, SQLite state, approved-only export) with two exported casts (E36B 25 banks, E17A 24 banks, each bank holding seven worldview replies for the wizard). It runs only at development time; nothing in the runtime needs Ollama. It should keep that boundary.
7. **The legacy `story_quantum` runs in every world, including training worlds**, from `HybridWorld.advance` (`world.py` line 887) with no switch, and its state is part of `state_hash()` through `snapshot()`. Any gate added for the neuroevolution programme therefore interacts with the recorded hash baselines (section 8).
8. **Wizard Mode has no save/load.** `HybridEnv.save/load` pickles the whole world (format 2, hash-checked) for developer and training use; `wizard_rts/server.py` has no save or load op, and the Godot hybrid client never persists. Story state is already inside the pickled world (`world.story`, `world.dmb`), so the missing piece is a server op and a client call, not a new format.
9. **Nothing in the hybrid teaches magic.** The wizard can burn things within three tiles (`magic.py`), treat an outbreak region (`regions.begin_treatment`) and cast Flame, Frost or Vine on dungeon puzzles (`puzzle/logic.py` checks `ctx["spells"]`; the hybrid passes every spell). There is no known-spell list on the wizard, no mentor and no practice duel. The First Adventure (Halvard's staff, Ashby's lessons) exists only in the retired standalone Godot adventure.

---

## 2. Canonical world architecture (A1)

### 2.1 Authoritative and presentation layers, as built

| Layer | Component | Role | Status |
| --- | --- | --- | --- |
| Authoritative world | `WizardRTSHybrid/wizard_rts/world.py` `HybridWorld` (1,404 lines) | The one simulation: terrain, buildings, workers, carriers, units, roads, stocks, AI, eras, regions, history. Embeds the legacy `sim.dmb.core.WorldState` as `world.dmb` and `ClockService` as `world.clock`. `advance()` runs 24 quanta functions per game second (line 874). | WORKS |
| Legacy state slots reused | `world.dmb.people`, `world.dmb.quests`, `world.dmb.settlements`, `world.dmb.definitions` (quest templates, causes, dialogue runtime, aspects), `world.dmb.command_receipts`, `world.dmb.clock` (pause tokens) | The hybrid keeps story-facing durable state in the legacy typed slots so the legacy services work unchanged. | WORKS |
| Story core | `wizard_rts/story.py` | Detection, binding, dialogue lines, dungeon, duel, typed effects, snapshot rows, wizard op dispatch. Called from `advance()` every game second (`CHECK_EVERY = 10` quanta). | WORKS |
| Settlement identity | `wizard_rts/settlements.py` (56 lines), `territory.py` | `settlement:N` ids in `world.dmb.settlements` with name, faction, centre, tile, founded time, `state` (`standing`/`destroyed`), chronicle, `unrest` and `pressures` (from `society.py`). `settlements.of(world, building)` resolves membership by nearest command centre. | WORKS |
| Faction history | `wizard_rts/history.py` | decline, split (successor factions with new ids; settlement `faction` is rewritten), collapse, cycle reset (`cycle_reset` builds a *new* world; only the wizard carries over). | WORKS |
| Catastrophe regions | `wizard_rts/regions.py` | Hex overlay, cubes, outbreaks, treatment by wizard presence, production factor, unrest pressure. | WORKS |
| Disruptions | `wizard_rts/disruption.py` | Five causes (`collapse`, `sickness`, `blight`, `toxic_spill`, `signal_fault`) with repair recipes; `disruption.clear` is the typed effect behind `reopen_gallery`. | WORKS |
| Diplomacy and trade | `diplomacy.py` (propose/respond/set_state/break_treaty), `trade.py` (send_caravan, hostility) | Legal faction-level actions that story effects could call on an envoy's behalf. Not touched by any story yet. | WORKS |
| Wizard actions | `story.WIZARD_OPS` (`treat talk choose enter dungeon_move dungeon_interact duel_begin duel_guess duel_abandon story_view`), `magic.fire`, `set_pose` | The only ways the wizard changes the world (D02). Open in every profile; God ops are refused outside `developer`/`test_*` (`server.py` line 35). | WORKS |
| Presentation | `godot_project/client/scenes/hybrid_world.gd` (extends `overworld.gd`), `client/hybrid/story_ui.gd` (528 lines), `wizard_labels.gd`, `sim_client.gd` | Draws snapshot entities; `story_ui` presents the person, dialogue panel, dungeon and duel board purely from op replies; labels are click-driven for workers and carriers. | WORKS (placeholder art) |
| Bridge | `wizard_rts/server.py` (JSON lines over a socket) | One world per process; `HYBRID_PROFILE`, fixtures, developer switches. No save or load op. | WORKS |
| Training interface | `wizard_rts/sim_api.py` `HybridEnv` | Faction-level actions, observations, pickle save/load. Owned by the neuroevolution programme. Does not reference `story`. | WORKS, TEST-ONLY |
| Headless story environments | `wizard_rts/envs/{quest,dungeon,duel,outbreak}_env.py`, `_world_cache.py` | Wrap the story core; `_world_cache.attention_advance` steps only the systems the wizard interacts with (and calls `story.story_quantum` directly). | WORKS |
| Scripted wizards | `story_agent.py` (plays through the public ops), `dungeon_agent.py` (BFS solver), `wizard_pilot.py` (walks and treats regions at human speed) | Reference players for tests and crisis experiments (`docs/evidence/civilisation/crisis60_wiz`). | WORKS |
| Legacy Catan runtime | `sim/dmb/core/world.py`, `world/`, `construction/`, `logistics/`, `industry/`, `military/`, `ai/`, `eras/`, `hazards/`, `godot_project/sim/world/world_sim.gd` and projections | The earlier game. Economy, map and military rules are superseded (`CURRENT_STATUS_AND_GAPS.md` section 5). | SUPERSEDED as rules; reference only |

The architecture documents `INTEGRATED_RUNTIME_ARCHITECTURE.md` and `CANONICAL_GAME_ONTOLOGY.md` predate the hybrid (19 hexes, 54 nodes) but their ownership and identity invariants still hold and are restated by `ARCHITECTURE_CONTRACT.md`: Python owns durable truth; Godot presents; one person id is one identity and at most one actor; quests have one state owner (`QuestService`); never create a Person for presentation.

### 2.2 Where the hybrid departs from the ontology today

| Invariant | Current hybrid behaviour | Evidence |
| --- | --- | --- |
| One human identity = one Person id | `world.workers` rows (`spawn_worker`, `workers.py` line 434: id, role, building, tile, carrying, program) have no Person record; `world.carriers` likewise; `world.units` have no `person_id`. Story people are separate `PeopleService` records. | `grep -n "person\|people" wizard_rts/workers.py wizard_rts/logistics.py wizard_rts/military.py` returns nothing. |
| At most one actor per identity | The miner quest shows two actors beside a mine: the `worker` row (drawn by Godot from the snapshot) and the `npc` row from `story.entity_rows`. They never share an id. | `story._ensure_npc`, `world.snapshot` (`entities.extend(story.entity_rows(self))` then worker rows). |
| Never create a Person for presentation | `_ensure_npc` and the outbreak healer are created to be talked to. They are not decorative, but they duplicate a worker who exists. | `story.py` lines 149-161, 251-257. |
| Quest state owner is `QuestService` | Honoured: `world.dmb.quests` holds the instance; `story.state(world)["quests"]` holds hybrid-side binding and stage data keyed by the same id. | `story._open_quest`. |
| Typed effects only | Honoured: `ALLOWED_EFFECTS = ("reopen_gallery", "history_fact")`, receipts in `world.dmb.command_receipts`. | `story.apply_effects`. |

### 2.3 Save, load and game time

* Game time: `world.dmb.clock["game_ms"]`, advanced by `ClockService.request_advance`; pause tokens (`story_duel`, `hazard_duel`) stop it. The story duel pauses; dungeons do not (time keeps running underground by design).
* Persistence: `HybridEnv.save()` = `pickle` of `{"format": 2, "hash": world.state_hash(), "world": world, ...}`; `load()` refuses another format. `test_story_slice.py` and `test_quest_env.py` (`reload` scenario) already prove that a mid-quest pickle round trip keeps quests, people, dungeons, inventory and the duel. Nothing in Wizard Mode calls it (`grep -n "pickle\|save" wizard_rts/server.py` finds nothing).
* Cycle reset: `history.cycle_reset` creates a fresh `HybridWorld`; `server.py` line 267 swaps it in. The fresh world has no `story` state, so every quest, person and dungeon is dropped, which matches D11. Wizard-level progression (what the player has learned) does not survive either because nothing holds it yet.

### 2.4 Verified behaviour of the legacy story in ordinary worlds

Measured on this branch with `scripts`-style loops (`HybridWorld(seed, profile="campaign")`, AIs on, 60 game minutes, one game second per `advance`), to establish what the training path currently pays for the story code and whether quests open without a wizard:

Scripts and raw output: `WizardRTSHybrid/docs/evidence/narrative/audit/` (`measure_story.py`, `equiv_story.py`; to become `scripts/narrative_evidence.py` in W0.3). Hardware: the Ubuntu laptop, other work running; wall times are indicative only, the cProfile run is about seven times slower than an unprofiled one.

| Measurement | Seed 507 | Seed 11 |
| --- | --- | --- |
| 60 minutes, `campaign`, AIs on, cProfile: cumulative time inside `story.story_quantum` | 1.88 s of 607 s profiled wall (0.31%) | 1.85 s of 586 s profiled wall (0.32%) |
| story quests opened without a wizard | 1 (`quest:1`, family outbreak, status `offered`) | 1 (`quest:1`, family shortage: a real gallery collapse, status `offered`) |
| Persons created by the story layer | 1 | 1 (plus one cave dungeon) |
| world at minute 60: buildings, settlements, workers | 402, 41, 239 | 396, 42, 240 |
| 40 minutes, story on versus story off (`story_quantum` replaced by a no-op), same seed: first minute at which the **faction-only** hash (buildings, units, stocks, workers, carriers, tech, stats, fstats, faction_info, history, draft_state, wares_ledger, terrain) differs | never (40 of 40 minutes equal) | not run |
| first minute at which `world.rng.getstate()` differs | never | not run |
| first minute at which the full `state_hash()` differs | **minute 1** | not run |
| `world.events.total` after 40 minutes, on versus off | 79,383 versus 79,382 (the one `story_quest_offered` event) | not run |
| unprofiled wall time, 40 minutes, on versus off | 116.8 s versus 117.1 s (noise) | not run |

Three conclusions. First, the legacy story layer costs well under one percent of a training game and opens about one quest per hour of game time (outbreaks reach two cubes; mine collapses are rare at `COLLAPSE_PER_MIN = 0.004`). Second, it has **no effect on factions or on the simulation's random stream**: switching it off leaves every faction-level record identical for 40 minutes. Third, it **does** change `state_hash()` from the first minute, because `snapshot()["story"]` is `{}` when the story dict was never created and a six-key record when it was; so a gate that switches the layer off in training changes every recorded baseline hash at once, unless `story.snapshot` returns the same empty shape in both cases (a one-line change in the wizard-owned `story.py`, proposed as part of S1 in the contract), after which hashes differ only once a quest actually opens.

Interpretation is in section 8 and in the integration contract.

---

## 3. Story and quest assets, item by item (A2)

### 3.1 Hybrid story runtime (`WizardRTSHybrid/wizard_rts`)

| Asset | Status | What it provides | Hybrid-compatible | Decision | Depends on |
| --- | --- | --- | --- | --- | --- |
| `story.py` | WORKS (`test_story_slice.py` 12, `run_hybrid_story.gd`) | Two families: `quest.shortage.gallery_collapse` (collapsed mine; dialogue with evidence, Aspect check, sigil item, cave dungeon of four puzzles, Mastermind warden, `reopen_gallery` full/thin) and `quest.catastrophe.outbreak_treatment` (healer per settlement with two or more cubes; treatment by presence). World-fix, destroyed-target and abandon routes. `MAX_OPEN_QUESTS = 4`. | Yes, it is the hybrid | **REUSE and ADAPT**: keep the duel, dungeon, effect and op code; replace `_ensure_npc`/healer creation with person-to-worker binding; move detection and family logic behind the director and the template graph. | `sim/dmb` quests, people, aspects, mastermind, clock; `puzzle`; `disruption`; `regions`; `settlements` |
| `data/story/quest.shortage.gallery_collapse.json` (v2) | WORKS (registered by `story._binder`) | Template on the legacy schema: cause kinds, binding role, stages, solutions with effects, routes, dungeon, tunables. | Yes | REUSE; becomes the first template in the v2 format (section 7) | `content/schemas/quests.json` |
| `data/story/quest.catastrophe.outbreak_treatment.json` | WORKS | As above for outbreaks (`min_cubes: 2`). | Yes | REUSE | |
| `data/story/quest.shortage.mine_exhausted.json` | DATA, SUPERSEDED (D22: mines are inexhaustible; `story.py` registers only the other two) | Historical version with `deposit_vein` effects. | No (the cause cannot occur) | ARCHIVE (move under `data/story/archive/`) | |
| `story_fixture.py` | TEST-ONLY | Builds a real coal mine through the normal pipeline, lets it dig, collapses it, waits for the quest. | Yes | REUSE for tests and the headed story scenario | `tech.grant`, `ai._mine_site`, `construction` |
| `story_agent.py`, `dungeon_agent.py`, `mastermind_solvers.py` | WORKS | Scripted wizard over the public ops; BFS dungeon solver; consistent Mastermind solver. | Yes | REUSE as the scripted playthrough harness (Phase G) | `story.dispatch` |
| `wizard_pilot.py` | WORKS (crisis experiments) | Walks the wizard at 4 tiles/s by A* and treats regions. | Yes | REUSE for travel steps in the playthrough harness | `regions`, `set_pose` |
| `envs/quest_env.py`, `dungeon_env.py`, `duel_env.py`, `outbreak_env.py`, `_world_cache.py` | WORKS (32 tests) | Headless environments with scenario knobs (`world_fix_first`, `mine_destroyed`, `npc_dead`, `reload`). | Yes | REUSE; extend `_world_cache` with a "stories" scenario (several settlements with assigned stories) | `story_fixture` |
| `puzzle/` (`gen`, `logic`, `dungeon`, `items`, `rng`) | WORKS (`test_puzzle_parity` 6 Godot-RNG-exact, `test_puzzle_exhaustive`) | Eight puzzle templates, four-room dungeon, inventory, Godot-RNG parity. | Yes | REUSE | `data/puzzle_items.json` |
| `duel/ward.py`, `sim/dmb/adventure/mastermind.py`, `duels.py` | WORKS (`test_ward_parity` 5; `tests/sim/test_u05_retained_ward_duel.py`) | Ward Duel logical core and bot policies; `MastermindDuel` (4 slots, 6 colours, 10 casts; `attach(duel, rng)`); `HazardDuelService` for cube duels with the `hazard_duel` pause token. | Yes | REUSE; a practice duel for the tutorial is `MastermindDuel.attach` with a seeded `random.Random` and raised `max_casts`, exactly as `story.duel_begin` does | |
| `magic.py` | WORKS (`test_fire_magic` 5) | Fire within three tiles through the real destruction lifecycles. | Yes | REUSE; a known-spell gate belongs in the wizard-only `server.py` path, never in `magic.py` (section 8) | |
| `regions.begin_treatment` | WORKS | The `treat` wizard op. | Yes | REUSE | |
| `society.py` unrest and pressures | WORKS | Per-settlement `unrest` 0..1 from hunger, closures, war, isolation, garrison, plenty; docstring says quest systems may set unrest. | Yes | REUSE as a story *signal*; bounded unrest deltas are a candidate typed effect | |
| `feed.py`, `diagnostics.py` | WORKS | Spectator feed of selected event kinds; stuck-entity watch. | Yes | REUSE for the settlement chronicle (`feed.KINDS`) | |
| `inspector.py` | WORKS (God Mode only) | Read-only views (catalogue, factions, draft, catastrophe, coverage). | Developer only | Not for the wizard; the settlement context projection is a separate, wizard-safe view | |

### 3.2 Legacy Python services (`sim/dmb`)

| Asset | Status | What it provides | Hybrid-compatible | Decision |
| --- | --- | --- | --- | --- |
| `quests/runtime.py` `QuestService` | WORKS (used by `story.py`; `tests/sim/test_t083_quest_runtime.py`) | Six statuses, allowed transitions, `evaluate(world_signals)` for `world_repaired`, `target_destroyed`/`site_destroyed`, `stakeholder_dead` (suspend), `output_confirmed+intervention` (complete), `advance_stage`; `choose_branch` with receipts; `apply_outcome`. No public abandon (story uses `_transition`). | Yes | REUSE; add one public `abandon(quest_id, branch)` wrapper in the narrative package rather than editing the legacy file |
| `quests/binding.py` `QuestBinder` | WORKS | Template registry in `definitions["quest_templates"]`, eligibility by cause kind, dedupe of open instances by (template, cause, affected), refuses dead stakeholders, `_resolve_stakeholder` by workplace or role. | Yes | REUSE; the director supplies `stakeholder_id` explicitly after casting |
| `quests/causes.py` `CauseTracker` | WORKS | Stable occurrence keys `causeocc:<sha>` from (template, kind, affected), dedupe while active, resolve with reason. | Yes | REUSE |
| `people/registry.py` `PeopleService` | WORKS | `create_person` (role, workplace, affiliation, area, position, dialogue profile, flags), `displace`, `record_death`, relationships (-100..100, bands), `add_known_fact`, `append_history`, `promote_profile`, production job occupancy and explicit vacancy records, `displace_workplace`. | Yes | REUSE; the person-to-worker link is a new field pair, not a new service |
| `people/jobs.py` `JobService` | LEGACY-WORKS | Job registry and backfill. | Partly (jobs were Catan processors) | ARCHIVE; hybrid buildings own their worker ids (`building["worker_ids"]`) |
| `narrative/aspects.py` `AspectService` | WORKS (used by `story.choose("persuade")`) | Seven Aspects, thresholds easy/demanding/exceptional, evidence and relationship modifiers, retry fingerprint (no free retry), passive comments. | Yes | REUSE |
| `narrative/conditions.py` | LEGACY-WORKS | Allowlisted condition AST (`all any not eq gte lte has_knowledge relationship_band entity_status quest_state cause_active`). | Yes (reads `state.people/quests/definitions`) | REUSE for dialogue and graph `requires` conditions; extend with hybrid predicates in the narrative package by passing a context, not by editing the file |
| `narrative/dialogue.py` `DialogueResolver` | LEGACY-WORKS (`tests/sim/test_t084_dialogue.py`) | Deterministic line selection by quest/stage/cause/role/era/aspect with scores, stable variant pick per context, `{var}` rendering, sessions with choices and pending effects. | Partly: role and era filters work; `ordinary_talk_line` reaches into Catan `IndustryProjection` | ADAPT: reuse the scoring and session model behind a hybrid fact provider; replace `person_dialogue.person_talk_context` with a hybrid occupation context |
| `narrative/line_catalog.py` | LEGACY-WORKS | Loads only top-level `godot_project/content/source/dialogue/*.json`; archive scopes excluded. | Yes | REUSE the loader; point it at the new narrative packs as well |
| `narrative/person_dialogue.py` | LEGACY-WORKS | Occupation and activity based ordinary talk; opening lines. | No (`settlement_layout.public_occupation_for`, `IndustryProjection`) | ADAPT: rewrite the context function for hybrid buildings (`wl_defs.spec_for_kind`, `worker["role"]`, `building["stall"]`, `disrupted`) |
| `narrative/knowledge.py`, `semantic.py` | LEGACY-WORKS | Knowledge reveal/filter; semantic labels and available actions for the Catan board. | `knowledge` yes; `semantic` no | REUSE `knowledge` for "what the wizard has learned about a person"; EXCLUDE `semantic` (the hybrid has `wizard_labels.gd`) |
| `core/effects.py` | LEGACY-WORKS | `ALLOWED_EFFECT_KINDS` (destroy_*, apply_buff, relationship_change, knowledge_reveal, aspect_change, quest_transition, policy_commitment, diplomatic_agreement, item_transfer, production_modifier, conserved_stock_transfer, hazard_treatment, entity_relocation, history_fact, boulder_quest_accept) applied to the Catan `WorldState`. | Only the people/knowledge/aspect kinds touch state the hybrid shares | ADAPT the *vocabulary*: the narrative effect registry reuses these kind names where the semantics match and maps world-altering kinds to hybrid APIs (section 7.4) |
| `player/inventory.py`, `magic.py`, `grimoire.py`, `recovery.py`, `visits.py` | LEGACY-WORKS | Item catalogue and uses, destroy/buff magic on the Catan board, grimoire export, soft-lock recovery, node visits (`VisitService` is still called by the hybrid's hazard duel). | Inventory partly (hybrid uses `puzzle.items`), magic no | ARCHIVE except `visits` (already used) |
| `adventure/puzzles.py`, `item_recovery.py` | LEGACY-WORKS | Catan-era puzzle service and item recovery. | No (hybrid uses `wizard_rts/puzzle`) | ARCHIVE |
| `world/boulder_quest.py`, `fx_village_world.py`, `fx_village_solutions.py`, `settlement_layout.py` | LEGACY-WORKS (`tests/sim/test_boulder_quest.py`, `test_g05_*`) | The G05 village slice: boulder quest, FX-VILLAGE fixture, layout. | No (Catan nodes) | ARCHIVE; the "road blocked by a boulder" idea is a transport template |
| `persistence/` | LEGACY-WORKS | Repository, migrations, coordinator for the Catan save. | No (hybrid pickles) | ARCHIVE |

### 3.3 Quest content files

| Asset | Status | Content | Decision |
| --- | --- | --- | --- |
| `godot_project/content/source/quests/` (19 JSON) | DATA (validated by `content/schemas/quests.json`; only `shortage/factory_shortage.json` was ever bound, in G05) | Families and ids: shortage (`factory_shortage`, `fuel_yard`, `grain_store`), transport (`bridge_washout`, `cart_blockade`), conflict (`labour_strike`, `water_rights`), diplomacy (`border_truce`, `trade_embargo`), discovery (`ruin_map`, `strange_signal`), military (`deserter_hunt`, `raid_warning`), personal (`lost_heirloom`, `sibling_feud`), catastrophe (`fire_break`, `flood_berm`), `pollution_cleanup`, archive. Each has cause kinds, a stakeholder role, four stages, two solutions with effects (mostly `set_flag`), world-resolved, invalid-target, dead-target, displaced-target, full-cycle, ignore and persistent-return routes, and dialogue keys. **No dialogue text**: the keys point at lines that were never written except for Mara's shortage lines. | **MIGRATE**: the route vocabulary and family taxonomy become the template skeletons; each needs a hybrid cause predicate (section 6.2), a role list and a graph. |
| `content/schemas/quests.json`, `effects.json`, `puzzles.json`, `definition.json` | DATA | JSON Schemas for the legacy template, effects, puzzles. | REUSE as the base of the v2 template schema |
| `godot_project/sim/world/quests.gd` `DmbQuests` (219 lines) | LEGACY-WORKS (`sim/tests/test_quests.gd`) | Three authored settlement stories: *The Missing Flock* (shepherd, reeve, child), *The Tainted Well* (healer, well-digger, mother), *The Road Toll* (carter, tollman, smith). Binary trees of two or three decisions, four outcomes each, effects on the Catan sim (AI weights, resources, treat hex, mood, item, fight). Template chosen from infection and terrain. | **MIGRATE** the three stories and their outcome texts into v2 templates with hybrid roles (hunter or sheep farm; well plus region cubes; carriers plus trade post or a foreign soldier). EXCLUDE the engine. |
| `godot_project/client/world/world_play.gd` (493 lines) | LEGACY-WORKS | Client bridge for `DmbQuests`: dialogue UI, outcome application, battles. | EXCLUDE (the hybrid client is `story_ui.gd`) |
| `godot_project/sim/world/village_quest_runner.gd` (729 lines) | LEGACY-WORKS (Village Test Mode) | Generic graph runner: nodes `talk`, `investigate`, `travel`, `branch`, `choice`, `conclude`; `requires`/`sets` flags; dialogue index `npc_id|quest_id|node_id|variant`; ambient, phased and epilogue lines; objective text; choice payloads. No fixture-specific names. | **MIGRATE the format, re-implement the runner in Python** (about 300 lines). Keep the GDScript for Village Test Mode until the Python runtime is proven, then retire. |
| `godot_project/content/village_tests/E36B/` (`village.json`, `cast.json`, `quest.json`, `dialogue.json`) and `E17A/` | DATA (loaded by `VillageTestCatalog`) | E36B "Bellwater": 12 cast members with relationships and anchors; `broken_promise` graph (talk, investigate, branches, three endings); dialogue keyed per node and variant. E17A is the four-beat Reeve, Woodcutter, Miller, Miner slice. | **MIGRATE** as the first two authored templates in the v2 format (E36B maps to workbook structure 12 *The broken promise*; the reeve binds to the settlement's warehouse keeper, the potter to a brick or clay worker, the healer to a clinic or warehouse person, the scavenger to a quarry or charcoal worker). |
| `godot_project/content/source/dungeons/{alien,bunker,cave,industrial,machine}/` (`layout.json`, `puzzle.json`) | DATA | Era-themed dungeon dressings. | DATA for later eras; the hybrid generator takes `kind` and could take a theme from the era (Historic cave, Modern industrial, Dystopian bunker/machine/alien) |
| `DD/` (Deathtrap backbone JSON, encounter CSV, replacement first-adventure plot), `docs/DEATHTRAP_OVERHAUL_PLAN.md`, `docs/SECOND_ADVENTURE_PLAN.md` | DATA (plans; nothing implemented in the hybrid) | Book-faithful dungeon run design: traps, wounds, companions, riddles, "not every danger is a duel". | ARCHIVE for canon (D19). Two ideas carry: wounds as a duel cast penalty and riddle-or-duel branches are cheap template options later. |

### 3.4 Dialogue content and tools

| Asset | Status | Content | Decision |
| --- | --- | --- | --- |
| `godot_project/content/source/dialogue/settlement_normal.json` (12 lines) | LEGACY-WORKS (loaded by `LineCatalog`) | Role baselines (worker, villager, leader, soldier), invalidation lines (`missing_cause`, `dead`, ...), neutral fallback. | REUSE as the safe fallback bank |
| `dialogue/boulder_quest.json` (7), `tutorial/hints.json` (7) | DATA | Boulder quest lines; seven tutorial hints. | MIGRATE the hints into the tutorial pack |
| `dialogue/baseline/g08_baseline.json` (1,404 lines) | DATA, **not loaded** (`LineCatalog.load` reads only top-level files) | Generated placeholder lines `[era/family/role/aspect] I need help with ... (n)` across eras, families, eight roles and aspects, with accept/decline choices. | ARCHIVE (bracketed placeholders, not prose); useful only as a coverage shape |
| `dialogue/archive/aspect/aspect_bank.json` (341), `onboarding` (3), `shortage/mara_lines.json` (7), `mvp_shortage.json` (9) | DATA (archived scope) | Aspect-tagged lines, Mara's shortage lines. | ARCHIVE; Mara's lines are a worked example of fact-bound shortage dialogue |
| `godot_project/content/compiled/dialogue/*`, `compiled/packs/*` | DATA | Compiled packs from the G08 era. | ARCHIVE |
| `godot_project/content/source/people/{dialogue_profiles,goals,preferences}.json`, `aspects/` | LEGACY-WORKS (`PeopleService.load_people_content`, `AspectService.load_aspect_content`) | Profile catalogues and Aspect content. | REUSE |
| `docs/Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112_FANTASY_STORY_AUDITED.xlsx` | DATA (read by `tools/dialogue_generation/workbook_reader.py`) | Sheets: Summary; **Cast Matrix** (112 rows, 80 columns: cast id, economic profile, three hex kinds, three primary and three processor roles, six generic roles, situation shape, three choices with A/B immediate results, eight overall outcomes AAA..BBB, combat branch and consequence, tragic outcome, twelve personalities, soap-inspired premise, start/normal-end/tragic-end gossip ×4); **Economic Profiles** (56); **Role Catalogue** (6 terrains → primary building and worker; 21 terrain pairs → processing building and worker; 12 generic roles); **Generic Mixes** (112); **Situation Structures** (20 four-role skeletons with decision coding, combat and tragic rules); **Dialogue Matrix** (1,344 rows = 12 per cast: character letter, village role, story role, personality, trigger, opening line, choice prompt, options A/B, responses A/B, state changes A/B, normal end line). | **MIGRATE by tool**: the structure is mechanically convertible to the v2 template graph (section 6.3). Prove on three casts first (owner instruction). |
| `docs/Duel_Master_Battle_Village_Cast_Matrix_WORLDVIEW_DIALOGUE_PILOT_3_STORIES (1).xlsx` | DATA | Same sheets plus *Worldview Pilot Guide* and *John Dialogue Pilot* (854 rows: beat instances for E36B, E53A, E56A with seven worldview replies, context fit and conviction tiers). | MIGRATE as the wizard-reply source for the three pilot casts |
| `docs/characters/DMB_Character_Profiles_88_Disco_Elysium_Depth.csv` (88 profiles, 94 columns) | DATA (read by `tools/dialogue_generation/ensemble`) | Named characters with role, district, voice, wants, fears, secrets, worldview scores, relationships, daily routine, quest hook, complication, alternate solution, puzzle type, reward model, intro/vulnerable/angry/lie/truth lines, absence consequence. | DATA for now (named canon is deferred, D19). The *Quest_Hook / Quest_Complication / Quest_Alternate_Solution / Puzzle_Type* columns are a second template seed source once the workbook path is proven; the voice columns can drive dialogue profiles when canon is decided. |
| `tools/dialogue_generation/` (cli, config, database, exporter, fixture_builder, normalize, ollama_client, pipeline, validator, workbook_reader, worldviews, prompts, ensemble/*, 4 test modules; `dialogue_factory.db` 2.1 MB) | WORKS offline (15 tests; `generated/dialogue/E36B.json` 25 banks, `E17A.json` 24 banks) | Workbook ingestion, semantic bank classification, seven-worldview writer with Python-owned score deltas (`worldviews.json`), validation, review, bounded repair, SQLite recovery, approved-only export, fixture builder for Village Test Mode. Ensemble tools build relationship graphs and scene manifests from the 88 profiles (`Run Ensemble Authoring.bat`, `Validate Ensemble Authoring.bat`). | **REUSE** the pipeline; **ADAPT** the exporter and `fixture_builder` to emit the narrative pack format (section 7.5). Never a runtime dependency. |
| `docs/DIALOGUE_GENERATOR_STATUS.md`, `_HANDOFF.md`, `DIALOGUE_E36B_VERTICAL_SLICE.md` | Docs | Current and accurate for the tool; the "required integration work" section already says: converge fixture format with the production runtime, make exports target it, keep model-free tests. | Followed by this plan |
| `docs/NARRATOR_VOICE.md`, `docs/roles/*.md` | Docs | Voice and role briefs for authoring. | REUSE as authoring guidance for the packs |

### 3.5 Opening and tutorial material

| Asset | Status | Content | Decision |
| --- | --- | --- | --- |
| `docs/FIRST_ADVENTURE.md`, `godot_project/client/scripts/adventure.gd`, `client/world/{world_data,story_events}.gd`, `sim/bestiary.gd` | LEGACY-WORKS (standalone Godot adventure; `tools/run_adventure_flow.sh`) | Trial Day in Ashwell: John watches Halvard fall, takes the staff (learns Water), Ashby's lesson duels (fixed ward, guaranteed win; then a deduction lesson), the Trial Road, the gate. Flags, pickups, bestiary. | **ADAPT the ideas, not the code**: (1) a first spell comes from a person and an object, (2) a mentor teaches the duel with a told ward then a hidden one, (3) optional practice fights, (4) the player chooses when to commit. Names stay out of canon (D19). |
| `godot_project/content/source/dialogue/tutorial/hints.json` | DATA | Seven hint lines. | MIGRATE |
| `docs/SETTLEMENTS_AND_DUNGEONS.md` | Docs (describes the Catan-era pass: staff gives Water and Vine, lessons 1-3, quests, dungeon network with acyclic item dependencies, puzzle mechanics) | The dungeon dependency rule ("dependencies only point backwards in creation order") and "the imported item is shown, not consumed" are good rules for multi-dungeon stories. | REUSE the rules |
| `docs/ENCOUNTER_DESIGN.md`, `docs/RULES.md`, `godot_project/sim/duel_ruleset.gd` | Docs and code | Duel rules and encounter tiers. | REUSE for the practice-duel parameters |

### 3.6 What is absent in the hybrid (genuine gaps)

| Gap | Needed by | Note |
| --- | --- | --- |
| Person ↔ worker/carrier/unit link | C2 (cast real workers) | New fields `person["worker_id"]` / `worker["person_id"]` (or carrier/unit), pose taken from the worker row. |
| A story-graph runtime in Python | C5, D | Port of `VillageQuestRunner` semantics. |
| Settlement context projection | C1 | Read-only, cached, deterministic summary per settlement. |
| Director: per-settlement three-slot assignment, selection, refill | C3 | New module. |
| Template v2 format and validator | C3, D | Extends `content/schemas/quests.json`. |
| Narrative dialogue packs and fact binding | D | Extends `LineCatalog`/`DialogueResolver` ideas. |
| Living-story policies beyond the two families (rebind, suspend-with-deadline, ownership change) | C4 | `QuestService.suspend` exists; rebind and resume logic does not. |
| Wizard progression state (known spells, lessons, tutorial, journal) that survives cycle reset | B | Must live on the wizard, not on the world's story state. |
| Server save/load for Wizard Mode | B, C4 | The pickle format exists in `HybridEnv`. |
| Observe op and journal views for the wizard | B, C3 | Read-only ops in `story.WIZARD_OPS` style. |
| Headed presentation of a worker as a talk target, rumour markers, journal | Phase G | `story_ui.gd` extension. |
| Narrative gate for headless training and a non-`world.events` log for narrative events | E | Section 8. |

---

## 4. Conflicts between older canon and the hybrid

| Older material | Conflict | Ruling used by this plan |
| --- | --- | --- |
| Catan hexes, nodes, edges, "World Turn" (`CANONICAL_GAME_ONTOLOGY.md` places, `DmbQuests` terrain counts, dungeon placement on nodes) | The hybrid is a square grid with settlements as command-centre territories (D03, D07). | Settlement context reads territory and real buildings; dungeon entrances are placed on free tiles beside a real building (`story._ensure_dungeon` already does this). |
| Exhausted mines as a story cause (`mine_exhausted.json`, roadmap M3 text, design v0.5 section 1 "depleted mine") | D22: mineral sites are inexhaustible. | Collapse, sickness, blight, spill and fault are the shortage causes. |
| Named canon (John, Ashwell, Halvard, Ashby, Mara, Bellwater, the 88 profiles) | D19 defers named canon. | Templates carry roles; names are generated from faction and settlement (`"Miner of Red home 1"` today) until the owner decides canon. The workbook's personalities are kept as *voice tags* on roles, which does not name anyone. |
| Catan quest effects (`weight`, `resource`, Catan `treat hex`) | Factions are not commanded by the wizard (D02); wares are conserved. | Effects are mapped to typed hybrid actions or become narrative-only (section 7.4). |
| John's worldview score system (seven worldviews M/A/R/G/S/D/C with deltas) from the Dialogue Factory | Not in the hybrid; the hybrid has seven Aspects (`AspectService`). | Both are kept: worldview deltas are applied to a wizard-level `worldview` record (narrative-only state, like Aspects), never to factions. Whether worldviews should merge into Aspects is an owner decision (plan, open question Q4). |
| Village Test Mode as a separate projection and story runtime (`VILLAGE_SYSTEM_CURRENT_STATE.md` section 6) | The hybrid has one Overworld and one world. | Village Test Mode is not extended; the Python runtime takes over its format. |
| G08 baseline dialogue (bracketed placeholders) | Not prose. | Not loaded; archived. |

---

## 5. Test and tool inventory relevant to the narrative work

| Suite | Count | What it protects |
| --- | --- | --- |
| `WizardRTSHybrid/tests/test_story_slice.py` | 12 | The full quest chain on a real mine, idempotent effects, duel pause, dialogue facts, pickle round trip |
| `test_quest_env.py`, `test_dungeon_env.py`, `test_duel_env.py`, `test_outbreak_env.py` | 8, 8, 9, 7 | Headless environments and their scenario knobs |
| `test_puzzle_parity.py`, `test_puzzle_exhaustive.py`, `test_ward_parity.py` | 6, 1, 5 | Dungeon and duel parity with Godot |
| `test_outbreaks.py`, `test_civilisation_rules.py`, `test_vp_eras.py` | 15, 18, 17 | Regions, history (split/collapse/reset), eras |
| `test_fire_magic.py` | 5 | Wizard destruction |
| `test_determinism.py`, `test_hash_baseline.py`, `test_content_freeze.py` | | Two-process determinism, recorded v4 hashes (seeds 507, 11, 23; 20 minutes; first 3 checked), frozen roster |
| `tests/sim/test_t083_quest_runtime.py`, `test_t084_dialogue.py`, `test_t080_aspects.py`, `test_t028_people.py`, `test_t077_people_profiles.py`, `test_g05_dialogue_matrix.py` | legacy | The reused legacy services |
| `tools/dialogue_generation/tests` | 15 | The offline factory, model-free |
| Headed: `client/tests/run_hybrid_story.gd`, `run_hybrid_outbreak.gd`, `run_hybrid_playtest2.gd` (via `scripts/run_headed_suite.sh story outbreak playtest2`) | 3 | Story UI over the real client |

---

## 6. Mapping existing content to dynamic settlement templates

### 6.1 Archetype library proposed from existing material

| Archetype id | Category (owner's list) | Source material | Hybrid cause / context predicate | Roles (bound to real entities) | World effect candidates |
| --- | --- | --- | --- | --- | --- |
| `shortage.gallery_collapse` | economic / industrial accident | `story.py` + its template (WORKS) | a mine `disrupted.cause == "collapse"` | miner (worker of the mine), mine, starved workshop | `reopen_gallery` (exists) |
| `shortage.workplace_closed` | economic / outbreak-related | `disruption.REPAIR` causes `sickness`, `blight`, `toxic_spill`, `signal_fault`; legacy `pollution_cleanup`, `fuel_yard` | any workplace `disrupted` with those causes | worker of the building, building, a carrier or warehouse keeper | `clear_disruption` (via `disruption.clear`), `cure_region` |
| `shortage.starved_workshop` | economic shortage | legacy `factory_shortage`, `grain_store`; workbook *The withheld resource*, *The competing emergencies* | a processor with `stall.reason == "inputs"` for N minutes while another building of the settlement holds that ware | processor worker, supplier worker, warehouse keeper | narrative (relationship, history) plus a bounded `unrest_delta`; a `caravan` effect when a partner warehouse can supply |
| `catastrophe.outbreak_treatment` | outbreak / illness | `story.py` (WORKS) | region cubes ≥ 2 at a standing settlement | healer (clinic worker if a clinic stands, else warehouse person), affected workers | `treat` (exists) |
| `catastrophe.fire_break` | catastrophe | legacy `fire_break`; `disruption` `outbreak_fire` | a workplace destroyed by `outbreak_fire` in the last 10 minutes (`society._losses`) | displaced worker, neighbouring workers | narrative; `unrest_delta` |
| `transport.blocked_road` | lost goods / blocked delivery | legacy `cart_blockade`, `bridge_washout`; G05 boulder quest | a building with no road link to its warehouse (`world.adjacency`) while requesting wares | carrier, building worker, warehouse keeper | narrative (the faction AI rebuilds roads itself); optional `rock removal` by fire magic is already a real wizard action |
| `military.raid_warning` | military danger | legacy `raid_warning`; workbook *The reluctant witness* | hostile units within 40 tiles of the settlement (`diplomacy.hostile`, `military` positions) | watchkeeper (an armed unit of the faction, as a Person), worker, warehouse keeper | narrative; `diplomacy_offer` on behalf of an envoy |
| `military.deserter_hunt` | military / personal | legacy `deserter_hunt` | a unit of the faction died or was killed near the settlement recently | soldier person, kin (worker), reeve | narrative |
| `diplomacy.border_truce` | political intrigue | legacy `border_truce`, `trade_embargo`; workbook *The bad bargain* | two factions at war whose territories are within 30 tiles; or a trade partner now hostile (`trade.hostile`) | envoy (a person of the other faction bound to its nearest warehouse), reeve, trader (carrier of a caravan) | `diplomacy_offer` (`diplomacy.propose`; the AI answers by its policy) |
| `personal.disputed_ownership` | personal conflict | legacy `sibling_feud`, `water_rights`; workbook *The disputed ownership*, *The debt triangle*, *The succession problem* | two workers of the same kind in one settlement; or a well shared by farms | two workers, elder (warehouse person), a fourth voice | narrative; relationship and history facts |
| `personal.broken_promise` | mystery / personal | E36B `broken_promise`; workbook structure 12 | a settlement with at least a reeve-equivalent, two workplaces of different kinds and one disrupted or stalled building | reeve, potter/clay or brick worker (else a processor), healer, scavenger/quarry worker | narrative; `unrest_delta` |
| `mystery.tainted_well` | mystery / outbreak | `DmbQuests` *The Tainted Well* | a `well` in a region with ≥ 1 cube, or a well `disrupted` by blight | healer, well worker, a household person | `cure_region` (1 cube) or `clear_disruption` |
| `personal.missing_flock` | mystery / personal | `DmbQuests` *The Missing Flock* | a hunter or sheep farm whose program fails `no_game`/`no_space` for N minutes, or animals near a nest | hunter/shepherd, reeve, child (household person) | narrative; optional dungeon (cave) |
| `conflict.road_toll` | local dispute / intrigue | `DmbQuests` *The Road Toll* | a trade post with caravans and a foreign armed unit standing on the road, or a carrier road crossing another faction's territory | carter (carrier), tollman (foreign unit person), smith (processor worker) | narrative; `diplomacy_offer` |
| `conflict.labour_strike` | moral dilemma | legacy `labour_strike`; workbook *The absent worker* | settlement `unrest ≥ 0.4` with `closures` or `hunger` pressure | worker, reeve, healer | `unrest_delta` (bounded) |
| `discovery.ruin_map` | magical anomaly / dungeon | legacy `ruin_map`, `strange_signal`; `SETTLEMENTS_AND_DUNGEONS` network rule | a ruin (destroyed building footprint left by `lifecycle`) or a nest within 30 tiles | a curious worker, an elder | dungeon (reuse `_ensure_dungeon` with theme by era) |

Fifteen archetypes cover every category in the owner's list from existing material; none needs new buildings, units or wares.

### 6.2 Hybrid signals available for predicates (all read-only)

`building["disrupted"]` (cause, repair progress), `building["stall"]` (reason `inputs`/`not_needed`/..., detail, time), `building["operational"]`, `building["constructing"]`, `building["worker_ids"]`, `world.stocks[warehouse]`, `world.shortages`, `world.adjacency` (road graph), `world.carriers`, `world.units` (faction, weapon, alive, position), `diplomacy.state_of`, `trade.hostile`, `trade.partners_traded`, `regions.cubes_here`, `regions.production_factor`, `society.pressures`, `rec["unrest"]`, `world.__dict__["_losses"]`, `history.state(world)["faction"][f]["state"]`, `world.era_index`, `settlements.standing`, `world.faction_info[f]["tribe"]`, `wl_defs.spec_for_kind(kind)` (inputs, outputs, working positions), `workers._roles_of(building)`.

### 6.3 How much of the 112-story workbook can be incorporated

* **Structure**: 100%. Twenty situation structures are four-role skeletons (A needs B, C can persuade, D unlocks) with three binary decisions and eight coded outcomes. That is a fixed graph shape with role slots; a converter writes one v2 template per structure (20 graphs) and one *cast variant* per workbook cast (112 role lists plus text).
* **Roles**: the Role Catalogue maps six terrains to primary and processing occupations. Hybrid equivalents exist for five: Wood (producer/lumberjack, sawmill), Ore (mine/ironmine, smelter, smithy), Grain (Widelands farms, bakery/brewery), Wool (sheep farm, weaving mill), Brick (clay pit, brick kiln). **Wastes** (Scavenger, Charcoal Burner, Refiner, Cistern Keeper) has no Prehistoric or Historic equivalent and maps to quarry, charcoal kiln, and Modern scrap or Mindustry blocks. 56 of the 336 hex slots are Wastes; casts containing at least one Wastes hex are a minority but not small. The twelve generic roles (Reeve, Elder, Healer, Storekeeper, Carter, Trader, Watchkeeper, Messenger, Householder, Child, Apprentice, Shrine Keeper) map to: warehouse keeper person, clinic worker, carriers, trade caravans, armed units, and household persons attached to the command centre (the only persons the director may *create*, because the simulation has no residents).
* **Text**: 1,344 NPC rows are usable as authored prose after role-name substitution ("Woodcutter 1" becomes the bound person's name) and fact binding where the line states something the world must confirm. Wizard-side replies exist for three casts (the pilot) and two exported casts; the rest would come from the Factory **only after** the pilot is accepted by the owner.
* **Estimate**: with the role map above, about 70 of 112 casts are castable in a developed Historic settlement without substitution; about 30 more with the Wastes substitution; roughly 10 need Modern-era buildings. These are counts from the Cast Matrix role columns, not play-tested claims.

---

## 7. Decisions recorded by this audit (details in the plan)

1. **Canonical runtime**: Python, `wizard_rts/story.py` plus `sim/dmb/quests` plus a new `wizard_rts/narrative/` package. GDScript quest runners are retired for the hybrid.
2. **Template format**: the v2 JSON template = legacy quest schema (causes, routes, solutions, persistent return) + `roles` + `graph` (Village Test node types) + `dialogue` bank references + `living` policies + `select` metadata.
3. **People**: a Person is bound to an existing worker, carrier or unit whenever one plays the role; the director creates a Person only for household roles that the simulation does not model, capped per settlement, and never for presentation.
4. **Effects**: two registries, narrative-only and world-altering; world-altering effects call existing simulation APIs only (`disruption.clear`, `regions.cure`, `trade.send_caravan` when `can_supply`, `diplomacy.propose/respond`, bounded `unrest` on the settlement record, `history_fact`); nothing creates wares, buildings or units.
5. **Dialogue**: offline packs, deterministic selection, fact placeholders, safe fallback; no runtime model.
6. **Training**: the narrative layer is gated; see the contract for the mechanism and the hash-baseline consequence.

---

## 8. The training-path question in one place

* `story.story_quantum` runs in every `HybridWorld` (`world.py` line 887) and in `_world_cache.attention_advance`. It is deterministic (sorted iteration, `zlib.crc32` seeds, `random.Random(seed)` instances; it never touches `world.rng`).
* Its state reaches `state_hash()` through `snapshot()["story"]` and `story.entity_rows`. With the story switched off the hash differs from minute 1 (the empty `{}` versus the six-key empty record, section 2.4) and, once fixed to the same shape, only in worlds where a quest opens. The recorded baselines (`docs/perf/hash_baseline_v4.json`, 20 minutes) were recorded with the story on.
* Its effect on factions: none by construction when no wizard acts (persons and dungeon entrances occupy no blocked tiles; `CauseTracker`, `QuestService` and `PeopleService` records are read by nothing in the faction code; `world.events` receives `story_*` events that no AI reads). The measurement in section 2.4 reports the observed cost and the faction-level comparison.
* Consequence: a gate that switches the legacy story off in training changes the recorded hashes once, at a moment the neuroevolution agent chooses (its own T1.1 re-records them anyway). The contract proposes that order.
