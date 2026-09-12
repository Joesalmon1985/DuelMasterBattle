# Duel Master Battle — Village Generation, Story and Dialogue Implementation Plan

**Status:** Permanent implementation plan  
**Updated from repository audit:** 2026-09-12  
**Companion:** `VILLAGE_SYSTEM_CURRENT_STATE.md`

## 1. Objective

Complete the village system as a reusable production capability using the architecture already present in Duel Master Battle.

The target flow is:

```text
DmbWorldSim
  -> DmbSettlementProfile
  -> production village/node projection
  -> shared story spec/runtime
  -> shared dialogue lookup
  -> production Overworld
```

Authored/generated story content and local-LLM dialogue must plug into that same runtime rather than create a separate game.

Village Test Mode must become a reproducible selector/diagnostic harness around production behaviour.

---

## 2. What this plan no longer asks the coding agent to discover

The repository audit has already established:

- `DmbWorldSim` is the canonical deterministic/serialisable Catan/Pandemic-style simulation;
- `DmbSettlementProfile` already provides the settlement-context boundary;
- `DmbNodeProjection` already creates production playable settlement areas;
- `WorldFlow` and `Overworld` already use that production path;
- `DmbQuests` and `WorldPlay` already provide production settlement quests/effects;
- Village Test Mode already runs in the real Overworld, but uses a separate `VillageCompositeProjection` and `VillageQuestRunner`;
- E36B already demonstrates a richer data-driven quest graph;
- a substantial offline Dialogue Factory already exists;
- local Ollama should remain a development/content-build dependency, not a Godot runtime dependency;
- the main job is convergence and generalisation, not another rewrite.

The paid agent should read `VILLAGE_SYSTEM_CURRENT_STATE.md` before editing code.

---

## 3. Permanent constraints

### No parallel architecture

Do not introduce another independent village projector, quest engine or dialogue runtime.

Generalise/merge the existing seams.

### No art sprint

Do not create, search for or generate sprites, tilesets or polished artwork.

Use existing assets or obvious geometric placeholders:

- rectangles;
- squares;
- circles;
- simple labels.

### Canonical-state rule

Simulation/game code owns reality.

The LLM produces prose only.

### Reproduction rule

Every procedural/manual test case should be reproducible from stable identifiers such as:

- world seed;
- node ID;
- fixture/profile ID;
- story ID/node.

### Manual gates

After each phase, automated checks run and the agent stops for manual acceptance.

---

# Phase 1 — Baseline and certify the existing production world-to-settlement path

## Goal

Prove the architecture already present on `main` works locally before changing it.

This is a **certification phase**, not a design phase.

## Tasks

- Run the current Godot script/import/test baseline.
- Run the relevant current simulation suites.
- Confirm `DmbWorldSim -> DmbSettlementProfile -> DmbNodeProjection` for representative settlement/city nodes.
- Add only focused tests/diagnostics that are genuinely missing.
- Produce a small developer diagnostic that can report a settlement's:
  - seed;
  - node;
  - settlement kind;
  - owner;
  - terrain/resources;
  - production/processing;
  - development/housing/civic;
  - infection/mood;
  - projected important entities/buildings.
- Do not redesign settlement context unless a concrete missing requirement is demonstrated.

## Automated gate

At minimum establish evidence for:

- deterministic same-seed world state;
- save/restore continuity;
- settlements/cities discoverable;
- settlement profiles valid;
- production projection valid;
- city/settlement differences;
- current production quest selection remains valid.

Prefer existing tests. Extend them instead of duplicating them.

## Manual gate

Provide 3 concise settlement reports from contrasting deterministic cases.

Manual question:

**Do these reports make sense as the canonical facts from which a playable village and story should arise?**

Stop.

---

# Phase 2 — Make Village Test Mode test real generated production settlements

## Goal

Use Village Test Mode to launch deterministic settlement/city nodes through the production simulation/profile/projection path.

## Current problem being addressed

Normal world settlements use `DmbNodeProjection`.

Village Test fixtures currently use `VillageCompositeProjection`.

This is useful for authored fixtures but it means “generated village testing” is not yet a direct test of the production generator.

## Tasks

Add a Village Test selection mode for:

```text
world seed + settlement node
```

It should:

1. construct/restore the deterministic `DmbWorldSim`;
2. choose a valid settlement/city node;
3. use the real `DmbSettlementProfile`;
4. use the real `DmbNodeProjection`;
5. boot the existing production Overworld with John;
6. keep the existing disposable-session snapshot/reset/exit safety;
7. expose seed/node/context diagnostics.

Do not remove authored E17A/E36B fixture mode yet. It is still needed for story/dialogue integration.

## Automated gate

Start with 3 canonical generated cases, then approximately 10 deterministic cases.

Verify:

- real production projection used;
- John spawns;
- spawn is valid;
- key entities exist;
- important references resolve;
- reset/exit restores the original campaign snapshot;
- generated settlement/city distinctions survive;
- no new test-only gameplay path is introduced.

Add a dedicated scripted Village Test integration smoke if none exists.

## Manual gate

The user launches 2-3 contrasting generated settlements from Village Test Mode.

Check:

- John and normal movement/camera;
- settlement navigability;
- distinguishable settlement context;
- interactable inhabitants/buildings;
- placeholder readability.

Screenshots + seed/node identify defects.

Stop.

---

# Phase 3 — Converge production quests and the richer fixture story graph

## Goal

Create one shared story runtime/contract that can support both:

- stories generated from simulated settlement state;
- authored E17A/E36B-style story graphs.

## Current problem being addressed

Production:

```text
DmbQuests -> WorldPlay.run_quest
```

Village fixture test:

```text
quest.json -> VillageQuestRunner -> special Village-Test interaction path
```

`VillageQuestRunner` already has useful generic graph semantics and should be reused/extracted rather than discarded.

## Tasks

- Define the minimum shared story specification based on actual current formats.
- Support the useful graph concepts already present:
  - stable story/node IDs;
  - stable NPC IDs;
  - semantic anchors;
  - requires/sets;
  - talk/investigate/travel;
  - choice/branch;
  - conclusion/final state;
  - dialogue variant key;
  - explicit canonical effects where required.
- Separate:
  1. story generation;
  2. story execution;
  3. dialogue prose.
- Adapt one production `DmbQuests` template into the shared graph/runtime first.
- Preserve canonical production world effects.
- Make impossible/missing NPC/anchor references fail validation.
- Avoid a big quest-template expansion.

## Automated gate

Run the shared story runtime against:

1. one production-generated settlement story;
2. one authored fixture story;
3. several different settlement contexts.

Use fixed/plain dialogue.

Verify progression, wrong-NPC handling, prerequisites, choices, completion, effects, persistence/reset and reference validity.

## Manual gate

The user completes one generated settlement quest and one authored fixture quest using deliberately plain/fixed dialogue.

Manual question:

**Does the same story machinery feel correct in both cases, and does the generated story genuinely fit the village that produced it?**

Stop.

---

# Phase 4 — Unify authored dialogue binding

## Goal

Make dialogue a replaceable data input to the shared story runtime.

## Tasks

- Standardise the stable dialogue lookup contract.
- Prefer the semantic structure already used by the richer fixture pipeline, such as:
  - NPC ID;
  - story/quest ID;
  - story node ID;
  - variant.
- Make authored fixture dialogue use the shared runtime.
- Preserve safe fallback dialogue.
- Preserve a developer override mechanism if it remains useful.
- Remove/retire test-only story ownership such as `VillageTestDialogueStory` once no longer required.
- Remove the special Village-Test NPC interaction branch when shared dispatch can replace it safely.
- Do not change canonical story state based on dialogue prose.

## Automated gate

Test:

- correct NPC/node/variant lookup;
- wrong/missing dialogue;
- fallback;
- authored replacement without gameplay-code changes;
- story remains completable without optional prose;
- fixture and generated story use the same lookup API.

## Manual gate

Use deliberately unmistakable authored test lines.

The user confirms the correct line appears for:

- correct NPC;
- correct story node;
- different quest stage;
- branch variant;
- fallback case.

Stop.

---

# Phase 5 — Connect and accept the existing local Dialogue Factory

## Goal

Use the implemented offline local-LLM factory to populate the shared dialogue contract.

This phase does **not** build a new LLM subsystem.

## First gate: E36B live local acceptance

Run the existing E36B sequence:

```powershell
& ".\Run Dialogue Factory.bat" doctor
& ".\Run Dialogue Factory.bat" ingest --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" generate --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" review --cast-id E36B
& ".\Run Dialogue Factory.bat" export --cast-id E36B
```

User manually reviews quality before any large generation run.

## Integration tasks

- Make `fixture_builder` / exporter target the shared story/dialogue contract where needed.
- Retain SQLite persistence and prompt/worldview/source fingerprinting.
- Retain structured output, deterministic validation and bounded repair.
- Keep Ollama out of runtime gameplay.
- Ensure generated prose cannot change canonical state.
- Ensure approved output can be reloaded deterministically.
- Update permanent dialogue documentation to exact final behaviour.

## Automated gate

Most tests use fake/mock model output.

Run:

- dialogue pytest;
- export/fixture conversion;
- Godot fixture loading;
- shared dialogue lookup tests;
- one or a few real local-model samples only.

## Manual gate

Play/read 2-3 representative dialogue cases in actual villages.

Check:

- character appropriateness;
- village context;
- current story stage;
- factual consistency;
- branch consistency;
- latency/content-build usability;
- cache/reuse behaviour.

Do not generate all 112 stories merely because this phase passes.

Stop.

---

# Phase 6 — Reuse proof, integration and regression

## Goal

Prove the architecture works repeatedly through both normal game flow and Village Test Mode.

## Automated progression

### 3 canonical cases

Keep permanent readable regression anchors.

### 10 deterministic cases

Catch hard-coded assumptions.

### 25 structural cases

Run when stable.

### Up to 50

Only if cheap and informative.

Do not start with 100-500.

## Structural pipeline

Without live LLM calls:

```text
world
-> settlement node
-> settlement profile
-> production projection
-> story generation
-> shared story validation
-> dialogue lookup/request validation
```

Also run:

- current Godot simulation suite;
- relevant client integration smoke;
- Dialogue Factory model-free suite;
- save/reset/restore cases.

## Production-path requirement

By this phase:

- normal game and generated Village Test Mode use the same simulation/profile/projection;
- generated and authored stories use the same story runtime;
- authored and factory-generated dialogue use the same lookup contract;
- special temporary/duplicate paths are removed or explicitly retained only as adapters.

## Manual final gate

The user performs:

1. several Village Test Mode generated-village playtests;
2. an authored fixture playtest;
3. normal campaign/world settlement play;
4. at least one locally generated dialogue quest;
5. screenshots/notes for defects.

The coding agent should not perform routine visual screenshot review unless specifically needed for a hard-to-diagnose defect.

Stop until accepted.

---

## 4. Phase reporting format

At the end of each phase:

```text
PHASE:
OBJECTIVE:
FILES INSPECTED:
FILES CHANGED:
ARCHITECTURE DECISIONS:
TESTS ACTUALLY RUN:
RESULTS:
KNOWN DEFECTS:
MANUAL TEST CASES:
STATUS:
```

Valid status:

```text
AUTOMATED GATE PASSED — MANUAL ACCEPTANCE REQUIRED
AUTOMATED GATE FAILED — PHASE REMAINS OPEN
BLOCKED — USER DECISION REQUIRED
```

When manual acceptance is required, stop.

---

## 5. Test-cost policy

### Very frequent

- pure GDScript/Python tests;
- deterministic generation;
- ID/reference validation;
- story graph tests;
- model-free dialogue tests.

### Frequent

- Godot headless compile/import;
- production projection;
- scripted integration smoke.

### Phase gates only

- real local LLM generation;
- longer gameplay flows.

### User manual

- layout/aesthetic judgement;
- screenshots;
- dialogue quality;
- serious playthrough.

---

## 6. Definition of done

The programme is complete when:

- the existing world simulation remains canonical and deterministic;
- simulated settlement/city state reliably produces production settlement profiles;
- generated settlements are playable through the normal projection/Overworld path;
- Village Test Mode can reproduce production settlements from seed/node;
- generated settlement stories and authored fixture stories share one story runtime;
- story generation references only valid village entities/anchors/world facts;
- canonical world effects remain deterministic and saveable;
- authored and generated dialogue share one stable lookup contract;
- the existing Dialogue Factory exports to that contract;
- live local dialogue has passed manual E36B acceptance before wider scaling;
- no runtime LLM dependency is introduced;
- no redundant third/fourth village or quest architecture has been created;
- 3/10/25-case structural regression progression passes;
- normal game and Village Test Mode manual tests pass;
- procedural failures are reproducible;
- no sprite/art effort was spent beyond simple placeholders;
- current-state, dialogue and test documentation describes the actual final system.

---

## 7. Deferred work

After this programme, consider separately:

- more production quest/story archetypes;
- richer NPC social simulation;
- wider 50/100+ structural regression if useful;
- generation of the remaining story catalogue;
- dialogue-quality evaluation tooling;
- final village art/sprites/animation;
- project-level root README cleanup.
