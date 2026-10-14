# Wizard story integration contract: interface assumptions and foreseeable merge conflicts

What the wizard narrative programme (`feature/wizard-settlement-stories`) relies on, what it changes, and where it may later collide with the neuroevolution programme (`feature/neuroevolution-plan`). Status: **REVISED with the plan, 14 October 2026; a record, not a coordination plan.** Per the owner's direction this programme does no integration work on the other agent's behalf, designs no training gates, and schedules no baseline changes; the two branches are reconciled separately by the owner when appropriate.

---

## 1. Principles

1. One world (`HybridWorld`), one clock, one quest state owner (`QuestService`), one person identity per human (`CANONICAL_GAME_ONTOLOGY.md`), typed effects with receipts only.
2. The narrative layer exists only in Wizard Mode by construction: `world.narrative` is created by `server.py` (and by wizard-facing environments on request), never by `HybridWorld.__init__` or `HybridEnv`. A world without it runs exactly the code that runs today (the legacy `story.story_quantum` included, unchanged).
3. `wizard_rts/world.py` is not changed by this programme. Narrative behaviour attaches through the wizard-owned `story.py` hooks that `world.py` already calls (`story.story_quantum`, `story.entity_rows`, `story.snapshot`, `story.WIZARD_OPS`).
4. The frozen roster (D33) is untouched: templates, packs, casts, archetypes, names, opponents and config are data; `freeze.check()` stays empty on every commit.
5. The faction AIs learn of the wizard only through the shared world (plan section 9.2). No narrative state is read by `ai*.py`, `diplomacy.py` or `trade.py`, and this is tested.

---

## 2. File and module ownership (what this programme touches)

| Path | This programme | Note |
| --- | --- | --- |
| `WizardRTSHybrid/wizard_rts/narrative/**`, `data/narrative/**`, `data/story/**` | creates and changes | new package and data |
| `wizard_rts/story.py`, `story_agent.py`, `story_fixture.py`, `dungeon_agent.py`, `mastermind_solvers.py`, `wizard_pilot.py`, `puzzle/**`, `duel/**`, `magic.py` | changes | wizard-owned since M3; `magic.py` gains residents as fire targets (D.3) |
| `wizard_rts/envs/{quest,dungeon,duel,outbreak}_env.py`, `envs/_world_cache.py` | changes | wizard-facing environments |
| `wizard_rts/server.py` | changes | ops (`save`, `load`, the narrative ops through `story.dispatch`), fixtures `stories`, `acceptance`, `HYBRID_LOAD_SLOT`, cycle-reset carry-over of `world.narrative["wizard"]` |
| `wizard_rts/workers.py` | **one additive change** (C.2) | `summon`, `release`, a `summoned` branch in `worker_quantum`, a `prog_interrupted` guard in `production_quantum`; inert unless a wizard op calls `summon`; proven by `test_hash_baseline.py`, `test_determinism.py`, `test_forestry.py`, `test_logistics.py` |
| `godot_project/content/source/duel_rules/progression.json` | adds two tiers | `duel.tutorial_3x3`, `duel.wizard_3x3`; baseline and `era_binding` unchanged |
| `godot_project/client/hybrid/{story_ui,wizard_labels}.gd`, `client/scenes/hybrid_world.gd`, `client/scripts/game_board.gd` (optional reveal flag), `client/tests/run_hybrid_*.gd` | changes | presentation |
| `tools/dialogue_generation/**`, `generated/dialogue/**` | changes tools and exports | never moves or rewrites the workbooks or the 88-profile CSV |
| `sim/dmb/quests/**`, `people/**`, `narrative/**`, `adventure/{mastermind,duels}.py`, `time/clock.py` | calls only | "frozen by convention": wrappers live in `wizard_rts/narrative/` |
| `WizardRTSHybrid/tests/test_story_slice.py`, `test_quest_env.py`, `test_dungeon_env.py`, `test_duel_env.py`, `test_outbreak_env.py`, `test_puzzle_*.py`, `test_ward_parity.py`, `test_fire_magic.py`, `test_narrative_*.py`, `test_wizard_*.py` | changes | |
| `docs/WIZARD_*.md`, `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`, `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`, `docs/ledger/WIZARD_STORIES_PROGRESS.md` | changes | |
| `docs/DECISION_REGISTER.md` | appends rows only at a checkpoint the owner names | |
| **Never**: `wizard_rts/world.py`, `sim_api.py`, `visibility.py`, `ai.py`, `ai_plus.py`, `ai_industry.py`, `history.py`, `freeze.py`, `freeze_guard.py`, `sysinfo.py`, `neuro/**`, `train_ai.py`, `docs/perf/hash_baseline*.json`, `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`, `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`, `docs/ledger/NEUROEVO_PROGRESS.md`, `docs/CONTENT_FREEZE.md`, `tests/test_neuro_*.py`, `test_content_freeze.py`, `test_hash_baseline.py`, `test_sim_api.py`, `tests/conftest.py`, `test_determinism.py` | read only | the other workstream's files and the shared gates |

---

## 3. Interface assumptions (what this programme relies on, read-only)

| Interface | Used for | Assumption |
| --- | --- | --- |
| `HybridWorld.advance` calling `story.story_quantum(self)` every quantum; `snapshot()` calling `story.entity_rows(self)` and `story.snapshot(self)`; `server.py` dispatching `story.WIZARD_OPS` | the narrative tick, rows and ops | these three call sites stay (they exist since M3) |
| `world.buildings[id]` fields `kind`, `faction_name`, `tx`, `ty`, `hp`, `destroyed`, `operational`, `constructing`, `disrupted`, `stall`, `worker_ids`, `settlement_id`, `ground_footprint`, `stack`, `waiting_worker`, `working` | context, casting, facts, the summon | names kept |
| `world.workers[id]` fields `id`, `role`, `building`, `tx`, `ty`, `carrying`, `status`, `program`, `pc`, `path`, `returning`, `target_tree`, `target_tile`, `anim`; `workers.{find_path,_release,_begin_return,_arrive_home,_fail_program,worker_abort,_roles_of}` | the summon and the link | names kept; the summon composes these |
| `world.carriers`, `world.units` (`faction_name`, `alive`, `weapon`, `tx`, `ty`, `definition`, `order`) | casting, link watcher | names kept |
| `settlements.{register,of,record,standing,mark_destroyed}`, `world.dmb.settlements[sid]` (`faction`, `state`, `centre`, `tile`, `unrest`, `pressures`, `chronicle`) | slots, context, residents' anchors | kept |
| `territory.{settlement_of,covering,radius_of,command_centers,cheb}` | context, travel | kept |
| `disruption.{is_mine,active,clear,REPAIR}`, `regions.{state,cubes_here,production_factor,cure,begin_treatment,region_at}`, `society.pressures`, `trade.{send_caravan,can_supply,hostile,partners_traded}`, `diplomacy.{state_of,hostile,propose}`, `history.{state,split,cycle_reset}` (read; `cycle_reset` called by `server.py` as today), `vp.era_state`, `tech.{god_allowed,profile_flags}`, `wl_defs.spec_for_kind`, `lifecycle.purge_building` behaviour (drops the worker; emits `building_removed`) | predicates, world effects, mortality | signatures kept; behaviour changes are the simulation's to make |
| Event kinds read (never written) by the watcher: `building_removed`, `settlement_destroyed`, `worker_aborted`, `worker_spawned`, `carrier_killed`, `disruption`, `disruption_cleared`, `outbreak`, `era_advanced`, `split`, `collapse`, `caravan_*`, `diplomacy_*`; `world.events.total` | dirtiness, mortality | kinds kept; new kinds are fine |
| `HybridEnv.SAVE_FORMAT` (2) and its pickle shape | Wizard Mode saves reuse the format number and shape | a bump is noticed by `test_wizard_save.py`; the wizard save adds `narrative_version` |
| `sim/dmb/adventure/duels.py`: `encounter_for_tier`, `load_duel_progression`, the lease record shape (`id`, `kind`, `encounter`, `bot_seed`, `checkpoint`, `pause_token`, `state`), `HazardDuelService.save_checkpoint/resume` semantics (secret lock) | the story Ward lease copies the shape; the hazard lease is untouched | kept |
| `godot_project/sim/{combatant,battle_sim,feedback,weave_bot,candidate_gen,auto_cast}.gd` and `wizard_rts/duel/ward.py` parity | the 3x3 duel, Python verification of reported casts | parity holds for `candidate_filter` and `random` (bit-for-bit) and `fixed_ward`; `capped_minimax` wards are not used for verified leases |
| `client/encounters/duel_lease_adapter.gd`, `game_board.configure_from_lease`, `export_checkpoint`/`restore_checkpoint` | hosting the board for story leases | kept |
| `freeze.manifest()`, `freeze.check()` | template validation; the freeze gate | kept |

---

## 4. Changes this programme makes to shared simulation files, and why

| Id | File | Change | Why unavoidable | Smallest form | Proof it changes nothing else |
| --- | --- | --- | --- | --- | --- |
| W1 | `wizard_rts/workers.py` | `summon(world, worker, tile, by)`, `release(world, worker)`; `worker_quantum`: a summoned worker walks its path then stands `conversing`; `production_quantum`: `if building.pop("prog_interrupted", False): pass` instead of advancing the frame when the worker reports back | the owner requires a real economic interruption when a worker is asked outside; the building's programme stack and the worker's step counter are private to `workers.py`, and faking it from outside (clearing `program` without the stack knowing) would corrupt `waiting_worker` | about 25 additive lines; no existing line changes except the one `waiting_worker` branch, which gains a `pop` before its existing logic | `test_hash_baseline.py`, `test_determinism.py`, `test_forestry.py`, `test_logistics.py`, `test_programme_failure.py`, `test_widelands_sweep.py` unchanged; `test_narrative_interrupt.py` proves the summon's accounting |
| W2 | `wizard_rts/magic.py` | `find` includes narrative residents; `fire` kills one through `residents.kill` | residents must be as mortal as workers; `magic.py` is wizard-owned, listed here because `world.fire` calls it | one more `(cls, table)` pair and one branch | `test_fire_magic.py` unchanged; hash tests unchanged (no resident exists without `world.narrative`) |

No other core file changes. If a later milestone finds it needs one (for example a carrier pause on the road), it is recorded here as a new row with the same four columns and reported to the owner before it is made.

---

## 5. Guarantees and the tests that hold them

| Guarantee | Mechanism | Test |
| --- | --- | --- |
| A world without `world.narrative` behaves exactly as today | no gate; the tick is `if "narrative" in world.__dict__` inside `story.story_quantum` | `test_narrative_isolation` (a): 3-minute `state_hash` on seeds 507 and 11 equals the pre-change value; `test_hash_baseline` green |
| `HybridEnv` never creates narrative state | `enable` is called only by `server.py` and by the wizard environments | `grep -n narrative wizard_rts/world.py wizard_rts/sim_api.py` empty (asserted in a test) |
| Factions cannot read the story | no narrative reads in the AI modules | `test_narrative_separation` (grep and the same-decisions test) |
| No new `world.events` kinds | `narrative/events.py` only | `world.events.total` equal with and without the narrative pass over a story fixture |
| No RNG shift | `world.rng` never called by `narrative/` | a grep test; `world.rng.getstate()` equal with and without narrative after 20 minutes |
| No wall clock | `game_ms` only | grep limited to `perf.py` |
| Frozen roster untouched | data only; validator against `freeze.manifest()` | `test_content_freeze` green on every commit |
| Save compatibility | the `HybridEnv` pickle shape plus `narrative_version`, atomic writes, refusal rules | `test_wizard_save.py` |
| Negligible cost without Wizard Mode | one dict lookup per quantum | `test_narrative_perf` (disabled path under 5 microseconds per quantum) |
| Bounded cost with Wizard Mode | budgeted director and residents, cached contexts | `test_narrative_perf` numbers in the ledger |

---

## 6. Branches and foreseeable merge conflicts (documentation only)

### 6.1 Branches

* `feature/neuroevolution-plan`: the training workstream. At the time of this revision it stands at `cb2f538e` (T1.1 to T1.5: visibility memory, successor control, alive rule, full action surface, episode runner; baselines `hash_baseline_v5*.json`). Those commits touch `ai.py`, `history.py`, `sim_api.py`, `visibility.py`, `workers.py` (+2 lines for `visibility.reveal`), `openra_abilities.py`, `scripts/hash_gate.py`, `tests/test_hash_baseline.py`, `neuro/**`; none touches a wizard-owned file or `world.py`.
* `feature/wizard-settlement-stories`: this programme, cut from `4b67f55c`. It does not merge the other branch in on its own; the owner reconciles when appropriate.

### 6.2 Where the two branches may collide, and the mechanical resolution

| File | This branch | The other branch (observed or likely) | Resolution when the owner reconciles |
| --- | --- | --- | --- |
| `wizard_rts/workers.py` | W1 (summon, release, two guards) | T1.1 added `visibility.reveal` calls (2 lines) and may add more | both are additive in different functions; take both; rerun `test_narrative_interrupt`, `test_hash_baseline` |
| `wizard_rts/magic.py` | W2 | none expected | ours |
| `wizard_rts/story.py` | many changes | none expected (not on their file list) | ours |
| `wizard_rts/server.py` | ops, fixtures, load slot, cycle carry-over | possibly spectator or training ops | both; `_handle` is a chain of `if op ==` blocks, so hunks are independent |
| `wizard_rts/history.py` | untouched (read) | successor control, alive rule | theirs; our `cycle_reset` carry-over lives in `server.py`, not here |
| `wizard_rts/world.py` | untouched | changed by them | theirs, no conflict |
| `wizard_rts/sim_api.py`, `visibility.py`, `ai*.py` | untouched | changed by them | theirs, no conflict |
| `docs/perf/hash_baseline*.json`, `tests/test_hash_baseline.py` | untouched; W1 keeps the hashes identical | re-recorded by them | theirs; our `test_narrative_isolation` records its own reference hashes from the code it runs on, so it stays green after any re-record |
| `godot_project/content/source/duel_rules/progression.json` | two tiers | none expected | ours |
| `godot_project/client/**` | several files | none expected | ours |
| `docs/DECISION_REGISTER.md`, `docs/ledger/LEDGER.md` | appended rows at an owner-named checkpoint | appended rows | keep both sets of rows |
| `WizardRTSHybrid/tests/conftest.py`, `test_determinism.py` | untouched | may change | theirs |

Potential semantic (non-textual) conflicts to check at reconciliation: (1) if the other branch changes worker row fields or `production_quantum`'s `waiting_worker` logic, W1 must be re-read against it; (2) if the other branch bumps `HybridEnv.SAVE_FORMAT`, `persist.py` follows it; (3) if the other branch gives `story.py` new responsibilities or removes the `story_quantum` call from `advance` (not planned by their documents), the narrative tick needs a new home, which would be the first `world.py` change and would be raised with the owner; (4) if the other branch adds event kinds the watcher cares about, the watcher's allowlist is extended.

### 6.3 Model compatibility note

Nothing in this programme changes observations, legal actions, the roster, `RULES_VERSION` or the hash baselines; W1 and W2 are inert in worlds without a wizard op. Any later reconciliation is therefore a textual merge, not a retraining question. This is a statement of what this branch does, not a commitment made for the other agent.

---

## 7. Test gates on this branch

| Gate | Every commit | Every milestone |
| --- | --- | --- |
| `test_narrative_*`, `test_wizard_*`, `test_story_slice`, `test_quest_env`, `test_duel_env`, `test_ward_parity`, `test_fire_magic` | yes | yes |
| `test_content_freeze`, `test_determinism` | yes | yes |
| `test_hash_baseline`, `test_forestry`, `test_logistics`, `test_programme_failure` | after any `workers.py` or `magic.py` touch | yes |
| full hybrid suite | | yes |
| headed scripts (`launch`, `tutorial`, `quest`, `story`, `stories`, `acceptance` as they exist) | after any Godot touch | yes |
| `tools/dialogue_generation/tests` | after any tools touch | yes |
| `test_neuro_*`, `hash_gate check`, training smoke | never run by this programme | |
