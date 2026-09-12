# Duel Master Battle — Test Strategy

**Updated:** 2026-09-12  
**Purpose:** Current project test strategy, including world/village/story/dialogue work.

## 1. Principles

- Pure deterministic game logic receives the heaviest automated coverage.
- Production-path integration tests must prove wiring, not merely script compilation.
- Tests must report `passed`, `failed`, `errored`, `timed out` or `not run` accurately.
- A successful Godot import does not prove gameplay.
- Procedural failures must be reproducible by seed/node/profile.
- Real LLM calls are reserved for small acceptance samples.
- Visual and subjective playtesting is primarily performed manually by the user.
- No milestone is accepted solely because an agent says it looks correct.

---

## 2. Godot simulation tests

Primary runner:

```text
godot_project/sim/tools/run_tests.gd
```

At the time of this update it enumerates 26 simulation test modules, covering both legacy duel mechanics and newer world systems.

Village-programme-relevant suites include:

```text
test_hex_board.gd
test_catan.gd
test_carts.gd
test_infection.gd
test_units.gd
test_world_sim.gd
test_projection.gd
test_dungeons.gd
test_quests.gd
```

### Important existing guarantees

`test_world_sim.gd` exercises:

- long deterministic world runs;
- faction behaviour;
- same-seed repeatability;
- save/restore round trip;
- continuation after restore;
- different-seed divergence.

`test_projection.gd` exercises the real `DmbNodeProjection` across world nodes, including settlement buildings/workers/quest NPCs and city changes.

`test_quests.gd` exercises production settlement-quest selection, graph completeness, world effects, persistence, items and fight branches.

These tests should be extended rather than duplicated.

---

## 3. Script/import verification

Before/after meaningful Godot structural changes:

1. discover/use the installed Godot version and the actual project path;
2. run script compilation checks;
3. run a headless import when class/resource changes justify it;
4. inspect the output for errors.

Do not treat a hardcoded historical Godot path in an old script/doc as authoritative.

`Run Tests.bat` currently references a Windows Godot 4.5.1 console executable; older documentation contains a Linux 4.4.1 example. Tooling should be made environment-discoverable rather than multiplying fixed paths.

---

## 4. Client/gameplay integration tests

The repository contains scripted client flows under:

```text
godot_project/client/tests/
```

These include adventure/dialogue/dungeon/UI flows.

### Village gap to add

Create a focused Village Test / production settlement integration smoke that drives the real Overworld.

Minimum generated-settlement scenario:

```text
known world seed
-> known settlement node
-> start disposable Village Test session
-> production Overworld boots
-> John exists
-> production node projection loads
-> expected settlement NPC/building exists
-> interact through production path
-> start/advance a story
-> reset/exit restores campaign state
```

Once the story runtime is unified, also prove an authored fixture through the same runtime.

This is a high-value test because it catches the exact failure mode where a test harness renders a simplified world that is unlike real gameplay.

---

## 5. Village structural test progression

Do not begin with hundreds of cases.

Use this progression:

### Three canonical cases

Choose deliberately contrasting deterministic contexts, for example:

- resource/food-oriented settlement;
- woodland/production settlement;
- mining/industrial settlement or town.

These are human-understandable regression anchors.

### Ten deterministic cases

Catch obvious hidden assumptions and hard-coding.

### Twenty-five structural cases

Run once the pipeline is stable.

### Up to fifty if cheap and informative

Only increase if the structural suite is fast and failures remain useful.

100+ cases are optional later regression hardening, not an initial acceptance requirement.

### Structural run contents

Without rendering or live LLM:

```text
world seed/state
-> settlement profile
-> node/village projection/spec
-> story generation
-> story validation
-> dialogue request/lookup validation
-> serialisation where relevant
```

---

## 6. Dialogue Factory tests

Model-free tests live under:

```text
tools/dialogue_generation/tests/
```

Run them frequently.

They should cover the majority of pipeline correctness without requiring Ollama:

- workbook ingestion;
- source normalization;
- semantic banking;
- deterministic worldview logic;
- parsing;
- validation;
- persistence;
- recovery;
- review/repair plumbing;
- export gating;
- fixture building.

Real local-Ollama calls are acceptance tests.

---

## 7. Manual phase gates

The user performs manual acceptance after every major village phase.

Agent supplies:

- exact world seed;
- node ID / fixture ID;
- expected distinguishing features;
- concise instructions;
- expected story state;
- reproduction information.

The user checks:

- whether the place makes sense;
- whether John is present and movement feels normal;
- whether layout is understandable;
- whether NPCs/anchors are reachable;
- whether story progression makes sense;
- whether dialogue appears at the right time;
- subjective dialogue quality.

If something is visually wrong, report:

```text
seed
node/profile
story/node if relevant
screenshot
short defect description
```

The agent reproduces that exact case.

---

## 8. Visual-testing cost policy

Routine automated screenshot interpretation by a coding LLM is not required.

Prefer automated assertions for:

- spawn walkability;
- entity overlap;
- reachability where available;
- reference resolution;
- required NPC/anchor presence;
- quest state;
- dialogue binding.

Use human screenshots at phase gates and for defects.

During the village programme do not spend test effort generating or polishing sprites. Use simple geometric placeholders where new representation is required.

---

## 9. LLM-cost policy

Do not call a real model in:

- 10/25/50-case structural village suites;
- every dialogue lookup test;
- every quest transition;
- every CI/regression pass.

Mock the provider and test the contract.

Use real local generation for:

- E36B acceptance;
- 2-3 representative unified village/story cases;
- deliberate prompt-quality reviews.

---

## 10. Phase report

Every implementation phase should end with:

```text
PHASE:
FILES CHANGED:
TESTS RUN:
RESULTS:
KNOWN DEFECTS:
MANUAL CASES:
STATUS:
```

Status is one of:

```text
AUTOMATED GATE PASSED — MANUAL ACCEPTANCE REQUIRED
AUTOMATED GATE FAILED — PHASE REMAINS OPEN
BLOCKED — USER DECISION REQUIRED
```

When manual acceptance is required, stop.
