# Duel Master Battle — Village / Story / Dialogue Current-State Architecture

**Repository reviewed:** `Joesalmon1985/DuelMasterBattle`  
**Branch reviewed:** `main`  
**Review date:** 2026-09-12  
**Purpose:** Authoritative starting point for the village-generation implementation programme.

## 1. Executive conclusion

The village work is **not a blank-slate build**.

The repository already contains a substantial deterministic world simulation, a production settlement-profile layer, a production node-to-playable-area projection, production settlement quests, a real Overworld runtime, a separate fixture-driven Village Test Mode, a richer fixture quest graph runner, and a development-time local-LLM Dialogue Factory.

The main engineering problem is therefore **consolidation and reuse**, not invention.

There are currently three important flows:

### Production world flow

```text
DmbWorldSim
  -> DmbSettlementProfile
  -> DmbNodeProjection
  -> WorldFlow
  -> production Overworld
  -> DmbQuests / WorldPlay
```

This is already the normal game path for simulated world nodes and settlements.

### Village Test fixture flow

```text
content/village_tests/<profile>/
  -> VillageTestCatalog
  -> VillageCompositeProjection
  -> VillageTestRunner
  -> production Overworld
  -> VillageQuestRunner
  -> special village-test interaction handling
```

This correctly uses the real Overworld, John, camera and movement, but it still owns a **separate village projection and separate story runtime**.

### Development-time dialogue flow

```text
canonical 112-story workbook
  -> Python Dialogue Factory
  -> local Ollama / Mistral
  -> deterministic validation + review
  -> SQLite persistence
  -> approved JSON/CSV
  -> fixture_builder
  -> village test fixture content
```

This is deliberately offline/development-time. Ollama is not part of the Godot runtime.

The implementation programme should converge these systems without creating a fourth path.

---

## 2. Existing production world simulation

### Key files

- `godot_project/sim/world/world_sim.gd`
- `godot_project/sim/world/catan_state.gd`
- `godot_project/sim/world/settlement_profile.gd`
- `godot_project/sim/world/node_projection.gd`
- `godot_project/client/world/world_flow.gd`
- `godot_project/client/world/overworld.gd`

### What already exists

`DmbWorldSim` is the authoritative headless world simulation. It is seeded, serialisable and combines the Catan-style territorial/economic layer with infection/Pandemic-style world pressure and faction behaviour.

`WorldFlow` restores or creates the simulation from `Adventure` state, advances the simulation when John moves between world nodes, persists it back into the save, and asks `DmbNodeProjection` for playable areas.

This means the normal game already has the central architecture we wanted:

```text
canonical simulation state -> deterministic projection -> playable Overworld
```

Do not replace this with a new generic village generator unless a specific missing capability cannot be added cleanly to these existing seams.

---

## 3. Settlement context already exists

### Key file

`godot_project/sim/world/settlement_profile.gd`

`DmbSettlementProfile.describe(...)` already acts as the boundary between world simulation and settlement presentation.

It derives settlement facts from simulation state, including concepts such as:

- settlement/town kind;
- owner/faction;
- surrounding terrain;
- production;
- processing;
- housing/development;
- civic facilities;
- roads;
- infection;
- settlement mood;
- dungeon relationship;
- products/resources.

This is effectively the **Village Context** contemplated by earlier planning.

### Consequence for implementation

Do **not** spend a paid-agent phase inventing a new `VillageSeedContext` merely to rename information that is already available.

The first implementation phase should instead:

1. certify the existing settlement profile contract;
2. identify any facts genuinely missing for richer village/story generation;
3. add only those facts at the existing boundary;
4. expose deterministic diagnostics for manual inspection.

---

## 4. Production village/settlement projection already exists

### Key files

- `godot_project/sim/world/node_projection.gd`
- `godot_project/sim/tests/test_projection.gd`

`DmbNodeProjection.area_for(...)` converts simulated world nodes into the area dictionary already consumed by the production Overworld.

The existing projection covers much more than a marker on a world map. For settlement nodes it already projects buildings, workers, quest inhabitants and settlement/city differences.

The current projection tests inspect all projected world nodes for a deterministic simulation and check structural properties including:

- valid area shape;
- uniform map dimensions;
- reciprocal exits;
- walkable entity placement;
- no duplicate solid placements;
- settlement buildings;
- workers;
- quest inhabitants;
- visible settlement-to-city change;
- town walls;
- dungeon doors;
- deterministic projection.

### Consequence for implementation

The next village work should **extend/generalise `DmbNodeProjection` where needed**, not create another runtime village renderer for generated settlements.

The production world path should remain authoritative.

---

## 5. Production settlement quests already exist

### Key files

- `godot_project/sim/world/quests.gd`
- `godot_project/client/world/world_play.gd`
- `godot_project/sim/tests/test_quests.gd`

`DmbQuests` already generates local quests from settlement/world state.

The current tests demonstrate at least these production templates:

- `missing_flock`
- `tainted_well`
- `road_toll`

Template choice is influenced by simulated conditions such as infection and terrain.

Quest outcomes can alter real world state such as:

- faction AI priorities;
- resources;
- infection treatment;
- persistent settlement mood;
- granted items;
- battles.

`WorldPlay.run_quest(...)` is the production client bridge that presents those quests through the normal dialogue UI and applies/persists outcomes.

### Current limitation

The production quest model is relatively compact and purpose-built.

By contrast, the Village Test fixture system already contains a richer general graph representation with:

- `talk`;
- `investigate`;
- `travel`;
- `branch`;
- `choice`;
- `conclude`;
- `requires`;
- `sets`;
- semantic NPC IDs;
- semantic anchor IDs;
- dialogue variants;
- multiple endings.

The implementation programme should consolidate these capabilities rather than throwing either system away.

---

## 6. Village Test Mode: what is right and what is duplicated

### Key files

- `Play Village Test Menu.bat`
- `godot_project/client/scripts/village_test_runner.gd`
- `godot_project/sim/world/village_test_catalog.gd`
- `godot_project/sim/world/village_composite_projection.gd`
- `godot_project/sim/world/village_quest_runner.gd`
- `godot_project/sim/world/village_test_dialogue.gd`
- `godot_project/sim/world/village_test_dialogue_story.gd`
- `godot_project/client/world/overworld.gd`
- `godot_project/content/village_tests/`

### What is good

`VillageTestRunner` explicitly keeps gameplay in the **production Overworld**. Test sessions snapshot campaign state, run with the real player/runtime, and restore state afterwards.

This is the right testing philosophy and should be retained.

The current fixture catalogue is also useful. A fixture contains:

```text
village.json
cast.json
quest.json
dialogue.json
```

The repository currently contains at least E17A and E36B fixtures.

This gives the project a useful authored/reproducible content format.

### What is duplicated

Generated production settlements and fixture villages do not currently enter the Overworld through the same projection path.

Production uses:

```text
DmbNodeProjection
```

Fixture Village Test Mode uses:

```text
VillageCompositeProjection
```

Production settlement stories use:

```text
DmbQuests + WorldPlay
```

Fixture Village Test stories use:

```text
VillageQuestRunner
```

and the Overworld contains a special Village-Test NPC interaction branch.

There is also `VillageTestDialogueStory`, another explicitly test-only story-state helper.

### Required direction

Village Test Mode should become primarily a **selector, diagnostic wrapper and disposable-session manager around production systems**.

It should be able to test:

1. **generated production settlement mode** — world seed + node ID -> real `DmbWorldSim` / `DmbSettlementProfile` / `DmbNodeProjection`;
2. **authored fixture mode** — E17A/E36B-style content where required to test authored/generated story packs.

Both modes should ultimately share the same story/dialogue runtime.

Do not maintain two independent gameplay semantics.

---

## 7. Rich fixture story format already exists

### Example

`godot_project/content/village_tests/E36B/quest.json`

E36B's `broken_promise` quest already demonstrates a data-driven graph with stable NPCs, stable semantic anchors, prerequisites, flags, branches, investigations, final choices and multiple conclusions.

`VillageQuestRunner` is intentionally generic and contains no E36B/E17A-specific character names. It already supports much of the reusable graph execution needed by a general story runtime.

### Architectural recommendation

Do not create a third `GeneratedStoryEngine`.

Instead, evolve or extract the generic parts of `VillageQuestRunner` into a shared story-graph runtime capable of running:

- a story spec generated from `DmbQuests` / simulated settlement context;
- an authored E17A/E36B fixture story;
- future generated story templates.

`DmbQuests` can remain responsible for **choosing/building story facts and world effects**, while the shared graph runtime becomes responsible for **state transitions and presentation-independent quest progression**.

The final exact division should follow the code after implementation, but the principle is:

```text
story generation != story execution != dialogue prose
```

---

## 8. Dialogue Factory already exists

### Key files

- `Run Dialogue Factory.bat`
- `tools/dialogue_generation/cli.py`
- `tools/dialogue_generation/pipeline.py`
- `tools/dialogue_generation/database.py`
- `tools/dialogue_generation/ollama_client.py`
- `tools/dialogue_generation/validator.py`
- `tools/dialogue_generation/exporter.py`
- `tools/dialogue_generation/fixture_builder.py`
- `tools/dialogue_generation/prompts/`
- `tools/dialogue_generation/worldviews.json`
- `tools/dialogue_generation/tests/`

### Existing capabilities

The repository now contains a substantial development-time dialogue pipeline:

- canonical workbook ingestion;
- local Ollama model invocation;
- schema-constrained structured model output;
- seven-worldview logic with Python-owned score changes;
- semantic classification;
- writing;
- deterministic validation;
- reviewer stage;
- bounded repair/retry;
- SQLite persistence and restart recovery;
- prompt/worldview/source fingerprinting;
- approved-only export;
- fixture building.

The current E36B status document records successful model-free/unit/integration verification in the environment that implemented it.

### Important remaining acceptance item

A real generation run against the user's local Ollama instance and manual quality review remain the key acceptance gate before scaling generation to the other stories.

### Runtime rule

**Do not put Ollama into the Godot runtime as part of the village programme.**

The intended path remains:

```text
local LLM at development/content-build time
  -> validated approved dialogue data
  -> Godot consumes deterministic data
```

This provides reproducibility, no runtime model dependency, and preserves the rule that the game owns canonical state.

---

## 9. Dialogue integration gap

Two useful but separate dialogue boundaries currently exist:

### Fixture/runtime dialogue

`VillageQuestRunner` builds a dialogue index using:

```text
npc_id | quest_id | node_id | variant
```

This is already a strong semantic key.

### Older simple test override

`VillageTestDialogue` supports:

```text
user://village_test_dialogue.json
```

over the checked-in project JSON with fallback lines.

This is useful for fast development, but it is test-specific and much simpler than the E36B fixture/dialogue system.

### Required direction

The shared runtime should have one stable dialogue lookup contract.

Authored dialogue and Dialogue-Factory output should both target it.

Where practical, retain the useful local override/fallback behaviour as a developer feature, but do not let it become another story-state owner.

---

## 10. Existing automated verification

### Current Godot simulation runner

`godot_project/sim/tools/run_tests.gd` currently enumerates 26 simulation test modules, including:

- Catan;
- infection;
- units;
- world simulation;
- node projection;
- dungeons;
- puzzle rooms;
- quest logic.

### Particularly relevant tests

`test_world_sim.gd` already checks:

- a 200-turn simulation;
- deterministic same-seed behaviour;
- serialisation and continuation;
- different-seed divergence;
- faction behaviour.

`test_projection.gd` already checks production node/settlement projection over the world.

`test_quests.gd` already checks quest selection, graph completeness for current templates, world effects, persistence and item/fight branches.

### Dialogue Factory

The dialogue package has its own model-free pytest suite under:

```text
tools/dialogue_generation/tests/
```

This should remain the main frequent verification path for dialogue machinery.

### Gap

The inspected `client/tests/` listing contains several gameplay flows but does not currently expose a clearly named dedicated Village Test integration runner.

A focused scripted test should be added so the following can be tested without screenshot reasoning:

```text
select reproducible village
-> boot real Overworld
-> John exists
-> village loads
-> interact with expected NPC/anchor
-> advance story
-> complete/reset/exit safely
```

---

## 11. Documentation problems identified

### `docs/DIALOGUE_GENERATOR_HANDOFF.md`

The current file is obsolete. It predates the implemented Dialogue Factory and states that infrastructure/workbook/worldview inputs are missing.

It should be replaced with the current handoff supplied alongside this audit.

### `docs/TEST_STRATEGY.md`

The current file reflects an older, duel-focused test suite and older environment assumptions. It does not describe the current world, projection, quest, dungeon, village fixture or Dialogue Factory test layers.

It should be replaced/updated with the current test strategy supplied alongside this audit.

### Root `README.md`

The current root README is primarily a Village Dialogue / Story Test Patch handoff rather than a general project README.

This is documentation debt, but rewriting the whole project README is outside this focused village audit. Once the village consolidation work is complete, the root README should be converted back into a project-level entry point and link to the permanent subsystem docs.

---

## 12. Target architecture

The least disruptive target is:

```text
                        DmbWorldSim
                            |
                    DmbSettlementProfile
                            |
                    DmbNodeProjection
                            |
                     production Overworld
                            |
              +-------------+-------------+
              |                           |
        shared story runtime       ordinary world play
              |
        shared story spec
          /           \
 generated from     authored fixture /
 settlement state   generated content
          \           /
           shared dialogue lookup
                |
       approved dialogue pack
                ^
                |
     offline Dialogue Factory
```

Village Test Mode sits **around** this:

```text
Village Test Menu
  -> choose generated world seed/node OR authored fixture
  -> create disposable test session
  -> enter production Overworld
  -> expose diagnostics/reset/reproduction
```

It should not own separate gameplay rules.

---

## 13. No-art rule for this programme

Do not spend implementation effort on sprite production.

For any new representation required by the consolidation work use:

- rectangles;
- squares;
- circles;
- simple labels;
- existing assets only where already convenient.

The acceptance question is whether the system is structurally correct and readable enough to test.

Visual polish is a later programme.

---

## 14. What the paid coding agent should NOT rediscover

The following exploratory conclusions are already established by this audit:

1. The Catan/Pandemic world simulation exists and is deterministic/serialisable by design.
2. A settlement-context/profile layer already exists.
3. A production settlement-to-playable-area projector already exists.
4. Production settlement quests already exist and affect canonical world state.
5. Village Test Mode already uses the real Overworld but currently has a separate projector and quest runtime.
6. The E36B fixture demonstrates a richer reusable story graph format.
7. A substantial offline local-LLM Dialogue Factory already exists.
8. The Dialogue Factory should remain a development-time content pipeline, not a runtime dependency.
9. The principal architecture task is to **converge the production and fixture paths** without creating another village/story system.
10. Manual visual acceptance should be performed by the user using reproducible seed/node/profile cases.

The coding agent should begin from these facts and spend its paid reasoning on implementation and verification rather than re-performing this audit.

---

## 15. Verification status of this audit

This document is based on direct inspection of the current `main` repository.

It does **not** claim that the current test suite was executed during this architecture review.

The first implementation phase must run the relevant current test suites and establish a local baseline before editing production code.
