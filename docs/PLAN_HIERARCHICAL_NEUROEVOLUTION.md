# Plan: content freeze and hierarchical neuroevolution of faction controllers

Status: **APPROVED by the owner on 14 October 2026 with every recommended default of section 15** (decision register D33, D34, N01-N09). The step-by-step implementation guide for the executing agent is `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`; progress is tracked in `docs/ledger/NEUROEVO_PROGRESS.md`. Nothing in this document was implemented at the time of writing except the audits and benchmarks it cites. Written 14 October 2026 on branch `feature/neuroevolution-plan`, cut from `origin/main` at `fd6e3d80` (merge of PR #17). Owner brief: "Freeze content and plan hierarchical neuroevolution".

Evidence conventions: a number marked **measured** was produced in this session on the owner's Windows PC (AMD Ryzen 7 5800X, 8 cores / 16 threads, 32 GB, RTX 3060, Python 3.14, NumPy 2.4, no PyTorch, no C compiler) with the scripts named in section 11; a number marked **estimate** is derived from measurements and says how; **reported** means taken from an earlier run report and not re-measured here.

---

## 0. Read this first: what changes relative to the brief

The brief is accepted as the new direction. Five amendments make it more likely to succeed; each is argued where it applies and summarised here.

1. **Episodes are 240 simulated minutes, but the first evolution runs use a shorter proving horizon.** The brief already allows this. Measured throughput (section 11) gives about 20-30 wall minutes per 240-minute six-faction game per core on this PC, which is good, but a first end-to-end proof of evolution at 240 minutes would take a day before anyone knows whether the pipeline learns anything. The roadmap proves evolution on 60-minute games first (hours, not days), then switches the fitness horizon to 240 minutes for every promotion decision. Nothing is ever promoted on short games.
2. **The candidate controls several seats per game.** A six-faction game yields six fitness observations if the candidate plays three seats and the opponents play three (the tournament harness's mirrored A/B legs already do this for heuristic AIs). This triples sample efficiency at no simulation cost and is the single biggest lever on compute.
3. **One shared genome, module-wise mutation, not independently evolving specialist populations.** Cooperative coevolution with separate populations per network suffers from exactly the representation drift the brief worries about. The recommended scheme keeps one genome per candidate (all networks), mutates one to three modules per child, and measures every child by complete gameplay. This answers "can a specialist evolve while the rest stays stable" (yes, module-wise) without ever combining weights that were not evaluated together.
4. **Survival is a hard tier, but the tier is defined per world, and the fitness used for selection is an *advantage over a control game*.** Because outbreak loss is collective, a candidate's raw fitness depends mostly on which world it was dealt. Every seed is also played by the heuristic AI in the same seats (one control game per seed per generation, shared by all candidates), and selection uses candidate minus control. This removes most seed variance and gives a direct, honest measure of "did this controller make the world safer and richer than the heuristic would have".
5. **Imitation is allowed only as a labelled minority of the initial population.** The owner wants discovery, not reproduction of the heuristic AI. Random initial genomes will spend many generations learning to place a building legally. The compromise: generation 0 holds mostly random genomes plus up to 25% genomes whose action heads were fitted to the heuristic AI's choices by least squares (cheap, numpy). They are tagged `seed=imitation` in every log so the owner can see whether discovered or seeded lineages win. If seeded lineages dominate, that is a finding, not a failure.

Two findings that constrain everything else:

* **At the default outbreak cadence the collective failure state is rare.** The 180-minute stability run (reported) had 0 outbreaks; the two 240-minute benchmark games of this session are in section 11. If the measured games confirm that the world is never lost at cadence 1.0, the second objective ("prevent collective failure") is vacuous during training and the evolved controllers will not learn to contain anything. Section 8 proposes making `outbreak_interval_scale` a *recorded training parameter* chosen by a calibration study (not a silent change), and asks the owner to confirm. The opposite failure (nearly every game lost) was observed at scale 0.12 in the v2 run and is also reported.
* **A split successor faction is played by nobody in `HybridEnv` games** (section 3, B4): `ai_quantum` skips any faction not in `world.ai_factions`, and successors created by `history.split` are never added. This silently distorts every multi-agent game and must be fixed before any training.

---

## 1. Repository state and process

| Item | Value |
| --- | --- |
| Base commit | `fd6e3d80` (`origin/main`, 14 Oct 2026 10:26, "Merge pull request #17 from Joesalmon1985/feature/tech-faster-progression") |
| Plan branch | `feature/neuroevolution-plan` (new, from `origin/main`) |
| Unrelated work preserved | The previous checkout (`feature/wizard-rts-hybrid-v02`, fully merged into main) had an uncommitted edit to `docs/RELEASE_NOTES.md`; it is saved as `stash@{0}` ("stray RELEASE_NOTES edit ...") and nothing was overwritten. Note: the repository contains both `docs/RELEASE_NOTES.md` and `docs/release_notes.md`, which collide on Windows (case-insensitive file system) and show as a permanent modification; leave both alone. |
| `work/mechanics-completion-v4` | **Merged into this branch at `1b404a8b` on the owner's instruction (14 Oct 2026).** It brought 33 commits: the 168-card system (`content/cards.py`, D26), fake OpenRA buildings excluded (D27), a faction floor of six (D28), bare start and dealer guarantees (D29), ware classes (D31), a minimal visibility layer (D32), the faction command tier, `legal_actions` over the faction's `wl:` and `mdy:` kinds, versioned saves, a wider `state_hash`, new hash baselines (`docs/perf/hash_baseline_v4*.json`, `tests/test_hash_baseline.py`), the entity evidence catalogue (`docs/ENTITY_EVIDENCE.md`: 582 entities, 166 without a passing test naming them) and many mechanic fixes. Conflicts were resolved in favour of v4's card system over PR #17's `ERA_MIN_ENTITIES` augmentation (see section 1.1). Other unmerged branches (`work/visual-sim-qa`, `feature/hybrid-playtest-fixes-v03`) are superseded or unrelated. |
| Tests run here | `pytest` on `test_sim_api, test_vp_eras, test_outbreaks, test_content_graph, test_coverage, test_nn, test_neural_draft`: **64 passed in 99 s** (measured, Windows). The full suite (reported 850 passed / 10 skipped on Ubuntu for V3) was not run here; it takes 30-40 minutes. |

### 1.1 A card-system clash the owner should know about

`main` received PR #17 on the morning of 14 Oct ("tech cards: each card unlocks +1 entity (min 2/3/4/4 by era), pool stays 380 distinct combinations"), while `work/mechanics-completion-v4` (tip 13 Oct 23:19) replaced the generator with the owner-decided 168-card system (D26: four eras of exactly 42 cards, 1-4 slots, essential capabilities repeated in six cards so every faction can reach them, whole-era coverage across the ring). The two cannot coexist; the merge kept v4's system because it is a recorded owner decision and because it fixes the reachability problem that v4's audit measured (no faction ever held a complete Mindustry line under the 380-card draft). PR #17's intent (faster progression) is largely served by the 1-4 slot cards. If the owner wants PR #17's rule instead, it is a one-file revert of `content/graph.py` plus the test; the freeze manifest (M0) would then be regenerated before anything else.

Process for the implementation sessions: work on this branch (or a `feature/neuroevolution-m<N>` branch per milestone), never merge into `main` without the owner, commit evidence summaries under `WizardRTSHybrid/docs/evidence/neuroevo/`, keep raw run output outside git (`%DMB_RUNS%`, default `~/dmb_runs`).

---

## 2. Deliverable A: content freeze specification

### 2.1 What "content" is and where it is registered

The simulation has no single registry; kinds of things are assembled at import time from five places. All five are frozen.

| Registry | Code | Live count (measured, `fd6e3d80`) | Notes |
| --- | --- | ---: | --- |
| Hybrid build menu | `construction.BUILD_MENU` (+ `openra_content.install` adds OpenRA buildings) | 41 kinds (52 before v4 excluded the 11 OpenRA decoys, D27) | hand-written hybrid kinds plus the OpenRA roster installed at import |
| Runnable Widelands production sites | `wl_defs.runnable_names()` from `data/widelands_defs.json` | 193 kinds (`wl:<tribe>_<name>`) | `construction.full_menu()` = 41 + 193 = **234 building kinds** |
| Mindustry blocks | `industry.registry.kinds()` from `data/mindustry_defs.json` + `mindustry_full.json` + `mindustry_overrides.json` | 252 kinds (`mdy:*`) | includes hybrid `mdy:hy_*` industrial blocks |
| Units with recipes | `construction.RECIPES` (building -> unit -> recipe) | 46 unit kinds | hybrid, Widelands-primitive and OpenRA units |
| Mindustry producible units | `industry.units.unit_list()` filtered by `is_producible` | 50 | factories, reconstructors, assemblers |
| Content graph (the union the cards draw from) | `content.graph.entities()` | **582 entities** = 486 buildings + 96 units (measured on the merged tree `1b404a8b`; 593 before v4) | by game: widelands 206 buildings; openra 25 buildings + 42 units; mindustry 252 buildings + 50 units; hybrid 3 + 4 |
| Generated cards | `content.graph.generated_cards()` via `content/cards.py` | **168** (four eras of exactly 42; 1-4 slots per card; essentials repeated in at least six cards) | deterministic from the entities; `graph.check()` reports 0 problems; v4's reachability Monte Carlo is `tests/test_draft_reachability.py` |
| Hand-written cards | `tech.cards()` from `data/tech_cards.json` | 33 | legacy draft only |
| Raw imported data | `data/widelands_defs.json` (242 buildings, 128 wares, 161 workers), `data/openra_rules.json` (92 actors, 45 weapons), `data/mindustry_defs.json` (253 blocks, 64 units, 22 items, 11 liquids), `mindustry_full.json`, `mindustry_overrides.json`, `terrain_defs.json`, `outbreaks.json`, `puzzle_items.json` | | the importers' outputs; the registries above are derived from them |
| Exclusions | `coverage.py` (`EXCLUDED_RA`, `SANDBOX_CLASSES`), `openra_content.EXCLUDED_BUILDING/EXCLUDED_UNIT`, `industry.units.CORE_UNITS/INTERNAL`, Widelands military/training sites by type | 31 WL militarysites, 11 trainingsites, 2 warehouses; 17 OpenRA buildings (6 economy/power plus the 11 decoys of D27), 7 units; 17 Mindustry blocks, 14 units | `docs/evidence/coverage/coverage.md` (regenerated by v4): every imported entity is `functional` or `excluded`, 0 `pending` |

The coverage table (`scripts/coverage_report.py`) already proves there is nothing `pending`: the import programme is finished. The freeze turns "finished" into "fixed".

### 2.2 The frozen roster manifest

Add one generated, committed file, `WizardRTSHybrid/wizard_rts/data/content_freeze.json`:

```json
{
  "roster_version": "roster-1.0.0",
  "frozen_on": "2026-10-14",
  "base_commit": "fd6e3d80",
  "counts": {"entities": 582, "buildings": 486, "units": 96, "cards": 168, "hand_cards": 33, "wares": 128, "mdy_items": 22, "mdy_liquids": 11},
  "entities": ["mdy:additive_reconstructor", "...sorted stable ids..."],
  "units": ["unit:1tnk", "..."],
  "cards": ["gen.additive_reconstructor_mace", "..."],
  "hand_cards": ["dmb.card.farming", "..."],
  "wares": ["blackwood", "..."],
  "excluded": {"wl:barbarians_barrier": "Widelands military/training: replaced by the OpenRA military (D05)", "...": "..."},
  "data_files": {"widelands_defs.json": "sha256:...", "openra_rules.json": "sha256:...", "mindustry_defs.json": "...", "mindustry_full.json": "...", "mindustry_overrides.json": "...", "tech_cards.json": "..."},
  "roster_sha256": "7afaf3ae773ef391ddc9458babb96ea645d4f3106b6a34f5f3f234cd8a3d43f4"
}
```

The `roster_sha256` above is the **measured** prototype hash of the sorted entity, unit, card and hand-card ids on the merged tree `1b404a8b` (script `WizardRTSHybrid/docs/evidence/neuroevo/scripts/count_entities.py`, to become `scripts/freeze_content.py`; before the v4 merge it was `d2e8c059...` for 593 entities and 380 cards). A new module `wizard_rts/freeze.py` exposes `ROSTER_VERSION`, `manifest()`, `roster_hash()` (recomputed from the live registries) and `check()` (list of differences). Every run manifest, model file and checkpoint records `roster_version` and `roster_sha256` (section 10).

### 2.3 How future imports are prevented

1. **Importer guard.** Every `scripts/import_*.py` (23 scripts) gets a four-line preamble: refuse to run unless `DMB_UNFREEZE=1` is set and `--reason "<text>"` is given; print the freeze notice otherwise. Importers are kept (they are the provenance record), not deleted.
2. **Pinned sources stay pinned.** `sources/manifest.json` is unchanged; a test asserts the three commit SHAs equal the frozen ones so nobody re-pins by accident.
3. **The manifest is the oracle.** `tests/test_content_freeze.py` (fast, no world) asserts: live `graph.entities()` ids == manifest `entities`; live units == `units`; live generated card ids == `cards`; live ware list == `wares`; every `excluded` id is still excluded by `coverage.build()`; the data-file hashes match. **Any addition or removal fails the test.** The failure message names the ids.
4. **Changing the roster is a deliberate act.** `scripts/freeze_content.py --bump minor --reason "..."` regenerates the manifest, appends a dated row to `docs/CONTENT_FREEZE.md` (the changelog; created in M0) and bumps `roster_version`. Models and checkpoints record the version, so a bump makes old models "compatible with warnings" or "incompatible" by rule (section 10.4), never silently reused.
5. **Documents.** `CLAUDE.md`, `WizardRTSHybrid/AGENTS.md` and `DECISION_REGISTER.md` get the freeze as a closed decision once the owner approves (proposed rows D33, D34 in section 15). `PLAN_FULL_PROGRAMME_V2.md` milestones P6, P7, P9, P11 (content waves) are marked superseded.

### 2.4 What the freeze does not forbid

Fixing, completing, rebalancing, re-costing, re-arting and speeding up any entity on the manifest; adding **mechanics** (orders, policies, commands) that use existing entities; adding **data that is not content** (AI parameters, fitness configs, training scenarios). The rule of thumb for an implementer: if `graph.entities()` or `generated_cards()` changes, you are changing content and the test will say so. Renaming or removing an entity to make the freeze easier is forbidden by the brief; a genuine compatibility exception is recorded in `CONTENT_FREEZE.md` with the reason.

### 2.5 Compatibility

* **Saved games.** The world is pickled (`HybridEnv.save`) with instance ids from the id service; definition ids are strings. Freezing changes no id, so saves are unaffected. A roster bump that removes an id would break saves holding it; the changelog must say so (this is why removal is forbidden).
* **Cards.** Card ids are stable hashes of entity names (`gen.<slug>`); frozen with the entities.
* **Future AI.** Observation encoders index kinds through a frozen `kind -> index` table derived from the manifest (section 4.2); the table's hash is part of the observation schema version, so a roster bump is detected as a schema change.

---

## 3. Deliverable B: current readiness audit

### 3.1 What already supports neural training (verified by reading the code and by the 64 tests run here)

| Capability | Where | State |
| --- | --- | --- |
| Headless authoritative world, no Godot | `wizard_rts/world.py` `HybridWorld.advance` | works; 240-minute games run (section 11) |
| Per-faction agent stepping, the rest played by the heuristic AI | `sim_api.HybridEnv(agent_factions=...)`, `world.ai_factions` | works; `step()` takes one action list per agent faction |
| Same commands as God Mode and the AI | `HybridEnv.apply`: `build road queue cancel move order demolish rally stop deploy draft enhance ability dismantle convert waterway` | works; `belt upgrade configure trade` exist on the server but **not** in `HybridEnv` (B2) |
| Legal action masks | `HybridEnv.legal_actions` | partial: only the 52 `BUILD_MENU` kinds, sites sampled around the *home* warehouse only (B2) |
| Determinism and replay | `state_hash`, `replay`, `tests/test_determinism.py` (two processes, different `PYTHONHASHSEED`) | works |
| Save and load of a whole world | `HybridEnv.save/load` (pickle, RNG included; v4 added `SAVE_FORMAT = 2` with a stored state hash checked on load and a fresh-process load test) | works; enables mid-game checkpoints of long episodes |
| Per-faction visibility (v4) | `wizard_rts/visibility.py`: sight sources, explored memory, `seen_enemies`; used by `HybridEnv.observe` and the attack mask | works for what it covers; no building memory, not used by the heuristic AI (B1) |
| Faction command tier (v4) | `HybridWorld._not_mine`, `faction=` on world commands | works: a faction cannot command another's buildings or units even through world-level calls |
| Card reachability (v4) | 168 cards, essentials repeated, dealer guarantees, `tests/test_draft_reachability.py` | works by test; whether the heuristic AI then builds what it drafts is measured at about 50% (`V4_HANDOVER.md`) |
| Victory points from a ledger | `vp.faction_vp`, `vp.totals`, `vp.replay` (idempotent ledger `vp_ledger`) | works; `replay == totals` is checked every 30 minutes in long runs |
| Collective outbreak loss | `regions.regions_quantum` sets `world.collective_loss`, `cycle_pending`; `history.outcome` returns `collective_loss`; `world.advance` returns `terminal` and stops time | works; `HybridEnv.step` marks every agent terminated |
| Cycle completion | `vp.vp_quantum` sets `cycle_pending` when the last era ends; the headless world **keeps running** (only the Godot server calls `history.cycle_reset`) | works as a non-terminal marker; `history.outcome` returns `cycle_complete` |
| Faction collapse, decline, split | `history.history_quantum` | works; splits create new factions at run time (`Yellow-2`) |
| Eras and drafting v2 | `vp.py`, `draft.py`, `tech.py`; `campaign` profile defaults to v2 | works; the agent drafts through the `draft` action from `tech[faction].offers`; a lapsed round takes the first offer |
| Catastrophe toolkit for factions | clinics (`regions.cure`), nest combat (`nests.py`), aid caravans (`ai_plus.aid_step`), relations (`diplomacy.py`) | works; cooperation has no measured effect yet (reported, P10 study) |
| Tournament harness with Windows `spawn` pool, per-game atomic checkpoints and resume | `scripts/run_civilisation_tournament.py` | works on Linux; **crashes on Windows at import** (`import resource`, B3) |
| Run supervisor (heartbeat, stall kill, STOP file, disk guard) | `scripts/autorun/supervisor.py`, `tests/test_supervisor.py` | works, standard library only |
| NumPy neural toolkit | `learn/nn.py` (MLP, Adam, masked softmax), `learn/policy.py`, `learn/draft_module.py` (permutation-equivariant card scorer) | works; JSON weights; small |
| Hash gate for behaviour-preserving optimisation | `scripts/hash_gate.py` with baselines in `docs/perf/` | works; baselines are from 13 Oct and must be re-recorded after any rule change (V3 report says they were not) |

### 3.2 Defects and gaps, classified

**Must fix before any training (prerequisites of M1; each invalidates four-hour evaluations):**

| Id | Defect | Evidence | Fix |
| --- | --- | --- | --- |
| B1 | **Hidden information in observations: half fixed by v4.** `wizard_rts/visibility.py` (D32) now filters `enemy_capitals` (only ever-seen), `threats` (only visible units) and the attack mask (only visible targets). Still missing: a memory of enemy buildings once seen (the controller needs stale-but-legitimate knowledge of where enemy settlements are), and the heuristic AI's own targeting (`ai._known_targets`, the `_ai_known` set) does not use the layer. | `visibility.py`; `sim_api.py` observe/legal_actions; `ai.py` line 766 | Extend `visibility.py` with the building memory and make both the heuristic AI and the neural observation read only it (execution plan T1.1). Test: a hidden enemy settlement is absent from the observation and from every candidate target list; once seen it stays remembered. |
| B2 | **The action surface is narrower than the game: partly fixed by v4.** Masks now cover the faction's own Widelands kinds and every unlocked Mindustry kind, and world commands check ownership (`_not_mine`). Still missing in `HybridEnv`: `belt`, `upgrade`, `configure`, `link_power`, `trade` (caravan), diplomacy (`propose`/`respond`); sites are still sampled around the home warehouse only. | `sim_api.py` `ACTION_OPS`; server ops list; `ai_plus.trade_step`, `ai_industry` | Extend `ACTION_OPS` and `apply` (T1.4); candidate generation per settlement (section 4.5); keep every validation in the simulation (`check_placement`, `check_machine`, `check_belt`). |
| B3 | **Windows breakage in the tooling.** `scripts/bench_sim.py`, `long_stability.py`, `run_civilisation_tournament.py` import `resource` (POSIX only). No C compiler is installed, so the native A* kernel is unavailable (pure-Python fallback, slower). | measured: `ModuleNotFoundError: No module named 'resource'`; `shutil.which('gcc')` is None | Replace `resource` by a small `rss_mb()` helper (psutil if present, else `ctypes` `GetProcessMemoryInfo` on Windows). Decide separately whether to install a compiler (section 11.5). |
| B4 | **Split successors are uncontrolled in `HybridEnv` games.** `ai_quantum` skips any faction not in `world.ai_factions`; `history.split` never adds the successor. In a game with any agent faction, every successor (of an agent or of an AI faction) is frozen. v4's faction floor (D28: below six active factions the largest faction is force-split) makes successors routine, so this matters in every training game. | `ai.py` `ai_quantum`, `history.split`/`_floor_candidates`, `sim_api.reset` | Successors inherit their parent's controller: an AI parent's successor joins `ai_factions`; an agent parent's successor is controlled by the same candidate as an extra seat (or, by configured rule, handed to the heuristic AI). Test with a forced split. |
| B5 | **"Alive" in the env is the home warehouse only.** `HybridEnv._alive` returns False when the home command centre falls even if the faction holds other settlements, and True for a declining faction with no production. | `sim_api.py` lines 380-382 | Use `history.state(world)["faction"][f]["state"] != "collapsed"` as alive; expose decline. |
| B6 | **No episode runner for 240 minutes with checkpoints and a recorded end reason.** `HybridEnv.step` has `max_game_ms` and `info["outcome"]`, but nothing records *why* an episode ended, checkpoints a long game, or scores it. | | `neuro/episode.py` (section 9): end reasons `horizon`, `collective_loss`, `all_agents_collapsed`, `wall_cap`, `crash`; checkpoint every 30 game minutes via `HybridEnv.save`. |
| B7 | **Hash baselines: v4 re-recorded them** (`docs/perf/hash_baseline_v4*.json`, `tests/test_hash_baseline.py`) with a wider `state_hash`; the older files under `WizardRTSHybrid/docs/perf/` are stale. Unknown: whether the Linux-recorded hashes reproduce on this Windows PC under Python 3.14. | `docs/ledger/V4_HANDOVER.md` | Run the baseline test here in M0 (T0.5); if it differs, record Windows baselines under their own label and report the divergence. |

**Fix during AI development (they lower quality, not validity):**

| Id | Gap | Note |
| --- | --- | --- |
| C1 | Site candidate generation is slow and crude (`legal_actions` 25 ms, measured at minute 25, ring scan around one warehouse). | Replace by per-settlement candidate rings cached per minute and invalidated on build/destroy; target < 5 ms per faction. |
| C2 | `state_hash` costs 12 ms and `snapshot` 6 ms (732 KB) at minute 25 (measured); the episode runner must not call them per step. | Call once per checkpoint and at the end. |
| C3 | `legal_actions["attack"]` lists enemy *buildings* only; squads cannot be ordered against units except through `move(attack_move=True)`. | Tactical head uses attack-move and `order` on buildings and nests; fine for a first version. |
| C4 | Draft offers for an agent faction lapse to the first card after 6 minutes (`draft.default_pick`). | Acceptable ("waiting is an action") but the controller must see `offers` and the time left, which it will (section 4.3, technology network). |
| C5 | Event-triggered re-evaluation needs a cheap per-faction event filter; `world.events` is a bounded list of dicts with `kind`. | Section 5.2. |
| C6 | `worker_failed` events (about 108k per 180 minutes, reported) are noise for the observation layer. | Filter by kind. |

**Safe to defer (balance and content polish, outside this objective):**

| Id | Item |
| --- | --- |
| D1 | Era pacing: with drafting v2 the first era ends by VP at minute 25-35, later eras mostly by the 75-minute stall guard (reported and measured here, section 11). Training on these rules is valid; retuning is a separate owner decision. |
| D2 | AI balance (settlement VP saturates at 8-9, little war); the evolved controller is the intended answer, not another heuristic tweak. |
| D3 | Art, Godot inspector proofs, sea trade: irrelevant to headless training. |
| D4 | PyPy / Numba / structure-of-arrays: section 11.5 ranks them; none is a prerequisite. |

---

## 4. Deliverable C: game-state decomposition into networks

### 4.1 Design rules

1. **Shared entity encoders, pooled per container.** Every building is encoded by the same small network; a settlement pools its buildings (mean, max, count); the faction pools its settlements. The coordinator's input size never grows with the number of buildings.
2. **Never pool away the extreme.** Each pooling step passes three things: the mean, the element-wise max, and the *unpooled encoding of the single most important member* chosen by a fixed, cheap criterion (highest threat score for settlements; highest hp-loss rate for buildings; nearest enemy for units). A threatened settlement therefore reaches the coordinator as itself, not as 1/N of an average.
3. **Learned representations, fixed interfaces.** Each network's output is a vector with a fixed width and no prescribed meaning. Only the final action heads produce quantities with a defined meaning (scores over legal candidates).
4. **Inputs are what the faction may legitimately know** (section 3.2 B1): own state in full; enemy state only where visible or remembered; world state that the game shows every faction (era, VP table, outbreak counter, cubes in regions it has seen).
5. **Fixed topology, evolving weights** (owner preference). All widths below are starting values and part of the architecture version; they are not evolved.
6. **Frozen kind table.** Entity kinds are indexed by the `content_freeze.json` order; each kind has a learned 8-dimensional embedding row (part of the genome: 593 x 8 = 4,744 parameters). This is how the controller can tell a sawmill from a smelter without 593-wide one-hots.

### 4.2 Static feature tables (deterministic, not learned, computed once per process)

* `KIND_TABLE[kind] -> (index, game one-hot[4], type one-hot[2], era[4], size[3], is_military, is_clinic, is_warehouse/centre, is_producer_of[ware group x 6], consumes[ware group x 6], log cost total)` from `graph.entities()`, `wl_defs`, `industry.registry`, `rules.actor`.
* `WARE_GROUPS` (6): food, wood, stone, metal, cloth and tools, industrial (mdy items). Stocks and rates are reported per key ware (24 wares chosen from `trade.ware_value` and the AI's `WARE_WEIGHT`) and per group.
* `CARD_FEATURES[card] -> 28 numbers` reuses `learn/draft_module.card_features` (era, tribe fit, entity types, military, groups produced and consumed, cost) minus the parts that depend on the faction, which are recomputed live.

### 4.3 The networks

Widths are `in -> hidden -> out`; activation tanh; all weights float32; parameter counts are approximate and include the kind embeddings once.

| # | Network | Responsibility | Inputs (numerical representation) | In | Out | Structure | Consumers | Frequency | Cacheable | Params |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| N1 | **Building encoder** | one building -> vector | kind embedding 8; hp fraction; operational, working, constructing, disrupted, waiting-for-worker (5 flags); queue length/5; input satisfaction (requests outstanding / inputs) ; idle reason one-hot 6 (no input, no worker, no tree/rock, full, outbreak factor, none); outbreak factor; distance to settlement centre / 34; 3 flags: has road, is clinic, is nest nearby | 32 | 16 | 32-32-16 MLP | N2 | every strategic decision, per building; only buildings whose fields changed are re-encoded (dirty set from events) | yes, per building until an event touches it | 1.6 k |
| N2 | **Settlement encoder** | one settlement -> vector | N1 pooled (mean 16, max 16, count/50), most-damaged building 16; stocks at its centre: 24 key wares log1p/5; production rate per group 6 (made in last 5 min); consumption per group 6; unrest; standing VP flag; is home; radius/34; region cubes/3; nest hp fraction in region; own clinics in reach; enemy strength visible within 40 tiles / 1000; own strength within 40 / 1000; distance to nearest known enemy settlement / 200; founded minutes ago / 240 | 100 | 24 | 100-64-24 | N4, N6, N7, N9 | every strategic decision | yes, per settlement; invalidated by any event in its region or any building change | 8 k |
| N3 | **Unit encoder** | one unit -> vector | kind embedding 8; hp fraction; strength (OpenRA cost x hp) / 1000; loco one-hot 4 (foot, wheel, track, air, naval compressed to 4); has weapon; range / 8; is founder (settlers or MCV); carrying cargo; distance to nearest own centre / 100; distance to nearest visible enemy / 40; engaged, idle, moving (3 flags); region cubes/3 | 28 | 12 | 28-24-12 | N6 (pooled), N11 | every strategic decision for all units; every tactical tick for engaged units only | yes until the unit moves or takes damage | 1 k |
| N4 | **Resources and production** | economy health | stocks per key ware 24 (summed over settlements, log1p/5); stock per group 6; made per group last 5 min 6; consumed per group 6; outstanding construction requests per group 6; shortage events last 5 min per group 6; number of producers per group / 10 (6); chain coverage per group (produce, consume, deficit) 18 from the static chain table; N2 mean over settlements 24 | 102 | 16 | 102-48-16 | N9 | strategic | yes within a decision | 5.7 k |
| N5 | **Logistics** | transport health | roads / 100; unconnected buildings / 10; carriers busy fraction; carriers waiting fraction (from `waiting_for_this_road` counts); stuck entities / 10 (`diagnostics.stuck_report`); belt tiles / 100, machines unpowered fraction (Modern); waterways, ports (2); caravans active / 5 | 12 | 8 | 12-16-8 | N9 | strategic | yes | 0.3 k |
| N6 | **Military** | own force, visible enemy, front | N3 pooled over own armed units (mean 12, max 12, count/30, total strength/1000); nearest-enemy unit N3 12; visible enemy units pooled (count/30, strength/1000, mean distance/40, 3 nearest N3 = 36); known enemy buildings: count/20, nearest distance/200, mean hp fraction; kills minus losses last 10 min / 10 (units and buildings, 2); defences count / 10; factories operational / 5; unit production queue length / 10; most-threatened settlement N2 24 | 112 | 16 | 112-64-16 | N10, N11 | strategic; N11 reads its 16 at tactical ticks | yes within a decision | 8.3 k |
| N7 | **Territory and expansion** | where and whether to grow | settlements / 8; founders alive / 3 (settlers wagons, MCVs) and their cargo fraction; top-4 expansion candidates x 8 (distance/200, fertility/400 from `history.fertility`, deposits near 4 kinds /1000, threat/1000, region cubes/3, legal now) = 32; frontier contact: enemy centres within 80 tiles / 5; map fraction covered by own territory; N2 pooled max 24 | 68 | 12 | 68-32-12 | N9, N10 | strategic | yes | 2.6 k |
| N8 | **Technology and cards** | era, VP race, drafting | era one-hot 4; era progress / bar; minutes to stall guard / 75; own VP / 10; max other VP / 10; rank / 6; draft round / 7; minutes left in round / 6; cards held per entity type (buildings, units, military, industry) 4 / 10; offers: attention over up to 7 cards (each `CARD_FEATURES` 28 + "can I use it now" 3 flags = 31 -> 31-16 scorer, softmax-weighted sum 16 + max 16) | 50 | 16 (+ per-card scores 7) | 50-32-16 plus card scorer 31-16-1 (permutation equivariant) | N9, draft head | strategic and on `draft_offer` events | card features cacheable per offer | 2.8 k |
| N9 | **Economy coordinator** | one view of the economy | N4 16, N5 8, N7 12, N8 16, N2 pooled (mean 24, max 24), weakest settlement (lowest production) N2 24 | 124 | 16 | 124-64-16 | N12 | strategic | yes within a decision | 9 k |
| N10 | **Military coordinator** | one view of war | N6 16, N7 12, most-threatened N2 24, relations summary 8 (from N13), strongest visible enemy faction strength/1000, own strength/1000, VP gap to leader | 63 | 16 | 63-32-16 | N12, N11 | strategic | yes | 2.6 k |
| N11 | **Tactical controller** (optional, section 5.3) | orders for engaged units | per engaged squad: pooled N3 of its units 12+12, enemy pooled within 24 tiles 12+count+strength, force ratio, distance to nearest own centre/100, retreat path blocked flag, N10 16, N6 16 | 74 | 4 logits per squad (hold, attack-move nearest, focus nearest building or nest, retreat to centre) | 74-32-4 | commands | every 5 s game time, only squads within 24 tiles of a visible enemy or hit in the last 10 s | no | 2.5 k |
| N12 | **Faction coordinator** | the strategic context | N9 16, N10 16, N14 (crisis) 12, N13 8, N8 16, time: minutes/240, minutes since last decision/5, events since last decision one-hot 10, outcome risk: outbreaks/limit, era outbreaks/limit; recurrent state 16 (own previous output) | 112 | 32 context + 16 memory + 8 domain priorities + 1 wait logit | 112-64-(57) Elman recurrence on the 16 memory units | all action heads | strategic (60 s) and event-triggered | no | 11 k |
| N13 | **Diplomacy and trade** | relations | per other faction (up to 8 slots, zero-padded, sorted by distance): relation one-hot 4, pending offer from/to 2, truce minutes left/15, trades done/5, caravans lost to them/5, their VP/10, their visible strength/1000, their distance/200, their outbreak pressure (cubes in their visible regions)/6, are they collapsed = 16 x 8 = 128 -> per-slot 16-8 encoder pooled (mean, max) + global `diplomacy.pressure` | 17 (after pooling 8+8+1) | 8 | per slot 16-8; pooled 17-16-8 | N10, N14, trade and diplomacy heads | strategic | yes | 0.5 k |
| N14 | **Catastrophe coordinator** | outbreak risk and response | regions (25 on the standard map, measured) each: cubes/3, kind one-hot 4, has own settlement, has own clinic in reach, nest hp fraction, visible flag, distance to nearest own centre/200 = 10 x 25 -> per-region 10-8 encoder, pooled (mean 8, max 8) + 3 worst visible regions unpooled 24; global: outbreaks/limit, era outbreaks/limit, minutes to next cube/10, cubes cured by us last 20 min/5, clinics operational/5, rations and water stock/50 (2), N13 8 | 56 | 12 | 56-32-12 | N12, build head (clinic placement bias), military head (nest targets), trade head (aid) | strategic and on `outbreak`, `outbreak_cube`, `catastrophe_destroyed` events | region encodings cacheable until cubes change | 2.4 k |

Total about **60 k parameters** per candidate, plus action heads below (about 15 k). This is small enough for evolution strategies on CPU and for a candidate file under 400 KB in float32.

### 4.4 Action heads (the learned part of action selection)

Each head scores *candidates* generated mechanically from the legal-action machinery (section 4.5); scoring is learned, candidate generation is not. All heads share the coordinator context (32) and the domain priorities (8).

| Head | Candidates | Per-candidate features | Scorer | Output |
| --- | --- | --- | --- | --- |
| H1 Build | (kind, site) pairs: for each settlement, the 12 best legal sites by a cheap deterministic prefilter (free, reachable, near roads) x the affordable kinds unlocked (typically 20-80 kinds) -> capped at 96 pairs by a fixed rule (nearest sites first, kinds by cost) | kind embedding 8 + kind static 24; site: distance to centre/34, trees near/20, arable near/10, deposit kind one-hot 5 and amount/1000, water adjacent, on frontier, region cubes/3; settlement N2 24; context 32; priorities 8 | 108-48-1 | score per pair |
| H2 Road and link | (building, target) for unconnected buildings and settlement-to-settlement links; belt (machine, warehouse) proposals in Modern | distance, both sides' N1/N2, context | 70-32-1 | score |
| H3 Produce | (factory, unit kind) legal pairs | unit kind embedding 8 + static 12 (strength/1000, cost by group 6, loco 4, is founder), factory N1 16, military N6 16, context 32 | 84-32-1 | score |
| H4 Expand | (founder unit, candidate site) from N7's candidates; also "queue settlers/MCV" (a Produce candidate) | site features as H1 + founder N3 12 + N7 12 + context | 60-32-1 | score |
| H5 Military order | (squad, target): squads = idle armed units clustered within 6 tiles; targets = known enemy buildings and nests within reach, own threatened settlements (defend), rally points | squad pooled N3 24, target N1 16 or N2 24, distance/200, force ratio there (visible), is nest, is allied region (intervention), N10 16, context | 96-48-1 | score |
| H6 Draft | the offered cards (<= 7) | N8's per-card 16 + card score, N12 context | 49-16-1 | score (the draft happens only when an offer is open) |
| H7 Trade and aid | (partner warehouse, template): templates = {give surplus group g for wanted group h} over 6x6 minus identical, plus "aid rations and water" | partner slot 8 (N13), our surplus of g, our deficit of h, distance, partner's pressure, context | 60-24-1 | score |
| H8 Diplomacy | (partner, propose truce / propose peace / accept pending / break) | N13 slot 8, pressure, relative strength, VP gap, context | 50-24-1 | score |
| H9 Demolish, dismantle, convert, enhance, upgrade | per own building where legal | N1 16, settlement N2 24, kind static 24, context | 100-32-1 | score |
| H0 Wait | the single candidate "do nothing this tick" | context 32, priorities 8, minutes since last command | 41-16-1 | score |

**Selection rule.** All candidate scores and the wait score are placed on one scale (the heads share a learned temperature). Per decision tick the controller issues, in descending score order, every candidate whose score exceeds the wait score, at most one per head and at most **4 commands per tick**, each validated by the simulation (a rejection is logged with the simulation's reason and the next candidate of that head is tried once). Draft is exempt from the cap (an open offer can always be answered). The deterministic argmax is used in evaluation; during evolution the same rule applies (ES explores by weight noise, not by action sampling), which keeps games replayable from the genome and the seed.

This satisfies "actions genuinely come from the learned system": which building, where, which unit, where to move, which target, which card, whether to trade, when to wait are all head decisions. Pathfinding, placement legality, cost checks and road routing between two chosen endpoints remain mechanical.

### 4.5 Candidate generation (mechanical, deterministic, budgeted)

* Per settlement, a **site ring cache**: legal tiles for each of the three footprint sizes within the territory, refreshed once per game minute or on build/destroy in that settlement; prefiltered to 12 sites per settlement by distance from the centre and adjacency to roads. Cost target: under 5 ms per faction per decision (today's `legal_actions` is 25 ms, measured, and searches one ring around one warehouse).
* Unlocked, affordable kinds from `tech.kind_allowed` and current stocks (as `legal_actions` does today, extended to `full_menu()` and `industry.registry.kinds()`).
* Squads by single-link clustering of idle armed units within 6 tiles (the heuristic AI's `_station` and `_garrison` do similar grouping).
* Targets from the visibility memory only (B1).
* Expansion sites from a visibility-limited version of `ai_plus._expansion_site` / `_site_value` (the scorer is the head, not the heuristic's weights).

### 4.6 Variable-sized state: the techniques chosen and rejected

| Technique | Used for | Why |
| --- | --- | --- |
| Shared encoder + mean/max/count pooling | buildings, units, regions, diplomacy slots | O(n) cost, fixed output, order-invariant; the standard DeepSets construction |
| Fixed-criterion "keep the extreme member unpooled" | most threatened settlement, most damaged building, nearest enemy, three worst regions | guarantees the critical item survives pooling at zero learned cost |
| Single-query attention (softmax over per-card scores) | draft offers | the set is tiny (<= 7) and the per-card scores are reused by the draft head |
| Multi-head self-attention over all buildings | rejected | 500+ buildings x 60 k pairwise interactions per decision in NumPy is too slow for the gain; settlements already provide the grouping |
| Convolution over a map image | rejected for v1 | a 544 x 288 map would dominate inference cost; region-level and settlement-level summaries carry the spatial structure the strategic layer needs. Can be revisited for the tactical controller. |
| Recurrence (Elman memory in N12) | faction coordinator | lets the controller remember intent across 60-second gaps at 16 numbers of state; ES handles recurrence without backpropagation |

### 4.7 Inference cost (estimate)

Per strategic decision per faction: feature extraction dominates. Encoding 100 buildings x N1 is one batched matrix product (100 x 32 x 32): microseconds. Candidate generation and feature assembly in Python: estimate 5-15 ms per faction with the caches of 4.5, versus the 60 s of simulated time between decisions (about 2-4 s of wall time at mid-game speeds). Inference is therefore below 1% of the simulation cost; it is **not** a bottleneck and no GPU is needed for rollouts. The GPU is irrelevant to the design (noted so nobody buys compute for it).

---

## 5. Decision frequency

### 5.1 Is 60 seconds enough?

Measured behaviour of the heuristic AI in a 240-minute game (section 11): a faction ends with 60-90 buildings, issues on the order of 80 build, 50 road, 30-60 unit queue, 28 draft (7 per era x 4), 3-8 expansion and a few dozen military orders: **250-450 commands over 240 minutes**. At one decision per 60 s with up to 4 commands per tick the controller has 960 command slots plus event-triggered ticks; the economy's own pace (a building takes 20 s plus delivery; a draft round is 6 minutes) is slower than the decision cadence. **60 s is sufficient** as the base cadence. The first 10 minutes are the exception: the primitive start wants a burst of 6-10 builds; the plan allows a "boot" cadence of 20 s for the first 10 game minutes (configured, recorded).

### 5.2 Event-triggered re-evaluation

Events come from `world.events` (typed dicts). The controller keeps a per-faction event filter and a **coalescing rule**: any trigger schedules a decision at the next 5-second boundary; triggers within the same 5 s window are merged into one tick; a faction gets at most one event-triggered tick per 15 s; an event tick resets the 60-second timer.

| Trigger event kinds | Why |
| --- | --- |
| `building_destroyed`, `catastrophe_destroyed`, `settlement_destroyed` (own) | loss of capacity or a settlement |
| `unit_killed` (own, when losses in the last 60 s exceed 25% of strength) | substantial military loss |
| `ai_attack`-equivalent for agents: first enemy unit visible within 40 tiles of a settlement | enemy attack |
| `shortage` (own, repeated 3 times in 2 minutes for one ware) | critical shortage or broken chain |
| `draft_offer`, `draft_round` (own pack) | a drafting decision is available |
| `outbreak`, `outbreak_cube` in a region holding an own settlement; `terminal_loss` threshold approach (outbreaks >= limit - 2) | major outbreak, approaching collective failure |
| `era_advanced`, `relation_changed`, `caravan_lost` | strategic changes |

Everything else (`pickup`, `deliver`, `tree_*`, `worker_failed`: more than 90% of the event volume) is ignored at the filter.

### 5.3 Tactical controller

Combat in this simulation resolves in tens of seconds (OpenRA weapon numbers, 100 ms quanta); a 60-second cadence loses fights that a 5-second cadence wins or avoids. Recommendation: **N11 runs every 5 s of game time, only for squads within 24 tiles of a visible enemy or hit in the last 10 s**, with four discrete orders per squad (section 4.3). It reads the military coordinator's 16-vector computed at the last strategic tick (cached) so it never re-evaluates the economy. Cost: a handful of squads x one 74-32-4 pass: negligible. It is optional in M3 (strategic head H5 alone first) and added in M8 with an ablation test (with vs without, same seeds).

---

## 6. Deliverable D: architecture diagram

```
                                   AUTHORITATIVE WORLD (HybridWorld, one clock)
                                                   |
                 +---------------------------------+----------------------------------+
                 |          VISIBILITY FILTER (vision.py: own state, seen/remembered enemy, public world)        |
                 +----+----------+----------+----------+----------+----------+----------+----------+------------+
                      |          |          |          |          |          |          |          |
            buildings |    units |   stocks |  roads   | cards    | regions  | factions | sites    | events
                      v          v          v          v          v          v          v          v
                 [N1 bldg]   [N3 unit]  [N4 res] [N5 logi] [N8 tech] [N14 cat] [N13 dip] [N7 terr]  (filter+coalesce)
                   |pool         |pool                                 ^           |
                   v             v                                     |           |
            [N2 settlement]--+---+-------- most-threatened settlement -+-----------+
              (per settlement, pooled + extreme)
                   |             |
         +---------+------+  +---+-------------------------+
         v                v  v                             v
   [N9 ECONOMY COORD]   [N10 MILITARY COORD]         [N14 CRISIS COORD]
         |                   |        \                    |
         +---------+---------+---------+-------------------+
                             v                             
                 [N12 FACTION COORDINATOR]  (recurrent memory 16; every 60 s + events)
                   context 32 | priorities 8 | wait
                             v
   +------+------+------+------+------+------+------+------+------+
   | H1   | H2   | H3   | H4   | H5   | H6   | H7   | H8   | H9   |  H0 wait
   |build |road  |produce|expand|military|draft|trade |diplo |demolish|
   +------+------+------+------+--+---+------+------+------+------+
   candidates from the legal-action machinery (mechanical, budgeted)
                                  |
                        up to 4 commands per tick, each validated by the simulation
                                  |
   [N11 TACTICAL] every 5 s for engaged squads only <- reads N10/N6 cache ---> move / attack-move / order / stop
```

Information flows upward only (specialists -> coordinators -> faction coordinator -> heads); the coordinator's recurrent memory is the only state kept between ticks. Nothing in the diagram is a heuristic making a strategic choice.

---

## 7. Deliverable E: evolutionary training design

### 7.1 Algorithm

**Recommendation: a (mu, lambda) evolution strategy with mirrored Gaussian perturbations, rank-based fitness shaping, module-wise mutation masks, an elite archive and a small behaviour archive.** In detail:

* **Genome.** One flat float32 vector of all networks (about 75 k values) with a layout table (`module -> slice`) stored in the model manifest.
* **Population.** `pop = 24` children per generation (owner-configurable), produced from a parent mean `theta` plus `sigma * eps_i` with mirrored pairs (`+eps`, `-eps`) so that 12 noise vectors give 24 children. **Module-wise masks:** each noise vector is zeroed outside 1-3 randomly chosen modules (probability 0.5 one module, 0.35 two, 0.15 three; the full-genome mask with probability 0.1). This is the owner's "evolve one specialist while the rest stays stable", evaluated always in full games, so compatibility between specialists is tested by construction rather than assumed.
* **Update.** The natural-gradient estimate `theta += alpha * (1 / (pop * sigma)) * sum_i rank(F_i) * eps_i` (OpenAI-ES), Adam on `theta`, `sigma` adapted per module by the 1/5 success rule within [0.01, 0.2]. Rank shaping (centered ranks) means a single lucky game cannot dominate.
* **Elitism and archive.** The best child of each generation is re-evaluated on held-out seeds before it may enter the **champion archive** (hall of fame, section 7.5). The parent mean is never replaced by a child that was not evaluated.
* **Quality-diversity (light).** A behaviour descriptor per candidate is logged from outcome metrics only: (military share of VP = conquest VP / total VP, settlements founded, cubes cured, trades made). A **MAP-Elites-style grid** with 3 x 3 x 2 cells over (military share, expansion, cooperation) keeps the best candidate per cell. These are *preserved strategies*, not fitness bonuses; they seed the opponent pool and can be exported.
* **Why not pure CEM, GA or NEAT.** CEM is close to ES without mirrored sampling or Adam and converges to a point too early for a 75 k genome; a classic GA with crossover of networks that were never co-evaluated is exactly the incompatibility problem; NEAT-style topology evolution is excluded by the owner for now and would multiply the inference code paths.

### 7.2 Candidate evaluation per generation

Each generation plays the same **seed set S_g** (4 seeds, rotated from a reproducible stream, never reused as held-out seeds). For every seed:

* **Control game** (one per seed, shared): all six seats played by the heuristic `plus` AI. Its per-seat fitness `F_ctrl(seed, seat)` is the baseline for that seat.
* **Candidate games:** each child plays **3 seats** (A or B side, alternating per generation so every child sees both sides over time) against a 3-seat opponent mixture (section 7.4), so one game yields three fitness samples. With 24 children and 2 seeds each (legs A and B on different seeds), that is 48 games plus 4 controls = **52 games per generation**, giving 6 samples per child.
* **Advantage.** `A_i = mean over (seed, seat) of [F_i(seed, seat) - F_ctrl(seed, seat)]`. Selection uses ranks of `A_i`. The raw `F_i` is logged too.

### 7.3 Candidate generation, mutation, selection: the loop

```
gen g: theta, sigma[module], seeds S_g
  children <- mirrored module-masked noise (24)
  games <- controls(S_g) + candidate games (children x seeds)      # all independent, dispatched to workers
  F <- fitness(section 8) per (child, seed, seat); A <- advantages
  theta <- Adam step on rank-shaped A; sigma[module] <- 1/5 rule
  best <- argmax A; if A[best] > promotion_threshold: queue held-out evaluation (section 7.5)
  checkpoint (section 10.3); log generation summary; prune disk
```

### 7.4 Opponents

Per candidate game the three opponent seats are drawn (deterministically from the seed) from a mixture: heuristic `plus` 40%, heuristic `baseline` 10%, current champion 25%, a random archive member (champion archive or behaviour grid) 25%. Mirrored seats: on seed s a candidate plays seats {Red, Green, Purple} in leg A and {Blue, Yellow, Orange} in leg B (the tournament harness's convention), and the opponents swap. Tribe, start position and map vary with the seed (generated maps; the two imported Widelands maps are added to the held-out set only).

### 7.5 Champion promotion (training results versus held-out evaluation)

A candidate becomes champion only after a **held-out evaluation**: 12 games (6 seeds x 2 legs, seeds from a disjoint held-out stream, two map families) against the current champion and the heuristics, scored by the same fitness. Promotion rule: mean advantage over the current champion on paired games > 0 with a bootstrap 90% lower bound > 0, and the collective-loss rate not higher than the champion's. A sequential test is used: after 6 games, stop early only if the paired result is decisive in either direction. The old champion is never deleted (archive); the behaviour grid keeps alternative strategies. A newer run that performs badly cannot overwrite anything: `best_ai.json` is rewritten only by a promotion event.

### 7.6 Compatibility between specialists

Because every child is a full genome evaluated in full games, there is no cross-candidate recombination of modules. The one place where modules are combined is intentional and tested: **module transplant experiments** (an offline tool, not part of training) that swap one module between two archive champions and evaluate the hybrid on held-out seeds; results are reported as evidence and may seed the population if they win, never promoted directly.

### 7.7 Initial population

Generation 0: `theta` is random (He-scaled), `sigma = 0.1`. Up to 25% of generation-0 children are **imitation-seeded**: their action heads are fitted by ridge regression to the heuristic AI's choices recorded from 20 control games (features of the chosen candidate against the alternatives); tagged `seed=imitation` in all logs (amendment 5). Whether to use any imitation seed is a configuration flag the owner can turn off.

---

## 8. Deliverable F: fitness specification

### 8.1 Inputs (all from the game's own systems)

* `vp.faction_vp(world, f)` at the episode end (standing settlements plus conquest awards from the idempotent ledger); `vp.replay(world) == vp.totals(world)` is asserted at the end of every game (a mismatch voids the game).
* `history.outcome(world)`: `collective_loss` (with `cause`, `outbreaks`), `cycle_complete`, or empty.
* `history.state(world)["faction"][f]["state"]`: `active`, `declining`, `collapsed`.
* End reason from the episode runner: `horizon` (240 minutes reached), `collective_loss` at `t_c`, `agent_collapsed` at `t_e` (the agent's seat collapsed; the game continues for the others unless all agent seats are gone), `wall_cap`/`crash` (the game is voided and replayed once; a second failure is reported, not scored).

### 8.2 Definition

For a seat `f` in a game with horizon `T = 240` minutes:

```
Tier S (world survived to T, f not collapsed):      F = 1000 + 10*VP_f + 3*(VP_f - median VP of the other root factions)
Tier E (world survived to T, f collapsed at t_e):   F =  100 + 400*(t_e / T) + 10*VP_f(permanent conquest VP only)
Tier C (collective loss at t_c, every seat):        F = -1000 + 500*(t_c / T)             (VP ignored)
```

Consequences, checked against the brief:

* Survival dominates: the worst survivor (1000 + 0) beats the best eliminated seat (100 + 400 + 10 x VP < 1000 as long as VP < 50) and every collective-loss seat (max -500).
* Among survivors VP decides; the margin term (weight 3) rewards winning the race, not just owning settlements, and is symmetric so it cannot be farmed by shrinking others' VP except by conquest, which is the game.
* Earlier collective loss is worse than later: -1000 at minute 0, -500 at minute 240.
* VP earned before a collective loss never outweighs completion: Tier C ignores VP entirely.
* Elimination is better than a lost world but far below survival; a faction that lasts longer scores higher, so suicidal play is not rewarded.
* Cycle completion before T (all four eras finished): the world keeps running to T (section 3.1); the seat is scored as Tier S at T, and `cycle_complete` is logged as an achievement metric. No automatic cycle reset happens in training (the brief forbids disguising a first-cycle result).
* Ties: identical F; ranks are averaged in fitness shaping.

### 8.3 Selection fitness is the advantage over the control (section 7.2)

`A = F_candidate(seed, seat) - F_ctrl(seed, seat)`. In a world where every policy survives, A is driven by VP margins; in a world the heuristics lose, a candidate that survives scores +2000, which is exactly the signal the owner wants. The control game is also the diagnostic for "is the catastrophe avoidable": the control's collective-loss rate per generation is logged.

### 8.4 Cooperation and credit

* The penalty is shared by construction (Tier C applies to every seat), so a candidate playing three seats is penalised for a world it helped lose, and rewarded for one it helped save, relative to the control where heuristics played those seats.
* **Prevention statistics are diagnostics, never fitness:** cubes cured, nests cleared, aid caravans delivered, truces signed, intervention orders. They appear in logs and in the behaviour descriptor (section 7.1), so a cooperative strategy is preserved in the behaviour grid if it also survives and scores.
* **Mixed-seat credit:** the per-seat advantage is reported per seat; the candidate's fitness is the mean. Seat-level logs let the owner see whether one seat carried the others.

### 8.5 Is collective failure realistically avoidable, and does it ever happen?

Evidence so far: at the design cadence (one cube per 10 game minutes) the 180-minute run had **0 outbreaks** (reported) and the two 240-minute benchmark games here are reported in section 11.3. At scale 0.12 every 90-minute game was lost by minute 42-64, at 0.3 the `selfish` policy with clinics lost 0 of 2 and `ignore` lost 2 of 2, at 0.2 one of two was lost (reported, P10 study, tiny samples). So the regime where survival is in play is roughly **scale 0.2-0.4 over 90 minutes**; over 240 minutes the design cadence may or may not reach the limit (cubes accumulated to 14 in 180 minutes with no overflow).

**Recommendation (owner decision Q2):** training worlds use `outbreak_interval_scale` from a *calibration study run in M4* (10 seeds x scales {1.0, 0.5, 0.35, 0.25}, 240 minutes, six `plus` AIs), choosing the largest scale at which the heuristic world is lost in 20-40% of games. The chosen value is a recorded training parameter (run manifest, model file); held-out evaluation reports results at the training scale **and** at 1.0. If no scale produces an avoidable-but-real risk (for example loss is either 0% or 100% everywhere), that is reported as a blocker. Nothing is changed silently in `outbreaks.json`.

### 8.6 How this avoids the earlier exploit

The 2026-10-12 experiment learned to expand and wait because territory cells paid continuously and losses cost. Here: no wealth, territory, kill or production term exists; VP is only standing settlements and conquests under the game's rules; settlement VP saturates at 8-9 per faction (reported), so beyond that only conquest moves F; the control-advantage formulation means "do what the heuristic does" scores exactly 0; survival to 240 minutes is required for the top tier, so a passive faction that is conquered is in Tier E. The remaining exploitable degree of freedom is "expand to 8 settlements and turtle", which is a legitimate strategy the game rewards; if it dominates, the behaviour grid will show it and the owner can judge the balance (D2).

---

## 9. Deliverable G: Python training suite design

### 9.1 Layout

```
train_ai.py                              # thin CLI at the repository root (py -3 train_ai.py ...)
WizardRTSHybrid/neuro/
  __init__.py
  config.py        # dataclasses + JSON load/validate; defaults in neuro/configs/default.json
  manifest.py      # git SHA, roster version/hash, rules version, schema versions, fitness config, hardware record
  vision.py        # the visibility model shared with the heuristic AI (B1)
  features.py      # static tables (KIND_TABLE, WARE_GROUPS, CARD_FEATURES) and per-decision feature assembly with caches
  candidates.py    # site rings, squads, targets, trade templates: mechanical candidate generation (section 4.5)
  nets.py          # NumPy layers, genome layout, forward passes for N1-N14 and heads
  controller.py    # FactionController: schedule (60 s, boot cadence, events), caching, decision -> commands, logging
  tactical.py      # N11 squad controller (M8)
  episode.py       # run one 240-minute game with agent seats, checkpoints, end reason, fitness inputs
  fitness.py       # section 8, pure functions with tests
  league.py        # opponent mixture, champion archive, behaviour grid, held-out promotion test
  evolve.py        # ES loop: population, masks, Adam, sigma adaptation, generation checkpoint
  persist.py       # model export/import (best_ai.json + .npz), checkpoints, atomic writes, pruning
  workers.py       # spawn-based process pool, heartbeat files, per-game wall cap, crash capture (repro.json)
  report.py        # status tables, per-generation JSONL -> markdown/HTML summary
  imitation.py     # optional generation-0 seeding by ridge regression (section 7.7)
  configs/default.json, smoke.json, proving60.json, full240.json
WizardRTSHybrid/tests/test_neuro_*.py    # section 12
```

The existing `wizard_rts/learn/nn.py` MLP is reused for the per-module layers; `scripts/autorun/supervisor.py` wraps long runs; `run_civilisation_tournament.py` remains the heuristic tournament tool.

### 9.2 Command-line interface

```
py -3 train_ai.py train    --config full240 --run runs/2026-10-20a --workers 14 [--population 24] [--episode-game-minutes 240] [--seed-from best|archive|none] [--generations N|--hours H]
py -3 train_ai.py resume   --run runs/2026-10-20a                      # verifies compatibility, continues from the last generation checkpoint, replays no finished game
py -3 train_ai.py evaluate --model best [--games 12] [--opponents plus,champion] [--outbreak-scale 1.0] [--seeds held-out]
py -3 train_ai.py status   [--run ...]                                 # generations, best advantage, champion history, games played, wall time, disk use
py -3 train_ai.py export   --run ... --out best_ai.json                # writes best_ai.json + best_ai.npz from the champion archive
py -3 train_ai.py smoke                                                 # 10-minute end-to-end check: random genome plays legally, fitness computed, checkpoint written and resumed
py -3 train_ai.py play     --model best --seed 7 --minutes 240 --record game.jsonl   # one game, full decision log for inspection (also the Godot spectator feed later)
```

Simulated duration and wall time are always printed together ("240 game minutes, 27.4 wall minutes, 8.8x").

### 9.3 Configuration (JSON, validated)

```json
{
  "episode": {"game_minutes": 240, "boot_cadence_s": 20, "boot_minutes": 10, "decision_s": 60, "event_min_gap_s": 15, "tactical_s": 5, "checkpoint_game_minutes": 30, "wall_cap_minutes": 120, "outbreak_interval_scale": 1.0, "map": "standard", "profile": "campaign", "diplomacy": true},
  "evolution": {"population": 24, "mirrored": true, "sigma0": 0.1, "sigma_bounds": [0.01, 0.2], "module_mask_probs": [0.5, 0.35, 0.15], "full_mask_prob": 0.1, "adam_lr": 0.02, "seeds_per_generation": 4, "seats_per_game": 3},
  "league": {"opponent_mix": {"plus": 0.4, "baseline": 0.1, "champion": 0.25, "archive": 0.25}, "heldout_games": 12, "promotion_lb": 0.0, "behaviour_grid": [3, 3, 2]},
  "fitness": {"survive_base": 1000, "vp_weight": 10, "margin_weight": 3, "elim_base": 100, "elim_time_weight": 400, "loss_base": -1000, "loss_time_weight": 500},
  "workers": {"count": 14, "spawn": true, "heartbeat_s": 60, "stall_s": 1800},
  "storage": {"runs_dir": "%DMB_RUNS%", "keep_checkpoints": 3, "keep_game_logs_per_generation": 4, "max_run_gb": 20, "min_free_gb": 10}
}
```

### 9.4 Logging format

* `runs/<name>/manifest.json`: everything in section 10.2, written once, re-verified on resume.
* `generations.jsonl`: one line per generation: `{gen, wall_s, games, mean_A, best_A, best_F, ctrl_loss_rate, cand_loss_rate, sigma_by_module, promoted, champion_id, disk_mb}`.
* `games/<gen>/<seed><leg>.json`: per game: seats, policies, end reason, `t_end`, per-seat VP and F and A, outcome, outbreaks, state hash, wall seconds, step-time p95, validation flags (`vp_replay_ok`, `ledger_ok`). Kept for the last 4 generations plus every promotion game (bounded).
* `decisions/<gen>/<seed><leg>_<seat>.jsonl.gz`: the decision log (tick, trigger, chosen commands, rejected candidates with reasons) for 2 games per generation only (sampled), compressed. This is the diagnostic the owner reads to see whether the controller actually decides.
* `champions/`: `champion_<n>.npz + .json` for every promotion ever; never pruned.
* `STATUS.json`: heartbeat and the last generation summary for `status` and for the supervisor.

### 9.5 Lifecycle

1. `train` writes the manifest (refuses if the repository is dirty in `wizard_rts/` or `neuro/` unless `--allow-dirty`, which is recorded), **copies the simulation package into the run directory** (`runs/<name>/code/` holds `wizard_rts/`, `neuro/`, `sim/dmb/` and the data files), and every worker imports from that copy. Editing the repository during a run therefore cannot change the rules of running or future evaluations in that run. The copy is about 10 MB.
2. Each generation dispatches games to a `multiprocessing` `spawn` pool (Windows-safe); workers write heartbeat files; a game over `wall_cap_minutes` is killed and recorded as `wall_cap` (voided, replayed once).
3. After every generation: fitness, update, checkpoint (atomic), log, prune.
4. Promotion evaluations run as ordinary jobs in the next generation's batch (no idle workers).
5. `STOP` file or Ctrl-C: finish in-flight games (or kill after `--grace`), checkpoint, exit 0.
6. `resume`: load the newest valid checkpoint (fallback to the previous on corruption), verify the manifest against the run's code copy, continue; finished games of an interrupted generation are reused from `games/`.

### 9.6 Parallel execution and CPU use

One game per process, 14 processes on 16 threads (two left for the parent and the OS); memory per game is small (reported 64-73 MB peak RSS at 180 minutes on Linux; to be measured here). The parent does only bookkeeping and the ES update (milliseconds). Scaling is linear in processes until memory bandwidth matters; measured scaling is a M5 acceptance item.

### 9.7 Recovery

* Per-game crash: `repro.json` (seed, seats, genome id, config, SHA) and the traceback; the game is voided and replayed once; a second failure is logged and the candidate gets the control's fitness for that game (neutral), never a bonus.
* Supervisor-level: `scripts/autorun/supervisor.py` restarts the trainer with back-off; the trainer resumes itself.
* Mid-game checkpoints (every 30 game minutes via `HybridEnv.save`, pickle, about 1-3 MB) let a killed 240-minute game resume rather than restart; they live in the worker's temp directory and are deleted when the game ends.

---

## 10. Deliverable H: model format and persistence

### 10.1 Trained model export (portable)

Two files, both required; the JSON carries the SHA-256 of the NPZ.

`best_ai.json`
```json
{
  "format": "dmb-neuro-model", "format_version": "1.0.0",
  "model_id": "champion_0007", "created": "2026-10-21T03:12:00Z",
  "architecture": {"version": "arch-1.0.0", "modules": {"N1": {"sizes": [32, 32, 16]}, "...": {}, "H1": {"sizes": [108, 48, 1]}}, "layout": {"N1": [0, 1616], "...": []}, "kind_embedding_dim": 8, "recurrent": {"N12": 16}},
  "connections": [["N1", "N2"], ["N2", "N4"], ["...", "..."]],
  "schemas": {"observation": "obs-1.0.0", "action": "act-1.0.0", "fitness": "fit-1.0.0"},
  "compatibility": {"roster_version": "roster-1.0.0", "roster_sha256": "d2e8c0...", "rules_version": "rules-2026-10-14", "code_sha": "fd6e3d80...", "outbreak_interval_scale": 0.35},
  "provenance": {"run": "2026-10-20a", "generation": 31, "lineage": ["champion_0006"], "seeded_from": "random|imitation", "training_seeds": "stream:train:0-123", "heldout_seeds": "stream:heldout:0-11"},
  "evaluation": {"heldout_games": 12, "mean_F": 1087.5, "mean_A_vs_plus": 41.2, "ci90": [12.0, 70.4], "collective_loss_rate": 0.08, "control_loss_rate": 0.25, "vp_mean": 8.3},
  "weights": {"file": "best_ai.npz", "sha256": "...", "dtype": "float32", "count": 75212}
}
```

`best_ai.npz`: one array per module plus the flat genome (`theta`). JSON alone would be 1-2 MB of digits for 75 k weights and slow to load; NPZ is portable, versioned by the manifest and needs only NumPy. A `--json-weights` option exists for inspection.

### 10.2 Run manifest (recorded once per training session)

Git commit SHA and dirty flag; roster version and hash; `rules_version` (a hand-maintained string in `wizard_rts/__init__.py` bumped on any rule change, plus the SHA-256 of the copied `wizard_rts/` tree); architecture, observation, action and fitness schema versions; the full configuration; opponent roster (policy names and champion ids); training and held-out seed streams (named streams, so seeds are reproducible without storing them all); hardware record (`scripts/probe_hardware.py`); Python and NumPy versions.

### 10.3 Evolutionary checkpoint (resumable)

`checkpoint_<gen>.npz` + `checkpoint_<gen>.json`, atomic (temp file, fsync, rename), last 3 kept:

* `theta`, Adam moments, `sigma` per module, generation index, the noise seed stream position (children are regenerated from it, so the population itself need not be stored), fitness history, the pending-games ledger (which games of the current generation are finished, with their results), the champion archive index and behaviour grid, the held-out promotion queue, NumPy `Generator` bit-generator states as dicts, wall-time accounting.
* Resume verifies: same manifest hash; same code copy hash; same config (differences require `--override` and are recorded). An incompatible checkpoint is refused with the list of differences.

### 10.4 Starting new sessions from previous champions

`train --seed-from best` (or `--seed-from archive`): loads the champion(s), checks compatibility by rule: same `roster_version` and `architecture.version` and observation/action schema versions -> **compatible, reused as-is**; same architecture but different `rules_version` or `outbreak_interval_scale` -> **compatible with fresh evaluation required** (the champion is re-evaluated under the new rules before it can be a champion again; its old evaluation numbers are kept as history, not as current); different roster, architecture or schema -> **incompatible**, refused (no weight surgery). The new population is `theta = champion`, `sigma = sigma0 / 2`, plus archive members as initial children. Cumulative learning over sessions is the champion archive itself, which only grows.

---

## 11. Deliverable I: performance and compute budget

### 11.1 Measured throughput of one 240-minute six-faction game on this PC

Two games (seeds 7 and 11), `campaign` profile, six `plus` AIs, drafting v2, diplomacy on, cooperative nest policy, default outbreak cadence, standard map (544 x 288, 25 catastrophe regions), one core each, running concurrently with other work in this session (figures are therefore conservative by perhaps 10-20%). Script: `WizardRTSHybrid/scripts/bench_full_game.py` (a Windows-safe copy of `long_stability.py`); progress logs committed under `WizardRTSHybrid/docs/evidence/neuroevo/bench_240/`. These two games ran on the pre-merge tree (`fd6e3d80`). After the v4 merge (`1b404a8b`) a 40-minute check on seed 7 (same settings, `bench_240/merged_seed7_40_progress.jsonl`) took 79 s against 66 s before, with 371 buildings at minute 40 against 376: the merged rules are about 15-20% slower in the early game on a shared machine, within the range that needs a proper idle-machine measurement in M7 rather than a conclusion now. The merged-tree test subset (84 tests including `test_hash_baseline`, `test_visibility`, `test_ware_classes`, `test_draft_reachability` and both determinism tests) passed on this PC in 193 s.

| Game minute | seed 7: x real time | seed 7: wall s so far | seed 7: buildings / units / factions | seed 11: x real time | seed 11: wall s so far | seed 11: buildings / units / factions |
| ---: | ---: | ---: | --- | ---: | ---: | --- |
| 20 | 44.9 | 21 | 255 / 10 / 6 | 46.7 | 20 | 252 / 10 / 6 |
| 40 | 19.7 | 66 | 376 / 9 / 7 | 18.7 | 68 | 403 / 7 / 6 |
| 60 | 19.1 | 129 | 402 / 19 / 7 | 14.6 | 145 | 465 / 15 / 6 |
| 90 | 14.5 | 238 | 452 / 27 / 9 | 14.9 | 267 | 505 / 30 / 6 |
| 120 | 13.6 | 361 | 472 / 27 / 9 | 12.2 | 400 | 559 / 28 / 7 |
| 150 | 13.3 | 492 | 490 / 28 / 9 | 11.2 | 555 | 572 / 41 / 7 |
| 180 | 10.8 | 652 | 525 / 47 / 9 | 10.0 | 726 | 574 / 40 / 7 |
| 210 | 10.5 | 825 | 529 / 49 / 9 | 9.3 | 912 | 580 / 47 / 7 |
| 240 | 9.9 | 1003 | 534 / 37 / 9 | 8.6 | 1125 | 584 / 40 / 7 |

| | seed 7 | seed 11 |
| --- | --- | --- |
| Wall time for 240 game minutes (one core, shared machine) | **1003 s** (16.7 min, 14.4x average) | **1125 s** (18.8 min, 12.8x average) |
| End reason | horizon (no collective loss, no cycle completion) | horizon (no collective loss, no cycle completion) |
| Era first seen at minute (0 Prehistoric, 1 Historic, 2 Modern, 3 Dystopian) | {0: 5.0, 1: 75.0, 2: 150.0, 3: 225.0} | {0: 5.0, 1: 30.0, 2: 105.0, 3: 180.0} |
| Final VP | {'Red': 5, 'Blue': 4, 'Green': 6, 'Yellow': 5, 'Purple': 7, 'Orange': 5, 'Yellow-2': 1, 'Yellow-3': 1, 'Red-2': 1} | {'Red': 6, 'Blue': 3, 'Green': 5, 'Yellow': 7, 'Purple': 10, 'Orange': 10, 'Red-2': 1} |
| Sum of VP at minute 40 / 120 / 240 | 35 / 35 / 35 | 40 / 40 / 42 |
| Outbreaks (collective-loss counter) / cubes on the map at the end | 0 / 3 | 0 / 6 |
| Buildings / units at the end | 534 / 37 | 584 / 40 |
| Attack-move orders / unit hits over the game | 2183 / 1541 | 2973 / 2329 |
| Memory | not measured (no `psutil`; the Linux runs reported 64-73 MB peak RSS at 180 minutes) | |

Reading: throughput falls from about 45x in the first 20 minutes to about 10x after minute 160 as the world grows to 530-590 buildings; the mean over a whole game is **about 13-14x real time per core, 17-19 wall minutes per 240-minute game**. Both games ran concurrently with each other and with the session's other work, so an idle machine should be somewhat faster. **The VP race is essentially over by minute 40**: the summed VP changes by at most 2 over the remaining 200 minutes in both games (settlement VP saturates at 8-10 per faction; the heuristic AIs fight, with 2,000-3,000 attack-move orders, but rarely raze a settlement). An evolved controller that conquers would therefore find VP where the heuristics do not, which is the intended discriminator; but it also means a fitness based on VP alone would be flat among heuristic-like candidates after minute 40 (section 8.6).

### 11.2 Where the time goes (measured, minute 25, seed 7, 299 buildings, one profiled game minute)

| Share of 5.0 s profiled | Function | Note |
| ---: | --- | --- |
| 14% | `dict.get` (7.7 M calls) | the per-entity dict representation |
| 9% | `territory.command_centers` (130 k calls) + `cheb` (810 k) + `settlement_of` (66 k) | still redundant per-tick recomputation despite the v2 cache: 1 call per 5 ms of game time |
| 15% | `workers.production_quantum`, `_run_step`, `worker_quantum`, `find_path` | Widelands programmes and walking |
| 10% | `logistics._warehouse*`, `scan_requests`, `waiting_for_this_road` | request matching |
| 10% | `military_quantum`, `_scan` | combat scans (few units yet at minute 25) |
| 4% | `animals.animal_quantum` | wildlife |
| 2% | `tech.lookup` (11 k calls) | a cache miss pattern |

Per game second at minute 25: **31 ms** (32x real time) with 299 buildings; the six heuristic AI decisions cost **40 ms per 5-second decision tick** together (8 ms per game second, about a quarter of the total). `HybridEnv.observe` costs 1.3 ms, `legal_actions` 25 ms, `state_hash` 12 ms, `snapshot` 6 ms (732 KB) at the same point.

### 11.3 Outbreaks at the default cadence over 240 minutes

Both games: **0 outbreaks** in 240 minutes at the default cadence (one cube per 10 game minutes); cubes on the map stayed between 1 and 6 because the factions' clinics cured them (the clinic is a foundation building that every faction gets). The 180-minute run of 13 Oct (reported) also had 0 outbreaks. **At cadence 1.0 the collective failure state is not reachable in a four-hour game with the current heuristic AIs**, so objective B of the brief would be vacuous during training unless the training cadence is raised; see section 8.5 and owner decision Q2. The opposite regime is documented in the P10 study (reported): at scale 0.12 every 90-minute game was lost by minute 42-64 even with clinics. The interesting regime is in between and must be measured at 240 minutes (M4 calibration).

### 11.4 Compute budget (estimate from 11.1)

| Quantity | Value |
| --- | --- |
| Wall time per 240-minute game, one core | **about 18 minutes** (measured 1003 s and 1125 s, shared machine; pure-Python A*) |
| Games per day with 14 workers | about **853** (estimate: 14 x 86,400 s / 1064 s = 1137 at perfect scaling, taken at 75% to allow for memory-bandwidth contention; to be measured in M5) |
| Generation of 52 games (section 7.2) | about **1.1 hours** (52 games / 14 workers x 18 min); with the 60-minute proving horizon about 10 minutes (a 60-minute game took 129-145 s in the benchmarks) |
| 100 generations | about **4.6 days** of continuous running at 240 minutes per game |
| 1,000 complete games | about **21 hours** (0.9 days) at 14 workers |
| Memory | per game: measured in 11.1 (RSS); 14 games fit easily in 32 GB |
| Neural inference | under 1% of simulation time (section 4.7); no GPU |

The proving horizon of 60 minutes (amendment 1) costs about a tenth of a full game (early game runs at 30-45x), so a 10-generation proof of evolution on 60-minute games is an evening, not a week.

### 11.5 Optimisations worth doing before extended training (all hash-equal, in this order)

| # | Change | Expected gain (estimate) | Proof |
| --- | --- | --- | --- |
| O1 | Cache `territory.command_centers`/`settlement_of` per faction with invalidation on build/destroy/deploy/split (the v2 run cached the list but callers still rebuild per tick) | 5-9% | hash gate |
| O2 | Index logistics requests by ware and road (replace `waiting_for_this_road` scans) | 5-10% | hash gate, conservation tests |
| O3 | Skip idle Widelands sites (sleeping programmes) in `production_quantum` with a wake-up heap | 5-10% | hash gate |
| O4 | Spatial hash for `military._scan` (exists as `CELL=16` grid; verify it is used for all scans) and for nest/aid searches | grows with army size; late game 10-20% | hash gate |
| O5 | Event log: skip appending the 90% noise kinds when no consumer is subscribed (a per-world `event_kinds_wanted` set) | 2-5% | hash gate (events are not in the hash) |
| O6 | Install a C compiler (MinGW-w64 or MSVC Build Tools, owner decision Q4) to enable the existing native A* kernel (`tests/test_native_astar.py` proves identical paths) | reported 1.6x at 30 min on Linux | existing test |
| O7 | Candidate generation for the controller designed with caches from day one (section 4.5) | keeps the controller under 15 ms per decision | timing test |

Not before training: PyPy (NumPy-heavy controller code and pickle compatibility make it a research item), Numba (no compiler needed, but a large refactor to arrays), structure-of-arrays.

---

## 12. Tests and acceptance criteria

| Test | Proves | Milestone |
| --- | --- | --- |
| `test_content_freeze.py`: live registries == manifest; excluded stay excluded; data hashes; importers refuse without `DMB_UNFREEZE` | the roster cannot expand or shrink accidentally | M0 |
| existing suite + `hash_gate check` against re-recorded baselines | the simulation still functions; optimisations preserve behaviour | M0, every milestone |
| `test_neuro_episode.py`: a 240-minute headless episode with 3 random-genome seats completes (marked slow), records end reason `horizon`, VP replay equals totals, ledger balanced; a scenario with `outbreak_interval_scale=0.05` ends with `collective_loss` and Tier C fitness for every seat; a forced collapse yields Tier E | four-hour episodes run; collective failure detected; VP read from the ledger; early termination handled | M1, M4 |
| `test_neuro_vision.py`: an enemy settlement outside sight is absent from observations and from every candidate list; appears after a scout sees it; remembered after the scout dies | no hidden information | M1 |
| `test_neuro_successor.py`: after a forced split, the successor is controlled (issues commands) in a `HybridEnv` game | B4 fixed | M1 |
| `test_neuro_features.py`: every network receives an input of its declared width for worlds with 0, 1 and many settlements/units/regions; NaN-free; the most-threatened settlement's encoding is bit-identical whether the faction has 1 or 40 settlements | correctly shaped observations; extremes survive pooling | M2 |
| `test_neuro_nets.py`: forward pass shapes; `genome -> modules -> genome` round trip is exact; combining specialist outputs into coordinators is deterministic given the genome | specialist outputs combined correctly | M3 |
| `test_neuro_actions.py`: every emitted command is accepted by the simulation or rejected with a reason that the candidate generator then excludes; no command references an entity the faction cannot see or own | legal actions generated and executed | M3 |
| `test_neuro_determinism.py`: same genome, seed and config in two processes with different `PYTHONHASHSEED` give the same final state hash and the same decision log | training is deterministic under control | M3 |
| `test_neuro_fitness.py`: table-driven cases for every tier, tie, early loss ordering, cycle completion, and the advantage formula | fitness as specified | M4 |
| `test_neuro_evolve_smoke.py`: 2 generations x 4 children x 10-minute games on the small map: candidates created, evaluated, `theta` updated, checkpoint written, `resume` continues to the same `theta` as an uninterrupted run; killing a worker mid-game leads to one replay and no duplicate result | evolution runs; interrupted training resumes | M5 |
| `test_neuro_persist.py`: export then import gives identical outputs on 100 random inputs; a model with a different roster version is refused; a model with a different rules version is marked "fresh evaluation required" | models save/load without changing outputs; compatibility enforced | M5 |
| `test_neuro_league.py`: a candidate with a better training mean but a losing held-out record is not promoted; the champion archive keeps every past champion | promotion only after meaningful evaluation; champions preserved | M5 |
| `test_neuro_storage.py`: after 3 simulated generations with pruning, disk use is below the configured cap and the memory of the parent process is flat | unattended operation without uncontrolled growth | M5 |
| **End-to-end proof of evolution (M6 acceptance, not a unit test):** 60-minute games, population 16, 8 generations, 14 workers, overnight. Pass if the mean advantage of the generation-8 children over the control is higher than that of generation 0 with a bootstrap 90% lower bound above 0 on held-out seeds, and the best child beats the random generation-0 best on 8 of 8 paired held-out seeds. A run that merely completes does **not** pass. | learning actually occurred | M6 |

---

## 13. Deliverable J: implementation roadmap

Each milestone ends with tests green, a ledger row, evidence under `docs/evidence/neuroevo/<milestone>/`, and a commit on the feature branch. "Prerequisite for long training" says whether extended runs may start before it is done.

| Id | Milestone | Code changes | Depends on | Tests / acceptance | Risks | Prerequisite for long training | Sessions |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| **M0** | **Freeze the catalogue** | `wizard_rts/freeze.py`, `data/content_freeze.json`, `scripts/freeze_content.py`, importer guards, `docs/CONTENT_FREEZE.md`, decision rows D33/D34 (after approval), AGENTS/CLAUDE pointers; re-record hash baselines; Windows `resource` fixes (B3) | owner approval of this plan | `test_content_freeze.py`; `hash_gate record`; the three benchmark scripts run on Windows | the full suite has not been run on Windows: expect a few path/`resource` failures to fix | yes | 1 |
| **M1** | **Environment hardening** | `neuro/vision.py` used by `HybridEnv.observe` and by the heuristic AI's target memory (B1); `HybridEnv` action surface extended to `full_menu`, `mdy` kinds, `belt/upgrade/configure/link_power/trade/propose/respond` (B2); successor control (B4); alive = not collapsed (B5); `neuro/episode.py` with end reasons and 30-minute checkpoints (B6); `rss_mb` helper | M0 | `test_neuro_vision`, `test_neuro_successor`, `test_neuro_episode` (10-minute variant in the quick suite, 240-minute marked slow); existing `test_sim_api` green | changing the heuristic AI's visibility may change its play: compare tournaments before/after (it is allowed to change, but must be reported) | yes | 2 |
| **M2** | **Observation layer** | `neuro/features.py` static tables and per-decision assembly with caches; `neuro/candidates.py`; observation schema `obs-1.0.0` with a hash of the kind table | M1 | `test_neuro_features`; timing: features + candidates under 15 ms per faction at minute 120 of a benchmark save | feature bugs are silent; mitigate with the NaN/shape/extreme tests and a feature-dump tool in `play` | yes | 2 |
| **M3** | **Networks and controller** | `neuro/nets.py` (genome layout, forward passes), `neuro/controller.py` (schedule, events, heads, selection rule, decision log); `train_ai.py play` with a random genome | M2 | `test_neuro_nets`, `test_neuro_actions`, `test_neuro_determinism`; a random-genome faction plays 60 minutes issuing only legal commands and at least 30 distinct kinds of command | selection rule tuning (how many commands per tick) affects everything downstream; make it config | yes | 2 |
| **M4** | **Fitness, league, manifest, calibration** | `neuro/fitness.py`, `neuro/league.py`, `neuro/manifest.py`; the outbreak calibration study (section 8.5) with `plus` AIs at 240 minutes; `rules_version` string | M1 | `test_neuro_fitness`; calibration report with the recommended `outbreak_interval_scale` and the control loss rate | the study is 40 games x ~30 wall minutes / 14 workers = about 1.5 hours | yes | 1 |
| **M5** | **Evolution loop, persistence, CLI, recovery** | `neuro/evolve.py`, `persist.py`, `workers.py`, `report.py`, `config.py`, `train_ai.py train/resume/evaluate/status/export/smoke` | M3, M4 | `test_neuro_evolve_smoke`, `test_neuro_persist`, `test_neuro_league`, `test_neuro_storage`; `smoke` passes in under 10 minutes | Windows `spawn` and the code-copy import path need care (sys.path per worker) | yes | 2 |
| **M6** | **First proof of evolution** (60-minute games) | configs `proving60.json`; optional imitation seeding (`neuro/imitation.py`) as a labelled arm | M5 | the M6 acceptance in section 12; report with curves, behaviour grid, decision-log excerpts, honest negatives | the most likely outcome of a first run is "no learning yet": the report must then say which signal was missing (candidate coverage, selection rule, sigma) before anything longer is run | yes (gate) | 1-2 |
| **M7** | **Performance pass** (interleaved, hash-equal) | O1-O5 of section 11.5; O6 if a compiler is approved | M0 | `hash_gate check`; perf gate; re-measured 240-minute curve | none to behaviour by construction | no, but it halves cost | 1-2 |
| **M8** | **Tactical controller and event triggers at scale** | `neuro/tactical.py`, event coalescing tuned on logs | M6 | ablation: with vs without N11 on 12 paired held-out games | adds a second decision clock; keep it optional | no | 1 |
| **M9** | **Full 240-minute training programme** | `full240.json`; supervisor wrapper (`.ps1`), keep-awake; first overnight and multi-day runs; `best_ai.json` export; champion archive | M6, M4 | first champion promoted by the held-out rule or an honest report that none qualified; the owner can `train`, stop, `resume`, `evaluate`, `status` without reading code | compute: a 100-generation run is about a week of continuous use at 14 workers (section 11.4) | this *is* the long training | continuous |

Shortest credible path to "a command I can leave running": M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 (about 11-12 sessions), with M7 slotted after M6 because its gain only matters once runs are long.

---

## 14. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Random-initialised controllers never place a legal first building, so fitness is flat and evolution has no gradient | high in generation 0 | stalls M6 | candidate generation guarantees legality; the wait threshold and head temperatures start so that about 2 commands per tick are issued; the labelled imitation arm; the 60-minute proving horizon exposes this in hours |
| Outbreak loss never happens (objective 2 vacuous) or always happens | medium | the survival tier never discriminates | M4 calibration; the control loss rate is logged every generation; owner decision Q2 |
| Collective loss dominated by factions the candidate does not control | medium | noisy fitness | control-game advantage; three seats per game; rank shaping |
| Evolution finds a degenerate strategy the fitness rewards (turtle at 8 settlements) | medium | dull champions | it is the game's rule; the behaviour grid preserves alternatives; report it as balance evidence (D2) |
| Windows-specific failures in long runs (spawn, paths, sleep) | medium | lost nights | `smoke` and `test_neuro_storage` on Windows; supervisor; keep-awake in the `.ps1` |
| Repository edits during a run | medium | invalid comparisons | code copy per run (9.5) |
| Simulation slows in the late game more than measured here (large armies) | medium | fewer games per day | wall cap per game (voided, replayed once), M7 |
| Full test suite has Windows failures unrelated to this work | medium | noise | run it once in M0 and record; fix only what blocks |
| Owner's hardware needed for other things | certain at times | interrupted runs | STOP file, resume, `--hours` budget |

---

## 15. Decisions needed from the owner

**Resolved 14 October 2026: the owner approved every recommended default below** (register rows D33, D34, N01-N09).

| Id | Question | Recommended default (approved) |
| --- | --- | --- |
| Q1 | Approve the content freeze as decision **D33** ("The imported catalogue at `fd6e3d80` is the permanent roster; no new buildings, units, wares, items or liquids; fixes and rebalancing continue within it") and the priority change as **D34** ("Development priority is autonomous faction play by hierarchical neuroevolution; D24's 'neural training is secondary' is superseded") | yes to both |
| Q2 | Training outbreak cadence: use a calibrated `outbreak_interval_scale` recorded as a training parameter (section 8.5), with held-out evaluation also at 1.0? | yes; the study in M4 picks it; nothing in `outbreaks.json` changes |
| Q3 | Allow the labelled imitation-seeded minority (up to 25%) in generation 0, with a switch to disable it? | yes, with the switch |
| Q4 | Install a C compiler (MinGW-w64 via winget, or MSVC Build Tools) to enable the existing native A* kernel on this PC? | yes (about 1.6x reported on Linux at minute 30); otherwise pure Python, which is what the benchmarks here measured |
| Q5 | Three candidate seats per game against three opponents (amendment 2), or one seat? | three |
| Q6 | Where may runs store data (`%DMB_RUNS%`)? 215 GB are free on C:; a 20 GB cap per run is proposed | `C:\Users\joesa\dmb_runs`, cap 20 GB |
| Q7 | May the first overnight proof (M6) run unattended on this PC with sleep prevented? | yes |
| Q8 | Should split successors of a candidate's seat be played by the same candidate (extra seat) or by the heuristic AI? | same candidate |
| Q9 | PyTorch: not needed by this design (NumPy ES). Confirm no new ML dependency? | confirm none; `psutil` (tiny) is the only proposed addition, optional |
| Q10 | The `work/mechanics-completion-v4` audit branch (2 commits ahead of main): merge before M1? | owner reads and decides; the plan does not depend on it |
