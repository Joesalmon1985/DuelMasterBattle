# Wizard story integration contract

The boundaries between the wizard narrative programme (`feature/wizard-settlement-stories`), the authoritative world simulation, the Godot presentation and the neuroevolution programme (`feature/neuroevolution-plan`). Both programmes read this file; only the owner changes it. Status: **PROPOSED with the plan (14 October 2026)**.

---

## 1. Principles

1. One world (`HybridWorld`), one clock, one quest state owner (`QuestService`), one person identity per human (`CANONICAL_GAME_ONTOLOGY.md`), typed effects with receipts only.
2. The narrative layer is **optional and isolated**: enabled for Wizard Mode (the server), disabled for headless faction training and evaluation. Disabled means one attribute read per game second and nothing else.
3. The neuroevolution programme's training inputs are invariant under the narrative layer: observations, legal actions, decision timing, RNG consumption, physics, economy, combat, settlement and building behaviour, VP, catastrophe timing, the frozen roster, and (once the shared change lands) the recorded state hashes with the layer off.
4. Shared files change rarely, minimally, by the procedure in section 4, and never overwrite newer neuroevolution work.
5. The content roster is frozen (D33). Narrative templates, casts, dialogue packs and config are data, not content; `freeze.check()` must stay empty on both branches.

---

## 2. File and module ownership matrix

| Path | Owner | Wizard programme may | Neuroevolution programme may |
| --- | --- | --- | --- |
| `WizardRTSHybrid/wizard_rts/narrative/**`, `data/narrative/**`, `data/story/**` | wizard | create, change | read |
| `WizardRTSHybrid/wizard_rts/story.py`, `story_agent.py`, `story_fixture.py`, `dungeon_agent.py`, `mastermind_solvers.py`, `wizard_pilot.py`, `puzzle/**`, `duel/**`, `magic.py` | wizard | change | read (do not depend on internals) |
| `WizardRTSHybrid/wizard_rts/envs/{quest,dungeon,duel,outbreak}_env.py`, `envs/_world_cache.py` | wizard | change | read |
| `WizardRTSHybrid/wizard_rts/server.py` | wizard (the Godot path; not used by training) | change ops, fixtures, save/load | read; coordinate before adding a spectator op |
| `godot_project/client/hybrid/story_ui.gd`, `wizard_labels.gd`, `client/scenes/hybrid_world.gd`, `client/tests/run_hybrid_story*.gd`, `run_hybrid_stories.gd`, `run_hybrid_tutorial.gd` | wizard | change | read |
| `tools/dialogue_generation/**`, `generated/dialogue/**`, `docs/characters/**`, the two workbooks | wizard | change tools and exports; never move or rewrite the workbooks | read |
| `sim/dmb/quests/**`, `people/**`, `narrative/**`, `adventure/mastermind.py`, `adventure/duels.py`, `time/clock.py` | shared legacy, **frozen by convention** | call; add wrappers in `wizard_rts/narrative/` rather than editing | call |
| `WizardRTSHybrid/wizard_rts/world.py` | **shared** | the gate and the snapshot fields only (section 4) | everything else |
| `WizardRTSHybrid/wizard_rts/sim_api.py`, `visibility.py`, `ai.py`, `ai_plus.py`, `ai_industry.py`, `history.py`, `freeze.py`, `freeze_guard.py`, `sysinfo.py`, `learn/**`, `native/**` | neuroevolution | read only; propose changes through section 4 | change |
| `WizardRTSHybrid/neuro/**`, `train_ai.py`, root `*.bat` launchers for training, `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`, `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`, `docs/ledger/NEUROEVO_PROGRESS.md`, `docs/CONTENT_FREEZE.md`, `docs/perf/hash_baseline*.json`, `WizardRTSHybrid/tests/test_neuro_*.py`, `test_content_freeze.py`, `test_hash_baseline.py`, `test_sim_api.py` | neuroevolution | never | change |
| Every other `wizard_rts/*.py` (economy, logistics, workers, construction, military, industry, regions, disruption, society, trade, diplomacy, tech, vp, settlements, territory, lifecycle, terrain, mapgen, ...) | simulation core, **shared read-only for the wizard programme** | read; propose through section 4 if an API is missing | change (behaviour changes re-record baselines by their rules) |
| `WizardRTSHybrid/tests/test_story_slice.py`, `test_quest_env.py`, `test_dungeon_env.py`, `test_duel_env.py`, `test_outbreak_env.py`, `test_puzzle_*.py`, `test_ward_parity.py`, `test_fire_magic.py`, `test_narrative_*.py` | wizard | change | keep green |
| `WizardRTSHybrid/tests/conftest.py`, `test_determinism.py` | shared | not changed by the wizard programme | change |
| `docs/DECISION_REGISTER.md`, `docs/ledger/LEDGER.md`, `CLAUDE.md`, `WizardRTSHybrid/AGENTS.md`, `docs/NEXT_AGENT_HANDOFF.md` | owner / shared | append rows only at sync points | append rows |
| `docs/WIZARD_*.md`, `docs/PLAN_WIZARD_SETTLEMENT_STORIES.md`, `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md`, `docs/ledger/WIZARD_STORIES_PROGRESS.md` | wizard | change | read |

---

## 3. Protected interfaces (what the wizard programme relies on, read-only)

| Interface | Used for | Stability request |
| --- | --- | --- |
| `HybridWorld.advance`, `snapshot`, `state_hash`, `set_pose`, `solid_for_wizard`, `tile_in_map`, `player`, `seed`, `economy_quanta`, `events` (read), `dmb` slots | everything | keep names; additive changes fine |
| `world.buildings[id]` fields `kind`, `faction_name`, `tx`, `ty`, `hp`, `destroyed`, `operational`, `constructing`, `disrupted`, `stall`, `worker_ids`, `settlement_id`, `ground_footprint` | context, casting, facts | keep names |
| `world.workers[id]` fields `id`, `role`, `building`, `tx`, `ty`, `carrying`, `status`, `program`; `world.carriers`, `world.units` (`faction_name`, `alive`, `weapon`, `tx`, `ty`, `definition`) | casting, person link | keep names; the wizard programme adds `person_id` (written only when narrative is enabled) |
| `settlements.{register,of,record,standing,mark_destroyed}`, `world.dmb.settlements[sid]` (`faction`, `state`, `centre`, `tile`, `unrest`, `pressures`, `chronicle`) | slots, context | keep |
| `territory.{settlement_of,covering,radius_of,command_centers,cheb}` | context, travel | keep |
| `disruption.{is_mine,active,clear,REPAIR}`, `regions.{state,cubes_here,production_factor,cure,begin_treatment,region_at}`, `society.pressures`, `trade.{send_caravan,can_supply,hostile,partners_traded,is_post}`, `diplomacy.{state_of,hostile,propose,respond}`, `history.state`, `vp.era_state`, `tech.god_allowed`, `wl_defs.spec_for_kind`, `workers._roles_of` | predicates and world effects | keep signatures; behaviour changes are theirs to make |
| Event kinds read (never written) by the director: `building_destroyed`, `settlement_destroyed`, `worker_aborted`, `worker_spawned`, `disruption`, `disruption_cleared`, `outbreak`, `era_advanced`, `split`, `collapse`, `caravan_*`, `diplomacy_*`; `world.events.total` | dirtiness | keep kinds; adding kinds is fine |
| `HybridEnv.save/load` pickle format (`SAVE_FORMAT`) | Wizard Mode save reuses it | tell the wizard programme when it bumps |
| `freeze.manifest()`, `freeze.check()` | template validation (every referenced kind must be on the roster) | keep |

---

## 4. Shared-file changes: what, why, when

Only three shared changes are foreseen. Each is small, each is proposed as a patch with evidence, and the neuroevolution agent applies it on its branch at a checkpoint of its choosing (so it re-records any baseline in the same commit, by its own rule 8).

| Id | File | Change | Why unavoidable | Training impact | Tests that must pass | When | Postponable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | `wizard_rts/world.py` | `self.narrative_enabled = os.environ.get("HYBRID_NARRATIVE", "1") != "0"` in `__init__`; in `advance`: `if self.narrative_enabled: story.story_quantum(self); narrative.director_quantum(self)` (replacing the unconditional `story.story_quantum(self)`) | the gate must sit where the quanta run | env unset: identical hashes (the audit's W0.2 test). `HYBRID_NARRATIVE=0` in training workers: faction-only state and `world.rng` are identical for 40 minutes (measured, audit section 2.4), but `state_hash()` differs from the current baselines **from minute 1** because `snapshot()["story"]` is `{}` when the story dict was never created. S1 therefore includes a one-line change in the wizard-owned `story.py` so `story.snapshot` returns the same empty six-key shape whether or not the dict exists; after that, hashes differ only in worlds where a quest actually opens (measured: one outbreak quest in 60 minutes on seed 507). Cost saved: about 0.3% of wall time (measured). | `test_hash_baseline` (env unset), `test_determinism`, `test_sim_api`, `test_story_slice` | at the neuroevolution agent's next baseline re-record or at M7 (T1.1 already re-recorded `hash_baseline_v5*.json` on 14 Oct, after this branch was cut) | yes: until then training runs with the env var unset and pays the measured cost |
| S2 | `wizard_rts/world.py` `snapshot()` | worker and unit rows gain `person_id`, `has_quest`, `quest_status`, `label` **only when `narrative_enabled` and a link exists** (otherwise the row is byte-identical) | Godot draws one actor per person from the snapshot | none with the layer off (rows unchanged); with it on, `state_hash` changes only in Wizard Mode worlds | as S1 | with S1 | yes |
| S3 | `wizard_rts/story.py` | narrative events to `world.narrative["log"]` instead of `world.events`; person link instead of `_ensure_npc` | `HybridEnv` and the controller's event filter must not see narrative events; one actor per person | with the layer off nothing runs; with it on (final integrated game) the controller's event window no longer carries `story_*` kinds | `test_story_slice`, `test_quest_env`, `test_outbreak_env` | wizard branch, any time (file is wizard-owned); becomes effective for training only with S1 | n/a |

Recommended order: S3 and the W0 isolation tests on the wizard branch first (evidence), then S1+S2 as one patch to the neuroevolution agent with the `equiv` and `cost` numbers attached. The wizard programme never changes `RULES_VERSION`; if the neuroevolution agent judges the hash change from S1 to be a rule change, it bumps `RULES_VERSION` (champions become "re-evaluate", not incompatible, by its section 10.4 rule).

Additional API requests go through the same table as new rows; the default answer to "I need a new simulation API" is to compose existing ones in `wizard_rts/narrative/`.

---

## 5. Feature gating and deterministic guarantees

| Guarantee | Mechanism | Test |
| --- | --- | --- |
| Off in training | `HYBRID_NARRATIVE=0` set by the training workers (one line in `neuro/workers.py` and `neuro/episode.py`, applied by the neuroevolution agent with S1); the `HybridEnv` constructor may also set `world.narrative_enabled = False` | `test_narrative_isolation` (a): 3-minute hashes equal with env unset vs "1"; (b): no `world.narrative`, no `world.story` with "0" |
| On in Wizard Mode | `server.py` sets `world.narrative_enabled = True` after construction, every profile | headed `story` |
| No observation leak | `HybridEnv.observe` and `legal_actions` never read `world.narrative`, `world.story` or `world.dmb.people/quests` | `test_narrative_isolation` (d): identical observation dicts with the layer on and off after a story opened (the story fixture world with AI on) |
| No RNG shift | the narrative package never calls `world.rng`; its randomness is `random.Random(crc32(...))` per decision | `grep -n "world.rng\|\.rng\." wizard_rts/narrative/` empty (a test); `test_narrative_isolation` (e): `world.rng.getstate()` equal on/off after 20 minutes |
| No `world.events` writes | `narrative/events.py` only | `test_narrative_isolation` (f): `world.events.total` equal on/off |
| No hidden iteration order | sorted iteration, dict insertion order for registries, `PYTHONHASHSEED` two-process test | `test_narrative_director` (b) |
| No wall clock | `game_ms` only | `grep -n "time\.\|datetime" wizard_rts/narrative/` limited to `perf.py` |
| Frozen roster untouched | templates reference kinds by id; validator checks against `freeze.manifest()`; no importer run | `test_content_freeze` green on the wizard branch at every commit |
| Negligible cost when off | one attribute read per quantum | `test_narrative_perf` (disabled path under 5 microseconds per quantum) |
| Bounded cost when on | budgeted director, cached contexts | `test_narrative_perf` numbers in the ledger |
| Save compatibility | narrative state inside the pickled world; `SAVE_FORMAT` unchanged | `test_narrative_living` reload cases |

---

## 6. Branch and merge procedure

### 6.1 Branches

* `feature/neuroevolution-plan`: workstream 1 (training). Milestone branches `feature/neuroevolution-m<N>` may appear; the wizard programme tracks only the main one.
* `feature/wizard-settlement-stories`: workstream 2 (this plan). Created from `4b67f55c` on the neuroevolution branch so it carries the content freeze, the command tier, visibility and the wider `state_hash`. By the time the plan was committed the neuroevolution branch had moved to `fa0dea0d` (T1.1-T1.4: visibility memory, successor control, alive rule, action surface, baselines v5); none of those commits touches a wizard-owned file or `world.py`, and the first sync happens at their M1 checkpoint per section 6.2.
* `integration/wizard-neuro` (to be created by the owner or at the owner's word at the first sync point): where the two meet; never a working branch for either agent.

### 6.2 Sync points

The wizard branch merges `origin/feature/neuroevolution-plan` **only** at the neuroevolution programme's OWNER CHECKPOINTS (end of M1, M3, M5, M6 in its ledger), never between them, and only after the owner has accepted that checkpoint. This avoids merging half-finished training work. Between sync points the wizard programme works against the interfaces in section 3, which the neuroevolution plan does not change (its M1 changes `visibility`, `history.split` successors, `HybridEnv` alive and actions; none is on the wizard's list).

Merge direction is always **their branch into ours**. Conflict rule: in any file the neuroevolution programme owns or that is shared, **take theirs**, then re-apply the wizard hunks (S1, S2 are small and recorded as separate commits so they re-apply mechanically). Never resolve a conflict by keeping an older wizard-branch version of a simulation file.

### 6.3 The final integration

1. The neuroevolution agent has applied S1+S2 (with its baseline re-record) on its branch; the wizard branch has synced to that commit (W9.1).
2. `integration/wizard-neuro` is created from `feature/neuroevolution-plan` at that commit; `feature/wizard-settlement-stories` is merged into it (fast-forward expected after W9.1; otherwise the conflict rule above).
3. Gates on the integration branch, all green: the full hybrid suite (`python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py`), `tests/sim` legacy quest/dialogue/people tests, `test_determinism.py`, `test_neuro_determinism.py` (when it exists), `hash_gate.py check` against the branch's baselines with `HYBRID_NARRATIVE` unset, `freeze_content.py --check`, the headed suite including `story stories tutorial`, the dialogue factory tests, and `narrative_evidence.py equiv` on two seeds.
4. Model compatibility: models trained with `HYBRID_NARRATIVE=0` keep their `roster_version`, `ARCH_VERSION`, schema versions unchanged by this programme; if `RULES_VERSION` was bumped for S1, the champion is re-evaluated under the integrated code once (its rule), not discarded.
5. The owner merges `integration/wizard-neuro` into `main` when both agents have signed the gates in their ledgers.

### 6.4 Divergence handling

| Situation | Action |
| --- | --- |
| The neuroevolution agent changes a protected interface (section 3) | it says so in `NEUROEVO_PROGRESS.md`; the wizard agent adapts at the next sync point; never a hotfix on their branch by the wizard agent |
| The wizard agent needs an API that only a shared file can provide | add a row to section 4; implement in `narrative/` by composition until the row is accepted |
| Both touched `world.py` | theirs, then re-apply S1/S2 by hand, run `test_narrative_isolation`, `test_hash_baseline` |
| A baseline re-record on their branch makes `test_hash_baseline` fail on ours after sync | expected; the test reads their baselines, so it passes after the sync merge; never re-record baselines on the wizard branch |
| Training is running from a run directory code copy | unaffected by any merge (their section 9.5 copies the code); no coordination needed |

---

## 7. Test gates per programme

| Gate | Wizard branch, every commit | Wizard branch, every milestone | Integration |
| --- | --- | --- | --- |
| `test_narrative_*`, `test_story_slice`, `test_quest_env` | yes | yes | yes |
| `test_content_freeze`, `test_determinism` | yes | yes | yes |
| `test_hash_baseline` (env unset) | after any `world.py` touch | yes | yes |
| full hybrid suite | | yes | yes |
| headed `story` (+ `stories`, `tutorial` once they exist) | after any Godot touch | yes | yes |
| `tools/dialogue_generation/tests` | after any tools touch | yes | yes |
| `test_neuro_*`, `hash_gate check`, `train_ai.py smoke` | never run by the wizard agent | | yes (run by the neuroevolution agent or the owner) |
