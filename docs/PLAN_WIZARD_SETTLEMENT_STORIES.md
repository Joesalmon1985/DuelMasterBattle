# Plan: Wizard Mode, introductory quests and three dynamic storylines per settlement

Status: **PROPOSED, awaiting owner approval. No gameplay code is changed by this document.** Branch `feature/wizard-settlement-stories` from `origin/feature/neuroevolution-plan` at `4b67f55c`. Audit of what exists: `WIZARD_NARRATIVE_AUDIT.md`. Tasks: `EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`. Boundaries with the neuroevolution programme: `WIZARD_STORY_INTEGRATION_CONTRACT.md`.

Decisions in force that this plan obeys: D02 (the wizard commands no faction), D03/D07 (square grid, settlement = command centre plus territory), D10 (real world effects), D11 (cycle reset keeps only the wizard), D14 (Python owns the world, Godot presents), D19 (named canon deferred; preserve existing stories), D22 (inexhaustible mines; collapse is the shortage cause), D33 (content freeze), D34 (neuroevolution is the development priority). Terms: a **story** is a template bound to a settlement; a **quest** is a story the wizard has accepted (one `QuestService` instance); a **slot** is one of the three story positions a settlement holds.

---

## 1. System design and ownership

### 1.1 One world, two perspectives

```text
                      HybridWorld (wizard_rts/world.py)  -- the only simulation
                      | buildings, workers, carriers, units, stocks, roads, regions,
                      | settlements (world.dmb.settlements), history, diplomacy, trade
                      |
   advance() ---------+--- existing quanta (economy, logistics, AI, military, ...)
                      |
                      +--- if world.narrative_enabled:            <-- the gate (section 10)
                             narrative.director.quantum(world)    <-- new, once a game minute + events
                             story.story_quantum(world)           <-- existing, moved behind the gate at merge

   wizard ops (server.py -> story.dispatch -> narrative.ops) : talk, choose, observe, journal, enter, dungeon_*, duel_*, treat, save, load
   faction ops (sim_api.HybridEnv, God Mode)                  : untouched

   Godot hybrid_world.gd / story_ui.gd : draws snapshot["narrative"] and snapshot entities; sends wizard ops; owns no rules
```

Everything narrative lives in a new package `WizardRTSHybrid/wizard_rts/narrative/` and its data under `wizard_rts/data/narrative/`. The existing `story.py` keeps its public surface (`WIZARD_OPS`, `dispatch`, `entity_rows`, `snapshot`, `apply_effects`, dungeon and duel functions) and becomes the *execution* layer the director calls; its two hard-coded families become templates. `sim/dmb/quests`, `people`, `narrative/aspects`, `narrative/conditions`, `adventure/mastermind` are called as they are.

### 1.2 Module map (new package)

| Module | Responsibility | Reads | Writes |
| --- | --- | --- | --- |
| `narrative/__init__.py` | `enabled(world)`, `state(world)` (the `world.narrative` dict, pickled with the world), config loading | | `world.narrative` |
| `narrative/config.py` | `data/narrative/config.json`: unlock time, slot count (3), max accepted (4), cadences, caps; every number configurable | | |
| `narrative/context.py` | `settlement_context(world, sid) -> dict` (section 4), cached by a per-settlement version stamp | world (read-only) | cache in `world.narrative["context_cache"]` |
| `narrative/templates.py` | load, validate and index v2 templates (`data/narrative/templates/*.json`); schema in `data/narrative/schema/template_v2.json` | files | in-process registry |
| `narrative/casting.py` | bind abstract roles to real entities: workers, carriers, units, buildings, settlements, other-faction people; create household persons only when allowed; the **PersonLink** (section 5) | world, `PeopleService` | `world.dmb.people`, link fields |
| `narrative/director.py` | per-settlement slots, eligibility, scoring, selection, refill, living-story checks, suspend/resolve/fail, epochs; the only writer of slots | context, templates, casting | `world.narrative["settlements"][sid]["slots"]`, `QuestService`, `CauseTracker` |
| `narrative/graph.py` | the story-graph runtime (Village Test node semantics in Python): current node, `requires`/`sets` flags, talk/investigate/travel/choice/branch/conclude, objective text | templates | per-quest graph state in `world.narrative["quests"][qid]` |
| `narrative/dialogue.py` | pick lines from packs by (template, node, role, variant, worldview), fill `{facts}`, fallback; Aspect checks via `AspectService` | packs, facts | dialogue sessions (transient) |
| `narrative/facts.py` | the per-quest truthful facts dict from live state (generalises `story.facts`) | world | |
| `narrative/effects.py` | two registries (narrative-only, world-altering), validation, receipts; wraps `story.apply_effects` | | `world.dmb.command_receipts` and the APIs it calls |
| `narrative/tutorial.py` | the introductory lessons, the mentor binding, the unlock rule | | `world.narrative["wizard"]` |
| `narrative/wizard.py` | wizard-level state that survives a cycle reset: known spells, lessons, journal, Aspects/worldview, memory of settlements | | `world.narrative["wizard"]` |
| `narrative/ops.py` | wizard ops added to `story.WIZARD_OPS`: `observe`, `journal`, `accept`, `decline`, `travel_hint`, `save`, `load` (the last two in `server.py`) | | |
| `narrative/events.py` | the narrative log (`world.narrative["log"]`, bounded) and the presentation events forwarded to the snapshot; **nothing narrative is appended to `world.events`** (section 10) | | |
| `narrative/perf.py` | counters (calls, ms per quantum, contexts rebuilt) for the performance tests | | |

Tests: `WizardRTSHybrid/tests/test_narrative_*.py`. Scripts: `scripts/narrative_report.py` (assigned stories per settlement for a seed and minute), `scripts/build_story_templates.py` (offline workbook → templates and packs), `scripts/validate_narrative.py`.

### 1.3 Data flow of one story

```text
settlement context  --eligible-->  templates  --score+seed-->  3 slots per settlement
      |                                                             |
      |  (wizard enters the settlement, observes, talks)            v
      |                                                        offer: bind roles (casting) -> CauseTracker.observe -> QuestBinder.bind -> QuestService "offered"
      v                                                             |
 facts.py <------ live world ------>  graph.py node  ---->  dialogue.py lines  ---->  Godot story_ui
                                           |
                                   choice / investigate / travel / dungeon / duel
                                           |
                                   effects.py (typed, receipts) -> simulation APIs  -> QuestService completed / failed / resolved_by_world
                                           |
                                   director living checks every minute (rebind, suspend, resolve, fail)
```

---

## 2. Introductory quest progression (Phase B)

### 2.1 What exists to build on

The tutorial uses only real systems: walking (`set_pose`), talking (`talk`/`choose`), the Mastermind duel (`MastermindDuel.attach` with a seeded `random.Random`, the `story_duel` pause token), fire magic (`magic.fire`), treatment (`regions.begin_treatment`), settlement territory (`territory.covering`), and the first dynamic story. The First Adventure's strongest ideas are kept as structure: a spell is learned from a person and an object; the duel is taught with a *told* ward, then a *hidden* one; practice is optional; the player chooses when to commit. No names from it are used (D19).

### 2.2 The lessons

| Id | Lesson | How it works through real systems | Essential |
| --- | --- | --- | --- |
| L1 `meet` | Talk to someone | The mentor is a Person bound to the keeper of the wizard's starting settlement's command centre (PersonLink to the warehouse; rebinds to any standing settlement's centre if that one falls). Any `talk` with any linked person also counts. | yes |
| L2 `first_spell` | Learn your first spell | The mentor's dialogue gives `spell:flame` to `wizard.known_spells`. Fire magic (`fire` op in `server.py`) and dungeon spell use (`dungeon_interact(spell=)`) are gated on `known_spells` **in the wizard path only** (the simulation function `magic.fire` is unchanged). Frost and Vine come from later stories or dungeons, Water-style treatment from L4. | yes |
| L3 `duel_lesson` | Learn the duel | Practice duel 1: `MastermindDuel.attach` with the secret *told* in the dialogue (the public view carries a `hint` listing the secret) and generous casts; practice duel 2: hidden secret, 2 colours' worth of hint ("not red, not blue"), normal casts. Loss is allowed and explained; no world effect. Uses the existing duel ops and pause token. | yes |
| L4 `observe` | Investigate a workplace | New read-only op `observe` on a building or person within 3 tiles returns the fact lines (`facts.py`): what it makes, whether it is working, why it is idle (stall reason), who works there. Completes when the wizard observes any workplace that is not a warehouse. | no |
| L5 `travel` | Travel between settlements | Completes when the wizard's tile is inside another standing settlement's territory (`territory.covering` for any faction). `travel_hint` op returns the nearest other settlement's direction and distance (no teleport). | yes |
| L6 `first_story` | Help an inhabitant | Completes when any story with `select.tier == "simple"` reaches `completed`. The director offers a simple story in the starting settlement from the start (section 3.5). | no |

Essential set `{L1, L2, L3, L5}`; configurable in `config.json` (`tutorial.essential`).

### 2.3 Transition rule and the recommended time threshold

Dynamic stories unlock when **all essential lessons are done OR `game_ms >= unlock_after_ms`**, whichever comes first. Recommended default **20 game minutes**, configurable (`narrative.unlock_after_ms`, 0 disables the wait).

Justification from measured worlds: a `campaign` world starts with seven buildings per faction and no workers; by minute 20-25 the measured games have a few dozen buildings per faction with lumberjacks, quarries, hunters, wells and the first drafted workplaces (section 2.4 of the audit; the 40-minute benchmark reaches about 370 buildings in total). Three distinct stories need at least two workplace kinds and one worker per settlement, which the primitive start reaches around minute 15-20. The walk between two neighbouring homelands is about 100-150 tiles, under a minute at the wizard's 4 tiles/s, so the essential lessons take under ten minutes of play; 20 minutes leaves a margin without making a fast player wait.

Late or returning players: lessons never close. The journal lists undone lessons under "Lessons"; the mentor offers the next undone one on every talk; L2 and L3 are repeatable. If the starting settlement was destroyed, the mentor rebinds to the nearest standing settlement's keeper. If the world has moved on (eras, splits), the lessons still bind, because they reference roles, not entities.

### 2.4 Determinism and persistence

Lesson state is in `world.narrative["wizard"]["lessons"]` (pickled with the world; copied by `server.py` across a cycle reset). Practice duels seed from `(world.seed, "tutorial", attempt)` as `story.duel_begin` does. Nothing reads the wall clock.

---

## 3. Dynamic story assignment (Phase C3)

### 3.1 Slots

`world.narrative["settlements"][sid] = {"epoch": n, "slots": [slot×3], "history": [...], "cooldown_until_ms": ...}`. A slot is `{"template": id, "status": "assigned"|"offered"|"accepted"|"closed", "quest": qid|None, "cast": {...}, "assigned_ms": t, "seed": int}`. "Assigned" is the settlement's story (a rumour, a marker on a person); it becomes a quest instance only when the wizard talks to the entry role and accepts (`QuestService` "offered" then "active"). The player's journal shows **accepted** quests (cap `max_accepted`, default 4, the current `MAX_OPEN_QUESTS`) separately from the three **rumours** of the settlement they stand in. This keeps the journal small while every settlement still holds three stories.

### 3.2 Eligibility

A template is eligible for a settlement when every predicate in its `requires` list passes against the context (allowlisted ops: `has_building_kind`, `has_building_class`, `has_role`, `count_gte`, `disrupted_cause`, `stall_reason`, `region_cubes_gte`, `unrest_gte`, `neighbour_hostile_within`, `foreign_units_within`, `no_road_link`, `trade_partner`, `era_in`, `age_gte_ms`, `recent_loss`, `all`, `any`, `not`) **and** every role marked `required` can be cast now (casting is a dry run with the same code that binds later).

### 3.3 Scoring and selection (deterministic, varied)

```text
score(t, sid) = relevance(t, ctx)                     # 0..1 from the template's `select.relevance` rules (e.g. a live disruption = 1.0, a stale one = 0.5)
              + 0.25 * cast_quality                    # fraction of roles bound to real workers/units rather than created persons
              - 1.0  * same_family_in_settlement       # another slot already holds this family
              - 0.5  * same_template_nearby            # the template is assigned in one of the 2 nearest settlements
              - 0.5  * recently_closed_here            # within `repeat_cooldown_ms`
              + 0.10 * jitter(seed = crc32(world.seed, sid, epoch, t))   # variety between games, identical for a given world and seed
```

Selection fills empty slots greedily: sort eligible templates by `(-score, template id)`, take the best whose family is not already in a slot, repeat. Ties break on the id, never on dict order. The epoch increments every time the settlement's slots are rebuilt, so the jitter changes when a slot refills, but a save and load reproduces the same choice because the epoch is saved.

### 3.4 Lifecycle and cadence

* `director.quantum(world)` runs when `economy_quanta % 600 == 0` (once a game minute) and processes at most `budget_per_minute` settlements (default 8) in a round-robin over `sorted(settlements.standing)`, preferring settlements whose context version changed and the settlement the wizard stands in (always processed).
* A settlement founded (`settlement_founded` in the chronicle, or a new id in `world.dmb.settlements`) gets slots at its next turn, after `min_age_ms` (default 3 minutes) so there is something to cast.
* A closed slot refills after `refill_cooldown_ms` (default 5 minutes) with a template of a different family than the one that closed.
* A destroyed settlement (`state != "standing"`) closes its slots: assigned ones silently, accepted ones through the quest's `invalid_target_route`.
* Ownership change (`rec["faction"]` rewritten by `history.split`): slots keep their templates; roles with `faction: same` are re-cast against the new faction; roles bound to real entities keep their bindings if the entity moved with the settlement (it does: `history.split` moves buildings, workers and units).

### 3.5 The simple tier

Templates with `select.tier == "simple"` (one role, one talk, one choice, narrative-only effect; for example `personal.kind_word`, migrated from the hint lines and the workbook's background-villager openings) are always eligible so a new settlement and the tutorial always have an entry story. They are never more than one of the three slots.

---

## 4. Settlement context (Phase C1)

`context.settlement_context(world, sid)` returns a plain dict, built only from reads, cached until the settlement's version changes. The version is a tuple of cheap counters: number of standing buildings of the faction near the centre, disrupted count, stalled count, region cube count, unrest band, foreign units within 40 tiles band, era index, `world.events.total` bucketed to the minute. Fields:

| Field | Source |
| --- | --- |
| `id, name, faction, tribe, home, founded_ms, age_ms, state, unrest, pressures, chronicle_tail` | `world.dmb.settlements[sid]`, `world.faction_info`, `society` |
| `era` | `world.era_index` |
| `centre` (id, tile, kind), `radius` | `territory.radius_of` |
| `buildings`: list of `{id, kind, class, label, operational, constructing, disrupted (cause, progress), stall (reason, detail, age), worker_ids, inputs, outputs, deposit}` | `world.buildings` filtered by `territory.settlement_of(world, b) is centre`, `wl_defs.spec_for_kind` |
| `kinds`: counts by kind and by class (producer, processor, mine, farm, military, warehouse, clinic, trade post, machine) | derived |
| `workers`: `{id, role, building, tx, ty, carrying, status}` | `world.workers` whose building is in the settlement |
| `carriers`: ids and roads | `world.carriers` |
| `units_own`, `units_foreign`: `{id, faction, definition, armed, distance}` within `units_radius` (40) | `world.units`, `diplomacy.hostile` |
| `neighbours`: other factions' centres within `neighbour_radius` (60) with `diplomacy.state_of`, `trade.partners_traded` | |
| `stocks`: warehouse stock by ware group; `food_ok` | `world.stocks[centre]` |
| `shortages`: wares requested and not delivered for more than N minutes | `world.shortages`, `building["stall"]` |
| `roads`: buildings with no path to the centre | `world.adjacency` |
| `region`: index, kind, cubes, production factor | `regions` |
| `losses_recent` | `world.__dict__["_losses"]` |
| `stories`: current slots and the last 5 closed | `world.narrative` |

Cost target: under 2 ms for a settlement with 80 buildings (measured in `test_narrative_perf.py`), rebuilt only on version change.

---

## 5. Existing-entity role binding (Phase C2)

### 5.1 The PersonLink

A story role is bound to one of: a **worker** (`world.workers[id]`), a **carrier**, a **unit**, a **building**, a **settlement**, a **faction**, or a **household person**. For the first three the director needs a Person record for dialogue, relationships, facts and history, so it creates or finds the link:

```text
world.dmb.people[pid]["link"] = {"kind": "worker"|"carrier"|"unit", "id": "worker:17", "building": "building:42"}
world.workers["worker:17"]["person_id"] = pid        # the only field added to a simulation row (written by the narrative package, read by snapshot)
```

Rules (these are the evolution of `story._ensure_npc`):

1. **Find before create.** `casting.person_for(world, entity)` returns the existing Person linked to the entity; if none, it creates one with `PeopleService.create_person(name, role=occupation, workplace_id=building, affiliation=faction, area_id="hybrid.world", position=entity tile, dialogue_profile="dialogue.<occupation>", profile_flags=["worker"])` and writes the link. One entity, one Person, forever (the id survives job changes: the link is updated, not replaced).
2. **Pose follows the entity.** The Person's position is the worker's live tile; `story.entity_rows` stops emitting a second actor for linked persons. The snapshot's worker row gains `person_id`, `label` (the person's name once known), `has_quest`, `quest_status`, and Godot's `wizard_labels.gd`/`story_ui.gd` treat a worker row with `person_id` as a talk target. One id, one actor.
3. **Talk range is to the entity's current tile**, so the wizard must stand near the miner wherever he is (walking to the warehouse with coal counts). Templates may mark a role `talk_at: "workplace"` so the conversation waits until the worker is at the building (`worker["status"] == "idle"` or inside).
4. **Job change.** `worker["role"]` changing (not observed today: a worker belongs to one building) or the worker aborting (`worker_aborted` event: the hut spawns a replacement) triggers the living-story rebind policy of the role: `rebind_same_building` (the replacement worker inherits the *Person*: the link moves, the name and history stay, because narratively the same person came back; this is the owner's "same person whether mining or carrying"), else `rebind_same_role_settlement`, else `suspend`.
5. **Death.** `worker_aborted` with a lethal reason (`killed_by_fire_magic`, a destroyed building), a unit's death (`military.kill_unit`): `PeopleService.record_death`; the quest follows its `dead_target_route` (`stakeholder_dead` → suspended, then the role rebinds if the policy allows, else fails with consequence after `suspend_deadline_ms`).
6. **Household roles** (Reeve, Elder, Healer, Child, Householder, Apprentice, Shrine Keeper, Storekeeper when no trade post) are the only roles the director may *create* a Person for, because the simulation has no residents. They are bound to the command centre (`workplace_id = centre`), capped at `household_cap` per settlement (default 4), reused across stories, and drawn as `npc` rows as today. A clinic's worker takes the Healer role when a clinic stands; the warehouse keeper takes Reeve/Storekeeper.
7. **Other-faction roles** (envoy, tollman, rival) bind to a real unit or carrier of that faction within range, else to that faction's nearest warehouse keeper person; never to a created soldier.
8. **Buildings and places** bind by id; `building_class` and `kind` filters come from `wl_defs` and the Mindustry registry (frozen roster, read-only).

No duplicate Person is ever created for display; the audit's two-actor problem disappears with rule 2.

### 5.2 Casting algorithm

For each role in template order: candidates = entities in the settlement context matching the role's filters; sort by `(role preference order, distance to the centre, id)`; skip entities already bound in this story; bind the first; if none and the role is `required`, casting fails (the template is ineligible); if none and optional, the role is left unbound and the graph's nodes that need it are skipped by `requires`. Casting is pure given the context, so the dry run at selection time and the real bind at offer time agree unless the world changed, in which case the slot is re-cast at offer time.

---

## 6. Story-template data format (v2)

```jsonc
{
  "id": "shortage.gallery_collapse", "schema_version": 2, "version": 3, "family": "shortage", "archetype": "industrial_accident",
  "source": "WizardRTSHybrid/wizard_rts/story.py (M3); legacy shortage schema",
  "select": {"tier": "standard", "relevance": [{"when": {"disrupted_cause": ["mine", "collapse"]}, "score": 1.0}], "exclusive_group": "mine", "era_in": [0,1,2,3]},
  "requires": [{"has_building_class": "mine"}, {"disrupted_cause": ["mine", "collapse"]}],
  "roles": {
    "miner":  {"bind": "worker", "of_role": "A_mine", "required": true, "talk_at": "anywhere", "living": "rebind_same_building"},
    "A_mine": {"bind": "building", "class": "mine", "disrupted": "collapse", "required": true, "living": "fail_if_destroyed"},
    "starved": {"bind": "building", "stall_reason": "inputs", "needs_ware_of": "A_mine", "required": false},
    "keeper": {"bind": "household", "role": "reeve", "required": false}
  },
  "cause": {"kind": "gallery_collapse", "affected": "A_mine", "stakeholder": "miner", "site": "settlement"},
  "graph": {
    "start": "talk_miner",
    "nodes": {
      "talk_miner":   {"type": "talk", "npc": "miner", "sets": ["heard"], "choices": [{"id": "ask_cause", "next": "cause"}, {"id": "give_up", "next": "abandon"}]},
      "cause":        {"type": "talk", "npc": "miner", "requires": ["heard"], "sets": ["cause"], "facts": ["collapsed_by", "minutes_since", "props_have", "props_need"], "choices": [{"id": "ask_gallery", "next": "gallery"}]},
      "gallery":      {"type": "talk", "npc": "miner", "sets": ["gallery"], "choices": [{"id": "accept_help", "next": "sigil", "accept": true}]},
      "sigil":        {"type": "talk", "npc": "miner", "effects": [{"kind": "give_item", "item": "@dungeon.needs"}], "next": "persuade"},
      "persuade":     {"type": "choice", "npc": "miner", "check": {"aspect": "empathy", "threshold": "easy", "evidence_from": "learned"}, "pass": {"sets": ["persuaded"]}, "next": "descend"},
      "descend":      {"type": "dungeon", "dungeon": "cave", "at": "A_mine", "guardian": "mastermind", "on_solved": "resolve_full", "on_exhausted": "resolve_thin"},
      "resolve_full": {"type": "conclude", "branch": "warden_solved", "effects": [{"kind": "reopen_gallery", "mode": "full", "target": "A_mine"}, {"kind": "history_fact", "person": "miner", "fact": "gallery_reopened:full"}]},
      "resolve_thin": {"type": "conclude", "branch": "warden_unsolved", "effects": [{"kind": "reopen_gallery", "mode": "thin", "target": "A_mine"}]},
      "abandon":      {"type": "conclude", "branch": "abandoned", "status": "failed_with_consequence", "effects": [{"kind": "relationship_change", "person": "miner", "delta": -20}]}
    }
  },
  "routes": {"world_resolved": {"when": {"not": {"disrupted_cause": ["A_mine", "collapse"]}}, "status": "resolved_by_world"},
             "invalid_target": {"when": {"destroyed": "A_mine"}, "status": "failed_with_consequence", "branch": "destroyed_mine"},
             "dead_target": {"status": "suspended", "deadline_ms": 600000}},
  "dialogue": {"pack": "shortage.gallery_collapse", "fallback_role": "worker"},
  "persistent_return": {"dedupe_by": ["template_id", "cause_id", "stakeholder_id"], "no_duplicate_reward": true},
  "tunables": {"thin_repair_left_ms": 120000, "duel_extra_casts_with_evidence": 2}
}
```

Node types: `talk` (lines from the pack for `npc`, choices), `choice` (a decision with optional Aspect check), `branch` (automatic by condition), `investigate` (wizard within range of a bound building or tile; returns facts), `travel` (wizard inside a bound settlement's territory), `deliver` (wizard gives a dungeon item or the story's own token; never wares), `dungeon`, `duel` (a Mastermind duel outside a dungeon, with a bound person as the rival), `wait` (game time), `conclude`. `requires`/`sets` are flags per quest; `accept: true` on a choice moves the quest to `active`. Every `conclude` names a branch and effects; one `conclude` per workbook outcome code (AAA..BBB).

Validation (`validate_narrative.py`, also a test): schema; every node reachable from `start`; every path ends in a `conclude`; every role referenced exists; every `facts` name exists in `facts.py` for the template's family; every effect kind is registered and world-altering kinds name a bound target; every `talk` node has at least a fallback line in the pack; no two conclusions apply the same world effect twice.

### 6.1 Converting the workbook

`scripts/build_story_templates.py --cast E36B` reads the Cast Matrix and Dialogue Matrix (reusing `tools/dialogue_generation/workbook_reader.py`), emits `data/narrative/templates/wb.<structure>.json` once per situation structure (graph with three `choice` nodes A/B and eight conclusions) and `data/narrative/casts/<cast id>.json` (role list by workbook role, personalities as voice tags, the twelve rows as pack lines keyed by node and character letter, gossip as ambient lines). A role map `data/narrative/role_map.json` translates workbook roles to hybrid filters (Woodcutter → `{"bind": "worker", "of_building_class": "producer"}`, Sawmiller → processor with `plank` output, Miner → mine, Smelter → `smelter`, Reeve → household reeve, Carter → carrier, Watchkeeper → unit armed, Wastes roles → quarry/charcoal/scrap by era). Outcome text becomes the conclusion's narration; outcome effects are narrative-only by default (relationship, history, mood as `unrest_delta` within ±0.05) unless the structure's combat branch maps to a `duel` node.

---

## 7. State machine, persistence and effects

### 7.1 Quest state

`QuestService` statuses stay authoritative: `offered → active → (suspended ↔ active) → completed | resolved_by_world | failed_with_consequence`. The narrative package adds per-quest graph state (`node`, `flags`, `learned`, `evidence`, `bindings`, `effects_pending`) in `world.narrative["quests"][qid]`, mirroring what `story.state(world)["quests"]` holds today. Transitions are made only through `QuestService` calls (plus one `abandon` wrapper that does what `story.choose("give_up")` does).

### 7.2 Persistence

All narrative state is in `world.narrative` and the legacy slots inside `world.dmb`; a pickle of the world carries everything (proved for the current story by `test_story_slice.py` and `test_quest_env.py`). New: `server.py` ops `save` (writes `{"format": 2, "hash", "world", "narrative_version"}` next to the `HybridEnv` format) and `load`; the Godot pause menu calls them. Cycle reset: `server.py` copies `world.narrative["wizard"]` into the fresh world before swapping.

### 7.3 Receipts

Every effect id is `f"{qid}:{node}:{i}:{kind}"` and is applied once (`world.dmb.command_receipts`), exactly as `story.apply_effects` does; `QuestService.choose_branch` receipts cover branch choices. A load after an effect never re-applies it; a rebound role never re-offers a completed template for the same cause (CauseTracker occurrence key).

### 7.4 Effects: narrative-only versus world-altering

| Kind | Class | Implementation (existing API) |
| --- | --- | --- |
| `history_fact`, `known_fact`, `relationship_change`, `aspect_change`, `worldview_delta`, `give_item` (story/dungeon items only), `set_flag`, `journal_note`, `settlement_mood` (a label on the chronicle) | narrative-only | `PeopleService`, `AspectService`, `world.narrative` |
| `reopen_gallery` | world | `disruption.clear` / repair progress (exists) |
| `clear_disruption` | world | `disruption.clear(world, b, "wizard")` for any cause (same mechanism as above) |
| `cure_region` | world | `regions.cure(world, building, cubes)`; the wizard must stand in the region (the `treat` rule) |
| `caravan` | world | `trade.send_caravan(world, faction, wh, partner_wh, give, want)` only if `trade.can_supply`; wares move, none appear |
| `diplomacy_offer` | world | `diplomacy.propose(world, a, b, state, duration)`; the AI's `diplomacy_quantum` answers; the story reads the result |
| `unrest_delta` | world (bounded) | `rec["unrest"] = clamp(rec["unrest"] + d)`, `|d| <= 0.1`, at most once per story; `society.py` documents unrest as a quest input |
| `destroy_target` | world | only through `magic.fire` range rules (the wizard does it, the story only asks) |

Not allowed, by validator: creating wares, buildings, units or roads; commanding units; changing stocks except by caravan; changing VP, eras, cards, the roster.

---

## 8. Dialogue and dungeon integration (Phase D)

### 8.1 Packs

`data/narrative/dialogue/<pack>.json`:

```jsonc
{"pack": "shortage.gallery_collapse", "schema_version": 1, "approved": true, "source": "story.py lines, 12 Oct 2026",
 "lines": [
   {"id": "gc.cause.1", "node": "cause", "role": "miner", "variant": "default", "voice": ["proud"], "era": "all",
    "text": "{why}: the gallery of {mine_label} caved in {minutes_since} minutes ago. The seam is still there; we cannot reach it.",
    "requires": ["heard"], "condition": null},
   {"id": "gc.choice.ask_cause", "node": "talk_miner", "role": "wizard", "choice": "ask_cause", "worldview": null, "text": "What happened to the mine?"},
   {"id": "gc.choice.ask_cause.M", "node": "talk_miner", "role": "wizard", "choice": "ask_cause", "worldview": "monarchist", "text": "...", "scores": {"M": 3, "A": -1}}
 ]}
```

Selection (`dialogue.pick`): exact `(pack, node, role, variant)`, then `(pack, node, role, "default")`, then the role baseline from `settlement_normal.json`, then the neutral fallback; among equals a stable pick seeded by `(qid, node, role)` as `DialogueResolver._stable_pick` does. Wizard choices show the plain text; when a worldview set exists for the choice and the owner has enabled worldviews, the seven variants are offered instead and the chosen one's `scores` go to `wizard.worldview`. `{facts}` placeholders are filled from `facts.py`; an unknown placeholder is a validation error, never a runtime blank.

Missing dialogue is never a dead end: the graph still advances on the fallback line plus a generated "report" sentence from the facts (`"The mine is shut: gallery collapsed, 2 of 4 props on site."`), marked `generated: true` in the reply so the UI can style it.

### 8.2 Offline pipeline

```text
workbook / authored JSON / Dialogue Factory exports
   -> scripts/build_story_templates.py (deterministic; records source sha256)
   -> data/narrative/{templates,casts,dialogue}/*.json  (committed, approved: true only after human review)
   -> scripts/validate_narrative.py  (schema, reachability, placeholders, coverage)  == tests/test_narrative_content.py
```

The Dialogue Factory keeps its own SQLite and approval flow; its `exporter.py` gains a `--format narrative-pack` target. No runtime path imports `tools/`.

### 8.3 Dungeons and duels

`story._ensure_dungeon` is kept and given a `theme` by era (Historic `cave`, Modern `industrial`, Dystopian `bunker`/`machine`/`alien` from `godot_project/content/source/dungeons` dressings when the generator supports them; `cave` until then) and an `at` building from the role binding. The dependency rule from `SETTLEMENTS_AND_DUNGEONS.md` is kept (a dungeon needs only items from earlier stops). Duels outside dungeons bind a `rival` role (a unit or a household person); the pause token and the solver-tested public view are unchanged.

---

## 9. World-change handling (Phase C4)

Checked by the director every minute for every settlement with an accepted or offered story, and immediately on `talk` (so the dialogue never lies):

| Event | Detection | Behaviour |
| --- | --- | --- |
| Bound worker gone (aborted, replaced) | `worker_id` missing or `person_id` mismatch | role `living` policy: `rebind_same_building` (link moves to the replacement, Person kept) → `rebind_same_role_settlement` → `suspend` (deadline, then `failed_with_consequence` branch `lost_contact`) |
| Bound person dead | `PeopleService.record_death` by the link watcher | `stakeholder_dead` → suspended; rebind by policy or fail |
| Bound building destroyed | `building not in world.buildings` or `destroyed` | `invalid_target_route` (fail with consequence) unless the template allows `rebind_same_kind` |
| Cause gone (repaired, cured, road rebuilt) | the template's `world_resolved.when` | `resolved_by_world`; lines acknowledge it; no reward |
| Settlement destroyed | `rec["state"] != "standing"` | all slots closed; accepted quests fail by `site_destroyed` |
| Settlement founded | new id | slots after `min_age_ms` |
| Ownership change (split) | `rec["faction"]` changed | re-cast faction-filtered roles; keep entity-bound roles; a `faction_changed` fact for dialogue |
| Faction collapse | `history.state` `collapsed` | its settlements are destroyed by `history.collapse`; handled as above |
| Era change | `era_advanced` | nothing breaks (building ids persist, D09); templates with `era_in` not containing the new era are not *offered* again but an active one continues |
| Cycle reset | new world | all settlement state dropped (D11); `wizard` state copied by `server.py` |
| Save/load mid-quest | pickle | identical state; dungeon runs resume at the mouth as today; duels in progress are abandoned on load (pause token released) |
| Duplicate instances | CauseTracker occurrence key + binder dedupe + slot key | never two quests for one cause; never two slots with one template in one settlement |
| Rewards twice | receipts | never |

Suspension is bounded (`suspend_deadline_ms`, default 10 game minutes) so a journal never fills with permanently suspended quests.

---

## 10. Simulated-time triggers and the narrative director lifecycle

* Construction: `HybridWorld.__init__` sets `self.narrative_enabled` from `HYBRID_NARRATIVE` (default "1"); the server sets it from the profile too (campaign on; `HybridEnv` and the episode runner off, see the contract). `world.narrative` is created lazily on first use, so a world that never enables narrative never allocates it.
* Per quantum: one boolean test. Per minute (enabled): the director's budgeted pass. On wizard ops: immediate consistency checks for the settlement involved.
* Timers are game-time only (`game_ms`), read from `world.dmb.clock`.
* Events: the director reads simulation events through `world.events.total` and a bounded scan of new entries (kinds `building_destroyed`, `settlement_destroyed`, `worker_aborted`, `worker_spawned`, `disruption`, `disruption_cleared`, `outbreak`, `era_advanced`, `split`, `collapse`, `caravan`, `diplomacy`) to mark settlement contexts dirty; it never appends to `world.events` (narrative events go to `world.narrative["log"]` and to `snapshot()["narrative"]["events"]` for Godot). The existing `story.py` appends to `world.events` today and is moved to the narrative log in the shared-change step.

---

## 11. Example stories in contrasting settlements

Illustrative, composed from building kinds, disruptions, outbreaks and diplomatic states that the measured `campaign` worlds contain (seed 507 reaches 41 settlements and 402 buildings by minute 60; AIs rarely reach the Modern era unaided, so the third example is a later-game or fixture settlement). Settlement names follow `settlements.register`; people keep generated role names until canon is decided (D19). The showcase test in W3.5 forces these conditions in a fixture rather than waiting for them.

### 11.1 Red home 1, Historic, a mining town (coal mine, iron mine, smelter, smithy, lumberjacks, quarry; Blue at war to the east)

| Slot | Template | Cast (real entities) | Entry and arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `shortage.gallery_collapse` | miner = the coal mine's worker; mine = `building:…`; starved = the smelter (stall `inputs: coal`) | The miner, carrying nothing, says the roof came down 12 minutes ago; props 1 of 4. Evidence, Aspect check, the old gallery (four puzzles), the warden's code. | `reopen_gallery` full or thin: coal flows, the smelter restarts (measured in `test_story_slice`) |
| 2 | `shortage.starved_workshop` (*The withheld resource*) | smith = the smithy's worker; supplier = the smelter's worker; keeper = warehouse household person | The smith blames the smelter for hoarding iron; the smelter blames the mine; the keeper knows the warehouse holds 6 iron reserved for construction. Three choices: side with the smith, side with the smelter, or carry the keeper's ledger to both. | narrative: relationships and a history fact; optional `caravan` from an allied warehouse if `can_supply`; `unrest_delta -0.05` on the fair ending |
| 3 | `military.raid_warning` | watchkeeper = a Red spearman unit standing in the territory (as a Person); carter = a carrier on the east road; envoy = Blue's nearest warehouse keeper | The watchkeeper has seen Blue riders within 30 tiles; the carter refuses the east road. Investigate (walk to the frontier, `observe` the units), then choose: warn the keeper (unrest down, nothing else), or carry a truce offer to Blue (`diplomacy_offer`; Blue's AI accepts or declines by its policy; the story reads the answer). | world: a real truce if Blue accepts; otherwise narrative only |

### 11.2 Green outpost 9, Historic, agricultural (farm, well, bakery, sheep farm, hunter; two outbreak cubes in its region; unrest 0.45)

| Slot | Template | Cast | Arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `catastrophe.outbreak_treatment` | healer = the clinic's worker (Green drafted a clinic) else a household healer; affected = the bakery's worker (production factor 0.6) | The healer names the two marks in the region and the slowed bakery; stand in the region and treat. | `treat`: cubes removed, production factor back to 1.0 (existing) |
| 2 | `mystery.tainted_well` | healer (same Person, reused), digger = the well's worker, mother = a household person | The well water "has gone sweet"; go down (a two-room cave dungeon at the well) or seal it (narrative), or treat the water (`cure_region` 1 cube if the wizard has treated before). | world: one cube cured on the magic ending; narrative on the others |
| 3 | `conflict.labour_strike` (*The absent worker*) | worker = the sheep farm's worker (program failing `no_space`), reeve = the warehouse keeper, healer | The shepherd will not go back out while the marks stand; the reeve wants him back; the healer says the real problem is the blighted field (a `blight` disruption on the farm). Choices resolve who yields. | `clear_disruption` on the farm if the wizard takes that branch; `unrest_delta` |

### 11.3 Yellow outpost 12, Modern, a militarised border town (war lodge, barracks, trade post with caravans to Purple, drills and belts, a toxic-spill disruption; Orange hostile 25 tiles away)

| Slot | Template | Cast | Arc | Consequence |
| --- | --- | --- | --- | --- |
| 1 | `conflict.road_toll` | carter = the caravan's carrier, tollman = an Orange unit standing on the road (Person of another faction), smith = the drill's operator | The carter says a toll is being taken on the Purple road; the "tollman" is an Orange soldier nobody ordered there. Fight (a Mastermind duel with the soldier as rival), report (narrative; `diplomacy_offer` truce with Orange), or make him road-warden (narrative, relationship). | world only through the truce offer |
| 2 | `shortage.workplace_closed` (toxic spill) | operator = the crafter's worker, keeper, healer | The crafter is shut by a toxic spill (`disruption` cause `toxic_spill`, repair planks and water); the keeper is short of water. Investigate the belt, choose to clear it (`clear_disruption`) at the cost of a relationship with the operator who blames the keeper, or help the faction's own repair by carrying nothing but words (narrative). | `clear_disruption` on one branch |
| 3 | `military.deserter_hunt` | soldier = a Yellow unit killed near the town in the last 10 minutes (its Person stays as a tombstone fact), kin = a worker of the same faction, reeve | Who let the patrol die? The reeve blames the deserter; the kin says the order was wrong. Reluctant-witness structure; no world effect; the ending writes history facts and a settlement mood. | narrative |

Three settlements, nine distinct stories, no two of one family in a settlement, every role a real entity except household persons.

---

## 12. Performance approach

* Lazy: contexts are built on demand and cached by version; slots are built once and refilled on close; nothing scans all buildings every second.
* Event-driven dirtiness: a bounded scan of new `world.events` per minute (the log is already bounded) marks settlements dirty; a settlement that is not dirty costs one dict lookup per minute.
* Budgeted: at most `budget_per_minute` settlements per director pass; the wizard's settlement always; the rest round-robin.
* Targets (asserted by `test_narrative_perf.py`, printed numbers recorded in the ledger): director pass under 2 ms per processed settlement on the 20-minute campaign fixture; under 20 ms per minute at 30 settlements; zero allocations when disabled; `settlement_context` under 2 ms for 80 buildings; casting under 1 ms per role.
* Scaling test: a God-fixture world with 6, 12, 24 and 48 settlements (founded through `territory.deploy` in the developer profile); the report prints ms per minute against the count and asserts linearity within a factor of 1.5.

---

## 13. Compatibility with the frozen simulation and neuroevolution

Summarised here; binding text in `WIZARD_STORY_INTEGRATION_CONTRACT.md`.

* No new buildings, units, wares, items, liquids or cards; templates reference existing kinds by id and the validator checks them against `freeze.manifest()`; `test_content_freeze.py` must stay green on this branch.
* The narrative package is imported by `world.py` only through one guarded call; when `narrative_enabled` is false the only cost is one attribute read per quantum; no `world.rng` use; no `world.events` writes; no change to observations, legal actions, AI timing, combat, economy, VP, catastrophes.
* The only shared-file change is the gate in `world.py` (three lines) plus moving the existing `story.story_quantum` call behind it, and the `person_id` field on worker rows written only when narrative is enabled; the hash baselines change only for worlds where the legacy story would have opened a quest and only when the neuroevolution agent re-records them at its own checkpoint.
* Narrative state never enters `HybridEnv.observe` or `legal_actions` (test: observation dicts identical with narrative on and off).

---

## 14. Open design alternatives and owner decisions

| Id | Question | Recommendation | Alternative |
| --- | --- | --- | --- |
| Q1 | Should the legacy `story.story_quantum` be gated off in training (changes recorded hashes once) or left running (costs CPU, keeps hashes)? | Gate it, at the neuroevolution agent's T1.1 or next re-record. | Leave it on until M7's hash-equal pass finishes. |
| Q2 | Names: generate from role and settlement (today) or adopt the 88 named profiles now? | Generate (D19). | Adopt names for household roles only. |
| Q3 | Should the director create household persons at all (Reeve, Healer, Child), or should every role be a simulation entity? | Create, capped at 4 per settlement, bound to the centre; otherwise half the workbook structures cannot cast. | No creation: fewer templates, no residents. |
| Q4 | Keep two moral systems (seven Aspects for checks, seven worldviews for the wizard's replies) or merge? | Keep both for the pilot; decide after the three-cast review. | Map worldview scores onto Aspect changes. |
| Q5 | Unlock threshold default. | 20 game minutes. | 10 or 30. |
| Q6 | Allowed world effects beyond the existing two: `clear_disruption`, `cure_region`, `caravan`, `diplomacy_offer`, `unrest_delta` (bounded). | Approve all five; each goes through an existing legal API. | Narrative-only until the three-settlement showcase is reviewed. |
| Q7 | Where does Wizard Mode save? | Server ops writing the `HybridEnv` pickle format to `%DMB_RUNS%`/`~/dmb_runs/saves/`. | A separate JSON save (more work, no benefit while the world is pickled). |
| Q8 | Should story people walk (workers already do) and should household persons wander? | Workers walk as they do; household persons stand at the centre until a later presentation pass. | Give household persons a simple patrol (presentation only). |
