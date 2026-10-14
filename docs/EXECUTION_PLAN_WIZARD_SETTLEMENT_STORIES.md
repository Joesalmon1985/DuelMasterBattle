# Execution plan: Wizard Mode tutorial and three dynamic stories per settlement

Task-by-task guide for the agent that implements `PLAN_WIZARD_SETTLEMENT_STORIES.md` (call it "the plan"). **Nothing below starts until the owner approves the plan.** Progress is ticked in `docs/ledger/WIZARD_STORIES_PROGRESS.md` (separate from `NEUROEVO_PROGRESS.md`). When this document and the plan disagree, this document wins; when the code disagrees with either, trust the code and the tests, then fix the document.

Repository root on the Ubuntu laptop is `/home/joe/dmb_runs/wt_wizard_stories` (a git worktree of `/home/joe/Projects/DuelMasterBattle`); on Windows use `py -3` for `python3`. The simulation package is `WizardRTSHybrid/wizard_rts/`; the new package is `WizardRTSHybrid/wizard_rts/narrative/`.

---

## 0. Working rules (read every session)

1. **Branch.** Work on `feature/wizard-settlement-stories`. Never merge into `main` or into `feature/neuroevolution-plan`; the owner does that. Push after every committed task. Sync from the neuroevolution branch only at the sync points in the contract (section 6), never mid-milestone.
2. **Ledger.** Start by reading `docs/ledger/WIZARD_STORIES_PROGRESS.md` and `git log --oneline -10`. Tick a task only when its "Done when" holds and its tests pass; write the evidence (command and result, or an evidence path under `WizardRTSHybrid/docs/evidence/narrative/`) on the same line. End every session by updating the ledger, committing and pushing, even half way through a task (write "IN PROGRESS: what is left").
3. **Content is frozen (D33).** No new buildings, units, wares, items, liquids or cards. Never run `scripts/import_*.py`. Templates, packs, casts and narrative config are data, not content, and must not change `freeze.check()`.
4. **Do not touch the neuroevolution programme.** `WizardRTSHybrid/neuro/`, `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`, `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`, `docs/ledger/NEUROEVO_PROGRESS.md`, `sim_api.py`, `visibility.py`, `ai*.py`, the hash baselines and `test_neuro_*` are theirs. Shared files are listed in the contract; changing one is a task of its own with the contract's procedure.
5. **Determinism.** Never iterate a `set` of strings to decide; sort. Never read the wall clock. Narrative randomness comes from `random.Random(zlib.crc32(...))` instances seeded from `(world.seed, settlement id, epoch, template id)`; `world.rng` is never touched. `tests/test_determinism.py` must stay green.
6. **Nothing narrative writes `world.events`.** Narrative events go to `world.narrative["log"]`. (The existing `story.py` appends are moved in task W1.4.)
7. **One world.** Every quest, person, dungeon and duel is bound to `HybridWorld`; no fixture implements a second rule.
8. **Tests after every task.** The quick set for narrative work is `python3 -m pytest WizardRTSHybrid/tests/test_story_slice.py WizardRTSHybrid/tests/test_quest_env.py WizardRTSHybrid/tests/test_narrative_*.py WizardRTSHybrid/tests/test_content_freeze.py WizardRTSHybrid/tests/test_determinism.py -q` (about 4 minutes). The full suite at the end of every milestone.
9. **Headed proof.** A wizard-facing change counts as done only when a headed Godot script shows it (`WizardRTSHybrid/scripts/run_headed_suite.sh story stories`; screenshots under `WizardRTSHybrid/docs/evidence/narrative/<milestone>/`).
10. **Commits.** One task per commit when practical, message `stories(W<id>): <what>` plus the attribution line the harness requires. Never `git add -A`; never commit `external/`, `runtime/`, `~/dmb_runs`, saves, or `docs/release_notes.md`.
11. **Stop points.** Stop and report to the owner at the end of W1, W3, W5, W6 and W9 (the ledger says OWNER CHECKPOINT).
12. **Honesty.** Report measured numbers, test counts and anything that deviates from the plan. A story that cannot be cast in a real world is a finding, not a failure to hide.

---

## Milestone W0: baseline, package skeleton and the isolation harness (no behaviour change)

### W0.1 Baseline on this branch

**Objective.** Record what passes before any change. **Reuse.** The existing suites. **Commands.** `python3 -m pytest WizardRTSHybrid/tests/test_story_slice.py WizardRTSHybrid/tests/test_quest_env.py WizardRTSHybrid/tests/test_dungeon_env.py WizardRTSHybrid/tests/test_duel_env.py WizardRTSHybrid/tests/test_outbreak_env.py WizardRTSHybrid/tests/test_puzzle_parity.py WizardRTSHybrid/tests/test_ward_parity.py WizardRTSHybrid/tests/test_fire_magic.py WizardRTSHybrid/tests/test_content_freeze.py WizardRTSHybrid/tests/test_hash_baseline.py WizardRTSHybrid/tests/test_determinism.py -q`; `python3 -m pytest tests/sim/test_t083_quest_runtime.py tests/sim/test_t084_dialogue.py tests/sim/test_t080_aspects.py tests/sim/test_t028_people.py -q`; `PYTHONPATH=tools python3 -m pytest tools/dialogue_generation/tests -q`. **Done when** the counts are in the ledger with any pre-existing failures listed. **Risk.** None.

### W0.2 Package skeleton and gate (shared change, read the contract first)

**Objective.** Create `wizard_rts/narrative/` with `__init__.py` (`enabled(world)`, `state(world)`), `config.py` and `data/narrative/config.json`; add the gate in `world.py`: `self.narrative_enabled = os.environ.get("HYBRID_NARRATIVE", "1") != "0"` in `__init__` and, in `advance`, `if self.narrative_enabled: story.story_quantum(self)` followed by `narrative.director_quantum(self)` (a no-op function in W0). **Files.** New package; `world.py` (+3 lines, -1); `server.py` sets `world.narrative_enabled = True` for every profile (wizard play); `story.snapshot` returns the empty six-key shape when `world.story` was never created (so the off path hashes like the on path until a quest opens; see the audit section 2.4). **Tests.** `tests/test_narrative_isolation.py`: (a) with `HYBRID_NARRATIVE` unset, `state_hash()` after 3 minutes on seeds 507 and 11 equals the value with the env var set to "1"; (b) with "0", `story.state(world)` is never created and `world.narrative` does not exist, and `state_hash()` after 3 minutes equals the "1" value (no quest opens in 3 minutes); (c) `tests/test_hash_baseline.py` still passes (env var unset); (d) `HybridEnv(seed).reset()` followed by 3 minutes gives identical `observe("Red")` dicts with the env var "1" and "0" (the legacy story opens nothing in 3 minutes, so this is a smoke check; the real check is W0.3). **Done when** all pass and `hash_gate.py check --baseline docs/perf/hash_baseline_v4.json --limit-minutes 3` is OK with the env var unset. **Risk: shared file (`world.py`), low; see contract section 4.**

### W0.3 Faction-equivalence and cost evidence

**Objective.** Prove that switching the story layer off changes nothing for factions and measure the cost of leaving it on. **Reuse.** The audit's scripts (kept under `WizardRTSHybrid/scripts/narrative_evidence.py`). **Commands.** `python3 WizardRTSHybrid/scripts/narrative_evidence.py equiv --seed 507 --minutes 40` prints the first minute at which the faction-only hash or `world.rng` state differs between `HYBRID_NARRATIVE=1` and `0` (expected: never); `... cost --seed 507 --minutes 60` prints the share of wall time in `story_quantum`. **Done when** both numbers are in the ledger and in `WizardRTSHybrid/docs/evidence/narrative/w0/`. **Risk.** None.

### W0.4 Performance harness

**Objective.** `wizard_rts/narrative/perf.py` counters and `tests/test_narrative_perf.py` with a cached 20-minute campaign fixture (pickled once per session as `envs/_world_cache` does). Asserts in W0: the director no-op costs under 5 microseconds per quantum (one attribute read), measured over 600 quanta. **Done when** the test passes and prints its numbers.

---

## Milestone W1: the person link (smallest vertical slice: a real worker becomes the miner)

### W1.1 `casting.person_for` and the link fields

**Objective.** `narrative/casting.py`: `person_for(world, entity_kind, entity_id) -> person_id` finds the Person linked to a worker, carrier or unit, else creates one through `PeopleService.create_person` with the occupation as role, the building as workplace, the faction as affiliation, and writes `person["link"]` and `row["person_id"]`. `unlink` and `relink(world, person_id, new_entity)`. **Reuse.** `PeopleService`, `workers._roles_of`, `wl_defs.spec_for_kind` for a readable occupation. **Tests.** `test_narrative_casting.py`: one worker → one person on repeated calls; relink keeps the id, name and history; a created person for a unit has `link.kind == "unit"`; no `world.events` entry is written; `freeze.check() == []`. **Done when** green. **Risk.** Low (new file).

### W1.2 The existing miner quest binds the mine's worker

**Objective.** Replace `story._ensure_npc` with `casting.person_for` on the mine's `worker_ids` (first by sorted role), falling back to the old creation only when the mine has no worker (and log the fallback). The Person's `position` follows the worker's tile; `story.entity_rows` emits no `npc` row for a linked person; `world.snapshot` worker rows carry `person_id`, `has_quest`, `quest_status`, `label`. `talk` range uses the worker's live tile. **Files.** `story.py`, `world.py` snapshot (worker row fields; shared file, additive, written only when narrative is enabled: see contract). **Tests.** `test_story_slice.py` stays green with `len(w.dmb.people) == 1` and the person's `link.id` in `w.workers`; a new test asserts the snapshot has exactly one actor for the miner (no `npc` row with the mine as building) and that `talk` succeeds when the wizard stands beside the worker away from the mine. The outbreak healer keeps creating a household person for now (W3). **Done when** green plus the headed `story` script passes with the miner drawn once (`run_headed_suite.sh story`; screenshot). **Risk.** Medium: `story_ui.gd` must treat a worker row with `person_id` as a talk target (`person_at`, `nearest_interactive`): a small Godot change (`client/hybrid/story_ui.gd`, `wizard_labels.gd`).

### W1.3 Rebind on replacement

**Objective.** When a linked worker aborts and its hut spawns a replacement, the link moves to the replacement (`rebind_same_building`), the Person keeps id, name and facts; a lethal abort records death and suspends the quest. **Reuse.** `worker_aborted` / `worker_spawned` events (read-only), `PeopleService.record_death`, `QuestService.suspend`. **Tests.** Burn the miner with `magic.fire` in the story fixture: the quest is suspended; after the replacement spawns, the link moves and `talk` works again; `QuestService` shows `active` after the wizard talks. **Done when** green. **Risk.** Low.

### W1.4 Narrative log instead of `world.events`

**Objective.** `narrative/events.py`; every `story._log` and `world.events.append` in `story.py` goes to the narrative log and to `snapshot()["narrative"]["events"]` (Godot reads the same kinds). **Tests.** `world.events.total` identical with narrative on and off over the story fixture; `run_hybrid_story.gd` still passes (it reads the snapshot, not events). **Done when** green. **Risk.** Low, but check `feed.KINDS` for `story_*` kinds and keep the spectator feed fed from the narrative log.

### W1.5 Wrap-up. **OWNER CHECKPOINT.**

Full narrative quick set; headed `story`; ledger with the two-actor screenshot before and after. Report the person-link approach for approval before it is generalised.

---

## Milestone W2: story-graph runtime, template v2, migration of the two existing families

### W2.1 Template v2 schema and loader

**Objective.** `data/narrative/schema/template_v2.json` (base: `content/schemas/quests.json` plus `roles`, `graph`, `dialogue`, `select`, `living`), `narrative/templates.py` (`load_all()`, `get(id)`, `validate(template) -> list[str]`), `scripts/validate_narrative.py`. **Tests.** `test_narrative_content.py`: every file under `data/narrative/templates` validates; a deliberately broken fixture reports each error named in the plan section 6 (unreachable node, path without conclude, unknown role, unknown fact, unknown effect, missing fallback line). **Done when** green. **Risk.** None.

### W2.2 Graph runtime

**Objective.** `narrative/graph.py`: `GraphRun(template, quest_state)` with `current()`, `available_choices(world)`, `choose(world, choice_id)`, `arrive(world, node)` for investigate/travel, `conclude(world, node)`; `requires`/`sets`; objective text; Aspect checks through `AspectService` with the same fingerprint rule as `story.choose("persuade")`. Semantics copied from `village_quest_runner.gd` (document each function's GDScript origin in the docstring). **Tests.** `test_narrative_graph.py`: the E36B `broken_promise` graph converted by hand to v2 runs every path listed by a path enumerator to a conclusion; flags gate nodes; a stale choice is rejected; state pickles. **Done when** green. **Risk.** None.

### W2.3 Facts and dialogue packs

**Objective.** `narrative/facts.py` (`facts(world, template, quest) -> dict`, generalising `story.facts` and `_outbreak_facts` per family), `narrative/dialogue.py` (`pick`, placeholder fill, fallback, generated report line), `data/narrative/dialogue/shortage.gallery_collapse.json` and `catastrophe.outbreak_treatment.json` holding today's hard-coded lines. **Tests.** Lines from the pack equal the current `story._lines` output for the fixture at each stage (byte-equal, so `test_story_slice::test_dialogue_facts_come_from_the_live_world` stays green); an unknown placeholder fails validation; a missing node line falls back to the role baseline plus the generated report line and the graph still advances. **Done when** green. **Risk.** None.

### W2.4 Migrate `gallery_collapse` and `outbreak_treatment` to templates

**Objective.** `data/narrative/templates/shortage.gallery_collapse.json` and `catastrophe.outbreak_treatment.json` in v2 (the plan's section 6 example); `story.py`'s family branches call `graph.py`; `story.dispatch` unchanged for the client. **Tests.** The whole existing story and env suites green unchanged (`test_story_slice`, `test_quest_env`, `test_outbreak_env`, `test_dungeon_env`, `test_duel_env`), plus `test_narrative_isolation` and the headed `story` and `outbreak` scripts. **Done when** green and `data/story/*.json` are moved to `data/story/archive/` with a note (keep `mine_exhausted.json` there). **Risk.** Medium (refactor of a working module): do it behind the template registry in small commits; `story.py` keeps every public name.

---

## Milestone W3: settlement context, director and the first four archetypes

### W3.1 Settlement context

**Objective.** `narrative/context.py` as in plan section 4, with the version stamp and cache. **Tests.** `test_narrative_context.py`: on the 20-minute fixture every standing settlement has a context; buildings are exactly those `territory.settlement_of` assigns; a disruption changes the version and the field; the cache is hit when nothing changed; cost under 2 ms for the largest settlement (printed). **Done when** green.

### W3.2 Casting for every role kind

**Objective.** Extend `casting.py`: workers, carriers, units (as Persons), buildings, settlements, factions, household persons (cap, reuse, bound to the centre), other-faction people; dry-run mode. **Tests.** A fixture settlement casts each role kind; the cap holds; the same context casts identically twice; an impossible required role makes the template ineligible; `len(world.dmb.people)` grows only by household persons. **Done when** green.

### W3.3 Director: slots, eligibility, scoring, selection, refill

**Objective.** `narrative/director.py` as in plan section 3; `narrative_quantum` wired in W0.2 now does the budgeted pass; `scripts/narrative_report.py --seed 507 --minutes 40` prints the three stories per settlement. **Templates in this task** (migrated or new, with packs of placeholder lines): `shortage.gallery_collapse`, `catastrophe.outbreak_treatment`, `shortage.starved_workshop`, `military.raid_warning`, plus `personal.kind_word` (tier simple). **Tests.** `test_narrative_director.py`: (a) every standing settlement of the 20-minute fixture holds three slots with distinct families; (b) two seeds give different slot lists for at least one settlement and the same seed gives identical lists across two processes (`PYTHONHASHSEED` 0 and 1); (c) a settlement founded by `territory.deploy` in the developer profile gets slots after `min_age_ms`; (d) a God-fixture world with 24 settlements is processed within the budget and every settlement has slots within `24 / budget` minutes; (e) no slot's template appears in both of the two nearest settlements when an alternative was eligible; (f) a closed slot refills with another family after the cooldown; (g) `freeze.check() == []`; (h) the whole pass writes nothing to `world.events`. **Done when** green. **Risk.** None to shared files.

### W3.4 Offer, accept, journal

**Objective.** Talking to a slot's entry role offers the story (`CauseTracker.observe_changes` with the template's cause kind and affected entity, `QuestBinder.bind` with the cast stakeholder); `accept` moves to active; the journal op returns accepted quests (cap `max_accepted`) and the rumours of the settlement the wizard stands in; `observe` op returns facts for a building or person within 3 tiles. **Tests.** `test_narrative_ops.py`: offer dedupes on the cause key; a fifth accept is refused with `journal_full`; journal shape; observe range. **Done when** green and `story_agent.py` gains `accept_story(world, sid, slot)`.

### W3.5 Wrap-up. **OWNER CHECKPOINT.**

`narrative_report.py` output for three seeds in the evidence folder; the three-settlement showcase from plan section 11 reproduced as `tests/test_narrative_showcase.py` (a scenario fixture that forces the conditions: a collapsed mine, two cubes, a hostile neighbour, a toxic spill) asserting the nine stories cast to real entities. Report cast quality (fraction of roles bound to real entities) per archetype.

---

## Milestone W4: living stories, save and load

### W4.1 Living policies

**Objective.** Director checks every minute and on `talk`: rebind (same building, same role), suspend with deadline, resolve by world, fail with consequence, settlement destroyed, ownership change, era change; one consequence per outcome; receipts. **Reuse.** `QuestService.evaluate` signals, `CauseTracker.resolve`, `history.split` behaviour. **Tests.** `test_narrative_living.py`, one test per row of plan section 9 on the story fixture and the 20-minute fixture: worker replaced; worker killed; building destroyed by God `damage`; cause repaired by the faction (`disruption` repair completes); settlement destroyed; a forced split (reuse the fixture pattern in `test_civilisation_rules.py`) moves a settlement to a successor and the faction-filtered role re-casts; `vp.advance_era`; deadline expiry; a quest never duplicates; effects never apply twice after reload. **Done when** green.

### W4.2 Wizard Mode save and load

**Objective.** `server.py` ops `save {"slot": "auto"|name}` and `load`, writing the `HybridEnv` pickle format (format 2 with hash) under `$DMB_RUNS/saves/<profile>/<slot>.pkl`; Godot pause menu buttons in `hybrid_world.gd`; autosave on settlement travel (optional config). Cycle reset copies `world.narrative["wizard"]`. **Tests.** A quest mid-dungeon saved and loaded in the server process resumes with identical `state_hash()`; a duel in progress is abandoned on load and the pause token released; the wizard's lessons survive `history.cycle_reset` through the server path. Headed: `run_hybrid_stories.gd` saves, reloads, and the journal is unchanged (screenshot). **Done when** green. **Risk.** `server.py` is a wizard-path file (contract: wizard-modifiable).

### W4.3 Playthrough harness

**Objective.** `scripts/play_stories.py --seed 507 --minutes 40 --stories 3`: a scripted wizard (`story_agent`, `wizard_pilot` for walking) that accepts and completes three stories in two settlements through the public ops while the AIs run, with a JSON trace; `tests/test_narrative_playthrough.py` runs it on the showcase fixture. **Done when** the trace shows three completions with receipts and the faction-only hash of the world is reproducible across two runs.

---

## Milestone W5: dialogue pipeline and the three-cast pilot

### W5.1 Workbook converter and role map

**Objective.** `scripts/build_story_templates.py` (reusing `tools/dialogue_generation/workbook_reader.py` read-only), `data/narrative/role_map.json`, twenty structure templates `wb.<n>.json`, cast files for E36B, E53A and E56A (the pilot casts), packs from their Dialogue Matrix rows; `approved: false` until reviewed. **Tests.** Converter is deterministic (sha256 of outputs recorded); all 20 structures validate; the three casts cast in the showcase fixture (which roles bound to what is printed). **Done when** green and the owner can read the three generated packs. **Risk.** Wastes roles need the substitution rule; record which casts fail to cast and why.

### W5.2 Dialogue Factory export adapter

**Objective.** `tools/dialogue_generation/exporter.py --format narrative-pack` emits wizard-choice lines with worldview variants and `scores` for the three pilot casts from `generated/dialogue/*.json` and the pilot workbook; the runtime offers worldview variants only when `config.worldviews == true`. **Tests.** Factory tests still green (`PYTHONPATH=tools python3 -m pytest tools/dialogue_generation/tests -q`); the adapter test uses the committed E36B export, no model. **Done when** green. **Risk.** None; `tools/` is wizard-owned.

### W5.3 Coverage validator and fallback audit

**Objective.** `validate_narrative.py --coverage` lists every (template, node, role) without an approved line; the runtime's `generated: true` lines are counted in the playthrough trace. **Done when** the three pilot casts play through with zero generated lines in the headed test and the count for the other 17 structures is in the ledger.

### W5.4 Wrap-up. **OWNER CHECKPOINT (human review of the three casts' dialogue in play).**

Headed `stories` script with the E36B cast bound to a real settlement (screenshots of each talk). The owner decides whether to run the Factory for more casts (the instruction stands: not before this review).

---

## Milestone W6: tutorial and the transition

### W6.1 Wizard state and known spells

**Objective.** `narrative/wizard.py`: `known_spells`, `lessons`, `journal_notes`, `worldview`, `visited_settlements`; `server.py` `fire` op refuses with `spell_unknown` unless `flame` is known (campaign profile only; developer and test profiles know every spell so no existing test changes); `story.dungeon_interact(spell=)` passes `ctx["spells"]` from the wizard state in campaign. **Tests.** `test_narrative_tutorial.py`: fire refused then allowed; dungeon spell gating; `magic.py` untouched (import hash of the module unchanged is overkill; assert `test_fire_magic` green). **Done when** green.

### W6.2 Mentor and lessons L1-L6

**Objective.** `narrative/tutorial.py` and `data/narrative/templates/tutorial.*.json` (lessons as simple-tier templates so the graph runtime and packs serve them); the mentor binds to the starting settlement's keeper (household person at the centre) and rebinds if it falls; practice duels through `story.duel_begin` with a `tutorial` mode (told secret in the public view; raised casts); `travel_hint` op. **Tests.** A new campaign world offers L1; completing L1, L2, L3, L5 through the ops unlocks dynamic stories at minute 6 even though `unlock_after_ms` is 20 minutes; with no lessons done, stories unlock at 20 minutes (`HYBRID_NARRATIVE_UNLOCK_MS` or config override to 60 s for the test); lessons persist across save/load; a destroyed starting settlement rebinds the mentor; a player at minute 90 still sees undone lessons in the journal. **Done when** green and the headed `tutorial` script shows the first spell and the practice duel. **Risk.** The told-secret hint must not leak into non-tutorial duels (`test_story_slice` asserts `"secret" not in public view` already).

### W6.3 Wrap-up. **OWNER CHECKPOINT (tutorial feel).**

---

## Milestone W7: Godot presentation

### W7.1 Worker as talk target, rumours, journal, lessons panel

**Objective.** `story_ui.gd`: a worker or unit row with `person_id` is a talk target with a marker when `has_quest`; a settlement rumour panel (three lines) when the wizard enters a territory; journal (accepted quests with objective text) and lessons; `observe` and `travel_hint` keys. No rules in GDScript. **Tests.** `client/tests/run_hybrid_stories.gd`: starts the `stories` fixture (`HYBRID_FIXTURE=stories`, added to `server.py` fixtures: the showcase world), walks to a worker, opens the dialogue, accepts, reads the journal, saves and loads; screenshots. Add `stories` and `tutorial` to `run_headed_suite.sh`. **Done when** both pass headed on the laptop and the marks are in the ledger.

---

## Milestone W8: archetype library and scale

### W8.1 Migrate the remaining archetypes

**Objective.** Templates and placeholder packs for `shortage.workplace_closed`, `catastrophe.fire_break`, `transport.blocked_road`, `military.deserter_hunt`, `diplomacy.border_truce`, `personal.disputed_ownership`, `personal.broken_promise` (E36B), `mystery.tainted_well`, `personal.missing_flock`, `conflict.road_toll`, `conflict.labour_strike`, `discovery.ruin_map` (with the era theme on the dungeon). World effects `clear_disruption`, `cure_region`, `caravan`, `diplomacy_offer`, `unrest_delta` in `effects.py`, each with a test that the simulation API was called and that nothing was created (ledger `ledger.check` balanced). **Tests.** Per template: eligible in a fixture that has its cause and not otherwise; casts to real entities; every path completes in the playthrough harness; world effects applied once. **Done when** fifteen archetypes validate and `narrative_report.py` shows at least ten distinct templates in use across a 40-minute seed-507 world.

### W8.2 Scale and performance report

**Objective.** `test_narrative_perf.py` extended: 6, 12, 24 and 48 settlements; ms per director minute; context build cost; casting cost; the disabled path cost; a 60-minute AI world with narrative on versus off wall time (expected difference under 1%). **Done when** the numbers are in `WizardRTSHybrid/docs/evidence/narrative/w8/perf.md`.

---

## Milestone W9: integration with the neuroevolution branch

### W9.1 Sync and the shared-interface patch

**Objective.** At the agreed sync point (contract section 6), merge `origin/feature/neuroevolution-plan` into this branch (theirs wins in every shared file; re-apply the narrative hunks of `world.py` and the snapshot fields); submit the shared-change patch (the gate, the `person_id` snapshot field, the narrative log) to the neuroevolution agent with the evidence from W0.3. **Done when** the merge commit passes both quick sets and `freeze_content.py --check`.

### W9.2 Final gates

**Objective.** Full hybrid suite; `tests/test_determinism.py`; `test_neuro_determinism.py` if present; `hash_gate.py check` against the baselines current on the neuroevolution branch with `HYBRID_NARRATIVE` unset; the headed suite including `story stories tutorial`; `PYTHONPATH=tools pytest tools/dialogue_generation/tests`. **Done when** every gate is green and the ledger has the counts. **OWNER CHECKPOINT: merge decision.**

---

## Appendix A: files this programme creates or changes

```
WizardRTSHybrid/wizard_rts/narrative/{__init__,config,context,templates,casting,director,graph,dialogue,facts,effects,tutorial,wizard,ops,events,perf}.py
WizardRTSHybrid/wizard_rts/data/narrative/{config.json, role_map.json, schema/template_v2.json, templates/*.json, casts/*.json, dialogue/*.json}
WizardRTSHybrid/wizard_rts/data/story/archive/*.json              (moved)
WizardRTSHybrid/scripts/{narrative_evidence,narrative_report,build_story_templates,validate_narrative,play_stories}.py
WizardRTSHybrid/tests/test_narrative_{isolation,perf,casting,content,graph,context,director,ops,showcase,living,playthrough,tutorial}.py
godot_project/client/hybrid/story_ui.gd, wizard_labels.gd, client/scenes/hybrid_world.gd, client/tests/run_hybrid_stories.gd, run_hybrid_tutorial.gd
WizardRTSHybrid/scripts/run_headed_suite.sh (two entries)
tools/dialogue_generation/exporter.py (one output format)
docs/{WIZARD_NARRATIVE_AUDIT,PLAN_WIZARD_SETTLEMENT_STORIES,EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES,WIZARD_STORY_INTEGRATION_CONTRACT}.md, docs/ledger/WIZARD_STORIES_PROGRESS.md
Shared (contract procedure): WizardRTSHybrid/wizard_rts/world.py (gate, snapshot fields), story.py (narrative log, person link), server.py (ops, fixtures)
```

## Appendix B: approval checkpoints

| After | Owner decides |
| --- | --- |
| plan (now) | approve the plan, Q1-Q8 in the plan's section 14 |
| W1 | the person-link approach (one actor per person) |
| W3 | the director's assignments on three seeds; the showcase; cast quality |
| W5 | dialogue quality of the three pilot casts; whether to run the Factory for more |
| W6 | the tutorial and the 20-minute default |
| W9 | merge order and date |
